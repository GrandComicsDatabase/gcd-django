"""Apply a bulk change: one change of the objects that pass, then submit."""
from datetime import datetime, timedelta, timezone
from html import unescape

import pytest

from django.core.cache import cache
from django.db import OperationalError, connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import IndiciaPublisher, Issue, Series, Story
from apps.indexer.views import ErrorWithMessage
from apps.oi import bulk, states
from apps.oi.models import (
    Changeset, IndiciaPublisherRevision, IssueRevision, ReprintRevision,
    RevisionLock, SeriesRevision, StoryRevision, CTYPES, _get_revision_lock)
from apps.oi.views import copy_cached_sequences
from apps.oi.tests.bulk.invariants import check_invariants
from apps.oi.tests.bulk.page_forms import PageForms

TOKEN = 'test-token'
SOURCE = '/list/?series=1'
PRICE = {'field': 'price', 'shown': 'price', 'operation': 'replace_exact',
         'old_value': '=0.10 USD', 'new_value': '0.12 USD'}
RATING = {'field': 'rating', 'shown': 'rating', 'operation': 'replace_exact',
          'old_value': '=', 'new_value': 'Teen'}
NO_ISBN = {'field': 'no_isbn', 'shown': 'no_isbn', 'operation': 'set',
           'new_value': 'on'}
ISBN = '9780306406157'
PAGE_COUNT_ERROR = 'You cannot check page count uncertain without a page ' \
                   'count.'
FREQUENCY_ERROR = 'You cannot specify an indicia frequency and check ' \
                  '"no indicia frequency" at the same time.'
FREQUENCY = {'field': 'indicia_frequency', 'shown': 'indicia_frequency',
             'operation': 'replace_exact', 'old_value': '=',
             'new_value': 'monthly'}
REFUSED = 'A bulk change is changed only by its operations.'
CHOICE_ERROR = 'Select a valid choice. That choice is not one of the ' \
               'available choices.'


@pytest.fixture(autouse=True)
def invariants(db):
    """Start without applied tokens; check the invariants at the end."""
    cache.clear()
    yield
    check_invariants()


def _select(client, issues, token=TOKEN):
    """Keep issues as the selection of token, as a list would."""
    session = client.session
    session[bulk.SELECTION_KEY] = {
      'token': token, 'model': 'issue', 'source': SOURCE,
      'ids': sorted(issue.id for issue in issues)}
    session.save()


@pytest.fixture
def selection(client, settings, reserving_indexer, approved_issues):
    """
    Turn bulk changes on, log the indexer in and keep the three approved
    issues as the selection of TOKEN.
    """
    settings.BULK_CHANGE_ENABLED = True
    client.force_login(reserving_indexer)
    _select(client, approved_issues)
    return approved_issues


def _apply(client, token=TOKEN, **params):
    """Post an operation to the bulk change page of token."""
    return client.post(reverse('edit_issues_in_bulk') + '?token=' + token,
                       params or PRICE)


def _change():
    """The only bulk change."""
    return Changeset.objects.get(change_type=CTYPES['bulk'])


def _record(changeset):
    """The operation that the first comment of changeset records."""
    return bulk.operation_record(changeset)


def _allow_open_changes(user):
    """Let user hold several open changes, as an experienced indexer."""
    user.indexer.max_reservations = 5
    user.indexer.save()


def _update(issue, **values):
    """Change the stored values of issue, as another edit would have."""
    Issue.objects.filter(id=issue.id).update(**values)


def _approved(issue, **values):
    """
    Change the stored values of issue and of its latest approved revision,
    as an approved edit would have.
    """
    _update(issue, **values)
    IssueRevision.objects.filter(issue=issue, committed=True,
                                 next_revision=None).update(**values)


@pytest.mark.django_db
def test_approval_refused_only_after_a_lock_conflict(client, selection,
                                                     monkeypatch, bulk_change,
                                                     any_approver):
    """Another database error of an approval stays a server error."""
    changeset = bulk_change(selection[:1], IssueRevision, price='0.12 USD')
    changeset.submit()
    changeset.assign(any_approver)
    client.force_login(any_approver)

    def server_gone(*args, **kwargs):
        """Fail as the database does when the connection is lost."""
        raise OperationalError(2006, 'MySQL server has gone away')

    monkeypatch.setattr(Changeset, 'approve', server_gone)

    with pytest.raises(OperationalError):
        client.post(reverse('approve', kwargs={'id': changeset.id}),
                    {'comments': ''})


@pytest.mark.django_db
def test_variant_of_a_free_base_is_changed(client, selection,
                                           approved_variant):
    """A variant goes into the change when nothing is writing its base."""
    _select(client, selection + [approved_variant])

    _apply(client)

    revision = _change().issuerevisions.get(issue=approved_variant)
    assert revision.price == '0.12 USD'
    assert revision.variant_of == selection[-1]


@pytest.mark.django_db
def test_apply_makes_one_open_change(client, selection, reserving_indexer):
    """The changed issues go into one OPEN change, which the page shows."""
    response = _apply(client)

    changeset = _change()
    assert response['Location'] == reverse('compare',
                                           kwargs={'id': changeset.id})
    assert changeset.state == states.OPEN
    assert changeset.indexer == reserving_indexer
    revisions = changeset.issuerevisions.order_by('issue_id')
    assert [revision.issue for revision in revisions] == selection
    assert {revision.price for revision in revisions} == {'0.12 USD'}
    assert set(Issue.objects.filter(id__in=[issue.id for issue in selection])
               .values_list('price', flat=True)) == {'0.10 USD'}
    assert changeset.revision_locks.count() == 3
    record = _record(changeset)
    assert (record['model'], record['name'], record['operation'],
            record['values']) == ('issue', 'price', 'replace_exact',
                                  ['0.10 USD', '0.12 USD'])
    assert record['source'].endswith(SOURCE)
    assert (record['checked'], record['total']) == (3, 3)
    assert record['counts'] == {'changed': 3, 'unchanged': 0,
                                'turned_off': 0, 'reserved': 0,
                                'invalid': 0, 'blocked': 0}


@pytest.mark.django_db
@pytest.mark.parametrize('operation, value, changed', [
    (PRICE, '0.12 USD', 3),
    (NO_ISBN, True, 2),
])
def test_apply_form_as_rendered(client, selection, operation, value,
                                changed):
    """
    The forms of the page, submitted as rendered with the choices of the
    indexer, give the change that the preview shows; no page repeats an
    id.  The first issue has "no isbn" already.
    """
    url = reverse('edit_issues_in_bulk')
    page = PageForms(client.get(url, {'token': TOKEN}).content.decode())
    for chosen in ({'field': operation['field']}, operation):
        assert page.repeated_ids() == []
        data = page.data(page.form('GET', url), **chosen)
        page = PageForms(client.get(url, data).content.decode())
    assert page.repeated_ids() == []
    form = page.form('POST', url + '?token=' + TOKEN)

    response = client.post(form['action'], page.data(form))

    changeset = _change()
    assert response['Location'] == reverse('compare',
                                           kwargs={'id': changeset.id})
    assert [getattr(revision, operation['field'])
            for revision in changeset.issuerevisions.all()] == \
        [value] * changed


@pytest.mark.django_db
def test_value_changed_since_the_preview(client, selection):
    """Each value is read again: one changed meanwhile is left alone."""
    _approved(selection[0], price='0.20 USD')

    _apply(client)

    changeset = _change()
    assert not changeset.issuerevisions.filter(issue=selection[0]).exists()
    assert not RevisionLock.objects.filter(object_id=selection[0].id)\
                                   .exists()
    assert _record(changeset)['counts']['unchanged'] == 1
    assert changeset.issuerevisions.count() == 2


@pytest.mark.django_db
def test_other_fields_keep_their_stored_values(client, selection,
                                               any_approver):
    """
    Only the field changes, to the value that the edit form cleans; the
    other fields keep their spaces and dashes, as stored.
    """
    notes = '  Two  spaces - and a dash  '
    _approved(selection[1], notes=notes, indicia_frequency='monthly ')

    _apply(client, **dict(PRICE, new_value=' 0.12 USD '))

    changeset = _change()
    revision = changeset.issuerevisions.get(issue=selection[1])
    assert (revision.price, revision.notes, revision.indicia_frequency) == \
        ('0.12 USD', notes, 'monthly ')
    changeset.submit()
    changeset.assign(any_approver)
    changeset.approve()
    issue = Issue.objects.get(id=selection[1].id)
    assert (issue.price, issue.notes, issue.indicia_frequency) == \
        ('0.12 USD', notes, 'monthly ')


@pytest.mark.django_db
def test_object_already_invalid_is_blocked(client, selection):
    """An issue that already fails its edit form is left out, blocked."""
    _approved(selection[1], page_count=None, page_count_uncertain=True)

    _apply(client)

    changeset = _change()
    record = _record(changeset)
    assert record['counts']['blocked'] == 1
    assert record['listed']['blocked'] == [selection[1].id]
    assert PAGE_COUNT_ERROR in changeset.comments.get().text
    assert not changeset.issuerevisions.filter(issue=selection[1]).exists()
    assert not RevisionLock.objects.filter(object_id=selection[1].id)\
                                   .exists()


@pytest.mark.django_db
def test_new_error_behind_an_old_one_is_not_applied(client, selection):
    """
    A change that would add an error to an issue that already has one is
    not applied: the edit form stops at the first error, so only the
    check before the change tells the two apart.
    """
    _approved(selection[1], isbn=ISBN, page_count=None,
              page_count_uncertain=True)

    _apply(client, **NO_ISBN)

    changeset = _change()
    assert _record(changeset)['listed']['blocked'] == [selection[1].id]
    assert Issue.objects.get(id=selection[1].id).no_isbn is False
    assert not changeset.issuerevisions.filter(issue=selection[1]).exists()
    assert {revision.no_isbn
            for revision in changeset.issuerevisions.all()} == {True}


@pytest.mark.django_db
def test_change_that_breaks_the_rules_is_invalid(client, selection):
    """An issue that the change would make invalid leaves no rows."""
    _approved(selection[1], isbn=ISBN)

    _apply(client, **NO_ISBN)

    changeset = _change()
    record = _record(changeset)
    assert record['listed']['invalid'] == [selection[1].id]
    assert 'You cannot specify an isbn and check "no isbn"' in \
        changeset.comments.get().text
    assert not IssueRevision.objects.filter(issue=selection[1],
                                            changeset=changeset).exists()
    assert not RevisionLock.objects.filter(object_id=selection[1].id)\
                                   .exists()
    # The first issue has "no isbn" already.
    assert (record['counts']['changed'], record['counts']['unchanged']) == \
        (1, 1)


@pytest.mark.django_db
@pytest.mark.parametrize('after_the_check', [False, True])
def test_object_reserved_by_another_change(client, selection, any_approver,
                                           monkeypatch, after_the_check):
    """
    An issue that another change holds is left out, reserved, also when
    the other change takes it just after the check for its lock.
    """
    other = Changeset.objects.create(indexer=any_approver,
                                     state=states.OPEN,
                                     change_type=CTYPES['issue'])
    _get_revision_lock(selection[1], other)
    if after_the_check:
        monkeypatch.setattr(bulk, '_locked', lambda data_object: False)

    _apply(client)

    changeset = _change()
    assert _record(changeset)['listed']['reserved'] == [selection[1].id]
    assert RevisionLock.objects.get(object_id=selection[1].id).changeset \
        == other
    assert changeset.issuerevisions.count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize('case, outcome', [
    ('open revision without lock', 'reserved'),
    ('no revision', 'invalid'),
])
def test_object_without_one_approved_revision(client, selection,
                                              any_approver, case, outcome):
    """
    An issue without exactly one latest approved revision cannot be
    cloned: reserved if a change holds a revision of it, else invalid.
    """
    if case == 'no revision':
        IssueRevision.objects.filter(issue=selection[1]).delete()
    else:
        other = Changeset.objects.create(indexer=any_approver,
                                         state=states.OPEN,
                                         change_type=CTYPES['issue'])
        IssueRevision.clone(selection[1], other)

    _apply(client)

    changeset = _change()
    assert _record(changeset)['listed'][outcome] == [selection[1].id]
    assert changeset.issuerevisions.count() == 2


@pytest.mark.django_db
def test_object_deleted_since_the_selection(client, selection):
    """An issue deleted after the list was chosen is invalid."""
    _update(selection[1], deleted=True)

    _apply(client)

    changeset = _change()
    assert _record(changeset)['listed']['invalid'] == [selection[1].id]
    assert 'It was deleted.' in changeset.comments.get().text


@pytest.mark.django_db
def test_nothing_changed_says_why(client, selection):
    """
    When the edit form refuses every object, the page gives the reason,
    once, with the first object it applies to.
    """
    for issue in selection:
        _approved(issue, indicia_frequency='', no_indicia_frequency=True)

    page = unescape(_apply(client, **FREQUENCY).content.decode())

    assert 'invalid 3' in page
    assert '%s: %s' % (selection[0], FREQUENCY_ERROR) in page
    assert page.count(FREQUENCY_ERROR) == 1
    assert not Changeset.objects.filter(change_type=CTYPES['bulk']).exists()


def _two_reasons(selection):
    """Make each of the issues fail its edit form, for two reasons."""
    _approved(selection[0], no_indicia_frequency=True)
    _approved(selection[1], page_count_uncertain=True)
    _approved(selection[2], no_indicia_frequency=True)


@pytest.mark.django_db
def test_nothing_changed_gives_each_reason(client, selection):
    """Objects already failing are listed once for each reason."""
    _two_reasons(selection)

    page = unescape(_apply(client).content.decode())

    assert 'blocked 3' in page
    assert '%s: %s' % (selection[0], FREQUENCY_ERROR) in page
    assert '%s: %s' % (selection[1], PAGE_COUNT_ERROR) in page
    assert page.count(FREQUENCY_ERROR) == 1


@pytest.mark.django_db
def test_nothing_changed_limits_the_reasons(client, selection, monkeypatch):
    """The page gives at most LISTED_OBJECTS reasons."""
    _two_reasons(selection)
    monkeypatch.setattr(bulk, 'LISTED_OBJECTS', 1)

    page = unescape(_apply(client).content.decode())

    assert FREQUENCY_ERROR in page
    assert PAGE_COUNT_ERROR not in page


@pytest.mark.django_db
def test_nothing_changed_has_no_reason_for_reserved(client, selection,
                                                    any_approver):
    """An object reserved by another change only counts: it has no reason."""
    other = Changeset.objects.create(indexer=any_approver,
                                     state=states.OPEN,
                                     change_type=CTYPES['issue'])
    for issue in selection:
        _get_revision_lock(issue, other)

    page = unescape(_apply(client).content.decode())

    assert 'reserved 3' in page
    assert str(selection[0]) not in page


@pytest.mark.django_db
def test_nothing_changed_makes_no_change(client, selection):
    """
    With every field turned off nothing changes: no change is made and
    the selection can be applied again.
    """
    Series.objects.filter(id=selection[0].series_id).update(has_volume=False)

    response = _apply(client, field='volume', shown='volume',
                      operation='set', new_value='2')

    assert 'Nothing was changed' in response.content.decode()
    assert 'turned off 3' in response.content.decode()
    assert not Changeset.objects.filter(change_type=CTYPES['bulk']).exists()
    assert not RevisionLock.objects.filter(
      object_id__in=[issue.id for issue in selection]).exists()
    assert _apply(client).status_code == 302


@pytest.mark.django_db
def test_token_is_applied_once(client, settings, selection,
                               reserving_indexer, monkeypatch):
    """
    The page of an applied selection, and a second post of it, ask to
    start again from the list; a request that passed that check before
    the first one ended, as with a second tab, finds the selection
    applied all the same.  The session keeps the selection.
    """
    _allow_open_changes(reserving_indexer)
    settings.BULK_CHANGE_MAX_ACTIVE = 2
    _apply(client)

    page = client.get(reverse('edit_issues_in_bulk'), {'token': TOKEN})
    again = _apply(client)
    monkeypatch.setattr(bulk, 'selection_applied',
                        lambda user, token: False)
    late = _apply(client)

    for response in (page, again, late):
        assert bulk.APPLIED_ALREADY in response.content.decode()
    assert client.session[bulk.SELECTION_KEY]['token'] == TOKEN
    assert Changeset.objects.filter(change_type=CTYPES['bulk']).count() == 1


@pytest.mark.django_db
def test_second_active_bulk_change_is_refused(client, selection,
                                              reserving_indexer):
    """One active bulk change at a time, by default."""
    _allow_open_changes(reserving_indexer)
    _apply(client)
    _select(client, selection, token='second')

    response = _apply(client, token='second')

    assert 'You already have 1 active bulk change' in \
        response.content.decode()
    assert Changeset.objects.filter(change_type=CTYPES['bulk']).count() == 1


@pytest.mark.django_db
def test_limit_for_a_new_indexer(client, settings, selection,
                                 reserving_indexer):
    """A new indexer may change at most BULK_CHANGE_MAX_NEW objects."""
    reserving_indexer.indexer.is_new = True
    reserving_indexer.indexer.save()
    settings.BULK_CHANGE_MAX_NEW = 2

    response = _apply(client)

    assert 'at most 2 objects' in response.content.decode()
    assert not Changeset.objects.filter(change_type=CTYPES['bulk']).exists()


@pytest.mark.django_db
def test_submit_and_approve(client, selection, any_approver):
    """The change goes through the approval of any change."""
    _apply(client)
    changeset = _change()

    response = client.post(reverse('process', kwargs={'id': changeset.id}),
                           {'submit': 'Submit', 'comments': ''})

    assert response.status_code == 302
    changeset.refresh_from_db()
    assert changeset.state == states.PENDING
    assert changeset.imps > 0
    changeset.assign(any_approver)
    changeset.approve()
    assert set(Issue.objects.filter(id__in=[issue.id for issue in selection])
               .values_list('price', flat=True)) == {'0.12 USD'}
    assert not changeset.revision_locks.exists()


@pytest.mark.django_db
def test_new_indexer_goes_to_the_mentor(client, selection,
                                        reserving_indexer, any_approver):
    """A new indexer's bulk change goes to their mentor, as any change."""
    reserving_indexer.indexer.is_new = True
    reserving_indexer.indexer.mentor = any_approver
    reserving_indexer.indexer.save()
    _apply(client)
    changeset = _change()

    client.post(reverse('process', kwargs={'id': changeset.id}),
                {'submit': 'Submit', 'comments': ''})

    changeset.refresh_from_db()
    assert (changeset.state, changeset.approver) == \
        (states.REVIEWING, any_approver)


@pytest.mark.django_db
def test_submit_checks_revisions_changed_since_the_operation(client,
                                                             selection):
    """A revision changed after its operation is checked again."""
    _apply(client)
    changeset = _change()
    revision = changeset.issuerevisions.first()
    revision.page_count = None
    revision.page_count_uncertain = True
    revision.save()

    response = client.post(reverse('process', kwargs={'id': changeset.id}),
                           {'submit': 'Submit', 'comments': ''})

    assert 'This bulk change cannot be submitted.' in \
        response.content.decode()
    assert PAGE_COUNT_ERROR in response.content.decode()
    changeset.refresh_from_db()
    assert changeset.state == states.OPEN


@pytest.mark.django_db
def test_submit_refuses_other_kinds_of_revisions(client, selection):
    """A bulk change holds no revision that its operations do not make."""
    _apply(client)
    changeset = _change()
    ReprintRevision.objects.create(changeset=changeset,
                                   origin_issue=selection[0],
                                   target_issue=selection[1])

    with pytest.raises(bulk.ErrorWithMessage) as refusal:
        changeset.submit()

    assert 'reprintrevisions' in refusal.value.message
    changeset.refresh_from_db()
    assert changeset.state == states.OPEN
    changeset.reprintrevisions.all().delete()


def _manual_edits(changeset, revision, issue):
    """The routes that change revisions by hand, as (method, url)."""
    issue_id = {'issue_id': issue.id, 'changeset_id': changeset.id}
    return [
      ('get', reverse('edit_revision', kwargs={'model_name': 'issue',
                                               'id': revision.id})),
      ('post', reverse('process_revision', kwargs={'model_name': 'issue',
                                                   'id': revision.id})),
      ('get', reverse('compare_issues_copy', kwargs={
        'issue_revision_id': revision.id, 'issue_id': issue.id})),
      ('get', reverse('add_story', kwargs={
        'issue_revision_id': revision.id, 'changeset_id': changeset.id})),
      ('get', reverse('reorder_stories', kwargs=issue_id)),
      ('post', reverse('migrate_issue_revision', kwargs={'id': revision.id})),
      ('get', reverse('move_issue', kwargs={
        'issue_revision_id': revision.id, 'series_id': issue.series_id})),
      ('get', reverse('add_issue_reprint', kwargs={
        'issue_id': revision.id, 'changeset_id': changeset.id})),
      ('get', reverse('add_variant_to_issue_revision', kwargs={
        'issue_revision_id': revision.id, 'changeset_id': changeset.id})),
      ('post', reverse('import_issue', kwargs=issue_id)),
      ('post', reverse('import_stories', kwargs=issue_id)),
      ('post', reverse('move_cover', kwargs={'id': changeset.id})),
      ('post', reverse('undo_move_cover', kwargs={'id': changeset.id,
                                                  'cover_id': 1})),
      ('get', reverse('confirm_copy_story', kwargs={
        'issue_revision_id': revision.id, 'story_id': 1,
        'sequence_number': 1})),
      ('get', reverse('copy_story_revision', kwargs={
        'issue_revision_id': revision.id, 'changeset_id': changeset.id})),
      ('post', reverse('confirm_copy_story_revision', kwargs={
        'issue_revision_id': revision.id, 'story_revision_id': 1})),
      ('post', reverse('reserve_reprint', kwargs={
        'reprint_id': 1, 'changeset_id': changeset.id})),
      ('post', reverse('save_issue_issue_reprint', kwargs={
        'reprint_revision_id': 'new', 'issue_one_id': issue.id,
        'changeset_id': changeset.id, 'issue_two_id': issue.id})),
    ]


def _manual_sequence_edits(story_revision):
    """The routes that change sequence revisions by hand, as (method, url)."""
    story = {'story_revision_id': story_revision.id}
    own = {'id': story_revision.id}
    edited = {'model_name': 'story', 'id': story_revision.id}
    return [
      ('get', reverse('edit_revision', kwargs=edited)),
      ('post', reverse('process_revision', kwargs=edited)),
      ('get', reverse('story_select_compare', kwargs=story)),
      ('get', reverse('compare_stories_copy', kwargs=dict(
        story, story_id=story_revision.story_id))),
      ('get', reverse('create_character_order_revision',
                      kwargs=dict(story, type_id=1))),
      ('get', reverse('edit_character_order_revision',
                      kwargs=dict(story, type_id=1))),
      ('post', reverse('move_story_revision', kwargs=own)),
      ('post', reverse('remove_story_revision', kwargs=own)),
      ('post', reverse('toggle_delete_story_revision', kwargs=own)),
      ('post', reverse('migrate_story_revision', kwargs=own)),
    ]


@pytest.mark.django_db
def test_manual_edits_are_refused(client, selection):
    """No route changes the revisions of a bulk change by hand."""
    _apply(client)
    changeset = _change()
    revision = changeset.issuerevisions.get(issue=selection[0])

    for method, url in _manual_edits(changeset, revision, selection[0]):
        response = getattr(client, method)(url, {'save': 'Save'})
        assert REFUSED in response.content.decode(), url

    revision.refresh_from_db()
    assert revision.price == '0.12 USD'


@pytest.mark.django_db
def test_manual_edits_of_sequences_and_series_are_refused(
      client, selection, reserving_indexer, bulk_change, sequence_change,
      approved_stories):
    """
    No route changes the sequences or the series of a bulk change by
    hand, nor copies sequences into it.
    """
    changeset = sequence_change(approved_stories[:1], title='New')
    story_revision = changeset.storyrevisions.get()
    series_change = bulk_change([approved_stories[0].issue.series],
                                SeriesRevision, notes='New')
    series_revision = series_change.seriesrevisions.get()
    routes = _manual_sequence_edits(story_revision) + [
      ('get', reverse('move_series', kwargs={
        'series_revision_id': series_revision.id, 'publisher_id': 1}))]

    for method, url in routes:
        response = getattr(client, method)(url, {'save': 'Save'})
        assert REFUSED in response.content.decode(), url

    # A sequence revision without its sequence is removed, not deleted.
    StoryRevision.objects.filter(id=story_revision.id).update(story=None)
    response = client.post(reverse('remove_story_revision',
                                   kwargs={'id': story_revision.id}))
    assert REFUSED in response.content.decode()
    StoryRevision.objects.filter(id=story_revision.id).update(
      story=approved_stories[0])

    request = RequestFactory().post('/')
    request.user = reserving_indexer
    with pytest.raises(bulk.ErrorWithMessage):
        copy_cached_sequences(
          request, {'issue_revision_id': changeset.issuerevisions.get().id},
          'key')
    story_revision.refresh_from_db()
    assert story_revision.title == 'New'


@pytest.mark.django_db
def test_error_in_the_middle_undoes_everything(client, selection,
                                               monkeypatch):
    """
    An error on the second object undoes the whole request, and the
    selection can be applied again.
    """
    process_item = bulk.process_item
    calls = []

    def failing(*args):
        """Fail on the second object."""
        calls.append(args)
        if len(calls) == 2:
            raise RuntimeError('injected')
        return process_item(*args)

    monkeypatch.setattr(bulk, 'process_item', failing)
    with pytest.raises(RuntimeError):
        _apply(client)

    assert not Changeset.objects.filter(change_type=CTYPES['bulk']).exists()
    assert not RevisionLock.objects.filter(
      object_id__in=[issue.id for issue in selection]).exists()
    monkeypatch.setattr(bulk, 'process_item', process_item)
    assert _apply(client).status_code == 302


@pytest.mark.django_db
def test_deadlock_gives_a_clean_refusal(client, selection, monkeypatch):
    """
    A deadlock while an object is changed undoes the request and asks to
    apply again.
    """
    def deadlock(*args, **kwargs):
        """Fail as a deadlock does."""
        raise OperationalError(bulk.DEADLOCK, 'Deadlock found')

    monkeypatch.setattr(bulk, 'revision_form_messages', deadlock)

    response = _apply(client)

    assert 'Please apply again.' in response.content.decode()
    assert not Changeset.objects.filter(change_type=CTYPES['bulk']).exists()


@pytest.mark.django_db
def test_another_database_error_of_an_apply_stays_an_error(client, selection,
                                                           monkeypatch):
    """Only a lock conflict asks to apply again; others are server errors."""
    def server_gone(*args, **kwargs):
        """Fail as the database does when the connection is lost."""
        raise OperationalError(2006, 'MySQL server has gone away')

    monkeypatch.setattr(bulk, 'revision_form_messages', server_gone)

    with pytest.raises(OperationalError):
        _apply(client)

    assert not Changeset.objects.filter(change_type=CTYPES['bulk']).exists()


@pytest.mark.django_db
def test_operation_comment_reads_back(approved_issues):
    """The comment keeps exact values, counts, checkpoint and ids."""
    text = ' Two  "quoted" words' + chr(233) + ' '
    operation = bulk.Operation('notes', 'replace_exact', text, None)
    counts = dict(zip(bulk.OUTCOMES, range(6)))
    listed = {'reserved': [], 'invalid': [(approved_issues[0], 'Why.')],
              'blocked': [(approved_issues[1], '')] * 51}
    checkpoint = datetime(2026, 11, 7, 18, 30, 5, 999999,
                          tzinfo=timezone.utc)

    comment = bulk.operation_text(Issue, operation, SOURCE, 20, counts,
                                  listed, checkpoint)
    record = bulk.parse_operation(comment)

    assert record['values'] == [text, None]
    assert record['counts'] == counts
    assert (record['checked'], record['total']) == (15, 20)
    assert record['checkpoint'] == checkpoint.replace(microsecond=0)
    assert record['listed'] == {'reserved': [],
                                'invalid': [approved_issues[0].id],
                                'blocked': [approved_issues[1].id] * 50}
    assert comment.endswith('Blocked: and 1 more')
    assert bulk.parse_operation('A comment of the indexer.') is None
    for broken in ('Operation: issue.price set oops',
                   'Operation: issue.price set "1"\r\nCheckpoint: soon',
                   'Operation: issue.price set ' + '[' * 100000):
        assert bulk.parse_operation(broken) is None


@pytest.mark.django_db
def test_a_record_from_an_escaped_address_reads_back(client, settings,
                                                     reserving_indexer,
                                                     approved_issues):
    """
    A list address with a line break in a free segment of its path gives a
    record of one Source line, which reads back with its real checkpoint
    and counts.
    """
    settings.BULK_CHANGE_ENABLED = True
    for issue in approved_issues:
        _approved(issue, barcode='9781234567897', no_barcode=False)
    client.force_login(reserving_indexer)
    path = '/barcode/9781234567897/sort/alpha%0ACheckpoint%3A%20never%0Ax/'
    page = client.get(path + '?_export=bulk')['Location']
    before = datetime.now(timezone.utc).replace(microsecond=0)

    assert client.post(page, PRICE).status_code == 302

    changeset = _change()
    record = _record(changeset)
    assert record is not None
    assert record['source'].endswith(
      '/barcode/9781234567897/sort/alpha%0ACheckpoint:%20never%0Ax/')
    assert before <= record['checkpoint'] <= datetime.now(timezone.utc)
    assert record['counts']['changed'] == len(approved_issues)
    assert len(changeset.comments.get().text.split('\n')) == 4


@pytest.mark.django_db
def test_revision_records_the_time_of_its_change(client, selection,
                                                 monkeypatch):
    """The revision of a changed object records when it was changed."""
    clone = bulk._clone
    hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

    def made_an_hour_ago(rev_class, data_object, changeset):
        """Clone data_object, as if an hour ago."""
        revision = clone(rev_class, data_object, changeset)
        rev_class.objects.filter(id=revision.id).update(modified=hour_ago)
        revision.modified = hour_ago
        return revision

    monkeypatch.setattr(bulk, '_clone', made_an_hour_ago)
    _apply(client)

    assert all(revision.modified > hour_ago + timedelta(minutes=30)
               for revision in _change().issuerevisions.all())


@pytest.mark.django_db
@pytest.mark.parametrize('meanwhile', ['value', 'flag'])
def test_object_changed_while_the_change_runs(client, selection,
                                              monkeypatch, meanwhile):
    """
    Each object is read again once it is locked: a value, or a flag of
    its series, that another edit changed after the first read leaves it
    out.  The first issue has "no isbn" already.
    """
    process_item = bulk.process_item

    def edited_meanwhile(changeset, data_object, operation, user):
        """Let another edit change the second issue, then go on."""
        if data_object.id == selection[1].id:
            if meanwhile == 'value':
                _approved(selection[1], no_isbn=True)
            else:
                Series.objects.filter(id=selection[1].series_id) \
                              .update(has_isbn=False)
        return process_item(changeset, data_object, operation, user)

    monkeypatch.setattr(bulk, 'process_item', edited_meanwhile)
    response = _apply(client, **NO_ISBN)

    if meanwhile == 'value':
        counts = _record(_change())['counts']
        assert (counts['unchanged'], counts['changed']) == (2, 1)
    else:
        assert 'turned off 2' in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize('left_alone', ['unchanged', 'turned off'])
def test_objects_left_alone_are_not_locked(client, selection, any_approver,
                                           left_alone):
    """
    An object that the operation leaves as it is, or whose field is off,
    is never locked, so it is not reserved where another change holds it.
    """
    other = Changeset.objects.create(indexer=any_approver,
                                     state=states.OPEN,
                                     change_type=CTYPES['issue'])
    _get_revision_lock(selection[0], other)

    if left_alone == 'unchanged':
        _approved(selection[0], price='0.20 USD')
        _apply(client)
        counts = _record(_change())['counts']
        assert (counts['unchanged'], counts['reserved']) == (1, 0)
    else:
        Series.objects.filter(id=selection[0].series_id) \
                      .update(has_volume=False)
        response = _apply(client, field='volume', shown='volume',
                          operation='set', new_value='2')
        assert 'turned off 3, reserved 0' in response.content.decode()


@pytest.mark.django_db
def test_missing_object_is_invalid(client, selection):
    """An object that no longer exists is counted as invalid."""
    session = client.session
    session[bulk.SELECTION_KEY]['ids'].append(selection[-1].id + 1000)
    session.save()

    _apply(client)

    record = _record(_change())
    assert record['counts']['invalid'] == 1
    assert (record['checked'], record['total']) == (4, 4)


@pytest.mark.django_db
def test_parents_are_held_in_order_with_the_new_link(selection):
    """
    The rows that the new revisions will point to, the new link included,
    are held one table at a time, in the same order for every request.
    """
    new = selection[0].indicia_publisher_id + 1000
    operation = bulk.Operation('indicia_publisher', 'set', None, new)

    with CaptureQueriesContext(connection) as queries:
        bulk._hold_parents(Issue, [issue.id for issue in selection], operation)

    held = [query['sql'] for query in queries if 'FOR SHARE' in query['sql']]
    assert [sql.split(' WHERE ')[0].split()[-1].strip('`') for sql in held] \
        == ['gcd_series', 'gcd_indicia_publisher', 'gcd_brand',
            'gcd_indicia_printer']
    assert all(sql.endswith('ORDER BY id FOR SHARE') for sql in held)
    assert str(new) in held[1]


def _held_rows(model_ids, operation):
    """The queries with which _hold_parents holds rows of issues."""
    with CaptureQueriesContext(connection) as queries:
        bulk._hold_parents(Issue, model_ids, operation)
    return [query['sql'] for query in queries if 'FOR SHARE' in query['sql']]


@pytest.mark.django_db
@pytest.mark.parametrize('empty', [None, ''])
def test_an_emptied_link_holds_no_new_row(selection, empty):
    """A link that the operation empties adds no row to hold."""
    operation = bulk.Operation('indicia_publisher', 'set', None, empty)

    held = _held_rows([issue.id for issue in selection], operation)

    assert len(held) == 4


@pytest.mark.django_db
def test_new_value_counts_only_for_its_own_field(selection):
    """The new value of another field is no parent row to hold."""
    operation = bulk.Operation('price', 'set', None, 987654)

    held = _held_rows([issue.id for issue in selection], operation)

    assert not any('987654' in sql for sql in held)


@pytest.mark.django_db
def test_a_table_without_parents_is_left_out(selection):
    """Objects with no brand or printer hold no row of those tables."""
    operation = bulk.Operation('price', 'set', None, '1.00 USD')

    held = _held_rows([issue.id for issue in selection[1:]], operation)

    assert [sql.split(' WHERE ')[0].split()[-1].strip('`') for sql in held] \
        == ['gcd_series', 'gcd_indicia_publisher']


@pytest.fixture
def new_indicia_publisher(any_adding_changeset, indicia_publisher_add_values):
    """
    Return a function that adds an approved indicia publisher of the
    publisher of the issues, with the given values.
    """
    def add(**values):
        revision = IndiciaPublisherRevision(
          changeset=any_adding_changeset,
          **dict(indicia_publisher_add_values, **values))
        revision.save()
        revision.commit_to_display()
        return revision.indicia_publisher
    return add


def _set_indicia_publisher(indicia_publisher):
    """The parameters of an operation that sets indicia_publisher."""
    return {'field': 'indicia_publisher', 'shown': 'indicia_publisher',
            'operation': 'set', 'new_value': indicia_publisher.id}


@pytest.mark.django_db
def test_an_indicia_publisher_outside_the_years_of_the_issue_is_invalid(
      client, selection, new_indicia_publisher):
    """
    An indicia publisher whose years leave out the year of the issues is
    refused, as their edit form would not offer it; one without years is
    set.
    """
    outside = new_indicia_publisher(name='Outside', year_began=1969,
                                    year_ended=1979)
    free = new_indicia_publisher(name='Free', year_began=None,
                                 year_ended=None)

    page = unescape(_apply(client, **_set_indicia_publisher(outside))
                    .content.decode())

    assert 'invalid 3' in page
    assert '%s: %s' % (selection[0], CHOICE_ERROR) in page
    assert not IssueRevision.objects.filter(
      indicia_publisher=outside).exists()
    assert not Changeset.objects.filter(change_type=CTYPES['bulk']).exists()
    assert _apply(client, **_set_indicia_publisher(free)).status_code == 302
    assert _record(_change())['counts']['changed'] == 3


@pytest.mark.django_db
@pytest.mark.parametrize('state', ['deleted', 'being deleted'])
def test_an_indicia_publisher_deleted_or_being_deleted_is_invalid(
      selection, reserving_indexer, any_approver, new_indicia_publisher,
      state):
    """
    An indicia publisher that is deleted, or that an active change deletes,
    is refused for every object, also when the page form is passed by.
    """
    gone = new_indicia_publisher(name='Gone')
    if state == 'deleted':
        IndiciaPublisher.objects.filter(id=gone.id).update(deleted=True)
    else:
        deletion = Changeset.objects.create(
          indexer=any_approver, state=states.PENDING,
          change_type=CTYPES['indicia_publisher'])
        revision = IndiciaPublisherRevision.clone(data_object=gone,
                                                  changeset=deletion)
        revision.deleted = True
        revision.save()
    operation = bulk.Operation('indicia_publisher', 'set', None, gone.id)

    with pytest.raises(ErrorWithMessage) as refusal:
        bulk.apply(reserving_indexer, TOKEN, Issue,
                   [issue.id for issue in selection], SOURCE, operation)

    assert refusal.value.message.startswith('Nothing was changed')
    assert 'invalid 3' in refusal.value.message
    assert CHOICE_ERROR in refusal.value.message
    assert not IssueRevision.objects.filter(indicia_publisher=gone).exists()
    assert not Changeset.objects.filter(change_type=CTYPES['bulk']).exists()


@pytest.mark.django_db
def test_a_key_date_change_keeps_the_indicia_publisher_it_holds(
      client, selection, new_indicia_publisher):
    """
    A new key date outside the years of the indicia publisher that the
    issues hold is set, as on their edit page: only the held value is
    kept beyond its years.
    """
    held = new_indicia_publisher(name='Held', year_began=1940,
                                 year_ended=1950)
    for issue in selection:
        _approved(issue, indicia_publisher=held)

    _apply(client, field='key_date', shown='key_date',
           operation='replace_exact', old_value='=1947-01-00',
           new_value='2023-12-00')

    changeset = _change()
    assert _record(changeset)['counts']['changed'] == 3
    assert [revision.indicia_publisher_id
            for revision in changeset.issuerevisions.all()] == [held.id] * 3


@pytest.mark.django_db
def test_the_page_of_the_change_notes_a_key_date_outside_the_years(
      client, selection, new_indicia_publisher):
    """
    The key date change above, made through the page as rendered: the
    New cell of each Key Date row of the page of the change has, first,
    the note of the held indicia publisher, as the compare page of one
    issue does.
    """
    held = new_indicia_publisher(name='Held', year_began=1940,
                                 year_ended=1950)
    for issue in selection:
        _approved(issue, indicia_publisher=held)
    operation = {'field': 'key_date', 'shown': 'key_date',
                 'operation': 'replace_exact', 'old_value': '=1947-01-00',
                 'new_value': '2023-12-00'}
    url = reverse('edit_issues_in_bulk')
    page = PageForms(client.get(url, {'token': TOKEN}).content.decode())
    for chosen in ({'field': 'key_date'}, operation):
        data = page.data(page.form('GET', url), **chosen)
        page = PageForms(client.get(url, data).content.decode())
    form = page.form('POST', url + '?token=' + TOKEN)

    response = client.post(form['action'], page.data(form), follow=True)

    note = ('<br><br>Note: Indicia publisher "Held" used in 2023, after '
            'its last year 1950.')
    news = [new for revision, name, fields in response.context['rows']
            for field, old, new in fields if field == 'Key Date']
    assert len(news) == 3
    for new in news:
        # the note of the held publisher comes first; an issue that
        # holds a brand emblem gets the note of the emblem after it
        assert new.index(note) == new.index('<br><br>Note:')
    assert note in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize('params, errors', [
    ({'operation': 'set', 'new_value': '2023-12-00'},
     {'operation': ['Select a valid choice. set is not one of the '
                    'available choices.']}),
    ({'operation': 'replace_exact', 'old_value': '=',
      'new_value': '2023-12-00'},
     {'__all__': ['The old value of Key Date cannot be empty.']}),
])
def test_a_key_date_is_not_set_for_all_or_filled(client, selection, params,
                                                 errors):
    """
    A POST that sets one key date for all the issues, or that replaces
    the empty one, is refused by the form: no change, no revision and no
    lock.  The first issue has no key date.
    """
    Issue.objects.filter(id=selection[0].id).update(key_date='')
    models = (Changeset, IssueRevision, RevisionLock)
    counts = [model.objects.count() for model in models]

    response = _apply(client, field='key_date', shown='key_date', **params)

    assert response.status_code == 200
    assert response.context['form'].errors == errors
    assert [model.objects.count() for model in models] == counts


@pytest.mark.django_db
def test_apply_holds_the_parents_before_its_turn(client, selection,
                                                 monkeypatch):
    """The wait on the parents comes before the turn of the indexer."""
    calls = []

    def recording(name):
        """Keep the order of the calls of the function called name."""
        original = getattr(bulk, name)

        def record(*args):
            """Keep the name of this call, then make it."""
            calls.append(name)
            return original(*args)
        return record

    monkeypatch.setattr(bulk, '_hold_parents', recording('_hold_parents'))
    monkeypatch.setattr(bulk, '_take_turn', recording('_take_turn'))

    assert _apply(client).status_code == 302
    assert calls == ['_hold_parents', '_take_turn']


@pytest.mark.django_db
def test_deadlock_in_a_parent_row_is_not_a_busy_series(client, selection,
                                                       monkeypatch):
    """Only a wait beyond the limit says that the series are being saved."""
    def deadlock(*args):
        """Fail as a deadlock does."""
        raise OperationalError(bulk.DEADLOCK, 'from the test')
    monkeypatch.setattr(bulk, '_share_rows', deadlock)

    page = unescape(_apply(client).content.decode())

    assert 'Another change was using some of the same records' in page
    assert 'The series of these objects' not in page


@pytest.mark.django_db
def test_deadlock_in_the_turn_is_not_another_request(client, selection,
                                                     monkeypatch):
    """Only a wait beyond the limit says that another request is applying."""
    def deadlock(*args, **kwargs):
        """Fail as a deadlock does."""
        raise OperationalError(bulk.DEADLOCK, 'from the test')
    monkeypatch.setattr(bulk.Indexer.objects, 'select_for_update', deadlock)

    page = unescape(_apply(client).content.decode())

    assert 'Another change was using some of the same records' in page
    assert 'Another request of yours' not in page


@pytest.mark.django_db
def test_deadlock_while_holding_the_parents(client, selection, monkeypatch):
    """A deadlock on the rows of the parents gives a message, not a 500."""
    def deadlock(*args):
        """Fail as a deadlock does."""
        raise OperationalError(bulk.DEADLOCK, 'from the test')
    monkeypatch.setattr(bulk, '_hold_parents', deadlock)

    response = _apply(client)

    assert 'Please apply again.' in unescape(response.content.decode())
    assert not Changeset.objects.filter(change_type=CTYPES['bulk']).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('code', [bulk.LOCK_WAIT_TIMEOUT, bulk.DEADLOCK])
def test_lock_conflict_at_approval_gets_a_message(client, selection, code,
                                                  any_approver, monkeypatch):
    """
    An approval that the database gives up on, for a lock wait or for a
    deadlock, tells the approver to approve it again.
    """
    assert _apply(client).status_code == 302
    changeset = _change()
    changeset.submit()
    changeset.assign(any_approver)
    client.force_login(any_approver)

    def conflict(self, notes=''):
        """Fail as the database does in a lock conflict."""
        raise OperationalError(code, 'from the test')
    monkeypatch.setattr(Changeset, 'approve', conflict)

    response = client.post(reverse('approve', kwargs={'id': changeset.id}),
                           {'comments': ''})

    assert 'Please approve it again.' in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize('params, flag', [(NO_ISBN, 'has_isbn'),
                                          (RATING, 'has_rating')],
                         ids=['not written at commit', 'written at commit'])
def test_flag_off_refuses_approval(client, selection, any_approver, params,
                                   flag):
    """
    A field turned off in the series after the Apply would not be written
    or would stay hidden, so the approval refuses and writes nothing.
    """
    assert _apply(client, **params).status_code == 302
    changeset = _change()
    field = params['field']
    before = list(Issue.objects.filter(id__in=[i.id for i in selection])
                  .order_by('id').values_list(field, flat=True))
    changeset.submit()
    changeset.assign(any_approver)
    Series.objects.filter(id=selection[0].series_id).update(**{flag: False})
    client.force_login(any_approver)

    response = client.post(reverse('approve', kwargs={'id': changeset.id}),
                           {'comments': ''})

    page = unescape(response.content.decode())
    assert 'This bulk change cannot be approved.' in page
    assert 'is turned off in its series.' in page
    assert 'Please send it back to its author.' in page
    changeset.refresh_from_db()
    assert changeset.state == states.REVIEWING
    assert list(Issue.objects.filter(id__in=[i.id for i in selection])
                .order_by('id').values_list(field, flat=True)) == before
    assert not changeset.issuerevisions.filter(committed=True).exists()


@pytest.mark.django_db
def test_flag_off_refuses_submit(client, selection):
    """Submit refuses a field that was turned off after the Apply."""
    assert _apply(client, **NO_ISBN).status_code == 302
    changeset = _change()
    Series.objects.filter(id=selection[0].series_id).update(has_isbn=False)

    with pytest.raises(ErrorWithMessage) as refusal:
        changeset.submit()

    assert 'is turned off in its series.' in refusal.value.message
    changeset.refresh_from_db()
    assert changeset.state == states.OPEN


def _add_record(changeset, model, name, changed):
    """Add the record of an operation that changed the field of objects."""
    counts = dict.fromkeys(bulk.OUTCOMES, 0)
    counts['changed'] = changed
    changeset.comments.create(
      commenter=changeset.indexer, old_state=states.OPEN,
      new_state=states.OPEN, text=bulk.operation_text(
        model, bulk.Operation(name, 'set', None, 'New'), SOURCE, changed,
        counts, {outcome: [] for outcome in bulk.LISTED_OUTCOMES},
        datetime.now(timezone.utc)))


@pytest.mark.django_db
def test_turned_off_counts_only_revisions_that_change_the_field(selection,
                                                                bulk_change):
    """A revision that left the field as it was is no reason to refuse."""
    changeset = bulk_change(selection[:1], IssueRevision, rating='Teen')
    bulk_change(selection[1:2], IssueRevision, changeset=changeset)
    _add_record(changeset, Issue, 'rating', changed=1)
    Series.objects.filter(id=selection[0].series_id).update(has_rating=False)

    messages = bulk.turned_off_messages(changeset)

    assert len(messages) == 1
    assert str(changeset.issuerevisions.get(issue=selection[0])) in messages[0]
    assert 'is turned off in its series.' in messages[0]


@pytest.mark.django_db
def test_flag_of_another_field_is_no_reason_to_refuse(selection, bulk_change):
    """Only the field of the operation counts, not the other flags."""
    changeset = bulk_change(selection[:1], IssueRevision, rating='Teen')
    _add_record(changeset, Issue, 'rating', changed=1)
    Series.objects.filter(id=selection[0].series_id).update(has_isbn=False)

    assert bulk.turned_off_messages(changeset) == []


@pytest.mark.django_db
def test_turned_off_without_flags(sequence_change, approved_stories):
    """Objects whose fields no flag turns off give no message."""
    sequences = sequence_change(approved_stories[:1], genre='Superhero')
    _add_record(sequences, Story, 'genre', changed=1)

    assert bulk.turned_off_messages(sequences) == []


@pytest.mark.django_db
def test_approval_locks_the_series_in_order(selection, bulk_change):
    """The series are locked, in id order, before their flags are read."""
    changeset = bulk_change(selection[:1], IssueRevision, price='0.12 USD')

    with CaptureQueriesContext(connection) as queries:
        assert bulk.approval_refusal(changeset) is None

    locks = [query['sql'] for query in queries if 'FOR UPDATE' in query['sql']]
    assert len(locks) == 1
    assert locks[0].startswith('SELECT `gcd_series`.`id` AS `id` FROM')
    assert locks[0].endswith('ORDER BY 1 ASC FOR UPDATE')


@pytest.mark.django_db
def test_approval_of_a_change_without_revisions(any_indexer):
    """A bulk change without revisions has no reason for a refusal."""
    changeset = Changeset.objects.create(indexer=any_indexer,
                                         state=states.OPEN,
                                         change_type=CTYPES['bulk'])

    assert bulk.approval_refusal(changeset) is None


@pytest.mark.django_db
def test_another_kind_of_change_is_not_checked_at_approval(selection,
                                                           any_indexer,
                                                           any_approver,
                                                           monkeypatch):
    """The refusal of a bulk change plays no part in other approvals."""
    def checked(changeset):
        """Fail if an approval of another kind of change gets here."""
        raise AssertionError('the approval of a normal change was checked')
    monkeypatch.setattr(bulk, 'approval_refusal', checked)
    changeset = Changeset.objects.create(indexer=any_indexer,
                                         state=states.OPEN,
                                         change_type=CTYPES['issue'])
    assert _get_revision_lock(selection[0], changeset) is not None
    revision = IssueRevision.clone(data_object=selection[0],
                                   changeset=changeset)
    revision.notes = 'A normal change.'
    revision.save()
    changeset.submit()
    changeset.assign(any_approver)

    changeset.approve()

    assert changeset.state == states.APPROVED


@pytest.mark.django_db
def test_another_kind_of_change_is_not_checked_at_discuss(any_indexer,
                                                          any_approver,
                                                          monkeypatch):
    """The checks of a bulk change play no part in other changes."""
    def checked(changeset):
        """Fail if another kind of change gets here."""
        raise AssertionError('a normal change was checked')
    monkeypatch.setattr(bulk, 'submit_messages', checked)
    changeset = Changeset.objects.create(indexer=any_indexer,
                                         approver=any_approver,
                                         state=states.OPEN,
                                         change_type=CTYPES['issue'])

    changeset.discuss(any_approver)

    assert changeset.state == states.DISCUSSED


@pytest.mark.django_db
def test_discuss_under_review_is_not_checked(client, selection, any_approver):
    """Only the author's Discuss of an open change makes the checks."""
    assert _apply(client, **NO_ISBN).status_code == 302
    changeset = _change()
    changeset.submit()
    changeset.assign(any_approver)
    Series.objects.filter(id=selection[0].series_id).update(has_isbn=False)

    changeset.discuss(any_approver)

    changeset.refresh_from_db()
    assert changeset.state == states.DISCUSSED


@pytest.mark.django_db
def test_discuss_of_an_open_change_checks_it(client, selection, any_approver):
    """Discuss of an open change makes the checks of a Submit."""
    assert _apply(client, **NO_ISBN).status_code == 302
    changeset = _change()
    changeset.approver = any_approver
    changeset.save()
    Series.objects.filter(id=selection[0].series_id).update(has_isbn=False)

    with pytest.raises(ErrorWithMessage) as refusal:
        changeset.discuss(any_approver)

    assert 'is turned off in its series.' in refusal.value.message
    changeset.refresh_from_db()
    assert changeset.state == states.OPEN


@pytest.mark.django_db
def test_value_that_the_edit_form_stores_otherwise(client, selection,
                                                   monkeypatch):
    """
    An object for which the edit form would store another value than the
    preview showed is left out, never changed to that value.
    """
    check = bulk.revision_form_messages

    def other_value(revision, user, **kwargs):
        """Check revision, then store another price for the second."""
        messages = check(revision, user, **kwargs)
        if revision.issue_id == selection[1].id:
            revision.price = '0.13 USD'
        return messages

    monkeypatch.setattr(bulk, 'revision_form_messages', other_value)
    _apply(client)

    changeset = _change()
    assert _record(changeset)['listed']['invalid'] == [selection[1].id]
    assert 'Its edit form stores "0.13 USD" instead.' in \
        changeset.comments.get().text
    assert not changeset.issuerevisions.filter(issue=selection[1]).exists()


@pytest.mark.django_db
def test_change_that_the_edit_form_carries_further(client, selection):
    """
    An object whose edit form would change another field together with
    the field, which the preview does not show, is left out: an indicia
    printer no longer marked as not printed loses its source.
    """
    Series.objects.filter(id=selection[0].series_id) \
                  .update(has_indicia_printer=True)
    _approved(selection[0], indicia_printer_not_printed=True,
              indicia_printer_sourced_by='A catalogue')
    _approved(selection[1], indicia_printer_not_printed=True)

    _apply(client, field='indicia_printer_not_printed',
           shown='indicia_printer_not_printed', operation='set')

    changeset = _change()
    assert _record(changeset)['listed']['invalid'] == [selection[0].id]
    assert 'Its edit form would also change' in \
        changeset.comments.get().text
    assert [revision.issue for revision
            in changeset.issuerevisions.all()] == [selection[1]]


@pytest.mark.django_db
def test_limit_of_open_changes(client, selection, reserving_indexer):
    """An indexer who holds all the open changes allowed cannot apply."""
    Changeset.objects.create(indexer=reserving_indexer, state=states.OPEN,
                             change_type=CTYPES['issue'])
    reserving_indexer.indexer.max_reservations = 1
    reserving_indexer.indexer.save()

    response = _apply(client)

    assert 'You have reached your limit of open changes.' in \
        response.content.decode()
    assert not Changeset.objects.filter(change_type=CTYPES['bulk']).exists()


@pytest.mark.django_db
def test_submit_checks_only_revisions_changed_since(client, selection,
                                                    monkeypatch):
    """
    The submit checks again only the revisions changed after the
    checkpoint of the operation.
    """
    _apply(client)
    changeset = _change()
    changeset.issuerevisions.update(
      modified=datetime.now(timezone.utc) - timedelta(hours=1))
    changed = changeset.issuerevisions.first()
    changed.save()
    checked = []
    check = bulk.revision_form_messages

    def counting(revision, user):
        """Check revision and note its id."""
        checked.append(revision.id)
        return check(revision, user)

    monkeypatch.setattr(bulk, 'revision_form_messages', counting)
    changeset.submit()

    assert checked == [changed.id]
    assert changeset.state == states.PENDING


@pytest.mark.django_db
@pytest.mark.parametrize('text', [
    'Operation: issue.price set oops',
    'Operation: issue.price set "1"\r\nCheckpoint: soon',
    'a record with a later checkpoint',
])
def test_later_comments_are_no_record(client, selection, any_approver,
                                      text):
    """
    Only the first comment records the operation: a later one that looks
    like a record, broken or well formed, neither breaks the submit nor
    skips its checks.
    """
    _apply(client)
    changeset = _change()
    revision = changeset.issuerevisions.first()
    revision.page_count = None
    revision.page_count_uncertain = True
    revision.save()
    if text.startswith('a record'):
        text = bulk.operation_text(
          Issue, bulk.Operation('price', 'set', None, '0.12 USD'), SOURCE, 3,
          dict.fromkeys(bulk.OUTCOMES, 0),
          {outcome: [] for outcome in bulk.LISTED_OUTCOMES},
          datetime(2100, 1, 1, tzinfo=timezone.utc))
    changeset.comments.create(commenter=any_approver, text=text,
                              old_state=states.OPEN, new_state=states.OPEN)

    response = client.post(reverse('process', kwargs={'id': changeset.id}),
                           {'submit': 'Submit', 'comments': ''})

    assert PAGE_COUNT_ERROR in response.content.decode()
    changeset.refresh_from_db()
    assert changeset.state == states.OPEN


def test_the_form_data_helpers_stay_importable_from_the_views():
    """
    Tests elsewhere build POST data with these helpers from apps.oi.views,
    where they were before apps.oi.validation.
    """
    from apps.oi import validation, views
    assert views._add_form_data is validation._add_form_data
    assert views._add_formset_data is validation._add_formset_data
