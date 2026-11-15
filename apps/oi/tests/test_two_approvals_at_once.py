"""
Two changes of one series approved at the same moment: requests that
really run at once, each with a connection of its own, so each commits.
"""
import threading
import time
from contextlib import contextmanager

import pytest

from django.contrib.auth.models import Permission, User
from django.db import connection, connections, transaction
from django.test import Client
from django.urls import reverse

from apps.gcd.models import Publisher, Series
from apps.indexer.models import Indexer
from apps.oi import states
from apps.oi.models import (
    Changeset, IssueRevision, PublisherRevision, SeriesRevision, CTYPES,
    _get_revision_lock)
from apps.stats.models import CountStats


@pytest.fixture
def statistics(any_country):
    """
    The statistics that an approval updates; a transactional test empties
    the database when it ends, so each test makes them again.
    """
    CountStats.objects.init_stats()
    CountStats.objects.init_stats(country=any_country)


@pytest.fixture
def editor(any_country):
    """An editor who may approve changes."""
    user = User.objects.create_user('editor', password='editor')
    Indexer.objects.create(user=user, country=any_country)
    user.user_permissions.add(*Permission.objects.filter(
      codename__in=['can_reserve', 'can_approve'],
      content_type__app_label='indexer'))
    return user


def _assigned(editor, changeset):
    """Assign changeset to editor; return a client of editor."""
    client = Client()
    client.force_login(editor)
    response = client.post(reverse('process', kwargs={'id': changeset.id}),
                           {'assign': 'Assign', 'comments': ''})
    assert response.status_code == 302
    return client


def _approve(client, changeset):
    """Post the approval of changeset; return the response."""
    return client.post(reverse('process', kwargs={'id': changeset.id}),
                       {'approve': 'Approve', 'comments': ''})


def _lock_waits(cursor, table):
    """Return how many transactions wait for a lock on a row of table."""
    cursor.execute(
      'SELECT COUNT(*) FROM performance_schema.data_lock_waits w '
      'JOIN performance_schema.data_locks l '
      'ON l.ENGINE_LOCK_ID = w.REQUESTING_ENGINE_LOCK_ID '
      'WHERE l.OBJECT_SCHEMA = DATABASE() AND l.OBJECT_NAME = %s', [table])
    return cursor.fetchone()[0]


def _wait_for_lock_wait(table, timeout=30):
    """
    Wait until a transaction waits for a lock on a row of table, as the
    server shows it.
    """
    end = time.monotonic() + timeout
    with connection.cursor() as cursor:
        while time.monotonic() < end:
            if _lock_waits(cursor, table):
                return
            time.sleep(0.05)
    raise AssertionError('no transaction waits for %s' % table)


@contextmanager
def _held(work):
    """
    In the block, a thread with a connection of its own has done work in
    a transaction that it keeps open, holding the rows that it wrote; the
    transaction commits when the block ends.
    """
    held, release = threading.Event(), threading.Event()
    failures = []

    def hold():
        """Do work, then keep its transaction open until release."""
        try:
            with transaction.atomic():
                work()
                held.set()
                release.wait(60)
        except Exception as error:
            failures.append(error)
            held.set()
        finally:
            connections.close_all()

    holder = threading.Thread(target=hold)
    holder.start()
    assert held.wait(30) and not failures, failures
    try:
        yield
    finally:
        release.set()
        holder.join(60)
    assert not failures, failures


def _approval_started(client, changeset):
    """
    Start the approval of changeset in a thread with a connection of its
    own; return the thread and the dict that gets its response.
    """
    result = {}

    def run():
        """Post the approval and keep the response, or the error."""
        try:
            result['response'] = _approve(client, changeset)
        except Exception as error:
            result['response'] = error
        finally:
            connections.close_all()

    thread = threading.Thread(target=run)
    thread.start()
    return thread, result


def _added_after(issue, indexer, issue_add_values):
    """The add of an issue after issue, not yet approved; its revision."""
    changeset = Changeset.objects.create(state=states.REVIEWING,
                                         indexer=indexer,
                                         change_type=CTYPES['issue_add'])
    values = dict(issue_add_values, series=issue.series, after=issue,
                  number='43')
    values.pop('indicia_printer', None)
    values.pop('brand_emblem', None)
    return IssueRevision.objects.create(changeset=changeset, **values)


def _commit(revision):
    """Commit revision, read again in this connection, as an approval."""
    type(revision).objects.get(id=revision.id).commit_to_display()


def _change(indexer, data_object, revision_class, change_type, **values):
    """A submitted change of data_object, holding its lock, with values."""
    changeset = Changeset.objects.create(state=states.PENDING,
                                         indexer=indexer,
                                         change_type=change_type)
    assert _get_revision_lock(data_object, changeset=changeset)
    revision = revision_class.clone(data_object=data_object,
                                    changeset=changeset)
    for name, value in values.items():
        setattr(revision, name, value)
    revision.save()
    return changeset


@pytest.mark.django_db(transaction=True)
def test_an_edit_approved_during_an_add_keeps_the_new_last_issue(
        statistics, any_added_issue, issue_add_values, any_indexer, editor):
    """
    An edit of an issue approved while the add of a later issue of its
    series commits: the series keeps the added issue as its last one.
    """
    added = _added_after(any_added_issue, any_indexer, issue_add_values)
    edit = _change(any_indexer, any_added_issue, IssueRevision,
                   CTYPES['issue'])
    approver = _assigned(editor, edit)

    with _held(lambda: _commit(added)):
        thread, result = _approval_started(approver, edit)
        _wait_for_lock_wait('gcd_series')
    thread.join(60)

    assert result['response'].status_code == 302
    added.refresh_from_db()
    series = Series.objects.get(id=any_added_issue.series_id)
    assert series.last_issue_id == added.issue_id


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('parent', ['series', 'publisher'])
def test_an_edit_of_a_parent_approved_during_an_add_keeps_its_counts(
        statistics, parent, any_added_issue, issue_add_values, any_indexer,
        editor):
    """
    An edit of the series, or of its publisher, approved while the add of
    an issue of the series commits: the edited row keeps the issue count
    of the add, and the publisher counts the issue once.
    """
    series = Series.objects.get(id=any_added_issue.series_id)
    publisher = Publisher.objects.get(id=series.publisher_id)
    series_count, publisher_count = series.issue_count, publisher.issue_count
    added = _added_after(any_added_issue, any_indexer, issue_add_values)
    if parent == 'series':
        edit = _change(any_indexer, series, SeriesRevision, CTYPES['series'],
                       notes='Edited notes')
    else:
        edit = _change(any_indexer, publisher, PublisherRevision,
                       CTYPES['publisher'], notes='Edited notes')
    approver = _assigned(editor, edit)

    with _held(lambda: _commit(added)):
        thread, result = _approval_started(approver, edit)
        _wait_for_lock_wait('gcd_%s' % parent)
    thread.join(60)

    assert result['response'].status_code == 302
    added.refresh_from_db()
    series.refresh_from_db()
    publisher.refresh_from_db()
    if parent == 'series':
        assert series.issue_count == series_count + 1
        assert series.last_issue_id == added.issue_id
        assert series.notes == 'Edited notes'
        assert publisher.issue_count == publisher_count + 1
    else:
        assert publisher.issue_count == publisher_count + 1
        assert publisher.notes == 'Edited notes'
