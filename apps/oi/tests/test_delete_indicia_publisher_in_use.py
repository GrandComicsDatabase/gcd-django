"""
The approval of the deletion of an indicia publisher, when issues or
changes of issues have come to use it since the deletion was asked for.
"""
import threading
import time
from contextlib import contextmanager

import pytest

from django.contrib.auth.models import Permission, User
from django.db import connection, connections, transaction
from django.test import Client
from django.urls import reverse

from apps.indexer.models import Indexer
from apps.indexer.views import ErrorWithMessage
from apps.oi import states
from apps.oi.models import (
    Changeset, IndiciaPublisherRevision, IssueRevision, RevisionLock, CTYPES,
    _get_revision_lock)

REFUSED = ('This indicia publisher cannot be deleted while issues, or '
           'changes of issues, use it; please discard this change.')


@pytest.fixture
def unused_publisher(indicia_publisher_add_values, any_indexer):
    """An approved indicia publisher that no issue uses yet."""
    changeset = Changeset.objects.create(
      state=states.OPEN, indexer=any_indexer,
      change_type=CTYPES['indicia_publisher'])
    revision = IndiciaPublisherRevision.objects.create(
      changeset=changeset,
      **dict(indicia_publisher_add_values, name='Unused Publisher'))
    revision.commit_to_display()
    changeset.state = states.APPROVED
    changeset.save()
    return revision.indicia_publisher


@pytest.fixture
def editor(any_country):
    """An editor who may approve changes."""
    user = User.objects.create_user('editor', password='editor')
    Indexer.objects.create(user=user, country=any_country)
    user.user_permissions.add(*Permission.objects.filter(
      codename__in=['can_reserve', 'can_approve'],
      content_type__app_label='indexer'))
    return user


def _request_deletion(indexer, indicia_publisher):
    """Ask for the deletion of indicia_publisher; return its change."""
    indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client = Client()
    client.force_login(indexer)
    response = client.post(
      reverse('delete_revision', kwargs={'model_name': 'indicia_publisher',
                                         'id': indicia_publisher.id}),
      {'comments': 'Duplicate entry'})
    assert response.status_code == 302
    return Changeset.objects.get(
      indiciapublisherrevisions__indicia_publisher=indicia_publisher,
      indiciapublisherrevisions__deleted=True)


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


def _issue_change(indexer, issue, indicia_publisher, state, approver=None):
    """
    A change of issue in state, holding its lock, whose revision points to
    indicia_publisher.
    """
    changeset = Changeset.objects.create(state=state, indexer=indexer,
                                         approver=approver,
                                         change_type=CTYPES['issue'])
    assert _get_revision_lock(issue, changeset=changeset)
    revision = IssueRevision.clone(data_object=issue, changeset=changeset)
    revision.indicia_publisher = indicia_publisher
    revision.save()
    return changeset


def _check_refused(response, deletion, indicia_publisher):
    """
    The approval of deletion was refused with the message, and undone:
    the indicia publisher is live, the change keeps its state and lock.
    """
    indicia_publisher.refresh_from_db()
    assert indicia_publisher.deleted is False
    assert response.status_code == 200
    assert REFUSED in response.content.decode()
    deletion.refresh_from_db()
    assert deletion.state == states.REVIEWING
    assert RevisionLock.objects.filter(
      changeset=deletion, object_id=indicia_publisher.id).exists()


@pytest.mark.django_db
def test_deletion_of_an_unused_indicia_publisher_is_approved(
        unused_publisher, any_indexer, editor):
    """An indicia publisher that nothing uses is deleted as before."""
    deletion = _request_deletion(any_indexer, unused_publisher)

    response = _approve(_assigned(editor, deletion), deletion)

    assert response.status_code == 302
    unused_publisher.refresh_from_db()
    assert unused_publisher.deleted is True
    deletion.refresh_from_db()
    assert deletion.state == states.APPROVED


@pytest.mark.django_db
def test_deletion_refused_when_a_change_of_an_issue_uses_it(
        any_added_issue, unused_publisher, any_indexer, editor):
    """A change of an issue that links to it since the request refuses
    the deletion."""
    deletion = _request_deletion(any_indexer, unused_publisher)
    _issue_change(any_indexer, any_added_issue, unused_publisher,
                  states.OPEN)

    response = _approve(_assigned(editor, deletion), deletion)

    _check_refused(response, deletion, unused_publisher)


@pytest.mark.django_db
def test_deletion_refused_when_an_issue_uses_it(
        any_added_issue, unused_publisher, any_indexer, editor):
    """An issue approved with it since the request refuses the deletion,
    with no change of an issue left active."""
    deletion = _request_deletion(any_indexer, unused_publisher)
    _issue_change(any_indexer, any_added_issue, unused_publisher,
                  states.REVIEWING, approver=editor).approve()
    unused_publisher.refresh_from_db()
    assert unused_publisher.issue_count == 1
    assert not unused_publisher.issue_revisions.active_set().exists()

    response = _approve(_assigned(editor, deletion), deletion)

    _check_refused(response, deletion, unused_publisher)


@pytest.mark.django_db
def test_deletion_reads_the_indicia_publisher_again(
        any_added_issue, unused_publisher, any_indexer, editor):
    """
    The check reads the indicia publisher again, not the copy that the
    revision holds, which may be older than the issue that now uses it.
    """
    deletion = _request_deletion(any_indexer, unused_publisher)
    revision = deletion.indiciapublisherrevisions.get()
    assert revision.source.issue_count == 0
    _issue_change(any_indexer, any_added_issue, unused_publisher,
                  states.REVIEWING, approver=editor).approve()

    with pytest.raises(ErrorWithMessage) as refused:
        revision.commit_to_display()

    assert refused.value.message == REFUSED
    unused_publisher.refresh_from_db()
    assert unused_publisher.deleted is False


@pytest.mark.django_db
def test_an_edit_of_an_indicia_publisher_in_use_is_approved(
        any_added_issue, any_indexer, editor):
    """Only a deletion is checked: an edit of one in use is approved."""
    indicia_publisher = any_added_issue.indicia_publisher
    indicia_publisher.refresh_from_db()
    assert indicia_publisher.issue_count == 1
    change = Changeset.objects.create(
      state=states.PENDING, indexer=any_indexer,
      change_type=CTYPES['indicia_publisher'])
    assert _get_revision_lock(indicia_publisher, changeset=change)
    revision = IndiciaPublisherRevision.clone(data_object=indicia_publisher,
                                              changeset=change)
    revision.name = 'Renamed Indicia Publisher'
    revision.save()

    response = _approve(_assigned(editor, change), change)

    assert response.status_code == 302
    indicia_publisher.refresh_from_db()
    assert indicia_publisher.name == 'Renamed Indicia Publisher'


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


def _point_to(revision, indicia_publisher):
    """Save revision pointing to indicia_publisher, as the edit page does."""
    revision = IssueRevision.objects.select_for_update().get(id=revision.id)
    revision.indicia_publisher = indicia_publisher
    revision.save()


def _approve_change(changeset):
    """Approve changeset, as the approve view does."""
    Changeset.objects.select_for_update().get(id=changeset.id).approve()


@pytest.mark.django_db(transaction=True)
def test_deletion_waits_for_an_edit_or_approval_in_flight(
        any_added_issue, unused_publisher, any_indexer, editor):
    """
    Requests that really run at once, so each commits; the cases share one
    test, since a transactional test empties the database when it ends.

    The approval of the deletion waits for an edit of an issue that is
    being saved with a link to the indicia publisher, then for the
    approval of a change of an issue that sets it, and is refused once
    each of them commits.
    """
    deletion = _request_deletion(any_indexer, unused_publisher)
    approver = _assigned(editor, deletion)

    # An edit saved at this moment: the revision pointed to another
    # indicia publisher when the approval began.
    edit = _issue_change(any_indexer, any_added_issue,
                         any_added_issue.indicia_publisher, states.OPEN)
    with _held(lambda: _point_to(edit.issuerevisions.get(),
                                 unused_publisher)):
        thread, result = _approval_started(approver, deletion)
        _wait_for_lock_wait('gcd_indicia_publisher')
    thread.join(60)

    _check_refused(result['response'], deletion, unused_publisher)
    Changeset.objects.get(id=edit.id).discard(any_indexer)
    assert not unused_publisher.has_dependents()

    # An approval in flight, after it counted the issue for the indicia
    # publisher.
    change = _issue_change(any_indexer, any_added_issue, unused_publisher,
                           states.REVIEWING, approver=editor)
    with _held(lambda: _approve_change(change)):
        thread, result = _approval_started(approver, deletion)
        _wait_for_lock_wait('gcd_indicia_publisher')
    thread.join(60)

    _check_refused(result['response'], deletion, unused_publisher)
    unused_publisher.refresh_from_db()
    assert unused_publisher.issue_count == 1
    assert not unused_publisher.issue_revisions.active_set().exists()
