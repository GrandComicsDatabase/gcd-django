"""
Requests that change the state of one change at the same moment: each
runs in a thread with its own database connection, and they are lined
up behind a row that the test holds, never by timed waits.
"""
import threading
from contextlib import contextmanager
from datetime import timedelta
from unittest import mock

import pytest

from django.contrib.auth.models import Permission, User
from django.db import connections, transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.indexer.models import Indexer
from apps.oi import states
from apps.oi.models import (
    Changeset, PublisherRevision, CTYPES, _get_revision_lock)
from apps.oi.tests.lock_waits import wait_for_lock_waits


@pytest.mark.django_db(transaction=True)
def test_state_changes_at_the_same_moment(any_indexer, any_added_publisher,
                                          any_country):
    """
    Two submits of one change, a submit and the sweep of old
    reservations, then two sweeps reach the change at the same moment:
    one of them changes its state, the other finds it changed, and none
    ends with a server error.  The cases share one test, since a
    transactional test empties the database when it ends.
    """
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    coordinator = User.objects.create_user('coordinator',
                                           password='coordinator')
    Indexer.objects.create(user=coordinator, country=any_country)
    coordinator.user_permissions.add(Permission.objects.get(
      codename='change_ongoingreservation', content_type__app_label='oi'))

    changeset = _open_change(any_indexer, any_added_publisher)
    first, second = _client(any_indexer), _client(any_indexer)
    submit = reverse('submit', kwargs={'id': changeset.id})
    data = {'comments': 'Submitted.'}

    responses = _behind_held_row(changeset,
                                 lambda: first.post(submit, data),
                                 lambda: second.post(submit, data))

    assert sorted(response.status_code for response in responses) == \
        [200, 302]
    _assert_one_state_change(changeset, states.PENDING)

    changeset.discard(any_indexer)
    old = _open_change(any_indexer, any_added_publisher, weeks=10)
    sweeper = _client(coordinator)
    submit = reverse('submit', kwargs={'id': old.id})

    responses = _behind_held_row(old,
                                 lambda: sweeper.get(reverse('clear_issues')),
                                 lambda: first.post(submit, data))

    assert [response.status_code for response in responses] in \
        ([200, 200], [200, 302])
    old.refresh_from_db()
    assert old.state in (states.PENDING, states.DISCARDED)
    _assert_one_state_change(old, old.state)

    if old.state == states.PENDING:
        old.discard(any_indexer)
    old = _open_change(any_indexer, any_added_publisher, weeks=10)
    other = _client(coordinator)

    responses = _behind_held_row(old,
                                 lambda: sweeper.get(reverse('clear_issues')),
                                 lambda: other.get(reverse('clear_issues')))

    assert [response.status_code for response in responses] == [200, 200]
    _assert_one_state_change(old, states.DISCARDED)

    # A mentor takes on a new indexer while a pending change of that
    # indexer is being discarded, from the mentor page and from the queue:
    # the request does not wait for that change and leaves it discarded,
    # and the free change goes to the mentor.
    mentor = _editor('mentor', any_country)
    taking_on = _client(mentor)

    mentee, (held_change, free) = _new_indexer_with_pending('mentee_one',
                                                            any_country)
    page = reverse('mentor', kwargs={'user_id': mentee.id})

    with _held_then_discarded(held_change):
        response = taking_on.post(page)

    assert response.status_code < 500
    _assert_left_to_holder(held_change, free, mentor)

    mentee, (held_change, free) = _new_indexer_with_pending('mentee_two',
                                                            any_country)
    assigned = _open_change(mentee, any_added_publisher)
    Changeset.objects.filter(id=assigned.id).update(state=states.PENDING)
    queue = reverse('assign', kwargs={'id': assigned.id})

    with _held_then_discarded(held_change):
        response = taking_on.post(queue, {'comments': ''})

    assert response.status_code < 500
    _assert_left_to_holder(held_change, free, mentor)

    # Two editors take on one new indexer at the same moment: one becomes
    # the mentor, and the changes go to that one.
    other = _client(_editor('other_mentor', any_country))
    mentee, changes = _new_indexer_with_pending('mentee_three', any_country)
    page = reverse('mentor', kwargs={'user_id': mentee.id})

    responses = _behind_held_row(mentee.indexer,
                                 lambda: taking_on.post(page),
                                 lambda: other.post(page))

    assert all(response.status_code < 500 for response in responses)
    winner = Indexer.objects.get(user=mentee).mentor
    assert winner is not None
    for change in changes:
        change.refresh_from_db()
        assert change.approver == winner


@pytest.mark.django_db
def test_adding_points_leaves_the_other_columns(any_indexer):
    """
    Points are added to a row read earlier, which must not write back what
    another request has committed in the meantime.
    """
    early = Indexer.objects.get(user=any_indexer)
    points = early.imps
    Indexer.objects.filter(id=early.id).update(mentor=any_indexer)

    early.add_imps(1)

    stored = Indexer.objects.get(id=early.id)
    assert stored.mentor == any_indexer
    assert stored.imps == points + 1


@pytest.mark.django_db
def test_the_queue_keeps_an_existing_mentor(any_added_publisher, any_country):
    """Assigning a change of a mentored indexer changes no mentor."""
    mentor = _editor('mentor', any_country)
    mentee, changes = _new_indexer_with_pending('mentee', any_country)
    Indexer.objects.filter(user=mentee).update(mentor=mentor)
    assigned = _open_change(mentee, any_added_publisher)
    Changeset.objects.filter(id=assigned.id).update(state=states.PENDING)

    response = _client(_editor('editor', any_country)).post(
      reverse('assign', kwargs={'id': assigned.id}), {'comments': ''})

    assert response.status_code < 500
    assert Indexer.objects.get(user=mentee).mentor == mentor
    changes[0].refresh_from_db()
    assert changes[0].state == states.PENDING


@pytest.mark.django_db
def test_the_queue_makes_no_mentor_once_not_new(any_added_publisher,
                                                any_country):
    """
    An indexer who stops being new after the queue has read them as new,
    by another request, gets no mentor, and their changes stay pending.
    """
    mentee, changes = _new_indexer_with_pending('mentee', any_country)
    assigned = _open_change(mentee, any_added_publisher)
    Changeset.objects.filter(id=assigned.id).update(state=states.PENDING)
    assign = Changeset.assign

    def assign_then_not_new(changeset, *args, **kwargs):
        """Read the indexer as new, then commit them as not new."""
        if changeset.id == assigned.id:
            assert changeset.indexer.indexer.is_new
            Indexer.objects.filter(user=mentee).update(is_new=False)
        return assign(changeset, *args, **kwargs)

    with mock.patch.object(Changeset, 'assign', assign_then_not_new):
        response = _client(_editor('editor', any_country)).post(
          reverse('assign', kwargs={'id': assigned.id}), {'comments': ''})

    assert response.status_code < 500
    assert Indexer.objects.get(user=mentee).mentor is None
    changes[0].refresh_from_db()
    assert changes[0].state == states.PENDING


@pytest.mark.django_db
def test_a_change_no_longer_pending_is_left_alone(any_indexer, any_country):
    """A change that stopped being pending after the list is not assigned."""
    mentor = _editor('mentor', any_country)
    change = Changeset.objects.create(indexer=any_indexer,
                                      state=states.DISCARDED,
                                      change_type=CTYPES['publisher'])

    with mock.patch('django.db.models.query.QuerySet.values_list',
                    return_value=[change.id]):
        any_indexer.indexer.assign_pending_changes(mentor)

    change.refresh_from_db()
    assert change.state == states.DISCARDED
    assert change.approver is None


def _editor(name, country):
    """A new user who may approve changes and mentor new indexers."""
    editor = User.objects.create_user(name, password=name)
    Indexer.objects.create(user=editor, country=country)
    for codename in ('can_approve', 'can_mentor'):
        editor.user_permissions.add(Permission.objects.get(
          codename=codename, content_type__app_label='indexer'))
    return editor


def _new_indexer_with_pending(name, country):
    """A new indexer without a mentor, and two pending changes of theirs."""
    mentee = User.objects.create_user(name, password=name)
    Indexer.objects.create(user=mentee, country=country, is_new=True)
    return mentee, [Changeset.objects.create(indexer=mentee,
                                             state=states.PENDING,
                                             change_type=CTYPES['publisher'])
                    for count in range(2)]


def _assert_left_to_holder(held_change, free, mentor):
    """The held change ended discarded, the free one went to mentor."""
    held_change.refresh_from_db()
    assert held_change.state == states.DISCARDED
    free.refresh_from_db()
    assert free.state == states.REVIEWING
    assert free.approver == mentor


def _client(user):
    """A client of user that returns server errors as responses."""
    client = Client(raise_request_exception=False)
    client.force_login(user)
    return client


def _open_change(indexer, publisher, weeks=0):
    """An OPEN change of publisher by indexer, created weeks ago."""
    changeset = Changeset.objects.create(indexer=indexer, state=states.OPEN,
                                         change_type=CTYPES['publisher'])
    assert _get_revision_lock(publisher, changeset) is not None
    PublisherRevision.clone(data_object=publisher, changeset=changeset)
    Changeset.objects.filter(id=changeset.id).update(
      created=timezone.now() - timedelta(weeks=weeks))
    return changeset


def _assert_one_state_change(changeset, state):
    """The change went once from OPEN to state, with one comment."""
    changeset.refresh_from_db()
    assert changeset.state == state
    assert list(changeset.comments.values_list('old_state', 'new_state')) \
        == [(states.OPEN, state)]


def _behind_held_row(row, *calls):
    """
    Hold row, start calls in threads, release it once each of them waits
    for it, and return their results.
    """
    held, release = threading.Event(), threading.Event()
    holder = threading.Thread(target=_hold, args=(row, held, release))
    holder.start()
    assert held.wait(30)
    results = [None] * len(calls)
    threads = [threading.Thread(target=_run, args=(results, index, call))
               for index, call in enumerate(calls)]
    try:
        for thread in threads:
            thread.start()
        wait_for_lock_waits(type(row)._meta.db_table, len(calls))
    finally:
        release.set()
        holder.join(30)
        for thread in threads:
            thread.join(60)
    return results


@contextmanager
def _held_then_discarded(changeset):
    """Hold the row of changeset in the block, then discard the change."""
    held, release = threading.Event(), threading.Event()
    holder = threading.Thread(target=_hold_and_discard,
                              args=(changeset, held, release))
    holder.start()
    assert held.wait(30)
    try:
        yield
    finally:
        release.set()
        holder.join(30)


def _hold(row, held, release):
    """In a transaction of its own, lock row until release."""
    try:
        with transaction.atomic():
            type(row).objects.select_for_update().get(id=row.id)
            held.set()
            release.wait(60)
    finally:
        connections.close_all()


def _hold_and_discard(changeset, held, release):
    """
    In a transaction of its own, lock the row of changeset until release,
    then discard the change.
    """
    try:
        with transaction.atomic():
            locked = Changeset.objects.select_for_update().get(id=changeset.id)
            held.set()
            release.wait(60)
            locked.discard(changeset.indexer)
    finally:
        connections.close_all()


def _run(results, index, call):
    """Keep the result of call, or the exception it raised, at index."""
    try:
        results[index] = call()
    except Exception as error:
        results[index] = error
    finally:
        connections.close_all()
