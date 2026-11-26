"""
Bulk changes applied at the same moment: requests in threads, each with
its own database connection, started together by a barrier or held by an
event, never by timed waits.
"""
import threading
import time
from contextlib import contextmanager
from datetime import timedelta

import pytest

from django.contrib.auth.models import Permission, User
from django.core.cache import cache
from django.db import connection, connections, transaction
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.gcd.models import Issue, Series
from apps.indexer.models import Indexer
from apps.mycomics.models import Collector, ConditionGradeScale
from apps.oi import bulk, states
from apps.oi.models import (
    Changeset, IndiciaPublisherRevision, IssueRevision, RevisionLock, CTYPES,
    _get_revision_lock)
from apps.oi.tests.bulk.invariants import check_invariants
from apps.stddata.models import Country

TOKEN = 'race-token'
PRICE = {'field': 'price', 'shown': 'price', 'operation': 'replace_exact',
         'old_value': '=0.10 USD', 'new_value': '0.12 USD'}
RATING = {'field': 'rating', 'shown': 'rating', 'operation': 'replace_exact',
          'old_value': '=', 'new_value': 'Teen'}
FREQUENCY = {'field': 'indicia_frequency', 'shown': 'indicia_frequency',
             'operation': 'replace_exact', 'old_value': '=monthly',
             'new_value': 'quarterly'}


@pytest.fixture(autouse=True)
def invariants():
    """
    Start without applied tokens; check the invariants at the end.  Each
    test is marked for the database it uses.
    """
    cache.clear()
    yield
    check_invariants()


def _logged_in(user, issues, token=TOKEN):
    """A client of user with issues as the selection of token."""
    client = Client()
    client.force_login(user)
    session = client.session
    session[bulk.SELECTION_KEY] = {
      'token': token, 'model': 'issue', 'source': '/list/',
      'ids': sorted(issue.id for issue in issues)}
    session.save()
    return client


def _apply(client, token=TOKEN, data=PRICE):
    """Post an operation, the price by default, to the page of token."""
    return client.post(reverse('edit_issues_in_bulk') + '?token=' + token,
                       data)


def _together(*calls):
    """
    Run calls in threads that start together and return their results.
    Fail if one of them is still running after its join, and raise the
    exception that one of them raised.
    """
    barrier = threading.Barrier(len(calls))
    results = [None] * len(calls)

    def run(index, call):
        try:
            barrier.wait()
            results[index] = call()
        except Exception as error:
            results[index] = error
        finally:
            connections.close_all()

    threads = [threading.Thread(target=run, args=(index, call))
               for index, call in enumerate(calls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    assert not any(thread.is_alive() for thread in threads), \
        'a request did not end in 60 seconds'
    for result in results:
        if isinstance(result, Exception):
            raise result
    return results


@pytest.fixture
def second_indexer(any_language):
    """Another indexer who may reserve changes."""
    user = User.objects.create_user('second', email='noreply@comics.org',
                                    password='second')
    Indexer.objects.create(user=user, country=Country.objects.get_or_create(
      code='XZZ', name='Test Country')[0])
    Collector.objects.create_collector(
      user, grade_system=ConditionGradeScale.objects.create(name='Second'),
      default_language=any_language)
    user.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    return user


@pytest.fixture
def second_indicia_publisher(indicia_publisher_add_values,
                             any_adding_changeset):
    """An approved indicia publisher besides that of the issues."""
    revision = IndiciaPublisherRevision(
      changeset=any_adding_changeset,
      **dict(indicia_publisher_add_values, name='Second Publisher'))
    revision.save()
    revision.commit_to_display()
    return revision.indicia_publisher


@pytest.mark.django_db(transaction=True)
def test_requests_at_the_same_moment(settings, monkeypatch,
                                     reserving_indexer, second_indexer,
                                     any_approver, approved_issues,
                                     approved_variant,
                                     second_indicia_publisher):
    """
    Requests that really run at once, so each commits; the cases share one
    test, since a transactional test empties the database when it ends.

    Two indexers apply to the same objects: one change takes them all,
    the other finds them reserved and makes no change, and no lock is
    left without its change.  Then one indexer posts one selection twice
    at once, as with a double click or two tabs: the second request waits
    for the first and finds the selection applied.  Then two tabs apply
    two lists at once, and the limit of active bulk changes holds; a
    request that waits too long for the other gets a message.  An approval
    that waits beyond the server's limit, on its series, on an issue after
    it wrote another, or on a lock that it frees in a savepoint, is undone
    as a whole, gets a message and can be repeated.  Last, the approval of
    a normal and of a bulk change in the series of an Apply waits for it
    without a deadlock, the discard of a change that holds an object of
    the Apply does not wait for it, and further work on a change waits for
    the request that holds the change.  A revert takes the same steps: it
    waits for the old value of a link before it writes anything, leaves
    out at once an object whose row another request is writing, waits for
    a reservation in flight, whose end decides its object, and is refused
    as a whole if a series or a reservation in flight outlasts the
    server's wait.  The sweep of old reservations waits for a request that
    works on a bulk change, and leaves the change open.
    """
    settings.BULK_CHANGE_ENABLED = True
    first = _logged_in(reserving_indexer, approved_issues)
    second = _logged_in(second_indexer, approved_issues)

    results = _together(lambda: _apply(first), lambda: _apply(second))

    changeset = Changeset.objects.get(change_type=CTYPES['bulk'])
    assert changeset.issuerevisions.count() == 3
    assert set(RevisionLock.objects.filter(
      object_id__in=[issue.id for issue in approved_issues])
      .values_list('changeset', flat=True)) == {changeset.id}
    pages = [result.content.decode() for result in results]
    assert sum('Nothing was changed' in page for page in pages) == 1
    assert 'reserved 3' in ''.join(pages)

    changeset.discard(changeset.indexer)
    settings.BULK_CHANGE_MAX_ACTIVE = 2
    reserving_indexer.indexer.max_reservations = 5
    reserving_indexer.indexer.save()
    first = _logged_in(reserving_indexer, approved_issues, token='twice')
    twin = Client()
    twin.cookies = first.cookies

    # The indexer row is held until both requests wait for it, so both
    # have passed the check of the page: apply refuses the second one,
    # after the first one ends.
    results, threads = {}, []
    try:
        with _held(_hold_indexer, reserving_indexer):
            threads.append(_started(results, 'first', lambda: _apply(
              first, token='twice')))
            threads.append(_started(results, 'twin', lambda: _apply(
              twin, token='twice')))
            _wait_for_lock_wait(Indexer._meta.db_table, waiting=2)
    finally:
        for thread in threads:
            thread.join(90)

    assert Changeset.objects.filter(change_type=CTYPES['bulk'],
                                    state=states.OPEN).count() == 1
    assert sum(result.status_code == 302 for result in results.values()) == 1
    assert any('This selection was applied already' in
               result.content.decode() for result in results.values())

    # Two tabs of one indexer, each with its own list, apply at once: the
    # requests take turns, and the second finds the first change active.
    Changeset.objects.get(change_type=CTYPES['bulk'], state=states.OPEN) \
             .discard(reserving_indexer)
    settings.BULK_CHANGE_MAX_ACTIVE = 1
    tab_a = _logged_in(reserving_indexer, approved_issues[:2], token='a')
    tab_b = _logged_in(reserving_indexer, approved_issues[2:], token='b')

    results = _together(lambda: _apply(tab_a, token='a'),
                        lambda: _apply(tab_b, token='b'))

    assert Changeset.objects.filter(change_type=CTYPES['bulk'],
                                    state=states.OPEN).count() == 1
    assert any('You already have 1 active bulk change' in
               result.content.decode() for result in results)

    # A request that waits too long for the indexer row, which another
    # request of the indexer holds, gets a message, not a server error.
    with _held(_hold_indexer, reserving_indexer):
        waiting = _logged_in(reserving_indexer, approved_issues,
                             token='held')
        with _short_server_wait():
            response = _apply(waiting, token='held')

    assert 'Another request of yours is applying a bulk change.' in \
        response.content.decode()

    # An Apply holds the row of the series from its start, which an
    # approval in that series writes.  While the Apply waits for a
    # reservation in flight, the approval of an issue added in the middle
    # of the series writes the later issues, which no lock protects, then
    # waits for the Apply.  The Apply leaves those issues out at once, so
    # the approval is no deadlock victim and ends after the Apply.
    first, held_issue, reviewed = approved_issues

    _discard_open_bulk_changes()
    adding = _reviewed_add(second_indexer, any_approver, held_issue)
    approver = Client()
    approver.force_login(any_approver)
    applying = _logged_in(reserving_indexer, approved_issues, token='add')
    results, threads = {}, []
    try:
        with _held_lock(held_issue):
            threads.append(_started(results, 'apply', lambda: _apply(
              applying, token='add')))
            _wait_for_lock_wait('oi_revision_lock')
            threads.append(_started(results, 'approve', lambda: approver.post(
              reverse('approve', kwargs={'id': adding.id}), {'comments': ''})))
            _wait_for_lock_wait('gcd_series')
    finally:
        for thread in threads:
            thread.join(90)

    assert not isinstance(results['approve'], Exception), results['approve']
    assert results['approve'].status_code == 302
    assert results['apply'].status_code == 302
    adding.refresh_from_db()
    assert adding.state == states.APPROVED
    assert _open_record(reserving_indexer)['listed']['reserved'] == \
        [reviewed.id]

    # While the Apply waits, a normal change, then a bulk change, of a
    # later issue is approved.  The normal approval frees its lock and
    # writes the issue, then waits for the Apply, which leaves out that
    # issue and, as its row is being written, the variant of it.  The bulk
    # approval waits for the series before it writes anything, so only its
    # issue, which it still holds, is left out.
    for kind, left_out, changed in (
          ('issue', [reviewed, approved_variant], 2),
          ('bulk', [reviewed], 3)):
        _discard_open_bulk_changes()
        reviewing = _reviewed_change(kind, second_indexer, any_approver,
                                     reviewed)
        applying = _logged_in(reserving_indexer,
                              approved_issues + [approved_variant],
                              token=kind)
        results, threads = {}, []
        try:
            with _held_lock(held_issue):
                threads.append(_started(results, 'apply', lambda: _apply(
                  applying, token=kind)))
                _wait_for_lock_wait('oi_revision_lock')
                threads.append(_started(results, 'approve', lambda: _approve(
                  reviewing.id)))
                _wait_for_lock_wait('gcd_series')
        finally:
            for thread in threads:
                thread.join(90)

        assert results['approve'] is None, kind
        assert results['apply'].status_code == 302
        reviewing.refresh_from_db()
        assert reviewing.state == states.APPROVED
        record = _open_record(reserving_indexer)
        assert record['listed']['reserved'] == [issue.id for issue in left_out]
        assert record['counts']['changed'] == changed
        if approved_variant in left_out:
            assert not RevisionLock.objects.filter(
              object_id=approved_variant.id).exists()
            assert not approved_variant.revisions.filter(
              changeset__state=states.OPEN).exists()

    # A discard of a change whose object the Apply left out, since the
    # change held it, must not wait for the Apply: while the Apply waits
    # for a reservation in flight, the discard ends.
    _discard_open_bulk_changes()
    holding = _logged_in(second_indexer, [first], token='held')
    assert _apply(holding, token='held').status_code == 302
    discarded = Changeset.objects.get(indexer=second_indexer,
                                      change_type=CTYPES['bulk'],
                                      state=states.OPEN)
    applying = _logged_in(reserving_indexer, approved_issues, token='last')
    results, threads = {}, []
    try:
        with _held_lock(held_issue):
            threads.append(_started(results, 'apply', lambda: _apply(
              applying, token='last')))
            _wait_for_lock_wait('oi_revision_lock')
            discard = _started(results, 'discard',
                               lambda: _discard(discarded.id))
            threads.append(discard)
            discard.join(20)
            assert not discard.is_alive()
    finally:
        for thread in threads:
            thread.join(90)

    assert results['discard'] is None
    discarded.refresh_from_db()
    assert discarded.state == states.DISCARDED
    assert results['apply'].status_code == 302
    assert _open_record(reserving_indexer)['listed']['reserved'] == \
        [first.id]

    # A further operation on a change waits for the request that holds the
    # change, such as another operation or a removal, and then runs.
    _discard_open_bulk_changes()
    author = _logged_in(reserving_indexer, approved_issues[:2], token='turns')
    assert author.post(reverse('edit_issues_in_bulk') + '?token=turns',
                       _pages('32')).status_code == 302
    changeset = Changeset.objects.get(indexer=reserving_indexer,
                                      change_type=CTYPES['bulk'],
                                      state=states.OPEN)
    with _held_change(changeset):
        operation = _started(
          results, 'operation',
          lambda: author.post(reverse('edit_issues_in_bulk') +
                              '?changeset=%d' % changeset.id, _pages('40')))
        _wait_for_lock_wait('oi_changeset')
        # It waits before it writes anything.
        assert _row_locks('oi_issue_revision') == 0
    operation.join(60)

    assert results['operation'].status_code == 302
    assert len(bulk.operation_records(changeset)) == 2

    # A reservation in flight decides its object when it ends: reserved
    # if it commits, changed if it is undone.
    for commits, left_out in ((True, [held_issue.id]), (False, [])):
        _discard_open_bulk_changes()
        applying = _logged_in(reserving_indexer, approved_issues,
                              token='flight%s' % commits)
        results, threads = {}, []
        try:
            with _held_lock(held_issue, commit=commits):
                threads.append(_started(results, 'apply', lambda: _apply(
                  applying, token='flight%s' % commits)))
                _wait_for_lock_wait('oi_revision_lock')
        finally:
            for thread in threads:
                thread.join(90)

        assert results['apply'].status_code == 302
        assert _open_record(reserving_indexer)['listed']['reserved'] == \
            left_out
        RevisionLock.objects.filter(changeset=None,
                                    object_id=held_issue.id).delete()

    # A row that another request is writing costs the Apply no wait: the
    # object, and a variant of it, are left out at once.  The bulk approval
    # above gave the object the new price, so this is another field.
    _discard_open_bulk_changes()
    applying = _logged_in(reserving_indexer,
                          approved_issues + [approved_variant], token='rows')
    results = {}
    with _held_row(reviewed):
        thread = _started(results, 'apply',
                          lambda: _apply(applying, token='rows',
                                         data=FREQUENCY))
        waits = _lock_waits_until_done(thread, 'gcd_issue')
    thread.join(90)
    assert not thread.is_alive(), 'the Apply did not end'

    assert waits == 0
    assert results['apply'].status_code == 302
    assert _open_record(reserving_indexer)['listed']['reserved'] == \
        [reviewed.id, approved_variant.id]

    # A series that stays busy beyond the server's wait refuses the Apply
    # before it has done anything.
    _discard_open_bulk_changes()
    applying = _logged_in(reserving_indexer, approved_issues, token='series')
    with _held_row(first.series), _short_server_wait():
        response = _apply(applying, token='series')

    assert b'The series of these objects are being saved at this moment' \
        in response.content
    assert not Changeset.objects.filter(change_type=CTYPES['bulk'],
                                        state=states.OPEN).exists()

    # Each busy parent is a wait of its own, and a wait that ends
    # refuses nothing.
    _discard_open_bulk_changes()
    applying = _logged_in(reserving_indexer, approved_issues, token='two')
    results = {}
    with _held_row(first.indicia_publisher):
        with _held_row(first.series):
            thread = _started(results, 'apply', lambda: _apply(
              applying, token='two', data=FREQUENCY))
            _wait_for_lock_wait('gcd_series')
        _wait_for_lock_wait('gcd_indicia_publisher')
    thread.join(90)
    assert results['apply'].status_code == 302

    # An approval that waits beyond the server's limit, on its series, on
    # an issue after it wrote another, or on a lock that it frees in a
    # savepoint, is undone as a whole and can be repeated.
    changeset = Changeset.objects.get(indexer=reserving_indexer,
                                      change_type=CTYPES['bulk'],
                                      state=states.OPEN)
    changeset.submit()
    changeset.assign(any_approver)
    last = list(changeset.revisions)[-1].issue
    lock = RevisionLock.objects.get(changeset=changeset, object_id=last.id)
    url = reverse('approve', kwargs={'id': changeset.id})
    comments, imps = changeset.comments.count(), _imps_of(changeset)
    for held in (first.series, last, lock):
        with _held_row(held), _short_server_wait(), \
             CaptureQueriesContext(connection) as queries:
            response = approver.post(url, {'comments': ''})

        _check_approval_undone(response, changeset, approved_issues, comments,
                               imps, 'indicia_frequency', 'monthly')
        if held is last:
            written = [query['sql'] for query in queries
                       if query['sql'].startswith('UPDATE `gcd_issue`')]
            assert written
            assert '`gcd_issue`.`id` = %d' % last.id not in written[0]

    assert approver.post(url, {'comments': ''}).status_code == 302
    changeset.refresh_from_db()
    assert changeset.state == states.APPROVED
    assert _values(approved_issues, 'indicia_frequency') == ['quarterly'] * 3
    assert not RevisionLock.objects.filter(changeset=changeset).exists()
    check_invariants()

    # A revert waits for the old value of a link before it writes anything,
    # though no object points to that row now, and a wait that ends
    # refuses nothing.
    _discard_open_bulk_changes()
    relinked = _approved_bulk_change(
      reserving_indexer, any_approver, [first], 'relinked',
      {'field': 'indicia_publisher', 'shown': 'indicia_publisher',
       'operation': 'set', 'new_value': str(second_indicia_publisher.id)})
    old_publisher = first.indicia_publisher
    reverting = _logged_in(reserving_indexer, [first], token='reverting')
    results = {}
    with _held_row(old_publisher):
        thread = _started(results, 'revert',
                          lambda: reverting.post(_revert_url(relinked)))
        _wait_for_lock_wait('gcd_indicia_publisher')
        # It waits before it writes anything.
        assert _row_locks('oi_issue_revision') == 0
    thread.join(90)

    assert results['revert'].status_code == 302
    assert Changeset.objects.get(indexer=reserving_indexer,
                                 change_type=CTYPES['bulk'],
                                 state=states.OPEN) \
        .issuerevisions.get().indicia_publisher_id == old_publisher.id

    # A series that stays busy beyond the server's wait refuses the revert
    # before it has done anything.
    _discard_open_bulk_changes()
    with _held_row(first.series), _short_server_wait():
        response = reverting.post(_revert_url(relinked))

    assert b'The series of these objects are being saved at this moment' \
        in response.content
    assert not Changeset.objects.filter(change_type=CTYPES['bulk'],
                                        state=states.OPEN).exists()

    # A row that another request is writing costs a revert no wait: the
    # object, and a variant of it, are left out at once.
    counted = _approved_bulk_change(
      reserving_indexer, any_approver, approved_issues + [approved_variant],
      'counted', _pages('64'))
    results = {}
    with _held_row(reviewed):
        thread = _started(results, 'revert',
                          lambda: reverting.post(_revert_url(counted)))
        waits = _lock_waits_until_done(thread, 'gcd_issue')
    thread.join(90)

    assert waits == 0
    assert results['revert'].status_code == 302
    assert _open_record(reserving_indexer)['listed']['reserved'] == \
        [reviewed.id, approved_variant.id]

    # A reservation in flight that outlasts the server's wait refuses the
    # whole revert at the first timeout: with two of them held it does not
    # go on to the second.  Nothing is written, and it can be applied again.
    _discard_open_bulk_changes()
    tried = []
    reserve = bulk._get_revision_lock

    def noted(data_object, changeset):
        """Note the object whose lock the revert takes, then take it."""
        tried.append(data_object.id)
        return reserve(data_object, changeset)

    monkeypatch.setattr(bulk, '_get_revision_lock', noted)
    with _held_lock(first), _held_lock(held_issue), _short_server_wait():
        response = reverting.post(_revert_url(counted))
    monkeypatch.undo()

    assert b'Another change was using some of the same records' in \
        response.content
    # It stopped at the first held object that it reached.
    in_flight = {first.id, held_issue.id}
    assert tried[-1] in in_flight and len(in_flight & set(tried)) == 1
    assert not Changeset.objects.filter(change_type=CTYPES['bulk'],
                                        state=states.OPEN).exists()
    assert not RevisionLock.objects.filter(
      object_id__in=[first.id, held_issue.id]).exists()
    assert reverting.post(_revert_url(counted)).status_code == 302

    # A reservation in flight decides the object of a revert as it does
    # for an Apply: reserved if it commits, changed if it is undone.
    for commits, left_out in ((True, [held_issue.id]), (False, [])):
        _discard_open_bulk_changes()
        results, threads = {}, []
        try:
            with _held_lock(held_issue, commit=commits):
                threads.append(_started(
                  results, 'revert',
                  lambda: reverting.post(_revert_url(counted))))
                _wait_for_lock_wait('oi_revision_lock')
        finally:
            for thread in threads:
                thread.join(90)

        assert results['revert'].status_code == 302
        assert _open_record(reserving_indexer)['listed']['reserved'] == \
            left_out
        RevisionLock.objects.filter(changeset=None,
                                    object_id=held_issue.id).delete()
    _discard_open_bulk_changes()

    # A field turned off in the series while an approval waits for the
    # series is seen by the approval, which refuses and writes nothing.
    reviewing = _reviewed_change('bulk', second_indexer, any_approver,
                                 held_issue, data=RATING)
    series = held_issue.series
    results, threads = {}, []
    try:
        with _held_row(series, then=lambda: Series.objects.filter(
          id=series.id).update(has_rating=False)):
            threads.append(_started(results, 'approve', lambda: approver.post(
              reverse('approve', kwargs={'id': reviewing.id}),
              {'comments': ''})))
            _wait_for_lock_wait('gcd_series')
    finally:
        for thread in threads:
            thread.join(90)

    assert b'This bulk change cannot be approved.' in \
        results['approve'].content
    reviewing.refresh_from_db()
    assert reviewing.state == states.REVIEWING
    assert Issue.objects.get(id=held_issue.id).rating == ''

    # The sweep of old reservations chose a bulk change left alone and
    # waits for its row, which a request that works on the change holds.
    # That work counts: the change stays open.
    applying = _logged_in(reserving_indexer, [first], token='swept')
    assert _apply(applying, token='swept',
                  data=_pages('72')).status_code == 302
    swept = Changeset.objects.get(indexer=reserving_indexer,
                                  change_type=CTYPES['bulk'],
                                  state=states.OPEN)
    long_ago = timezone.now() - timedelta(days=40)
    Changeset.objects.filter(id=swept.id).update(created=long_ago,
                                                 modified=long_ago)
    any_approver.user_permissions.add(Permission.objects.get(
      codename='change_ongoingreservation'))
    results = {}
    with _held_row(swept, then=lambda: Changeset.objects.filter(
      id=swept.id).update(modified=timezone.now())):
        thread = _started(results, 'sweep',
                          lambda: approver.get(reverse('clear_issues')))
        _wait_for_lock_wait('oi_changeset')
    thread.join(90)

    assert results['sweep'].status_code == 200
    swept.refresh_from_db()
    assert swept.state == states.OPEN


@pytest.mark.django_db
def test_a_lock_wait_timeout_refuses_the_whole_apply(settings, monkeypatch,
                                                     reserving_indexer,
                                                     approved_issues):
    """
    A reservation in flight that outlasts the server's wait refuses the
    whole Apply at the first timeout: with two of them held the Apply does
    not go on to the second.  Nothing is written, and the selection can be
    applied again.
    """
    settings.BULK_CHANGE_ENABLED = True
    client = _logged_in(reserving_indexer, approved_issues)
    tried = []
    reserve = bulk._get_revision_lock

    def noted(data_object, changeset):
        """Note the object whose lock the Apply takes, then take it."""
        tried.append(data_object.id)
        return reserve(data_object, changeset)

    monkeypatch.setattr(bulk, '_get_revision_lock', noted)
    with _held_lock(approved_issues[0]), _held_lock(approved_issues[1]), \
         _short_server_wait():
        response = _apply(client)
    monkeypatch.undo()

    assert b'Another change was using some of the same records' in \
        response.content
    # It stopped at the first held object that it reached.
    in_flight = {approved_issues[0].id, approved_issues[1].id}
    assert tried[-1] in in_flight and len(in_flight & set(tried)) == 1
    assert not Changeset.objects.filter(change_type=CTYPES['bulk']).exists()
    assert not RevisionLock.objects.filter(
      object_id__in=[issue.id for issue in approved_issues]).exists()
    assert _apply(client).status_code == 302
    assert Changeset.objects.get(change_type=CTYPES['bulk']) \
                    .issuerevisions.count() == 3


def _pages(value):
    """The operation that sets the page count of its objects to value."""
    return {'field': 'page_count', 'shown': 'page_count', 'operation': 'set',
            'new_value': value}


def _values(issues, name):
    """The stored values of the field name of issues, in id order."""
    return list(Issue.objects.filter(id__in=[issue.id for issue in issues])
                .order_by('id').values_list(name, flat=True))


def _imps_of(changeset):
    """The points of the indexer and of the approver of changeset."""
    return [Indexer.objects.get(user_id=user_id).imps
            for user_id in (changeset.indexer_id, changeset.approver_id)]


def _check_approval_undone(response, changeset, issues, comments, imps,
                           name, old):
    """
    Check an approval that waited beyond the server's limit: it asks to be
    repeated and has changed nothing, neither the field name of issues nor
    the state, the comments and the points, and the change keeps its locks.
    """
    assert response.status_code == 200
    assert b'Please approve it again.' in response.content
    changeset.refresh_from_db()
    assert changeset.state == states.REVIEWING
    assert changeset.comments.count() == comments
    assert _values(issues, name) == [old] * len(issues)
    assert not changeset.issuerevisions.filter(committed=True).exists()
    assert set(RevisionLock.objects.filter(changeset=changeset)
               .values_list('object_id', flat=True)) == \
        {issue.id for issue in issues}
    assert _imps_of(changeset) == imps


def _discard_open_bulk_changes():
    """Discard the OPEN bulk changes, so that a case starts alone."""
    for changeset in Changeset.objects.filter(change_type=CTYPES['bulk'],
                                              state=states.OPEN):
        changeset.discard(changeset.indexer)


def _open_record(user):
    """The record of the operation of the OPEN bulk change of user."""
    changeset = Changeset.objects.get(indexer=user,
                                      change_type=CTYPES['bulk'],
                                      state=states.OPEN)
    return bulk.parse_operation(changeset.comments.get().text)


def _reviewed_change(kind, indexer, approver, issue, data=PRICE):
    """
    A change of issue by indexer, which approver reviews: a normal change
    of its notes, or a bulk change with the operation data.
    """
    if kind == 'bulk':
        # A token is applied once: each field has its own.
        token = 'reviewed-' + data['field']
        client = _logged_in(indexer, [issue], token=token)
        assert _apply(client, token=token, data=data).status_code == 302
        changeset = Changeset.objects.get(indexer=indexer,
                                          change_type=CTYPES['bulk'],
                                          state=states.OPEN)
    else:
        changeset = Changeset.objects.create(indexer=indexer,
                                             state=states.OPEN,
                                             change_type=CTYPES['issue'])
        assert _get_revision_lock(issue, changeset) is not None
        revision = IssueRevision.clone(data_object=issue,
                                       changeset=changeset)
        revision.notes = 'A normal change.'
        revision.save()
    changeset.submit()
    changeset.assign(approver)
    return changeset


def _reviewed_add(indexer, approver, after):
    """A change that adds an issue after the issue after, in review."""
    changeset = Changeset.objects.create(indexer=indexer, state=states.OPEN,
                                         change_type=CTYPES['issue_add'])
    IssueRevision(
      changeset=changeset, number='99', after=after, series=after.series,
      no_title=True, no_volume=True,
      indicia_publisher=after.indicia_publisher,
      publication_date='January 1947', key_date='1947-01-00',
      price='0.10 USD', indicia_frequency='monthly').save()
    changeset.submit()
    changeset.assign(approver)
    return changeset


def _approved_bulk_change(indexer, approver, issues, token, data):
    """A bulk change of issues by indexer with the operation data, approved."""
    client = _logged_in(indexer, issues, token=token)
    assert _apply(client, token=token, data=data).status_code == 302
    changeset = Changeset.objects.get(indexer=indexer,
                                      change_type=CTYPES['bulk'],
                                      state=states.OPEN)
    changeset.submit()
    changeset.assign(approver)
    _approve(changeset.id)
    return changeset


def _revert_url(changeset):
    """The address of the page that reverts changeset."""
    return reverse('edit_issues_in_bulk') + '?revert=%d' % changeset.id


def _discard(changeset_id):
    """Discard a change in a transaction, as the discard view does."""
    with transaction.atomic():
        changeset = Changeset.objects.select_for_update().get(
          id=changeset_id)
        changeset.discard(changeset.indexer)


@contextmanager
def _held(target, *args):
    """Keep target running in a thread, holding what it holds, in the block."""
    held, release = threading.Event(), threading.Event()
    holder = threading.Thread(target=target, args=(*args, held, release))
    holder.start()
    try:
        assert held.wait(30)
        yield
    finally:
        release.set()
        holder.join(30)
        assert not holder.is_alive()


def _held_change(changeset):
    """Hold the row of changeset in a transaction of its own in the block."""
    return _held(_hold_change, changeset)


def _held_row(row, then=None):
    """
    Hold row in a transaction of its own in the block; at its end call
    then, if given, in that transaction.
    """
    return _held(_hold_row, row, then)


def _held_lock(data_object, commit=False):
    """Reserve data_object, uncommitted, in the block; commit, or undo it."""
    return _held(_hold_lock, data_object, commit)


@contextmanager
def _short_server_wait():
    """In the block, the server gives up on a lock wait after a second."""
    with connection.cursor() as cursor:
        cursor.execute('SELECT @@SESSION.innodb_lock_wait_timeout')
        saved = cursor.fetchone()[0]
        cursor.execute('SET SESSION innodb_lock_wait_timeout = 1')
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SET SESSION innodb_lock_wait_timeout = %s',
                           [saved])


def _started(results, name, call):
    """Start call in a thread that keeps its result under name."""
    thread = threading.Thread(target=_run, args=(results, name, call))
    thread.start()
    return thread


def _approve(changeset_id):
    """Approve a change in a transaction, as the approve view does."""
    with transaction.atomic():
        Changeset.objects.select_for_update().get(id=changeset_id).approve()


def _run(results, name, call):
    """
    Run call and keep its result under name, or the exception it raised;
    for the approval, None if it ends without one.
    """
    try:
        results[name] = call()
    except Exception as error:
        results[name] = error
    finally:
        connections.close_all()


def _lock_waits(cursor, table):
    """Return how many transactions wait for a lock on a row of table."""
    cursor.execute(
      'SELECT COUNT(*) FROM performance_schema.data_lock_waits w '
      'JOIN performance_schema.data_locks l '
      'ON l.ENGINE_LOCK_ID = w.REQUESTING_ENGINE_LOCK_ID '
      'WHERE l.OBJECT_SCHEMA = DATABASE() AND l.OBJECT_NAME = %s', [table])
    return cursor.fetchone()[0]


def _wait_for_lock_wait(table, waiting=1, timeout=30):
    """
    Wait until waiting transactions, one by default, wait for a lock on a
    row of table, as the server shows it.
    """
    end = time.monotonic() + timeout
    with connection.cursor() as cursor:
        while time.monotonic() < end:
            if _lock_waits(cursor, table) >= waiting:
                return
            time.sleep(0.05)
    raise AssertionError('fewer than %d transactions wait for %s'
                         % (waiting, table))


def _row_locks(table):
    """Return how many locks on rows of table the server shows."""
    with connection.cursor() as cursor:
        cursor.execute(
          'SELECT COUNT(*) FROM performance_schema.data_locks '
          "WHERE OBJECT_SCHEMA = DATABASE() AND OBJECT_NAME = %s "
          "AND LOCK_TYPE = 'RECORD'", [table])
        return cursor.fetchone()[0]


def _lock_waits_until_done(thread, table):
    """
    Return how often a lock wait on table was seen while thread ran, for
    at most 30 seconds.
    """
    seen = 0
    end = time.monotonic() + 30
    with connection.cursor() as cursor:
        while thread.is_alive() and time.monotonic() < end:
            seen += _lock_waits(cursor, table)
            time.sleep(0.02)
    return seen


def _hold_row(row, then, held, release):
    """
    In a transaction of its own, lock row until release, as another
    request that writes it does, then call then, if given.
    """
    try:
        with transaction.atomic():
            type(row).objects.select_for_update().get(id=row.id)
            held.set()
            release.wait(60)
            if then:
                then()
    finally:
        connections.close_all()


def _hold_change(changeset, held, release):
    """
    In a transaction of its own, lock the row of changeset until release,
    as another request that works on the change does.
    """
    try:
        with transaction.atomic():
            Changeset.objects.select_for_update().get(id=changeset.id)
            held.set()
            release.wait(60)
    finally:
        connections.close_all()


def _hold_indexer(user, held, release):
    """
    In a transaction of its own, lock the indexer row of user until
    release, as a request that applies a bulk change does.
    """
    try:
        with transaction.atomic():
            Indexer.objects.select_for_update().get(user=user)
            held.set()
            release.wait(60)
    finally:
        connections.close_all()


def _hold_lock(data_object, commit, held, release):
    """
    In a transaction of its own, reserve data_object and wait until
    release, then commit or undo it: a reservation not yet committed.
    """
    try:
        with transaction.atomic():
            RevisionLock.objects.create(locked_object=data_object)
            held.set()
            release.wait(90)
            if not commit:
                transaction.set_rollback(True)
    finally:
        connections.close_all()
