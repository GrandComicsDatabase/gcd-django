"""Work on an open bulk change: send back, further operations, removal."""
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from html import unescape

import pytest

from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.db import OperationalError
from django.db.models import F
from django.test import Client
from django.urls import reverse
from django.utils import timezone as django_timezone

from apps.gcd.models import Series
from apps.oi import bulk, coordinators, states
from apps.oi.models import (
    Changeset, ChangesetComment, CoverRevision, IssueRevision,
    ReprintRevision, RevisionLock, CTYPES, _get_revision_lock)
from apps.oi.templatetags.editing import is_overdue
from apps.oi.tests.bulk.invariants import check_invariants
from apps.oi.tests.bulk.page_forms import PageForms

TOKEN = 'open-token'
PRICE = {'field': 'price', 'shown': 'price', 'operation': 'replace_exact',
         'old_value': '=0.10 USD', 'new_value': '0.12 USD'}
BACK = {'field': 'price', 'shown': 'price', 'operation': 'replace_exact',
        'old_value': '=0.12 USD', 'new_value': '0.10 USD'}
PAGES = {'field': 'page_count', 'shown': 'page_count', 'operation': 'set',
         'new_value': '36'}
UNCERTAIN = {'field': 'page_count_uncertain', 'shown': 'page_count_uncertain',
             'operation': 'set', 'new_value': 'on'}
VOLUME = {'field': 'volume', 'shown': 'volume', 'operation': 'set',
          'new_value': '5'}
RATING = {'field': 'rating', 'shown': 'rating', 'operation': 'replace_exact',
          'old_value': '=', 'new_value': 'Teen'}
PAGE_COUNT_ERROR = 'You cannot check page count uncertain without a page ' \
                   'count.'
FREQUENCY = {'field': 'indicia_frequency', 'shown': 'indicia_frequency',
             'operation': 'replace_exact', 'old_value': '=',
             'new_value': 'monthly'}
FREQUENCY_ERROR = 'You cannot specify an indicia frequency and check ' \
                  '"no indicia frequency" at the same time.'
ADD_LINK = 'Add an operation'
LEAVING = 'Back to their present values, so they leave this change:'
REMOVE_OR_DISCARD = 'Please remove these issues from this change, or ' \
                    'discard it.'
ONLY_DISCARD = 'Please discard this change: it holds no other issue.'


@pytest.fixture(autouse=True)
def invariants(db):
    """Start without applied tokens; check the invariants at the end."""
    cache.clear()
    yield
    check_invariants()


@pytest.fixture
def change(client, settings, reserving_indexer, approved_issues):
    """
    The open bulk change of the price of the three approved issues, made
    as the page makes it; its author is logged in.
    """
    settings.BULK_CHANGE_ENABLED = True
    client.force_login(reserving_indexer)
    session = client.session
    session[bulk.SELECTION_KEY] = {
      'token': TOKEN, 'model': 'issue', 'source': '/list/',
      'ids': sorted(issue.id for issue in approved_issues)}
    session.save()
    response = client.post(reverse('edit_issues_in_bulk') + '?token=' + TOKEN,
                           PRICE)
    assert response.status_code == 302
    return Changeset.objects.get(change_type=CTYPES['bulk'])


def _page(changeset):
    """The address of the page of a further operation on changeset."""
    return reverse('edit_issues_in_bulk') + '?changeset=%d' % changeset.id


def _compare(changeset):
    """The address of the page of changeset."""
    return reverse('compare', kwargs={'id': changeset.id})


def _process(changeset):
    """The address that the buttons of the page of changeset post to."""
    return reverse('process', kwargs={'id': changeset.id})


def _preview(client, changeset, params):
    """Get the page of a further operation on changeset, with params."""
    response = client.get(reverse('edit_issues_in_bulk'),
                          dict(params, changeset=changeset.id))
    assert response.status_code == 200
    return ' '.join(_text(response).split())


def _operate(client, changeset, params):
    """Post a further operation on changeset."""
    return client.post(_page(changeset), params)


def _remove(client, changeset, *ids):
    """Post the removal of the objects of the revisions with these ids."""
    return client.post(_process(changeset),
                       {'bulk_remove': 'Remove selected',
                        'selected': [str(value) for value in ids]})


def _text(response):
    """The text of response, with its entities turned into characters."""
    return unescape(response.content.decode())


def _revisions(changeset):
    """The revisions of changeset, in the order of their issues."""
    return list(changeset.issuerevisions.order_by('issue_id'))


def _prices(changeset):
    """The prices of the revisions of changeset."""
    return [revision.price for revision in _revisions(changeset)]


def _page_counts(changeset):
    """The page count of each revision of changeset, by revision id."""
    return {revision.id: revision.page_count
            for revision in _revisions(changeset)}


def _sent_back(changeset, approver):
    """Submit changeset, let approver review it and send it back."""
    changeset.submit()
    changeset.assign(approver)
    changeset.disapprove(notes='Also the page count, please.')


def _turn_off_rating(changeset):
    """Turn off the rating in the series of the objects of changeset."""
    Series.objects.filter(id=_revisions(changeset)[0].issue.series_id).update(
      has_rating=False)


@pytest.mark.django_db
def test_second_operation_after_send_back(client, change, any_approver,
                                          approved_issues):
    """
    A change sent back takes a second operation, keeps the first, goes
    back to its approver at the new submission and approves both.
    """
    _sent_back(change, any_approver)

    assert _operate(client, change, PAGES).status_code == 302

    assert _prices(change) == ['0.12 USD'] * 3
    assert {revision.page_count for revision in _revisions(change)} == \
        {Decimal('36')}
    records = bulk.operation_records(change)
    assert [record['name'] for record in records] == ['price', 'page_count']
    assert records[1]['counts']['changed'] == 3
    assert records[1]['source'].endswith(_compare(change))

    client.post(_process(change), {'submit': 'Submit', 'comments': ''})
    change.refresh_from_db()
    assert change.state == states.REVIEWING
    assert change.approver == any_approver

    change.approve()
    for issue in approved_issues:
        issue.refresh_from_db()
        assert issue.price == '0.12 USD'
        assert issue.page_count == 36
    assert not change.revision_locks.exists()


@pytest.mark.django_db
def test_retract_opens_the_change_again(client, change):
    """The author can retract a change that nobody reviews and go on."""
    change.submit()
    page = client.get(_compare(change)).content.decode()
    assert 'name="retract"' in page
    assert ADD_LINK not in page

    response = client.post(_process(change),
                           {'retract': 'Retract', 'comments': ''})

    assert response.status_code == 302
    change.refresh_from_db()
    assert change.state == states.OPEN
    assert ADD_LINK in client.get(_compare(change)).content.decode()


@pytest.mark.django_db
def test_approver_can_send_it_back(client, change, any_approver):
    """The approver gets Send back, and nothing for the author."""
    change.submit()
    change.assign(any_approver)
    client.force_login(any_approver)

    page = client.get(_compare(change)).content.decode()

    assert 'name="disapprove"' in page
    assert ADD_LINK not in page
    assert 'name="selected"' not in page

    response = client.post(_process(change),
                           {'disapprove': 'Send back', 'comments': 'Why.'})

    assert response.status_code == 302
    change.refresh_from_db()
    assert change.state == states.OPEN


@pytest.mark.django_db
def test_preview_lists_the_values_of_the_change(client, change):
    """
    The page lists the values of the revisions, not of the objects, and
    its preview writes nothing.
    """
    modified = [revision.modified for revision in _revisions(change)]
    tables = (Changeset, ChangesetComment, RevisionLock, IssueRevision)
    before = [table.objects.count() for table in tables]

    listing = _preview(client, change, {'field': 'price'})
    preview = _preview(client, change, PAGES)

    assert '"0.12 USD" (3)' in listing
    assert '"0.10 USD"' not in listing
    assert 'Selection: the 3 issues of' in listing
    assert 'Changes to Page Count: 3 of 3 issues.' in preview
    assert 'Changes these 3 issues in this change' in preview
    assert [table.objects.count() for table in tables] == before
    assert [revision.modified for revision in _revisions(change)] == modified


@pytest.mark.django_db
def test_forms_of_the_page_as_rendered(client, change):
    """
    The link of the change leads to the page, whose forms, submitted as
    rendered, make the operation that the preview shows.  No page repeats
    an id, and the preview says what the second operation would do.
    """
    compare_page = PageForms(client.get(_compare(change)).content.decode())
    assert compare_page.repeated_ids() == []
    url = reverse('edit_issues_in_bulk')
    link = compare_page.link('?changeset=%d' % change.id)
    page = PageForms(client.get(link).content.decode())
    for chosen in ({'field': PAGES['field']}, PAGES):
        assert page.repeated_ids() == []
        data = page.data(page.form('GET', url), **chosen)
        page = PageForms(client.get(url, data).content.decode())
    assert page.repeated_ids() == []
    form = page.form('POST', _page(change))

    response = client.post(form['action'], page.data(form))

    assert response['Location'] == _compare(change)
    assert {revision.page_count for revision in _revisions(change)} == \
        {Decimal('36')}


@pytest.mark.django_db
def test_operation_leaves_out_what_the_form_refuses(client, change,
                                                    approved_issues):
    """
    Each revision passes the rules of its edit form: the first issue has
    a page count, so only it can be uncertain; the others keep their
    values and the record lists them.
    """
    assert _operate(client, change, UNCERTAIN).status_code == 302

    revisions = _revisions(change)
    assert [revision.page_count_uncertain for revision in revisions] == \
        [True, False, False]
    record = bulk.operation_records(change)[1]
    assert record['counts']['changed'] == 1
    assert record['counts']['invalid'] == 2
    assert record['listed']['invalid'] == [issue.id for issue
                                           in approved_issues[1:]]


@pytest.mark.django_db
def test_operation_takes_objects_back(client, change, approved_issues):
    """
    A revision that goes back to the values of its object leaves the
    change and frees its object; both records count it, and the preview
    says so first.
    """
    first, second, third = _revisions(change)
    IssueRevision.objects.filter(id=third.id).update(price='0.20 USD')
    preview = _preview(client, change, BACK)
    assert LEAVING + ' 2' in preview
    assert 'Changes these 2 issues in this change' in preview
    assert bulk.LEFT_EMPTY not in preview

    assert _operate(client, change, BACK).status_code == 302

    assert [revision.id for revision in _revisions(change)] == [third.id]
    locked = change.revision_locks.values_list('object_id', flat=True)
    assert list(locked) == [approved_issues[2].id]
    records = bulk.operation_records(change)
    assert records[0]['counts']['changed'] == 1
    assert records[0]['counts']['removed'] == 2
    assert records[0]['checked'] == 3
    assert records[1]['counts']['changed'] == 0
    assert records[1]['counts']['unchanged'] == 1
    assert records[1]['counts']['removed'] == 2


@pytest.mark.django_db
def test_operation_cannot_leave_the_change_empty(client, change):
    """
    Taking every object back is refused, and nothing is written; the
    preview says so and offers no Apply.
    """
    preview = _preview(client, change, BACK)
    response = _operate(client, change, BACK)

    assert bulk.LEFT_EMPTY in preview
    assert 'Changes these' not in preview
    assert bulk.LEFT_EMPTY in _text(response)
    assert _prices(change) == ['0.12 USD'] * 3
    assert change.revision_locks.count() == 3
    assert change.comments.count() == 1


@pytest.mark.django_db
def test_revision_with_another_change_stays(client, change):
    """
    A revision that goes back only in one field still changes another,
    so it stays, and the preview does not say that it leaves.
    """
    _operate(client, change, PAGES)
    preview = _preview(client, change, BACK)
    assert 'Changes to Price: 3 of 3 issues.' in preview
    assert LEAVING not in preview

    assert _operate(client, change, BACK).status_code == 302

    assert _prices(change) == ['0.10 USD'] * 3
    assert {revision.page_count for revision in _revisions(change)} == \
        {Decimal('36')}
    assert bulk.operation_records(change)[1]['counts']['changed'] == 3


@pytest.mark.django_db
def test_other_new_value_is_no_way_back(client, change):
    """A value other than that of the object does not make it leave."""
    preview = _preview(client, change, dict(BACK, new_value='0.15 USD'))

    assert 'Changes to Price: 3 of 3 issues.' in preview
    assert LEAVING not in preview


@pytest.mark.django_db
def test_object_with_two_changed_fields_has_one_box(client, change):
    """An object has one check box, whatever the fields it changes."""
    _operate(client, change, PAGES)

    page = client.get(_compare(change)).content.decode()

    assert page.count('name="selected"') == 3
    assert page.count('rowspan="2"') == 6


@pytest.mark.django_db
def test_change_without_objects_takes_no_work(client, settings, bulk_change,
                                              reserving_indexer):
    """A bulk change that holds no objects has nothing to work on."""
    settings.BULK_CHANGE_ENABLED = True
    changeset = bulk_change([], IssueRevision)
    client.force_login(reserving_indexer)

    assert 'This bulk change holds no objects.' in \
        _text(client.get(_page(changeset)))


@pytest.mark.django_db
def test_refused_operation_says_why(client, change, approved_issues):
    """
    An operation that the edit form refuses for every revision gives the
    reason, once, with the first object it applies to, and adds no record.
    """
    change.issuerevisions.update(indicia_frequency='',
                                 no_indicia_frequency=True)

    page = _text(_operate(client, change, FREQUENCY))

    assert 'invalid 3' in page
    assert '%s: %s' % (approved_issues[0], FREQUENCY_ERROR) in page
    assert page.count(FREQUENCY_ERROR) == 1
    assert change.comments.count() == 1


@pytest.mark.django_db
def test_operation_that_changes_nothing(client, change):
    """An operation that changes no revision adds no record."""
    response = _operate(client, change, {
      'field': 'price', 'shown': 'price', 'operation': 'set',
      'new_value': '0.12 USD'})

    assert 'Nothing was changed, so no operation was added' in _text(response)
    assert 'unchanged 3' in _text(response)
    assert change.comments.count() == 1


@pytest.mark.django_db
def test_a_further_operation_does_not_set_a_key_date(client, change):
    """
    A further operation that sets one key date for all the revisions of
    an open change is refused by the form, and writes nothing.
    """
    tables = (Changeset, ChangesetComment, RevisionLock, IssueRevision)
    before = [table.objects.count() for table in tables]
    key_dates = [revision.key_date for revision in _revisions(change)]

    response = _operate(client, change, {
      'field': 'key_date', 'shown': 'key_date', 'operation': 'set',
      'new_value': '2023-12-00'})

    assert response.status_code == 200
    assert response.context['form'].errors == {'operation': [
      'Select a valid choice. set is not one of the available choices.']}
    assert [table.objects.count() for table in tables] == before
    assert [revision.key_date for revision in _revisions(change)] == \
        key_dates


@pytest.mark.django_db
def test_field_turned_off_in_the_series(client, change, approved_issues):
    """A flag of the series turns the field of a revision off."""
    Series.objects.filter(id=approved_issues[0].series_id) \
                  .update(has_volume=False)

    page = _preview(client, change, VOLUME)
    response = _operate(client, change, VOLUME)

    assert 'Field turned off in their series, so left out: 3' in page
    assert 'turned off 3' in _text(response)
    assert change.comments.count() == 1


@pytest.mark.django_db
def test_only_the_author_may_work_on_it(client, change, any_approver):
    """Another user gets a refusal on every way in, and nothing changes."""
    revision = _revisions(change)[0]
    client.force_login(any_approver)
    message = 'Only the author of a bulk change may work on it.'

    assert message in _text(client.get(_page(change)))
    assert message in _text(_operate(client, change, PAGES))
    assert message in _text(_remove(client, change, revision.id))

    assert change.issuerevisions.count() == 3
    assert change.comments.count() == 1


@pytest.mark.django_db
def test_only_an_open_change_takes_work(client, change):
    """A submitted change takes no operation and loses no object."""
    revision = _revisions(change)[0]
    change.submit()
    message = 'Only an open bulk change can be changed.'

    assert message in _text(client.get(_page(change)))
    assert message in _text(_operate(client, change, PAGES))
    assert message in _text(_remove(client, change, revision.id))

    assert change.issuerevisions.count() == 3


@pytest.mark.django_db
def test_change_refusal_for_another_kind_of_change(settings,
                                                   reserving_indexer):
    """A change that is not a bulk change takes none of this work."""
    settings.BULK_CHANGE_ENABLED = True
    changeset = Changeset(indexer=reserving_indexer, state=states.OPEN,
                          change_type=CTYPES['issue'])

    assert bulk.change_refusal(reserving_indexer, changeset) == \
        'Only the author of a bulk change may work on it.'


@pytest.mark.django_db
def test_turned_off_site(client, change, settings):
    """With bulk changes off the page and the removal are not available."""
    settings.BULK_CHANGE_ENABLED = False
    revision = _revisions(change)[0]

    assert client.get(_page(change)).status_code == 302
    assert 'Bulk changes are turned off.' in \
        _text(_remove(client, change, revision.id))
    assert ADD_LINK not in client.get(_compare(change)).content.decode()
    assert change.issuerevisions.count() == 3


@pytest.mark.django_db
@pytest.mark.parametrize('value', ['abc', '999999', '9' * 5000])
def test_unknown_change(client, change, value):
    """An address without a known change is a page not found."""
    url = reverse('edit_issues_in_bulk') + '?changeset=' + value

    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_remove_selected_frees_the_objects(client, change, approved_issues):
    """
    Removal deletes the revisions and frees the objects, which a new
    change can take at once from their approved revisions; the record
    counts them and the page lists the others.
    """
    first, second, third = _revisions(change)

    response = _remove(client, change, first.id, second.id)

    assert response['Location'] == _compare(change)
    assert [revision.id for revision in _revisions(change)] == [third.id]
    assert list(change.revision_locks.values_list('object_id', flat=True)) \
        == [approved_issues[2].id]
    record = bulk.operation_record(change)
    assert record['counts']['changed'] == 1
    assert record['counts']['removed'] == 2
    assert record['checked'] == 3

    other = Changeset.objects.create(indexer=change.indexer,
                                     state=states.OPEN,
                                     change_type=CTYPES['issue'])
    assert _get_revision_lock(approved_issues[0], other) is not None
    clone = IssueRevision.clone(approved_issues[0], other)
    assert clone.previous_revision == first.previous_revision
    assert clone.price == '0.10 USD'
    other.discard(change.indexer)


@pytest.mark.django_db
def test_remove_form_as_rendered(client, change):
    """
    The check boxes and the button are in one form of the page, which
    removes the chosen object.
    """
    first = _revisions(change)[0]
    html = client.get(_compare(change)).content.decode()
    start = html.index('<form action="%s"' % _process(change))
    remove_form = html[start:html.index('</form>', start)]
    assert remove_form.count('name="selected"') == 3
    assert 'name="bulk_remove"' in remove_form
    page = PageForms(html)
    forms = [form for form in page.forms
             if (form['method'], form['action']) ==
             ('POST', _process(change))]

    client.post(forms[0]['action'], page.data(
      forms[0], selected=str(first.id), bulk_remove='Remove selected'))

    assert first.id not in [revision.id for revision in _revisions(change)]
    assert change.issuerevisions.count() == 2


@pytest.mark.django_db
def test_remove_cannot_empty_the_change(client, change):
    """Removing every object is refused, and nothing is removed."""
    ids = [revision.id for revision in _revisions(change)]

    assert bulk.LEFT_EMPTY in _text(_remove(client, change, *ids))
    assert change.issuerevisions.count() == 3
    assert change.revision_locks.count() == 3


@pytest.mark.django_db
def test_rows_of_revisions_read_before_a_removal(client, change):
    """
    The page reads the revisions of the change, then their values: an
    object removed in between has no values, so no changes and no row.
    """
    revisions = _revisions(change)
    assert _remove(client, change, revisions[0].id).status_code == 302

    rows = bulk.compare_rows(revisions)

    assert [row[0] for row in rows] == revisions[1:]
    assert bulk.exact_diff(IssueRevision, [revisions[0].id]) == \
        {revisions[0].id: {}}


@pytest.mark.django_db
def test_links_read_before_the_row_of_a_removed_revision(
      client, change, approved_issues, monkeypatch):
    """
    An object removed after the page has read the row of its revision
    shows no false change of its links, such as its brand emblems, as
    the links of the revision were read before its row.
    """
    revision = change.issuerevisions.get(issue=approved_issues[0])
    assert revision.brand_emblem.exists()
    previous_ids = bulk._previous_ids
    removed = []

    def remove_between_reads(*args):
        """Remove the object once, after the row of its revision."""
        if not removed:
            removed.append(revision.id)
            assert _remove(client, change, revision.id).status_code == 302
        return previous_ids(*args)

    monkeypatch.setattr(bulk, '_previous_ids', remove_between_reads)
    diff = bulk.exact_diff(IssueRevision, [revision.id])

    assert removed == [revision.id]
    assert diff == {revision.id: {'price': ('0.10 USD', '0.12 USD')}}


@pytest.mark.django_db
def test_remove_needs_objects_of_the_change(client, change, bulk_change,
                                            approved_variant):
    """
    Nothing selected, a text, too long a number or the id of a revision
    of another change: a message, and every revision stays.
    """
    other = bulk_change([approved_variant], IssueRevision, price='0.25 USD')
    foreign = other.issuerevisions.get()
    message = 'Please select the objects to remove.'

    assert message in _text(_remove(client, change))
    assert message in _text(_remove(client, change, 'abc', '9' * 5000))
    assert message in _text(_remove(client, change, foreign.id))
    assert change.issuerevisions.count() == 3
    assert other.issuerevisions.get() == foreign


@pytest.mark.django_db
def test_page_for_the_author_of_an_open_change(client, change):
    """The author can add an operation and take any object out."""
    page = client.get(_compare(change)).content.decode()

    assert ADD_LINK in page
    assert 'name="bulk_remove"' in page
    assert page.count('name="selected"') == 3


@pytest.mark.django_db
def test_change_of_one_object_has_nothing_to_remove(client, change):
    """A change keeps its last object: only a further operation is left."""
    revisions = _revisions(change)
    _remove(client, change, revisions[0].id, revisions[1].id)

    page = client.get(_compare(change)).content.decode()

    assert ADD_LINK in page
    assert 'name="selected"' not in page
    assert 'name="bulk_remove"' not in page


@pytest.mark.django_db
def test_approved_change_is_closed_to_work(client, change, any_approver):
    """An approved change has neither the link nor the check boxes."""
    change.submit()
    change.assign(any_approver)
    change.approve()

    page = client.get(_compare(change)).content.decode()

    assert ADD_LINK not in page
    assert 'name="selected"' not in page


@pytest.mark.django_db
def test_a_comment_cannot_pose_as_a_record(client, change):
    """A comment that repeats a record never counts as one."""
    text = change.comments.get().text

    client.post(_process(change), {'add_comment': 'Add', 'comments': text})

    assert change.comments.count() == 2
    assert len(bulk.operation_records(change)) == 1


@pytest.mark.django_db
@pytest.mark.parametrize('minutes, refused', [(30, False), (70, True)])
def test_submit_checks_since_the_latest_operation(client, change, minutes,
                                                  refused):
    """
    The submission checks again only the revisions changed after the
    checkpoint of the latest operation.
    """
    _operate(client, change, PAGES)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for hours, comment in enumerate(bulk._record_comments(change)):
        comment.text = re.sub(
          r'Checkpoint: .*',
          (start + timedelta(hours=hours))
          .strftime('Checkpoint: ' + bulk.CHECKPOINT_FORMAT), comment.text)
        comment.save(update_fields=['text'])
    IssueRevision.objects.filter(id=_revisions(change)[0].id).update(
      page_count=None, page_count_uncertain=True,
      modified=start + timedelta(minutes=minutes))

    response = client.post(_process(change),
                           {'submit': 'Submit', 'comments': ''})

    change.refresh_from_db()
    if refused:
        assert PAGE_COUNT_ERROR in _text(response)
        assert change.state == states.OPEN
    else:
        assert change.state == states.PENDING


@pytest.mark.django_db
def test_operation_starts_with_the_check_of_the_submission(client, change):
    """
    A revision changed since the last checkpoint is checked before a new
    operation, whose checkpoint would hide it from the submission.
    """
    IssueRevision.objects.filter(id=_revisions(change)[0].id).update(
      page_count=None, page_count_uncertain=True,
      modified=django_timezone.now() + timedelta(minutes=1))

    response = _operate(client, change, PAGES)

    assert 'cannot take another operation' in _text(response)
    assert PAGE_COUNT_ERROR in _text(response)
    assert change.comments.count() == 1


def _made_long_ago(changeset):
    """Date changeset, and its last work, forty days back."""
    Changeset.objects.filter(id=changeset.id).update(
      created=django_timezone.now() - timedelta(days=40),
      modified=django_timezone.now() - timedelta(days=40))
    changeset.refresh_from_db()


def _sweep(client, approver):
    """Run the sweep of old reservations, as a coordinator does."""
    approver.user_permissions.add(
      Permission.objects.get(codename='change_ongoingreservation'))
    client.force_login(approver)
    assert client.get(reverse('clear_issues')).status_code == 200


@pytest.mark.django_db
def test_sweep_discards_a_change_left_alone(client, change, any_approver):
    """An open bulk change with no work for three weeks is discarded."""
    _made_long_ago(change)

    _sweep(client, any_approver)

    change.refresh_from_db()
    assert change.state == states.DISCARDED


@pytest.mark.django_db
@pytest.mark.parametrize('work', ['send back', 'retract', 'operation',
                                  'removal'])
def test_sweep_counts_from_the_last_work(client, change, any_approver, work):
    """
    An old bulk change that was sent back, retracted or worked on is not
    swept away, and the editing queue gives it a new date.
    """
    revision = _revisions(change)[0]
    if work == 'send back':
        change.submit()
        change.assign(any_approver)
        _made_long_ago(change)
        change.disapprove(notes='Why.')
    elif work == 'retract':
        change.submit()
        _made_long_ago(change)
        change.retract()
    else:
        _made_long_ago(change)
        if work == 'operation':
            assert _operate(client, change, PAGES).status_code == 302
        else:
            assert _remove(client, change, revision.id).status_code == 302

    _sweep(client, any_approver)

    change.refresh_from_db()
    assert change.state == states.OPEN
    assert is_overdue(change) == ''
    assert change.expires > django_timezone.now() + timedelta(days=20)


@pytest.mark.django_db
def test_unassigning_is_no_work(client, change, any_approver):
    """
    The approver of a change sent back can unassign it, which is no work
    on it: its last work stays as it was, and the sweep discards it.
    """
    _sent_back(change, any_approver)
    _made_long_ago(change)
    client.force_login(any_approver)
    assert 'name="release"' in client.get(_compare(change)).content.decode()

    assert client.post(_process(change),
                       {'release': 'Unassign',
                        'comments': ''}).status_code == 302

    last_work = change.modified
    change.refresh_from_db()
    assert change.approver is None
    assert change.modified == last_work
    _sweep(client, any_approver)
    change.refresh_from_db()
    assert change.state == states.DISCARDED


@pytest.mark.django_db
@pytest.mark.parametrize('days', [0, 20])
def test_sweep_leaves_a_change_worked_on_after_selection(
      client, change, any_approver, reserving_indexer, bulk_change,
      approved_variant, monkeypatch, days):
    """
    The sweep makes its list first and discards later: a bulk change that
    its author works on in between stays open, if that work is less than
    three weeks old (days back).  Another one on the same list, whose last
    work is older than that, is still discarded, and so is a change of
    another kind, which counts from its creation.
    """
    alone = bulk_change([approved_variant], IssueRevision)
    _made_long_ago(change)
    _made_long_ago(alone)
    Changeset.objects.filter(id=alone.id).update(
      modified=django_timezone.now() - timedelta(days=22))
    upload = Changeset.objects.create(
      indexer=reserving_indexer, state=states.OPEN,
      change_type=CTYPES['cover'])
    CoverRevision.objects.create(changeset=upload, issue=approved_variant)
    Changeset.objects.filter(id=upload.id).update(
      created=django_timezone.now() - timedelta(days=40))
    real_sweep = coordinators.clear_reservations

    def worked_on_after_selection(request, changes):
        """Let the author work on the change, then go on with the sweep."""
        assert {item.id for item in changes} == \
            {change.id, alone.id, upload.id}
        author = Client()
        author.force_login(reserving_indexer)
        assert _operate(author, change, PAGES).status_code == 302
        Changeset.objects.filter(id=change.id).update(
          modified=F('modified') - timedelta(days=days))
        return real_sweep(request, sorted(
          changes, key=lambda item: item.id != change.id))

    monkeypatch.setattr(coordinators, 'clear_reservations',
                        worked_on_after_selection)

    _sweep(client, any_approver)

    change.refresh_from_db()
    assert change.state == states.OPEN
    alone.refresh_from_db()
    assert alone.state == states.DISCARDED
    upload.refresh_from_db()
    assert upload.state == states.DISCARDED


def test_other_changes_count_from_their_creation(settings):
    """In the editing queue only a bulk change counts from its last work."""
    created = django_timezone.now() - timedelta(days=40)
    changeset = Changeset(change_type=CTYPES['cover'], created=created,
                          modified=django_timezone.now())

    assert is_overdue(changeset) != ''
    assert changeset.expires == \
        created + timedelta(weeks=settings.RESERVE_ISSUE_WEEKS)


@pytest.mark.django_db
def test_points_follow_the_work(client, change, any_approver):
    """
    Points follow each operation and removal: a change sent back can go
    through Discuss to its approval without another submission.
    """
    _sent_back(change, any_approver)
    change.refresh_from_db()
    price_points = change.imps

    _operate(client, change, PAGES)
    change.refresh_from_db()
    assert change.imps > price_points

    client.post(_process(change), {'discuss': 'Discuss', 'comments': 'Why.'})
    change.refresh_from_db()
    assert change.state == states.DISCUSSED
    assert change.imps == bulk.changeset_imps(change)


@pytest.mark.django_db
def test_discuss_after_send_back_runs_submit_checks(client, change,
                                                    any_approver):
    """
    A change sent back reaches its approval through Discuss, with no other
    Submit, so Discuss makes the checks of a Submit: a field turned off
    stops it, whichever operation changed that field, neither the first
    nor the latest here, with one message for each object that it changed.
    """
    _sent_back(change, any_approver)
    for params in (RATING, dict(RATING, old_value='=Teen', new_value='Mature'),
                   PAGES):
        assert _operate(client, change, params).status_code == 302
    # The first issue is marked as having no rating, so it got none.
    assert [revision.rating for revision in _revisions(change)] == \
        ['', 'Mature', 'Mature']
    _turn_off_rating(change)

    response = client.post(_process(change),
                           {'discuss': 'Discuss', 'comments': 'Why.'})

    page = ' '.join(_text(response).split())
    assert 'This bulk change cannot be discussed.' in page
    assert page.count('Rating is turned off in its series.') == 2
    change.refresh_from_db()
    assert change.state == states.OPEN


@pytest.mark.django_db
def test_flag_off_refuses_a_further_operation(client, change):
    """
    A field that an operation changed and that is turned off later stops
    any further operation, which writes nothing: the page refuses it, and
    so does the code, which checks again under the lock of the change.
    """
    assert _operate(client, change, RATING).status_code == 302
    _turn_off_rating(change)
    comments = change.comments.count()

    page = ' '.join(_text(_operate(client, change, PAGES)).split())
    with pytest.raises(bulk.ErrorWithMessage) as refusal:
        bulk.add_operation(change.indexer, change,
                           bulk.Operation('page_count', 'set', None,
                                          Decimal('36')))

    assert 'cannot take another operation' in page
    assert 'Rating is turned off in its series.' in page
    assert REMOVE_OR_DISCARD in page
    assert REMOVE_OR_DISCARD in refusal.value.message
    assert change.comments.count() == comments


@pytest.mark.django_db
def test_flag_off_is_told_before_a_further_operation(client, change):
    """
    A field turned off while the change is open is told before a further
    operation: the page of the change says it, with the way out, in place
    of the link, and the page of the operation refuses it, GET included,
    with no preview and no Apply.  Nothing is written.  Once the objects
    that hold the field are out, the link is back.
    """
    assert _operate(client, change, RATING).status_code == 302
    _turn_off_rating(change)
    comments = change.comments.count()

    compare = ' '.join(_text(client.get(_compare(change))).split())

    assert ADD_LINK not in compare
    assert 'name="bulk_remove"' in compare
    page = _preview(client, change, PAGES)
    for text in (compare, page):
        assert 'This bulk change cannot take another operation.' in text
        # The first issue has no rating, so the operation left it out.
        assert text.count('Rating is turned off in its series.') == 2
        assert REMOVE_OR_DISCARD in text
    assert 'Changes to ' not in page
    assert 'not yet submitted' not in page
    assert change.comments.count() == comments
    rated = [revision.id for revision in _revisions(change) if revision.rating]
    assert len(rated) == 2
    assert _remove(client, change, *rated).status_code == 302
    assert ADD_LINK in _text(client.get(_compare(change)))


@pytest.mark.django_db
def test_flag_off_on_every_object_leaves_only_discard(client, change):
    """
    When every object of the change holds the field turned off, taking
    them out cannot help: the page of the change and the page of an
    operation give Discard as the only way out.  So does a change of one
    object, which has no Remove.
    """
    assert _operate(client, change, RATING).status_code == 302
    unrated = [revision.id for revision in _revisions(change)
               if not revision.rating]
    assert len(unrated) == 1
    assert _remove(client, change, *unrated).status_code == 302
    _turn_off_rating(change)

    compare = ' '.join(_text(client.get(_compare(change))).split())
    page = _preview(client, change, PAGES)

    for text in (compare, page):
        assert 'This bulk change cannot take another operation.' in text
        assert text.count('Rating is turned off in its series.') == 2
        assert ONLY_DISCARD in text
        assert 'Please remove these' not in text
    assert _remove(client, change,
                   _revisions(change)[0].id).status_code == 302
    compare = ' '.join(_text(client.get(_compare(change))).split())
    assert 'name="bulk_remove"' not in compare
    assert compare.count('Rating is turned off in its series.') == 1
    assert ONLY_DISCARD in compare
    assert 'Please remove these' not in compare


@pytest.mark.django_db
def test_way_out_counts_objects_not_messages(client, change, monkeypatch):
    """
    Discard is the only way out when the refusal names every object of
    the change, each counted once: two messages on one object of two
    leave Remove as the way out.
    """
    assert _remove(client, change, _revisions(change)[0].id).status_code == \
        302
    kept = _revisions(change)[0]
    monkeypatch.setattr(bulk, '_turned_off', lambda changeset: [
      (kept, 'First message.'), (kept, 'Second message.')])

    refusal = bulk.operation_refusal(change)

    assert 'First message. Second message.' in refusal
    assert refusal.endswith(REMOVE_OR_DISCARD)


@pytest.mark.django_db
def test_way_out_counts_no_anchor(sequence_change, approved_stories,
                                  monkeypatch):
    """
    The issues that anchor the sequences of a change are not objects of
    it: a refusal that names one sequence of two and its issue leaves
    Remove as the way out, not Discard alone.
    """
    change = sequence_change(approved_stories, title='New')
    # A sequence and its anchor with different ids, so that counting the
    # anchor would make two objects named.
    named, anchor = next(
      (story, issue) for story in change.storyrevisions.all()
      for issue in change.issuerevisions.filter(issue=story.issue)
      if story.id != issue.id)
    monkeypatch.setattr(bulk, '_submit_problems', lambda changeset, forms: [
      (named, 'Sequence message.'), (anchor, 'Issue message.')])

    refusal = bulk.operation_refusal(change)

    assert 'Sequence message. Issue message.' in refusal
    assert refusal.endswith('Please remove these sequences from this '
                            'change, or discard it.')


@pytest.mark.django_db
def test_way_out_of_a_problem_of_the_whole_change(change, approved_issues,
                                                  monkeypatch):
    """
    A problem of the change as a whole, such as a revision of a kind
    that bulk changes do not make, names no object, so taking objects
    out cannot solve it: Discard is the way out, also beside a problem
    of one object.
    """
    reprint = ReprintRevision.objects.create(
      changeset=change, origin_issue=approved_issues[0],
      target_issue=approved_issues[1])

    alone = bulk.operation_refusal(change)
    kept = _revisions(change)[0]
    monkeypatch.setattr(bulk, '_turned_off', lambda changeset: [
      (kept, 'Object message.')])
    beside = bulk.operation_refusal(change)
    reprint.delete()

    for refusal in (alone, beside):
        assert 'It holds revisions that a bulk change does not make: ' \
               'reprintrevisions.' in refusal
        assert refusal.endswith(' Please discard this change.')
    assert 'Object message.' in beside


@pytest.mark.django_db
def test_compare_page_builds_no_edit_form(client, change, monkeypatch):
    """
    The page of a change, shown at each view, decides its link from the
    checks that need no edit form; the page of an operation, where one is
    made, runs the edit forms of the revisions changed since the latest
    checkpoint, as a submission does.
    """
    change.issuerevisions.update(modified=django_timezone.now())
    calls = []
    original = bulk.revision_form_messages

    def counted(*args, **kwargs):
        """Count a call, then make it as the code would."""
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(bulk, 'revision_form_messages', counted)

    compare = client.get(_compare(change)).content.decode()

    assert len(calls) == 0
    assert ADD_LINK in compare
    assert client.get(_page(change)).status_code == 200
    assert len(calls) > 0


@pytest.mark.django_db
def test_flag_off_cycle_ends_with_the_objects_taken_out(client, change,
                                                        any_approver):
    """
    A field turned off during the review stops the approval.  Sent back,
    the author takes out the objects that changed the field, which the
    field being off does not prevent, and the rest is approved.
    """
    assert _operate(client, change, RATING).status_code == 302
    change.submit()
    change.assign(any_approver)
    _turn_off_rating(change)
    approver = Client()
    approver.force_login(any_approver)
    url = reverse('approve', kwargs={'id': change.id})

    page = ' '.join(_text(approver.post(url, {'comments': ''})).split())

    assert 'This bulk change cannot be approved.' in page
    assert 'so that they can take these objects out.' in page
    assert approver.post(_process(change),
                         {'disapprove': 'Send back',
                          'comments': 'Why.'}).status_code == 302
    rated = [revision.id for revision in _revisions(change) if revision.rating]
    assert len(rated) == 2
    assert _remove(client, change, *rated).status_code == 302
    assert client.post(_process(change),
                       {'submit': 'Submit',
                        'comments': ''}).status_code == 302
    assert approver.post(url, {'comments': ''}).status_code == 302
    change.refresh_from_db()
    assert change.state == states.APPROVED


@pytest.mark.django_db
@pytest.mark.parametrize('code, message', [
    (bulk.DEADLOCK, True),
    (bulk.LOCK_WAIT_TIMEOUT, True),
    (1064, False),
])
def test_lock_errors_while_working_on_a_change(client, change, monkeypatch,
                                               code, message):
    """
    A deadlock or a long wait gives a message, with nothing written; any
    other database error stays an error.  Every revision keeps its value,
    and the operation goes through when it is tried again.
    """
    def fail(*args, **kwargs):
        """Fail as the database does."""
        raise OperationalError(code, 'database error')

    before = _page_counts(change)
    monkeypatch.setattr(bulk, '_write_record', fail)
    if message:
        assert bulk.CHANGE_BUSY in _text(_operate(client, change, PAGES))
    else:
        with pytest.raises(OperationalError):
            _operate(client, change, PAGES)

    monkeypatch.undo()
    assert change.comments.count() == 1
    assert _page_counts(change) == before
    assert _operate(client, change, PAGES).status_code == 302
    assert _page_counts(change) == dict.fromkeys(before, Decimal('36'))
