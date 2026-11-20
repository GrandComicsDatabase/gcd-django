"""The revert of an approved bulk change."""
import re
from datetime import timedelta
from decimal import Decimal
from html import unescape
from itertools import count

import pytest

from django.conf import settings as django_settings
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.db import OperationalError, connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone as django_timezone

from apps.gcd.models import IndiciaPublisher, Issue, Publisher, Series
from apps.indexer.models import Indexer
from apps.oi import bulk, states
from apps.oi.models import (
    Changeset, IndiciaPublisherRevision, IssueRevision, RevisionLock, CTYPES,
    _get_revision_lock)
from apps.oi.tests.bulk.invariants import check_invariants
from apps.oi.tests.bulk.page_forms import PageForms

PRICE = {'field': 'price', 'shown': 'price', 'operation': 'set',
         'new_value': '0.12 USD'}
LATER_PRICE = dict(PRICE, new_value='0.15 USD')
PAGES = {'field': 'page_count', 'shown': 'page_count', 'operation': 'set',
         'new_value': '36'}
VOLUME = {'field': 'volume', 'shown': 'volume', 'operation': 'set',
          'new_value': '5'}
NOT_PRINTED = {'field': 'volume_not_printed',
               'shown': 'volume_not_printed', 'operation': 'set',
               'new_value': 'on'}
UNCERTAIN = {'field': 'page_count_uncertain', 'shown': 'page_count_uncertain',
             'operation': 'set', 'new_value': 'on'}
FREQUENCY = {'field': 'indicia_frequency', 'shown': 'indicia_frequency',
             'operation': 'replace_exact', 'old_value': '=monthly',
             'new_value': 'weekly'}
NO_FREQUENCY = dict(FREQUENCY, new_value='')
DATE = {'field': 'publication_date', 'shown': 'publication_date',
        'operation': 'replace_exact', 'new_value': 'February 1947'}
FREQUENCY_ERROR = 'You cannot specify an indicia frequency and check ' \
                  '"no indicia frequency" at the same time.'
PAGE_COUNT_ERROR = 'You cannot check page count uncertain without a page ' \
                   'count.'
CHOICE_ERROR = 'Select a valid choice. That choice is not one of the ' \
               'available choices.'
SPACES = 'Spaces at the start or end of an old value are not restored.'
LINK_TEXT = 'Revert this bulk change'
ADD_LINK = 'Add an operation'
NO_OPERATION = ('A revert only puts old values back, so it takes no further '
                'operation. To write a different value, discard this change '
                'and start a new bulk change on these issues.')
OLDER_OVER = ('This older kind of bulk change cannot be reverted '
              'automatically. It holds 3 issues, and one bulk change can '
              'hold at most 2. To put a field back, start a bulk change '
              'from a list of at most 2 of these issues, for example a '
              'search with a filter. Credits, brand emblems and indicia '
              'printers cannot be put back this way.')
OLDER_DELETED = ('This older kind of bulk change cannot be reverted '
                 'automatically. All its issues have been deleted.')


@pytest.fixture(autouse=True)
def invariants(db):
    """Start without applied tokens; check the invariants at the end."""
    cache.clear()
    yield
    check_invariants()


@pytest.fixture
def make_change(client, settings, reserving_indexer, approved_issues):
    """
    Return a function that makes an open bulk change as the page makes it,
    of the given issues or of the three approved ones; its author is
    logged in.
    """
    settings.BULK_CHANGE_ENABLED = True
    settings.BULK_CHANGE_MAX_ACTIVE = 10
    reserving_indexer.indexer.max_reservations = 10
    reserving_indexer.indexer.save()
    client.force_login(reserving_indexer)
    tokens = count(1)

    def make(params, issues=None):
        token = 'revert-token-%d' % next(tokens)
        session = client.session
        session[bulk.SELECTION_KEY] = {
          'token': token, 'model': 'issue', 'source': '/list/',
          'ids': sorted(issue.id for issue in issues or approved_issues)}
        session.save()
        response = client.post(
          reverse('edit_issues_in_bulk') + '?token=' + token, params)
        assert response.status_code == 302, _words(response)
        return Changeset.objects.filter(change_type=CTYPES['bulk']) \
                                .latest('id')
    return make


@pytest.fixture
def make_change_without_page(make_change, reserving_indexer):
    """
    Return a function that makes an open bulk change of the given issues
    without the page, with the engine: the replacement of old by new in
    the field name, also one that the page refuses.  As with make_change,
    its author is logged in.
    """
    tokens = count(1)

    def make(name, old, new, issues):
        return bulk.apply(
          reserving_indexer, 'engine-token-%d' % next(tokens), Issue,
          sorted(issue.id for issue in issues), '/list/',
          bulk.Operation(name, 'replace_exact', old, new))
    return make


@pytest.fixture
def approved(make_change, approve_change):
    """The approved bulk change of the price of the three issues."""
    changeset = make_change(PRICE)
    approve_change(changeset)
    return changeset


@pytest.fixture
def older_change(client, settings, bulk_change, approved_issues,
                 reserving_indexer, approve_change):
    """
    An approved change of the older kind on the three issues; its author
    is logged in.
    """
    settings.BULK_CHANGE_ENABLED = True
    client.force_login(reserving_indexer)
    changeset = bulk_change(approved_issues, IssueRevision, price='0.25 USD')
    Changeset.objects.filter(id=changeset.id).update(
      change_type=CTYPES['issue_bulk'])
    changeset = Changeset.objects.get(id=changeset.id)
    approve_change(changeset)
    return changeset


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


def _page(changeset):
    """The address of the page that reverts changeset."""
    return reverse('edit_issues_in_bulk') + '?revert=%d' % changeset.id


def _compare(changeset):
    """The address of the page of changeset."""
    return reverse('compare', kwargs={'id': changeset.id})


def _operation(changeset):
    """The address of the page of a further operation on changeset."""
    return reverse('edit_issues_in_bulk') + '?changeset=%d' % changeset.id


def _words(response):
    """The words of response, without tags, as a reader sees them."""
    text = re.sub(r'<[^>]+>', ' ', response.content.decode())
    text = ' '.join(unescape(text).split())
    return re.sub(r' ([.,:])', r'\1', text)


def _show(client, changeset):
    """The words of the page that reverts changeset."""
    response = client.get(_page(changeset))
    assert response.status_code == 200
    return _words(response)


def _apply_form(client, changeset):
    """The form that applies the revert of changeset, as rendered."""
    page = PageForms(client.get(_page(changeset)).content.decode())
    assert page.repeated_ids() == []
    return page.form('POST', _page(changeset))


def _posted_forms(client, changeset):
    """The addresses that the page that reverts changeset can post to."""
    page = PageForms(client.get(_page(changeset)).content.decode())
    return [form['action'] for form in page.forms
            if form['method'] == 'POST' and 'revert=' in form['action']]


def _revert(client, changeset):
    """Apply the revert of changeset as its page does; return the change."""
    response = client.post(_page(changeset),
                           PageForms.data(_apply_form(client, changeset)))
    assert response.status_code == 302, _words(response)
    made = Changeset.objects.filter(change_type=CTYPES['bulk']).latest('id')
    assert response['Location'] == _compare(made)
    return made


def _prices(issues):
    """The prices that issues hold now."""
    return [Issue.objects.get(id=issue.id).price for issue in issues]


def _on_object_and_head(issues, **values):
    """Give values to issues and to their latest approved revisions."""
    ids = [issue.id for issue in issues]
    Issue.objects.filter(id__in=ids).update(**values)
    IssueRevision.objects.filter(
      issue_id__in=ids, next_revision=None,
      changeset__state=states.APPROVED).update(**values)


def _counts():
    """The numbers of the rows that a look at a page must not change."""
    return (Changeset.objects.count(), IssueRevision.objects.count(),
            RevisionLock.objects.count())


def _snapshot():
    """The rows that a look at a page must not change, as values."""
    return (
      _counts(),
      list(Issue.objects.order_by('id')
           .values_list('id', 'price', 'modified')),
      list(IssueRevision.objects.order_by('id')
           .values_list('id', 'changeset_id', 'price', 'modified')),
      list(Changeset.objects.order_by('id')
           .values_list('id', 'state', 'modified')))


@pytest.mark.django_db
def test_page_writes_nothing(client, approved, approved_issues):
    """The page says what a revert would do, and writes nothing."""
    before = _snapshot()

    words = _show(client, approved)

    assert _snapshot() == before
    assert 'Revert a bulk change' in words
    assert ('Restores the values from before change %d in all 3 of its '
            'issues.' % approved.id) in words
    assert 'The other' not in words
    assert ('Reserves these 3 issues in one change, not yet submitted.'
            in words)
    assert 'To restore only some, apply' in words
    # The table marks the digit that changes, from the new to the old price.
    assert '0.1 2 USD' in words and '0.1 0 USD' in words
    assert _prices(approved_issues) == ['0.12 USD'] * 3


@pytest.mark.django_db
def test_apply_and_approval_put_the_values_back(client, approved,
                                                approved_issues,
                                                approve_change):
    """
    Apply makes a new open bulk change that holds the old values, with
    its record; only its approval changes the issues, and it earns the
    points of any bulk change.
    """
    revert = _revert(client, approved)

    assert revert.id != approved.id and revert.state == states.OPEN
    record = bulk.operation_record(revert)
    assert record['operation'] == 'restore'
    assert record['values'] == [approved.id]
    assert record['counts']['changed'] == 3
    assert record['source'].endswith(_compare(approved))
    assert 'Reverts change %d' % approved.id in \
        revert.comments.order_by('id').first().text
    assert {revision.price for revision in revert.issuerevisions.all()} == \
        {'0.10 USD'}
    assert revert.revision_locks.count() == 3
    assert _prices(approved_issues) == ['0.12 USD'] * 3

    approve_change(revert)

    assert _prices(approved_issues) == ['0.10 USD'] * 3
    assert not revert.revision_locks.exists()
    approved.refresh_from_db()
    revert.refresh_from_db()
    assert revert.imps == approved.imps > 0


@pytest.mark.django_db
def test_value_changed_later_stays(client, approved, approved_issues,
                                   make_change, approve_change):
    """
    An object whose value changed since is left out and shown with its
    three values; the others go back.
    """
    approve_change(make_change(LATER_PRICE, approved_issues[:1]))

    words = _show(client, approved)
    assert 'in 2 of its 3 issues.' in words
    assert 'The other one keeps its present value:' in words
    assert 'Changed later, so left out: 1' in words
    assert 'Before that change After that change Now' in words
    assert 'Price 0.10 USD 0.12 USD 0.15 USD' in words
    assert 'Reserves these 2 issues' in words

    revert = _revert(client, approved)
    record = bulk.operation_record(revert)
    assert record['counts']['later'] == 1
    assert record['counts']['changed'] == 2
    assert record['listed']['later'] == [approved_issues[0].id]
    lines = [line for line in
             revert.comments.order_by('id').first().text.split('\n')
             if line.startswith('Later: ')]
    assert len(lines) == 1
    assert lines[0].endswith('/issue/%d/' % approved_issues[0].id)
    assert ('Left out, keeping their present values: 1 changed later. '
            'The comments list them.') in \
        _words(client.get(_compare(revert)))

    approve_change(revert)
    assert _prices(approved_issues) == ['0.15 USD', '0.10 USD', '0.10 USD']


@pytest.mark.django_db
def test_other_field_changed_later_goes_back(client, approved,
                                             approved_issues, make_change,
                                             approve_change):
    """A later change of another field keeps nothing from going back."""
    approve_change(make_change(PAGES, approved_issues[:1]))

    revert = _revert(client, approved)
    approve_change(revert)

    assert _prices(approved_issues) == ['0.10 USD'] * 3
    assert Issue.objects.get(id=approved_issues[0].id).page_count == 36


@pytest.mark.django_db
@pytest.mark.parametrize('after_the_check', [False, True])
def test_object_reserved_by_another_change(client, approved, approved_issues,
                                           make_change, monkeypatch,
                                           after_the_check):
    """
    An object that another change holds is left out, and stays held, also
    when the other change takes its lock just after the check for it, and
    has no revision of it yet: the lock alone decides.
    """
    if after_the_check:
        other = Changeset.objects.create(indexer=approved.indexer,
                                         state=states.OPEN,
                                         change_type=CTYPES['issue'])
        assert _get_revision_lock(approved_issues[0], other) is not None
    else:
        other = make_change(PAGES, approved_issues[:1])

    assert 'Reserved by other changes, so left out: 1' in \
        _show(client, approved)

    if after_the_check:
        monkeypatch.setattr(bulk, '_locked', lambda data_object: False)
    revert = _revert(client, approved)
    monkeypatch.undo()
    record = bulk.operation_record(revert)
    assert record['counts']['reserved'] == 1
    assert record['listed']['reserved'] == [approved_issues[0].id]
    assert revert.issuerevisions.count() == 2
    assert other.revision_locks.count() == 1
    assert RevisionLock.objects.get(object_id=approved_issues[0].id) \
                       .changeset_id == other.id


@pytest.mark.django_db
def test_field_turned_off(client, make_change, approve_change,
                          approved_issues):
    """
    A field turned off in the series stays as it is: the commit would not
    copy it.  With nothing to restore there is no table and no Apply, and
    a post changes nothing.
    """
    changeset = make_change(FREQUENCY)
    approve_change(changeset)
    Series.objects.filter(id=approved_issues[0].series_id) \
                  .update(has_indicia_frequency=False)

    words = _show(client, changeset)
    assert 'Field turned off in their series, so left out: 3' in words
    assert 'Nothing to restore from change %d.' % changeset.id in words
    assert _posted_forms(client, changeset) == []

    before = _counts()
    response = client.post(_page(changeset))
    assert 'Nothing was changed, so no change was made' in _words(response)
    assert 'turned off 3' in _words(response)
    assert _counts() == before


@pytest.mark.django_db
def test_deleted_object(client, approved, approved_issues, make_change,
                        approve_change):
    """An object deleted since is left out, first of all."""
    approve_change(make_change(LATER_PRICE, approved_issues[:1]))
    Issue.objects.filter(id=approved_issues[0].id).update(deleted=True)

    assert 'Deleted since that change, so left out: 1' in \
        _show(client, approved)

    record = bulk.operation_record(_revert(client, approved))
    assert record['counts']['deleted'] == 1
    assert record['counts']['later'] == 0
    assert record['listed']['deleted'] == [approved_issues[0].id]


@pytest.mark.django_db
def test_value_refused_by_the_form_today(client, make_change, approve_change,
                                         approved_issues):
    """
    An old value that the edit form refuses today does not come back, and
    the page gives the reason; a refusal of every value offers no Apply.
    """
    changeset = make_change(NO_FREQUENCY)
    approve_change(changeset)
    _on_object_and_head(approved_issues, no_indicia_frequency=True)

    words = _show(client, changeset)

    assert 'Refused by the edit form today, so left out: 3' in words
    assert FREQUENCY_ERROR in words
    assert _posted_forms(client, changeset) == []


@pytest.mark.django_db
def test_object_already_failing_the_form(client, approved, approved_issues):
    """An object that fails its edit form as it is stays out, as blocked."""
    _on_object_and_head(approved_issues[:1], page_count=None,
                        page_count_uncertain=True)

    words = _show(client, approved)
    assert 'Already failing the edit form, so left out: 1' in words
    assert PAGE_COUNT_ERROR in words

    revert = _revert(client, approved)
    record = bulk.operation_record(revert)
    assert revert.issuerevisions.count() == 2
    assert record['counts']['blocked'] == 1
    assert record['counts']['changed'] == 2
    assert record['listed']['blocked'] == [approved_issues[0].id]


@pytest.mark.django_db
@pytest.mark.parametrize('how', ['deleted', 'other publisher'])
def test_old_link_that_cannot_come_back(client, make_change, approve_change,
                                        approved_issues, how,
                                        second_indicia_publisher):
    """
    An old indicia publisher goes back only if the edit form would offer
    it for a new link.
    """
    field = {'field': 'indicia_publisher', 'shown': 'indicia_publisher',
             'operation': 'set', 'new_value': str(second_indicia_publisher.id)}
    changeset = make_change(field)
    approve_change(changeset)
    old = approved_issues[0].indicia_publisher
    if how == 'deleted':
        IndiciaPublisher.objects.filter(id=old.id).update(deleted=True)
    else:
        other = Publisher.objects.get(id=old.parent_id)
        other.pk = None
        other.save()
        IndiciaPublisher.objects.filter(id=old.id).update(parent=other)

    words = _show(client, changeset)

    assert 'Refused by the edit form today, so left out: 3' in words
    assert bulk.OLD_LINK_REFUSED in words
    assert _posted_forms(client, changeset) == []


@pytest.mark.django_db
def test_old_link_comes_back(client, make_change, approve_change,
                             approved_issues, second_indicia_publisher):
    """A link goes back like any value, and the page shows its name."""
    old = approved_issues[0].indicia_publisher
    field = {'field': 'indicia_publisher', 'shown': 'indicia_publisher',
             'operation': 'set', 'new_value': str(second_indicia_publisher.id)}
    changeset = make_change(field)
    approve_change(changeset)

    assert old.name in _show(client, changeset)
    approve_change(_revert(client, changeset))

    for issue in approved_issues:
        assert Issue.objects.get(id=issue.id).indicia_publisher_id == old.id


@pytest.mark.django_db
def test_old_indicia_publisher_outside_the_years_today(
      client, make_change, approve_change, approved_issues,
      second_indicia_publisher):
    """
    An old indicia publisher whose years no longer cover the year of the
    issues stays out with the message of their edit form, which would not
    offer it for them; the other field of the change goes back.
    """
    old = approved_issues[0].indicia_publisher
    prices = _prices(approved_issues)
    changeset = make_change({'field': 'indicia_publisher',
                             'shown': 'indicia_publisher', 'operation': 'set',
                             'new_value': str(second_indicia_publisher.id)})
    assert client.post(_operation(changeset), PRICE).status_code == 302
    approve_change(changeset)
    IndiciaPublisher.objects.filter(id=old.id).update(year_began=1969,
                                                      year_ended=1979)

    words = _show(client, changeset)
    approve_change(_revert(client, changeset))

    assert 'Refused by the edit form today, so left out: 3' in words
    assert CHOICE_ERROR in words
    assert bulk.OLD_LINK_REFUSED not in words
    assert _prices(approved_issues) == prices
    for issue in approved_issues:
        assert Issue.objects.get(id=issue.id).indicia_publisher_id == \
            second_indicia_publisher.id


def _key_dates_and_links(issues):
    """The key dates and indicia publishers that issues hold now."""
    return [(now.key_date, now.indicia_publisher_id) for now in
            Issue.objects.filter(id__in=[issue.id for issue in issues])]


@pytest.mark.django_db
def test_old_indicia_publisher_comes_back_with_its_key_date(
      client, make_change, approve_change, approved_issues,
      second_indicia_publisher):
    """
    An old indicia publisher whose years cover only the old key date goes
    back in the same revert as that key date: the key date goes back
    first, so the edit form offers the old indicia publisher, as its
    choices depend on the key date.
    """
    old = approved_issues[0].indicia_publisher
    new = second_indicia_publisher
    assert (old.year_began, old.year_ended) == (1940, 2000)
    IndiciaPublisher.objects.filter(id=new.id).update(year_began=None,
                                                      year_ended=None)
    changeset = make_change({'field': 'key_date', 'shown': 'key_date',
                             'operation': 'replace_exact',
                             'old_value': '=1947-01-00',
                             'new_value': '2023-12-00'})
    assert client.post(_operation(changeset), {
      'field': 'indicia_publisher', 'shown': 'indicia_publisher',
      'operation': 'set', 'new_value': str(new.id)}).status_code == 302
    approve_change(changeset)
    assert _key_dates_and_links(approved_issues) == \
        [('2023-12-00', new.id)] * 3

    words = _show(client, changeset)
    revert = _revert(client, changeset)
    approve_change(revert)

    assert _key_dates_and_links(approved_issues) == \
        [('1947-01-00', old.id)] * 3
    assert 'Refused by the edit form today' not in words
    assert bulk.operation_record(revert)['counts']['changed'] == 6


@pytest.mark.django_db
def test_link_set_where_there_was_none_goes_back(client, make_change,
                                                 approve_change,
                                                 approved_issues):
    """
    An indicia publisher set on issues that had none goes back to none:
    an empty old link is neither held as a row nor refused.
    """
    publisher = approved_issues[0].indicia_publisher
    _on_object_and_head(approved_issues, indicia_publisher=None)
    changeset = make_change({'field': 'indicia_publisher',
                             'shown': 'indicia_publisher',
                             'operation': 'set',
                             'new_value': str(publisher.id)})
    approve_change(changeset)

    revert = _revert(client, changeset)
    assert bulk.operation_record(revert)['counts']['changed'] == \
        len(approved_issues)
    approve_change(revert)

    for issue in approved_issues:
        assert Issue.objects.get(id=issue.id).indicia_publisher_id is None


@pytest.mark.django_db
def test_spaces_of_an_old_value_are_cleaned(client, make_change,
                                            approve_change, approved_issues):
    """Spaces the form takes away do not come back, and the page says so."""
    issues = approved_issues[1:]
    _on_object_and_head(issues, publication_date='January 1947 ')
    changeset = make_change(dict(DATE, old_value='=January 1947 '), issues)
    approve_change(changeset)

    words = _show(client, changeset)
    assert SPACES in words
    assert 'all 2 of its issues' in words

    approve_change(_revert(client, changeset))
    for issue in issues:
        assert Issue.objects.get(id=issue.id).publication_date == \
            'January 1947'


@pytest.mark.django_db
def test_old_value_cleaned_into_the_present_one(client, make_change,
                                                approve_change,
                                                approved_issues):
    """An old value that the form cleans into the present one is unchanged."""
    issues = approved_issues[1:]
    _on_object_and_head(issues, publication_date='February 1947 ')
    changeset = make_change(dict(DATE, old_value='=February 1947 '), issues)
    approve_change(changeset)

    words = _show(client, changeset)

    assert 'Already back to the old value: 2' in words
    assert 'Nothing to restore from change %d.' % changeset.id in words
    assert SPACES not in words
    assert _posted_forms(client, changeset) == []


@pytest.mark.django_db
def test_value_and_flag_go_back_together(client, make_change, approve_change,
                                         approved_issues):
    """
    A value and its flag are one logical field: they go back together and
    count as one, in a change of several fields.
    """
    changeset = make_change(PAGES)
    assert client.post(_operation(changeset), UNCERTAIN).status_code == 302
    approve_change(changeset)

    words = _show(client, changeset)
    assert 'in all 3 of its changed values.' in words

    revert = _revert(client, changeset)
    assert bulk.operation_record(revert)['counts']['changed'] == 3
    approve_change(revert)

    first, second, third = [Issue.objects.get(id=issue.id)
                            for issue in approved_issues]
    assert first.page_count == Decimal(64)
    assert second.page_count is None and third.page_count is None
    assert not first.page_count_uncertain
    assert not second.page_count_uncertain


@pytest.mark.django_db
def test_refused_logical_field_leaves_the_other(client, make_change,
                                                approve_change,
                                                approved_issues):
    """If a rule refuses one logical field, the object's other goes back."""
    changeset = make_change(NO_FREQUENCY)
    assert client.post(_operation(changeset), PRICE).status_code == 302
    approve_change(changeset)
    _on_object_and_head(approved_issues, no_indicia_frequency=True)

    words = _show(client, changeset)
    assert 'Refused by the edit form today, so left out: 3' in words
    assert 'in 3 of its 6 changed values.' in words
    assert 'The other 3 keep their present values:' in words

    revert = _revert(client, changeset)
    record = bulk.operation_record(revert)
    assert record['counts']['changed'] == 3
    assert record['counts']['invalid'] == 3
    approve_change(revert)

    assert _prices(approved_issues) == ['0.10 USD'] * 3
    for issue in approved_issues:
        assert Issue.objects.get(id=issue.id).indicia_frequency == ''


@pytest.mark.django_db
def test_partial_revert_can_be_repeated(client, approved, approved_issues,
                                        make_change, approve_change,
                                        reserving_indexer):
    """
    A revert that left an object out can be run again for it; once all is
    back there is nothing to restore, and the page names both reverts.
    """
    other = make_change(PAGES, approved_issues[:1])
    first = _revert(client, approved)
    approve_change(first)
    assert _prices(approved_issues) == ['0.12 USD', '0.10 USD', '0.10 USD']

    words = _words(client.get(_compare(approved)))
    assert 'Partly reverted by change %d.' % first.id in words
    assert LINK_TEXT in words

    other.discard(reserving_indexer)
    second = _revert(client, approved)
    record = bulk.operation_record(second)
    assert record['counts']['changed'] == 1
    assert record['counts']['unchanged'] == 2
    approve_change(second)
    assert _prices(approved_issues) == ['0.10 USD'] * 3

    words = _words(client.get(_compare(approved)))
    assert 'Partly reverted by changes %d and %d.' % (first.id, second.id) \
        in words
    assert 'Nothing to restore from change %d.' % approved.id in \
        _show(client, approved)


@pytest.mark.django_db
@pytest.mark.parametrize('steps', [0, 1, 2])
def test_second_revert_is_refused(client, approved, any_approver, steps):
    """While a revert is active, in any state, there is no second one."""
    revert = _revert(client, approved)
    if steps > 0:
        revert.submit()
    if steps > 1:
        revert.assign(any_approver)

    words = _show(client, approved)
    assert 'Change %d is already reverting this change.' % revert.id in words
    assert _posted_forms(client, approved) == []
    assert 'Being reverted by change %d.' % revert.id in \
        _words(client.get(_compare(approved)))
    assert LINK_TEXT not in _words(client.get(_compare(approved)))

    before = _counts()
    response = client.post(_page(approved))
    assert ('Change %d is already reverting this change.' % revert.id
            in _words(response))
    assert _counts() == before


@pytest.mark.django_db
def test_two_reverts_under_way_are_both_named(client, approved,
                                              approved_issues, make_change,
                                              reserving_indexer, monkeypatch):
    """
    Two Applies that pass the check together can leave two reverts under
    way, each with its own objects: the page of the change names both.
    """
    other = make_change(PAGES, approved_issues[:1])
    first = _revert(client, approved)
    other.discard(reserving_indexer)
    monkeypatch.setattr(bulk, '_active_revert', lambda change: None)
    second = _revert(client, approved)
    monkeypatch.undo()
    assert (first.issuerevisions.count(), second.issuerevisions.count()) == \
        (2, 1)

    words = _words(client.get(_compare(approved)))

    assert 'Being reverted by changes %d and %d.' % (first.id, second.id) \
        in words
    assert LINK_TEXT not in words


@pytest.mark.django_db
def test_active_revert_shows_only_what_it_left_out(client, approved,
                                                   approved_issues,
                                                   make_change):
    """
    With a revert active the page lists what is left out, without a table
    or Apply, and the objects of the revert itself are not reserved.
    """
    make_change(PAGES, approved_issues[:1])
    _revert(client, approved)

    words = _show(client, approved)

    assert 'Reserved by other changes, so left out: 1' in words
    assert 'Reserves these' not in words
    assert _posted_forms(client, approved) == []


@pytest.mark.django_db
def test_two_applies_at_once(client, approved, monkeypatch):
    """
    If two Applies pass the check together the locks decide: the second
    finds every object reserved and writes nothing.
    """
    _revert(client, approved)
    before = _counts()

    monkeypatch.setattr(bulk, '_active_revert', lambda change: None)
    response = client.post(_page(approved))
    monkeypatch.undo()

    assert 'Nothing was changed, so no change was made' in _words(response)
    assert 'reserved 3' in _words(response)
    assert _counts() == before


@pytest.mark.django_db
def test_revert_of_a_revert(client, approved, approved_issues,
                            approve_change):
    """A revert is a bulk change: it can be reverted the same way."""
    first = _revert(client, approved)
    approve_change(first)
    assert _prices(approved_issues) == ['0.10 USD'] * 3

    assert ('Restores the values from before change %d in all 3 of its '
            'issues.' % first.id) in _show(client, first)
    second = _revert(client, first)
    assert bulk.operation_record(second)['values'] == [first.id]
    approve_change(second)

    assert _prices(approved_issues) == ['0.12 USD'] * 3
    assert 'Reverted by change %d.' % first.id in \
        _words(client.get(_compare(approved)))


@pytest.mark.django_db
def test_discarded_revert_does_not_count(client, approved, approved_issues,
                                         reserving_indexer):
    """A discarded revert leaves the change free to be reverted."""
    first = _revert(client, approved)
    first.discard(reserving_indexer)

    status = bulk.revert_status(approved)
    assert status['can_revert'] and status['text'] == ''
    assert bulk.reverts_of(approved) == []

    assert _revert(client, approved).id != first.id


@pytest.mark.django_db
def test_change_names_what_became_of_its_revert(client, approved,
                                                approved_issues,
                                                approve_change,
                                                reserving_indexer):
    """
    The page of a change whose revert is reverted in turn, or is being
    reverted, says so after the revert, one step only, as the page of
    each change names the next.  A discarded revert of the revert does
    not count, and the link that reverts the change does not come back:
    the revert of the revert has its own.
    """
    first = _revert(client, approved)
    approve_change(first)
    reverted = 'Reverted by change %d.' % first.id
    _revert(client, first).discard(reserving_indexer)

    words = _words(client.get(_compare(approved)))
    assert reverted in words
    assert 'is itself' not in words

    second = _revert(client, first)
    assert ('%s Change %d is itself being reverted by change %d.'
            % (reverted, first.id, second.id)) in \
        _words(client.get(_compare(approved)))

    approve_change(second)
    assert _prices(approved_issues) == ['0.12 USD'] * 3
    words = _words(client.get(_compare(approved)))
    assert ('%s Change %d is itself reverted by change %d.'
            % (reverted, first.id, second.id)) in words
    assert LINK_TEXT not in words

    third = _revert(client, second)
    approve_change(third)
    response = client.get(_compare(approved))
    assert _words(response) == words
    assert _compare(third) not in response.content.decode()
    assert ('Reverted by change %d. Change %d is itself reverted by change '
            '%d.' % (second.id, second.id, third.id)) in \
        _words(client.get(_compare(first)))


@pytest.mark.django_db
def test_removed_objects_count_as_left_out(client, approved, approve_change):
    """Objects that the author took out of a revert show as left out."""
    revert = _revert(client, approved)
    selected = revert.issuerevisions.order_by('issue_id').first()
    response = client.post(reverse('process', kwargs={'id': revert.id}),
                           {'bulk_remove': 'Remove selected',
                            'selected': [str(selected.id)]})
    assert response.status_code == 302

    record = bulk.operation_record(revert)
    assert record['counts']['changed'] == 2
    assert record['counts']['removed'] == 1
    words = _words(client.get(_compare(revert)))
    assert ('Reverts change %d: 2 of its 3 issues go back to the values '
            'before it.' % approved.id) in words
    assert 'Left out, keeping their present values: 1 removed by the '\
           'author.' in words
    assert 'The comments list them.' not in words

    approve_change(revert)
    assert 'Partly reverted by change %d.' % revert.id in \
        _words(client.get(_compare(approved)))


@pytest.mark.django_db
def test_long_lists_point_to_the_page(client, approved, approved_issues,
                                      make_change, approve_change,
                                      monkeypatch, settings):
    """Beyond the objects that a comment lists, the page has them all."""
    approve_change(make_change(LATER_PRICE, approved_issues[:2]))
    monkeypatch.setattr(bulk, 'LISTED_OBJECTS', 1)

    revert = _revert(client, approved)

    comment = revert.comments.order_by('id').first().text
    assert 'Later: and 1 more' in comment
    assert len(bulk.operation_record(revert)['listed']['later']) == 1
    response = client.get(_compare(revert))
    assert 'The comments list the first 1 of each: see the full list.' in \
        _words(response)
    assert PageForms(response.content.decode()).link('?revert=%d'
                                                     % approved.id)

    settings.BULK_CHANGE_ENABLED = False
    words = _words(client.get(_compare(revert)))
    assert 'The comments list the first 1 of each.' in words
    assert 'see the full list' not in words


def _two_fields(client, make_change, approve_change, first, second):
    """An approved bulk change of the three issues with two operations."""
    changeset = make_change(first)
    assert client.post(_operation(changeset), second).status_code == 302
    approve_change(changeset)
    return changeset


def _record_lines(changeset, label):
    """The lines of the record of changeset for the outcome label."""
    return [line for line in
            changeset.comments.order_by('id').first().text.split('\n')
            if line.startswith(label + ': ')]


def _object_line(label, issue, *messages):
    """The line of the record that lists issue for label with messages."""
    url = django_settings.SITE_URL.rstrip('/') + issue.get_absolute_url()
    return ' '.join(('%s: %s' % (label, url),) + messages)


@pytest.mark.django_db
def test_object_left_out_for_two_fields_is_listed_once(client, make_change,
                                                       approve_change,
                                                       approved_issues):
    """
    An object left out for two logical fields has one line for that
    outcome in the record, which counts both values, and a reason that
    both give appears once.
    """
    changeset = _two_fields(client, make_change, approve_change, PRICE,
                            PAGES)
    reserved, failing, changed = approved_issues
    make_change(LATER_PRICE, [reserved])
    _on_object_and_head([failing], no_indicia_frequency=True)

    revert = _revert(client, changeset)

    record = bulk.operation_record(revert)
    assert (record['counts']['reserved'], record['counts']['blocked'],
            record['counts']['changed']) == (2, 2, 2)
    assert record['listed']['reserved'] == [reserved.id]
    assert record['listed']['blocked'] == [failing.id]
    assert _record_lines(revert, 'Reserved') == \
        [_object_line('Reserved', reserved)]
    assert _record_lines(revert, 'Blocked') == \
        [_object_line('Blocked', failing, FREQUENCY_ERROR)]


@pytest.mark.django_db
def test_reasons_of_an_object_are_joined(client, make_change, approve_change,
                                         approved_issues):
    """
    The line of an object that the edit form refuses for two logical
    fields gives each reason once, in their order, joined by a space.
    """
    changeset = _two_fields(client, make_change, approve_change,
                            NO_FREQUENCY, PAGES)
    # Its page count was empty before the change.
    refused = approved_issues[1]
    _on_object_and_head([refused], no_indicia_frequency=True,
                        page_count_uncertain=True)

    revert = _revert(client, changeset)

    record = bulk.operation_record(revert)
    assert (record['counts']['invalid'], record['counts']['changed']) == \
        (2, 4)
    assert record['listed']['invalid'] == [refused.id]
    assert _record_lines(revert, 'Invalid') == \
        [_object_line('Invalid', refused, FREQUENCY_ERROR, PAGE_COUNT_ERROR)]


@pytest.mark.django_db
@pytest.mark.parametrize('cap, listed, more, words', [
    (3, 2, [], 'The comments list them.'),
    (1, 1, ['Deleted: and 1 more'],
     'The comments list the first 1 of each: see the full list.'),
])
def test_cap_of_a_list_counts_objects(client, make_change, approve_change,
                                      approved_issues, monkeypatch, cap,
                                      listed, more, words):
    """
    The cap on the objects that a record lists for an outcome counts
    objects, not values: more values than the cap on fewer objects are
    all listed, and "and N more" counts the objects beyond the cap.
    """
    changeset = _two_fields(client, make_change, approve_change, PRICE,
                            PAGES)
    deleted = approved_issues[:2]
    Issue.objects.filter(id__in=[issue.id for issue in deleted]) \
                 .update(deleted=True)
    monkeypatch.setattr(bulk, 'LISTED_OBJECTS', cap)

    revert = _revert(client, changeset)

    record = bulk.operation_record(revert)
    assert record['counts']['deleted'] == 4
    assert record['listed']['deleted'] == \
        [issue.id for issue in deleted[:listed]]
    assert _record_lines(revert, 'Deleted')[listed:] == more
    assert record['more'] == (['deleted'] if more else [])
    assert bulk.revert_summary(revert)['more'] is bool(more)
    page = _words(client.get(_compare(revert)))
    assert 'Left out, keeping their present values: 4 deleted. ' + words \
        in page


@pytest.mark.django_db
def test_change_of_the_older_kind_starts_a_selection(client, older_change,
                                                     approved_issues):
    """
    An approved change of the older kind has no record: its link starts a
    bulk change on its issues, with a line that names it.
    """
    changeset = older_change

    response = client.get(_compare(changeset))
    assert 'This older kind of bulk change cannot be reverted automatically' \
        in _words(response)
    link = PageForms(response.content.decode()).link('?revert=%d'
                                                     % changeset.id)

    started = client.get(link)
    assert started.status_code == 302
    assert 'Selection: 3 issues from change %d.' % changeset.id in \
        _words(client.get(started['Location']))
    assert client.session[bulk.SELECTION_KEY]['ids'] == \
        sorted(issue.id for issue in approved_issues)


def _older_way_back(client, changeset):
    """Whether the page of changeset offers to put a field back."""
    response = client.get(_compare(changeset))
    assert response.status_code == 200
    return ('This older kind of bulk change' in _words(response) or
            '?revert=%d' % changeset.id in response.content.decode())


@pytest.mark.django_db
def test_older_kind_offers_nothing_with_bulk_changes_off(client,
                                                         older_change,
                                                         settings):
    """With bulk changes off, a change of the older kind offers nothing."""
    settings.BULK_CHANGE_ENABLED = False

    assert not _older_way_back(client, older_change)


@pytest.mark.django_db
def test_older_kind_offers_nothing_before_its_approval(client, settings,
                                                       bulk_change,
                                                       approved_issues,
                                                       reserving_indexer):
    """A change of the older kind not yet approved offers nothing."""
    settings.BULK_CHANGE_ENABLED = True
    client.force_login(reserving_indexer)
    changeset = bulk_change(approved_issues, IssueRevision, price='0.25 USD')
    Changeset.objects.filter(id=changeset.id).update(
      change_type=CTYPES['issue_bulk'])

    assert not _older_way_back(client, changeset)


@pytest.mark.django_db
def test_refusals(client, approved, any_adding_changeset):
    """Only a bulk change with the record of its operations is reverted."""
    assert 'Only a bulk change can be reverted.' in \
        _show(client, any_adding_changeset)

    approved.comments.filter(old_state=states.UNRESERVED,
                             new_state=states.OPEN).update(text='Other.')
    assert 'no record of its operations' in _show(client, approved)
    assert bulk.revert_status(approved) is None


@pytest.mark.django_db
def test_open_change_cannot_be_reverted(client, make_change):
    """An open bulk change is corrected, not reverted; it has no link."""
    changeset = make_change(PRICE)

    assert 'Only an approved bulk change can be reverted.' in \
        _show(client, changeset)
    assert LINK_TEXT not in _words(client.get(_compare(changeset)))


@pytest.mark.django_db
def test_turned_off_site(client, approved, settings):
    """With bulk changes off no revert starts, and no link leads to one."""
    settings.BULK_CHANGE_ENABLED = False
    before = _counts()

    assert bulk.revert_refusal(approved) == 'Bulk changes are turned off.'
    assert 'Revert a bulk change' not in \
        _words(client.get(_page(approved)))
    assert LINK_TEXT not in _words(client.get(_compare(approved)))
    assert _counts() == before


@pytest.mark.django_db
@pytest.mark.parametrize('value', ['abc', '9' * 5000, '999999'])
def test_unknown_change(client, approved, value):
    """An address that names no change is not found."""
    url = reverse('edit_issues_in_bulk') + '?revert=' + value

    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_link_of_an_approved_change(client, approved):
    """The page of an approved change links to its revert."""
    response = client.get(_compare(approved))

    assert LINK_TEXT in _words(response)
    PageForms(response.content.decode()).link('?revert=%d' % approved.id)


@pytest.mark.django_db
def test_no_link_without_the_right_to_reserve(client, approved,
                                              reserving_indexer):
    """Who may not reserve changes gets no link."""
    reserving_indexer.user_permissions.remove(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(type(reserving_indexer).objects.get(
      id=reserving_indexer.id))

    assert LINK_TEXT not in _words(client.get(_compare(approved)))
    before = _counts()
    assert client.get(_page(approved)).status_code == 302
    assert client.post(_page(approved)).status_code == 302
    assert _counts() == before


@pytest.mark.django_db
def test_page_of_the_revert_names_the_change(client, approved):
    """The page of a revert says what it reverts."""
    revert = _revert(client, approved)

    response = client.get(_compare(revert))

    assert ('Reverts change %d: all 3 of its issues go back to the values '
            'before it.' % approved.id) in _words(response)
    assert 'Left out, keeping' not in _words(response)
    assert _compare(approved) in PageForms(response.content.decode()).links


def test_logical_fields_match_the_points():
    """
    Two fields of a bulk change are one logical field exactly when the
    points of an edit count them once.
    """
    groups = bulk.LOGICAL_FIELDS[IssueRevision]
    names = list(bulk.policy_fields(IssueRevision))
    revision = IssueRevision(page_count=Decimal(1))
    for first in names:
        for second in names:
            if first == second:
                continue
            revision._start_imp_sum()
            assert revision._imps_for(first) == 1, first
            together = any(first in group and second in group
                           for group in groups)
            assert revision._imps_for(second) == (0 if together else 1), \
                (first, second)


def test_the_check_of_an_old_link_knows_every_link():
    """
    The check of an old link knows only the indicia publisher: it must be
    the one link that a bulk change writes.
    """
    links = [name for rev_class in bulk.FIELD_POLICY
             for name in bulk.policy_fields(rev_class)
             if rev_class._meta.get_field(name).is_relation]

    assert links == ['indicia_publisher']


@pytest.mark.django_db
def test_page_checks_the_latest_approved_revision(client, approved,
                                                  approved_issues,
                                                  make_change, approve_change,
                                                  monkeypatch):
    """
    The page checks in memory the latest approved revision of the object,
    as a revision of the change without dependents, and saves nothing.
    """
    later = make_change(PAGES, approved_issues[:1])
    approve_change(later)
    head = later.issuerevisions.get()
    calls = []
    check = bulk.revision_form_messages

    def spy(revision, user, dependents=True, **kwargs):
        """Note what is checked, and check it."""
        calls.append((revision.id, revision.changeset_id, dependents))
        return check(revision, user, dependents, **kwargs)

    def no_formsets(*args, **kwargs):
        """Fail: the page has no dependents to check."""
        raise AssertionError('formsets on the page of a revert')

    monkeypatch.setattr(bulk, 'revision_form_messages', spy)
    monkeypatch.setattr(IssueRevision, 'extra_forms', no_formsets)
    _show(client, approved)
    monkeypatch.undo()

    assert (head.id, approved.id, False) in calls
    head.refresh_from_db()
    assert head.changeset_id == later.id


@pytest.mark.django_db
def test_only_the_fields_of_the_operations_go_back(client, approved,
                                                   approved_issues,
                                                   approve_change):
    """A field that no operation names stays, whatever the diff says."""
    first = approved_issues[0]
    IssueRevision.objects.filter(changeset=approved, issue=first) \
                         .update(notes='Other notes')
    Issue.objects.filter(id=first.id).update(notes='Other notes')

    approve_change(_revert(client, approved))

    issue = Issue.objects.get(id=first.id)
    assert issue.price == '0.10 USD' and issue.notes == 'Other notes'


@pytest.mark.django_db
def test_value_that_the_form_stores_otherwise(client, approved,
                                              approved_issues, monkeypatch):
    """An old value that the form would turn into another stays out."""
    check = bulk.revision_form_messages

    def other_value(revision, user, dependents=True, **kwargs):
        """Check revision, then store another price for the first."""
        messages = check(revision, user, dependents, **kwargs)
        if revision.issue_id == approved_issues[0].id:
            revision.price = '0.13 USD'
        return messages

    monkeypatch.setattr(bulk, 'revision_form_messages', other_value)
    words = _show(client, approved)
    monkeypatch.undo()

    assert 'Refused by the edit form today, so left out: 1' in words
    assert 'Its edit form stores "0.13 USD" instead.' in words


@pytest.mark.django_db
@pytest.mark.parametrize('values, outcome', [
    ({'price': '0.15 USD'}, 'later'),
    ({'deleted': True}, 'deleted'),
])
def test_object_that_changes_during_apply(client, approved, approved_issues,
                                          monkeypatch, values, outcome):
    """Apply reads each object again once it holds its lock."""
    locked = bulk._locked

    def changed_meanwhile(data_object):
        """Change the first object just before its lock."""
        if data_object.id == approved_issues[0].id:
            _on_object_and_head([data_object], **values)
        return locked(data_object)

    data = PageForms.data(_apply_form(client, approved))
    monkeypatch.setattr(bulk, '_locked', changed_meanwhile)
    response = client.post(_page(approved), data)
    monkeypatch.undo()

    assert response.status_code == 302
    revert = Changeset.objects.filter(change_type=CTYPES['bulk']).latest('id')
    record = bulk.operation_record(revert)
    assert record['counts'][outcome] == 1
    assert record['counts']['changed'] == 2
    assert revert.revision_locks.count() == 2


@pytest.mark.django_db
def test_apply_holds_the_rows_of_its_objects(client, approved,
                                             approved_issues, monkeypatch):
    """
    Apply holds the row of each object that it changes, and of its base,
    as any bulk change does.
    """
    kept = []
    monkeypatch.setattr(bulk, '_hold_rows', kept.append)
    _revert(client, approved)
    monkeypatch.undo()

    assert sorted(issue.id for issue in kept) == \
        sorted(issue.id for issue in approved_issues)


@pytest.mark.django_db
@pytest.mark.parametrize('code, words', [
    (bulk.LOCK_WAIT_TIMEOUT,
     'Another change was using some of the same records'),
    (bulk.NOWAIT_REFUSED, 'reserved 3'),
    (1064, None),
])
def test_lock_errors_during_apply(client, approved, monkeypatch, code, words):
    """
    A row that another transaction writes makes an object reserved, a wait
    beyond the server's limit refuses the whole revert, and other errors
    stay errors.
    """
    def fail(*args, **kwargs):
        """Fail as the database does."""
        raise OperationalError(code, 'database error')

    data = PageForms.data(_apply_form(client, approved))
    before = _counts()
    monkeypatch.setattr(bulk, '_clone', fail)
    if words:
        assert words in _words(client.post(_page(approved), data))
    else:
        with pytest.raises(OperationalError):
            client.post(_page(approved), data)
    monkeypatch.undo()

    assert _counts() == before


def _captured_post(client, changeset, data):
    """Post data to the page that reverts changeset; return its queries."""
    with CaptureQueriesContext(connection) as queries:
        response = client.post(_page(changeset), data)
    assert response.status_code == 302, _words(response)
    return [query['sql'] for query in queries]


@pytest.mark.django_db
def test_apply_holds_the_parents_before_its_turn(client, approved):
    """
    As in an Apply, the rows of the parents are held first, then the
    indexer takes a turn, and only then a revert under way is looked for.
    """
    data = PageForms.data(_apply_form(client, approved))

    sqls = _captured_post(client, approved, data)

    def place(*texts):
        """The place of the first query that holds all of texts."""
        return next(index for index, sql in enumerate(sqls)
                    if all(text in sql for text in texts))

    assert place('FOR SHARE', 'gcd_series') < place('FOR UPDATE', 'indexer')
    assert place('FOR UPDATE', 'indexer') < \
        place('LIKE', 'restore %d' % approved.id)


@pytest.mark.django_db
def test_apply_holds_the_old_value_of_a_link(client, make_change,
                                             approve_change, approved_issues,
                                             second_indicia_publisher):
    """
    The row of the old value of a link, which no object points to now, is
    held with the links that the objects hold, in one query of that table.
    """
    old = approved_issues[0].indicia_publisher
    new = second_indicia_publisher
    field = {'field': 'indicia_publisher', 'shown': 'indicia_publisher',
             'operation': 'set', 'new_value': str(new.id)}
    changeset = make_change(field)
    approve_change(changeset)
    data = PageForms.data(_apply_form(client, changeset))

    held = [sql for sql in _captured_post(client, changeset, data)
            if 'FOR SHARE' in sql and 'gcd_indicia_publisher' in sql]

    assert len(held) == 1
    assert sorted(re.findall(r'\d+', held[0].split(' IN ')[1])) == \
        sorted(str(pk) for pk in (old.id, new.id))


@pytest.mark.django_db
def test_deadlock_on_the_parents_gets_a_message(client, approved,
                                                monkeypatch):
    """
    A deadlock while the rows of the parents are held refuses the whole
    revert, with the words for a lock conflict, and writes nothing.
    """
    def deadlock(*args):
        """Fail as a deadlock does."""
        raise OperationalError(bulk.DEADLOCK, 'from the test')

    data = PageForms.data(_apply_form(client, approved))
    before = _counts()
    monkeypatch.setattr(bulk, '_share_rows', deadlock)

    page = _words(client.post(_page(approved), data))
    monkeypatch.undo()

    assert 'Another change was using some of the same records' in page
    assert 'The series of these objects' not in page
    assert _counts() == before


@pytest.mark.django_db
def test_turned_off_field_refuses_the_submit_of_a_revert(client, make_change,
                                                         approve_change,
                                                         approved_issues):
    """
    A field of a revert turned off in the series after its Apply stops the
    Submit, also when the revert names several fields, with a message for
    each object.
    """
    changeset = make_change(FREQUENCY)
    assert client.post(_operation(changeset), PRICE).status_code == 302
    approve_change(changeset)
    revert = _revert(client, changeset)
    Series.objects.filter(id=approved_issues[0].series_id) \
                  .update(has_indicia_frequency=False)

    response = client.post(reverse('process', kwargs={'id': revert.id}),
                           {'submit': 'Submit', 'comments': ''})

    assert _words(response).count('is turned off in its series.') == 3
    revert.refresh_from_db()
    assert revert.state == states.OPEN


@pytest.mark.django_db
def test_comment_naming_a_revert_does_not_count(client, approved,
                                                approved_issues, make_change):
    """Only the record of a change makes it a revert, not a comment."""
    other = make_change(PAGES, approved_issues[:1])
    other.comments.create(commenter=other.indexer, old_state=states.OPEN,
                          new_state=states.OPEN,
                          text='Please restore %d\nThanks.' % approved.id)

    assert bulk.reverts_of(approved) == []


@pytest.mark.django_db
def test_limit_of_open_changes(client, approved, reserving_indexer):
    """Who may not reserve another change neither sees nor applies a revert."""
    Indexer.objects.filter(user=reserving_indexer).update(max_reservations=0)
    before = _counts()
    message = 'You have reached your limit of open changes'

    assert message in _show(client, approved)
    assert message in _words(client.post(_page(approved)))
    assert _counts() == before


@pytest.mark.django_db
def test_change_of_one_object(client, make_change, approve_change,
                              approved_issues):
    """A change of one object has the words of one."""
    changeset = make_change(PRICE, approved_issues[:1])
    approve_change(changeset)

    words = _show(client, changeset)
    assert 'in its one issue.' in words
    assert 'Reserves this issue in one change' in words
    assert 'To restore only some' not in words

    revert = _revert(client, changeset)
    assert ('Reverts change %d: its one issue goes back to the values before '
            'it.' % changeset.id) in _words(client.get(_compare(revert)))


@pytest.mark.django_db
def test_turned_off_field_leaves_the_other(client, make_change,
                                           approve_change, approved_issues):
    """A field turned off stays out, and the other field of the object not."""
    changeset = make_change(FREQUENCY)
    assert client.post(_operation(changeset), PRICE).status_code == 302
    approve_change(changeset)
    Series.objects.filter(id=approved_issues[0].series_id) \
                  .update(has_indicia_frequency=False)

    revert = _revert(client, changeset)

    record = bulk.operation_record(revert)
    assert record['counts']['turned_off'] == 3
    assert len(record['listed']['turned_off']) == 3
    assert 'Left out, keeping their present values: 3 fields off.' in \
        _words(client.get(_compare(revert)))


@pytest.mark.django_db
def test_record_lists_fields_turned_off(client, make_change, approve_change,
                                        approved_issues):
    """
    The record of a revert lists the objects whose field is turned off
    under the words "Turned off", and its page points to them.
    """
    changeset = _two_fields(client, make_change, approve_change, PRICE,
                            FREQUENCY)
    Series.objects.filter(id=approved_issues[0].series_id) \
                  .update(has_indicia_frequency=False)
    issues = sorted(approved_issues, key=lambda issue: issue.id)

    revert = _revert(client, changeset)

    assert bulk.operation_record(revert)['listed']['turned_off'] == \
        [issue.id for issue in issues]
    assert _record_lines(revert, 'Turned off') == \
        [_object_line('Turned off', issue) for issue in issues]
    assert ('Left out, keeping their present values: 3 fields off. The '
            'comments list them.') in _words(client.get(_compare(revert)))


@pytest.mark.django_db
@pytest.mark.parametrize('outcome', bulk.REVERT_LISTED)
def test_revert_record_labels_read_back(approved_issues, outcome):
    """
    Each outcome that a revert lists has a label of words, without "_",
    whose lines read back: the first 50 of 51 objects, and the others as
    "and 1 more".
    """
    label = outcome.replace('_', ' ').capitalize()
    counts = dict.fromkeys(bulk.REVERT_OUTCOMES, 0)
    counts.update({'changed': 1, outcome: 51})
    listed = {name: [] for name in bulk.REVERT_LISTED}
    listed[outcome] = [(approved_issues[0], '')] * 51

    text = bulk.operation_text(
      Issue, bulk.Operation('price', 'restore', None, 1),
      '/changeset/1/compare/', 52, counts, listed, django_timezone.now())

    lines = text.split('\n')[5:]
    assert '_' not in label
    assert lines == [_object_line(label, approved_issues[0])] * 50 + \
        ['%s: and 1 more' % label]
    record = bulk.parse_operation(text)
    assert record['listed'][outcome] == [approved_issues[0].id] * 50
    assert record['more'] == [outcome]


@pytest.mark.django_db
def test_removal_counts_the_values_of_the_object(client, make_change,
                                                 approve_change):
    """Taking an object out of a revert counts each of its values."""
    changeset = make_change(PRICE)
    assert client.post(_operation(changeset), PAGES).status_code == 302
    approve_change(changeset)
    revert = _revert(client, changeset)
    assert bulk.operation_record(revert)['counts']['changed'] == 6
    selected = revert.issuerevisions.order_by('issue_id').first()

    response = client.post(reverse('process', kwargs={'id': revert.id}),
                           {'bulk_remove': 'Remove selected',
                            'selected': [str(selected.id)]})

    assert response.status_code == 302
    record = bulk.operation_record(revert)
    assert record['counts']['changed'] == 4
    assert record['counts']['removed'] == 2
    words = _words(client.get(_compare(revert)))
    assert ('Reverts change %d: 4 of its 6 changed values go back to the '
            'values before it.' % changeset.id) in words
    assert 'Left out, keeping their present values: 2 removed by the author.' \
        in words


@pytest.mark.django_db
def test_later_change_of_a_group_counts_once(client, make_change,
                                             approve_change, approved_issues):
    """
    A value and its flag, the volume group too, go back together, and
    count once also when a later change leaves them out.
    """
    _on_object_and_head(approved_issues, volume='1', no_volume=False)
    changeset = make_change(VOLUME)
    assert client.post(_operation(changeset), NOT_PRINTED).status_code == 302
    approve_change(changeset)
    assert 'in all 3 of its changed values.' in _show(client, changeset)
    approve_change(make_change(dict(VOLUME, new_value='7'),
                               approved_issues[:1]))

    words = _show(client, changeset)
    assert 'Changed later, so left out: 1' in words
    assert 'in 2 of its 3 changed values.' in words

    approve_change(_revert(client, changeset))
    first, second, third = [Issue.objects.get(id=issue.id)
                            for issue in approved_issues]
    assert first.volume == '7' and first.volume_not_printed
    assert second.volume == '1' and not second.volume_not_printed
    assert third.volume == '1' and not third.volume_not_printed


@pytest.mark.django_db
def test_repeated_revert_after_cleaned_spaces(client, make_change,
                                              approve_change, approved_issues,
                                              reserving_indexer):
    """A value that came back without its spaces is already back."""
    issues = approved_issues[1:]
    _on_object_and_head(issues, publication_date='January 1947 ')
    changeset = make_change(dict(DATE, old_value='=January 1947 '), issues)
    approve_change(changeset)
    other = make_change(PAGES, issues[:1])
    approve_change(_revert(client, changeset))
    other.discard(reserving_indexer)

    words = _show(client, changeset)

    assert 'Changed later' not in words
    assert 'in 1 of its 2 issues.' in words
    assert 'Already back to the old value: 1' in words


@pytest.mark.django_db
def test_submit_checks_every_value_of_a_revert(client, approved, monkeypatch):
    """Old values face the rules of today at each submission, however old."""
    revert = _revert(client, approved)
    IssueRevision.objects.filter(changeset=revert).update(
      modified=django_timezone.now() - timedelta(days=30))

    monkeypatch.setattr(bulk, 'revision_form_messages',
                        lambda *args, **kwargs: ['Refused today.'])
    with pytest.raises(bulk.ErrorWithMessage) as refusal:
        revert.submit()
    monkeypatch.undo()

    assert 'Refused today.' in refusal.value.message
    revert.refresh_from_db()
    assert revert.state == states.OPEN


@pytest.mark.django_db
def test_revert_can_be_retracted_and_sent_back(client, approved, any_approver):
    """A revert follows the work of any open bulk change."""
    revert = _revert(client, approved)
    process = reverse('process', kwargs={'id': revert.id})
    revert.submit()

    response = client.post(process, {'retract': 'Retract', 'comments': ''})
    assert response.status_code == 302
    revert.refresh_from_db()
    assert revert.state == states.OPEN

    revert.submit()
    revert.assign(any_approver)
    client.force_login(any_approver)
    response = client.post(process, {'disapprove': 'Send back',
                                     'comments': 'Why.'})
    assert response.status_code == 302
    revert.refresh_from_db()
    assert revert.state == states.OPEN
    assert bulk.operation_record(revert)['operation'] == 'restore'
    assert revert.revision_locks.count() == 3
    client.force_login(revert.indexer)
    assert NO_OPERATION in _words(client.get(_compare(revert)))


@pytest.mark.django_db
def test_old_value_the_form_turns_into_the_present_one(client, make_change,
                                                       approve_change,
                                                       approved_issues):
    """An old value that the form makes the present one is not refused."""
    issues = approved_issues[1:]
    _on_object_and_head(issues, key_date='1947.01.00')
    changeset = make_change({'field': 'key_date', 'shown': 'key_date',
                             'operation': 'replace_exact',
                             'old_value': '=1947.01.00',
                             'new_value': '1947-01-00'},
                            issues)
    approve_change(changeset)

    words = _show(client, changeset)

    assert 'Already back to the old value: 2' in words
    assert 'Refused by the edit form' not in words


@pytest.mark.django_db
def test_revert_empties_a_date_that_the_change_filled(
      client, make_change_without_page, approve_change, approved_issues):
    """
    A revert puts back the empty publication date that the change filled:
    no operation empties it, but a revert removes only what a change
    wrote.  The change was made without the page, which no longer fills
    an empty date.
    """
    issues = approved_issues[1:]
    _on_object_and_head(issues, publication_date='')
    changeset = make_change_without_page('publication_date', '',
                                         DATE['new_value'], issues)
    approve_change(changeset)

    revert = _revert(client, changeset)
    assert bulk.operation_record(revert)['counts']['changed'] == 2
    approve_change(revert)

    assert [Issue.objects.get(id=issue.id).publication_date
            for issue in issues] == ['', '']


@pytest.mark.django_db
def test_revert_leaves_out_an_empty_key_date_beside_a_date(
      client, make_change_without_page, approve_change, approved_issues):
    """
    An empty key date beside a publication date does not come back: the
    edit form refuses it today.  The change was made without the page,
    which no longer fills an empty key date.
    """
    issues = approved_issues[1:]
    _on_object_and_head(issues, key_date='')
    changeset = make_change_without_page('key_date', '', '1947-01-00',
                                         issues)
    approve_change(changeset)

    words = _show(client, changeset)

    assert 'Refused by the edit form today, so left out: 2' in words
    assert 'Dates are present, but the key date is empty.' in words


@pytest.mark.django_db
def test_older_kind_leaves_out_deleted_issues(client, older_change,
                                              approved_issues):
    """Issues deleted since an older change stay out of the selection."""
    Issue.objects.filter(id=approved_issues[0].id).update(deleted=True)

    started = client.get(_page(older_change))

    assert 'Selection: 2 issues from change %d.' % older_change.id in \
        _words(client.get(started['Location']))


@pytest.mark.django_db
@pytest.mark.parametrize('limits, new, refused', [
    ({'BULK_CHANGE_MAX': 2}, False, True),
    ({'BULK_CHANGE_MAX_NEW': 2}, True, True),
    ({'BULK_CHANGE_MAX': 3}, False, False),
])
def test_older_kind_over_the_limit(client, older_change, settings,
                                   reserving_indexer, limits, new, refused):
    """
    A change of the older kind with more issues than the limit of the
    reader shows why instead of its link, and so does the address of the
    link; nothing is written.  Within the limit the link stays.
    """
    for name, value in limits.items():
        setattr(settings, name, value)
    Indexer.objects.filter(user=reserving_indexer).update(is_new=new)
    before = _counts()

    response = client.get(_compare(older_change))
    started = client.get(_page(older_change))

    link = '?revert=%d' % older_change.id in response.content.decode()
    assert (OLDER_OVER in _words(response), link) == (refused, not refused)
    if refused:
        assert started.status_code == 200
        assert OLDER_OVER in _words(started)
        assert 'this list' not in _words(started)
    else:
        assert started.status_code == 302
    assert _counts() == before


@pytest.mark.django_db
def test_older_kind_with_all_issues_deleted(client, older_change,
                                            approved_issues):
    """
    A change of the older kind whose issues are all deleted says so
    instead of its link, and so does the address of the link.
    """
    Issue.objects.filter(id__in=[issue.id for issue in approved_issues]) \
                 .update(deleted=True)
    before = _counts()

    response = client.get(_compare(older_change))

    assert OLDER_DELETED in _words(response)
    assert '?revert=%d' % older_change.id not in response.content.decode()
    assert OLDER_DELETED in _show(client, older_change)
    assert _counts() == before


@pytest.mark.django_db
def test_older_kind_page_for_a_reader(client, older_change):
    """Anybody may read the page of a change of the older kind."""
    client.logout()

    response = client.get(_compare(older_change))

    assert response.status_code == 200
    assert '?revert=%d' % older_change.id not in response.content.decode()


@pytest.mark.django_db
def test_limit_counts_the_objects_that_go_back(client, approved,
                                               approved_issues, make_change,
                                               approve_change, settings):
    """The limit counts what the revert would hold, on the page and Apply."""
    approve_change(make_change(LATER_PRICE, approved_issues[:2]))
    settings.BULK_CHANGE_MAX = 1

    assert 'Reserves this issue' in _show(client, approved)
    assert _revert(client, approved).issuerevisions.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize('limits, new', [
    ({'BULK_CHANGE_MAX': 2}, False),
    ({'BULK_CHANGE_MAX_NEW': 2}, True),
])
def test_limit_refuses_too_many_objects(client, approved, settings,
                                        reserving_indexer, limits, new):
    """
    Too many objects are refused on the page and by Apply, with the limit
    of the indexer and the words of a revert.
    """
    for name, value in limits.items():
        setattr(settings, name, value)
    Indexer.objects.filter(user=reserving_indexer).update(is_new=new)
    before = _counts()
    message = ('A bulk change can hold at most 2 objects, and this revert '
               'would hold 3. To restore just one of them, edit it as '
               'usual.')

    assert message in _show(client, approved)
    assert message in _words(client.post(_page(approved)))
    assert _counts() == before


@pytest.mark.django_db
def test_revert_takes_no_further_operation(client, approved):
    """
    A revert only puts old values back: its page says so in place of the
    link, and neither the address nor the code writes anything.
    """
    revert = _revert(client, approved)
    before = _snapshot()

    words = _words(client.get(_compare(revert)))
    assert NO_OPERATION in words
    assert ADD_LINK not in words
    assert NO_OPERATION in _words(client.get(_operation(revert)))
    assert NO_OPERATION in _words(client.post(_operation(revert), PRICE))
    with pytest.raises(bulk.ErrorWithMessage) as refusal:
        bulk.add_operation(revert.indexer, revert,
                           bulk.Operation('price', 'set', None, '0.20 USD'))

    assert refusal.value.message == NO_OPERATION
    assert _snapshot() == before


@pytest.mark.django_db
def test_revert_with_a_field_off_takes_no_operation(client, make_change,
                                                    approve_change,
                                                    approved_issues):
    """
    A revert that fails the check of a submission, as a field it holds is
    turned off since its Apply, gives the reason of a revert first: no
    removal would make it take an operation.
    """
    changeset = _two_fields(client, make_change, approve_change, PRICE,
                            FREQUENCY)
    revert = _revert(client, changeset)
    Series.objects.filter(id=approved_issues[0].series_id) \
                  .update(has_indicia_frequency=False)
    assert bulk.submit_messages(revert)

    for words in (_words(client.get(_compare(revert))),
                  _words(client.get(_operation(revert)))):
        assert NO_OPERATION in words
        assert 'cannot take another operation' not in words


@pytest.mark.django_db
def test_no_full_list_without_the_right_to_reserve(client, approved,
                                                   approved_issues,
                                                   make_change, approve_change,
                                                   monkeypatch,
                                                   reserving_indexer):
    """Who may not reserve gets no link to a page they cannot open."""
    approve_change(make_change(LATER_PRICE, approved_issues[:2]))
    monkeypatch.setattr(bulk, 'LISTED_OBJECTS', 1)
    revert = _revert(client, approved)
    reserving_indexer.user_permissions.remove(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))

    words = _words(client.get(_compare(revert)))

    assert 'The comments list the first 1 of each.' in words
    assert 'see the full list' not in words


@pytest.mark.django_db
def test_refused_field_does_not_touch_the_check_of_the_next(client,
                                                            make_change,
                                                            approve_change,
                                                            monkeypatch):
    """
    A logical field left out goes back to its present value in memory, so
    the check of the next one sees the object as it is.
    """
    changeset = make_change(FREQUENCY)
    assert client.post(_operation(changeset), PRICE).status_code == 302
    approve_change(changeset)
    check = bulk.revision_form_messages
    seen = []

    def other_value(revision, user, dependents=True, **kwargs):
        """Store another frequency, and note what the next check sees."""
        messages = check(revision, user, dependents, **kwargs)
        if revision.price == '0.12 USD':
            revision.indicia_frequency = 'other'
        else:
            seen.append(revision.indicia_frequency)
        return messages

    monkeypatch.setattr(bulk, 'revision_form_messages', other_value)
    _show(client, changeset)
    monkeypatch.undo()

    assert seen == ['weekly'] * 3


@pytest.mark.django_db
def test_active_revert_offers_nothing_for_an_object_it_left(client, approved):
    """With a revert active, an object taken out of it is not offered."""
    revert = _revert(client, approved)
    selected = revert.issuerevisions.order_by('issue_id').first()
    response = client.post(reverse('process', kwargs={'id': revert.id}),
                           {'bulk_remove': 'Remove selected',
                            'selected': [str(selected.id)]})
    assert response.status_code == 302

    words = _show(client, approved)

    assert 'Change %d is already reverting this change.' % revert.id in words
    assert 'Reserves this' not in words
    assert _posted_forms(client, approved) == []


@pytest.mark.django_db
def test_no_link_on_a_partly_reverted_change_without_the_right(
      client, approved, approved_issues, make_change, approve_change,
      reserving_indexer):
    """Who may not reserve reads how far a change went back, without a link."""
    approve_change(make_change(LATER_PRICE, approved_issues[:1]))
    approve_change(_revert(client, approved))
    reserving_indexer.user_permissions.remove(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))

    words = _words(client.get(_compare(approved)))

    assert 'Partly reverted by change' in words
    assert LINK_TEXT not in words


@pytest.mark.django_db
def test_object_locked_by_another_change_without_a_revision(client, approved,
                                                            approved_issues):
    """A lock alone is enough for the page to call an object reserved."""
    holder = Changeset.objects.create(indexer=approved.indexer,
                                      state=states.OPEN,
                                      change_type=CTYPES['issue'])
    assert _get_revision_lock(approved_issues[0], holder) is not None

    words = _show(client, approved)

    assert 'Reserved by other changes, so left out: 1' in words
    assert 'in 2 of its 3 issues.' in words
