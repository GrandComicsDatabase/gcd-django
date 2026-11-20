"""The bulk issue edit and its entry from the advanced search."""
from collections import Counter
from urllib.parse import urlencode

import pytest

from django.contrib.auth.models import Permission
from django.forms import ModelMultipleChoiceField
from django.urls import reverse

from apps.gcd.models import CreditType, Issue
from apps.gcd.models.creator import Creator, CreatorNameDetail
from apps.gcd.models.issue import IssueCredit
from apps.gcd.models.story import CREDIT_TYPES
from apps.mycomics.models import Collector, ConditionGradeScale
from apps.oi.models import CTYPES, IssueCreditRevision, IssueRevision
from apps.stddata.models import Date, Script

SEARCH = {'target': 'issue', 'method': 'icontains', 'logic': 'False'}


@pytest.fixture
def searching_indexer(any_indexer, any_language):
    """An indexer with the collector a confirmed account gets."""
    Collector.objects.create_collector(
      any_indexer,
      grade_system=ConditionGradeScale.objects.create(name='Test scale'),
      default_language=any_language)
    return any_indexer


def _allow_reserving(user):
    """Give a test indexer the permission to reserve changes."""
    user.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))


@pytest.mark.django_db
def test_bulk_edit_of_empty_search_redirects(client, searching_indexer):
    """A search without results goes back to the search, not to an error."""
    _allow_reserving(searching_indexer)
    client.force_login(searching_indexer)

    response = client.get(reverse('edit_issues_in_bulk'),
                          dict(SEARCH, series='No Such Series'))

    assert response.status_code == 302
    assert response['Location'].startswith(
      reverse('process_advanced_search'))


@pytest.mark.django_db
@pytest.mark.parametrize('method, query', [('get', ''), ('post', ''),
                                           ('post', '?target=series')])
def test_bulk_edit_without_issue_target_redirects(client, searching_indexer,
                                                  method, query):
    """A request without the issue target goes back to the search."""
    _allow_reserving(searching_indexer)
    client.force_login(searching_indexer)

    response = getattr(client, method)(reverse('edit_issues_in_bulk') + query)

    assert response.status_code == 302
    assert response['Location'].startswith(
      reverse('process_advanced_search'))


@pytest.mark.django_db
@pytest.mark.parametrize('series, can_reserve, shown', [
    ('Series for Issues', True, True),
    ('Series for Issues', False, False),
    ('No Such Series', True, False),
])
def test_bulk_change_link_on_issue_search(client, any_added_issue,
                                          searching_indexer, series,
                                          can_reserve, shown):
    """The link needs results and the permission the bulk edit needs."""
    if can_reserve:
        _allow_reserving(searching_indexer)
    client.force_login(searching_indexer)

    response = client.get(reverse('process_advanced_search'),
                          dict(SEARCH, series=series))

    assert response.status_code == 200
    content = response.content.decode()
    assert (reverse('edit_issues_in_bulk') in content) is shown


def _creator_name(name):
    """A creator name to credit, of a creator of its own."""
    return CreatorNameDetail.objects.create(
      name=name, in_script=Script.objects.get_or_create(
        id=Script.LATIN_PK,
        defaults={'code': 'Latn', 'number': Script.LATIN_PK,
                  'name': 'Latin'})[0],
      creator=Creator.objects.create(
        gcd_official_name=name, sort_name=name,
        birth_date=Date.objects.create()))


def _add_editing_credit(name, issue_revision, credit_name='associate editor'):
    """Give the issue of a revision an editing credit with a description."""
    credit = IssueCredit.objects.create(
      issue=issue_revision.issue, creator=name,
      credit_name=credit_name,
      credit_type=CreditType.objects.get_or_create(
        id=CREDIT_TYPES['editing'],
        defaults={'name': 'editing', 'sort_code': 6})[0])
    IssueCreditRevision.objects.create(
      issue_credit=credit, issue_revision=issue_revision,
      changeset=issue_revision.changeset, creator=name,
      credit_type=credit.credit_type, credit_name=credit.credit_name)
    return credit


def _browser_post(*forms):
    """The values a browser posts for unbound forms as rendered."""
    data = {}
    for form in forms:
        for field in form:
            value = field.value()
            if isinstance(field.field, ModelMultipleChoiceField):
                data[field.html_name] = value or []
            elif value is True:
                data[field.html_name] = 'on'
            elif value is not False:
                data[field.html_name] = '' if value is None else value
    return data


@pytest.mark.django_db
def test_bulk_edit_removes_a_shared_credit(client, any_added_issue,
                                           any_added_issue_rev,
                                           searching_indexer):
    """Remove Above on a shared credit deletes it and keeps the others."""
    _allow_reserving(searching_indexer)
    client.force_login(searching_indexer)
    other_issue = Issue.objects.create(
      number='2', series=any_added_issue.series,
      sort_code=any_added_issue.sort_code + 1,
      editing=any_added_issue.editing)
    revisions = [any_added_issue_rev, IssueRevision.objects.create(
      changeset=any_added_issue_rev.changeset, issue=other_issue,
      series=other_issue.series, number=other_issue.number)]
    gone, staying = _creator_name('Ed Itor'), _creator_name('Co Editor')
    expected = {}
    for revision in revisions:
        expected[_add_editing_credit(gone, revision).id] = True
        expected[_add_editing_credit(staying, revision).id] = False
    url = reverse('edit_issues_in_bulk')
    search = dict(SEARCH, series='Series for Issues')
    page = client.get(url, search)
    formset = page.context['credits_formset']
    data = _browser_post(page.context['form'], formset.management_form,
                         *formset)
    for form in formset:
        # the only option of the credit type select
        data[form.add_prefix('credit_type')] = CREDIT_TYPES['editing']
        if form.initial.get('creator') == gone.id:
            # what the Remove Above link of the credit sets
            data[form.add_prefix('DELETE')] = 'on'

    response = client.post(url + '?' + urlencode(search), data)

    assert dict(IssueCreditRevision.objects.filter(
      changeset__change_type=CTYPES['issue_bulk']).values_list(
        'issue_credit', 'deleted')) == expected
    assert response.status_code == 302


def _credits_of_one_creator(issue, issue_rev, roles, swapped=None):
    """
    Give the issue and a second one a credit of one creator for each role,
    in the other order of id on the issue at the index swapped.
    """
    other_issue = Issue.objects.create(
      number='2', series=issue.series, sort_code=issue.sort_code + 1,
      editing=issue.editing)
    revisions = [issue_rev, IssueRevision.objects.create(
      changeset=issue_rev.changeset, issue=other_issue,
      series=other_issue.series, number=other_issue.number)]
    name = _creator_name('Ed Itor')
    credits = []
    for index, revision in enumerate(revisions):
        order = reversed(roles) if index == swapped else roles
        credits += [_add_editing_credit(name, revision, role)
                    for role in order]
    return credits


def _post_bulk_edit(client, removed=None, added=None, rejected=False):
    """
    Post the bulk issue edit as the page renders it, with a comment, with
    Remove Above on the row of the removed description and with the name
    and description added entered in the empty row.  When rejected, the
    removed row is also posted with a name as credited and without "Is
    credited", which the form rejects.
    """
    url = reverse('edit_issues_in_bulk')
    search = dict(SEARCH, series='Series for Issues')
    page = client.get(url, search)
    formset = page.context['credits_formset']
    data = _browser_post(page.context['form'], formset.management_form,
                         *formset)
    data['comments'] = 'Credits of one creator'
    for form in formset:
        # the only option of the credit type select
        data[form.add_prefix('credit_type')] = CREDIT_TYPES['editing']
        if removed and form.initial.get('credit_name') == removed:
            # what the Remove Above link of the credit sets
            data[form.add_prefix('DELETE')] = 'on'
            if rejected:
                # a name as credited needs "Is credited": the form rejects
                # the row, and the page still posts it
                data[form.add_prefix('credited_as')] = 'E. Itor'
                data.pop(form.add_prefix('is_credited'), None)
    if added:
        empty = formset.forms[-1]
        data[empty.add_prefix('creator')] = added[0].id
        data[empty.add_prefix('credit_name')] = added[1]
    return client.post(url + '?' + urlencode(search), data)


def _bulk_credit_revisions():
    """The credit, deletion and description of each bulk credit revision."""
    return Counter(IssueCreditRevision.objects.filter(
      changeset__change_type=CTYPES['issue_bulk']).values_list(
        'issue_credit', 'deleted', 'credit_name'))


@pytest.mark.django_db
@pytest.mark.parametrize('removed, swapped, rejected', [
    pytest.param(None, None, False, id='both-kept'),
    pytest.param('editor', None, False, id='first-row-removed'),
    pytest.param('publisher', None, False, id='second-row-removed'),
    pytest.param(None, 1, False, id='second-issue-other-order'),
    pytest.param(None, 0, False, id='first-issue-other-order'),
    pytest.param('editor', None, True, id='first-row-removed-with-errors'),
])
def test_bulk_edit_keeps_two_credits_of_one_creator_apart(
        client, any_added_issue, any_added_issue_rev, searching_indexer,
        removed, swapped, rejected):
    """Each of two credits of one creator follows its own row of the page."""
    _allow_reserving(searching_indexer)
    client.force_login(searching_indexer)
    credits = _credits_of_one_creator(any_added_issue, any_added_issue_rev,
                                      ['editor', 'publisher'], swapped)

    response = _post_bulk_edit(client, removed=removed, rejected=rejected)

    assert _bulk_credit_revisions() == Counter(
      (credit.id, credit.credit_name == removed, credit.credit_name)
      for credit in credits)
    assert response.status_code == 302


@pytest.mark.django_db
def test_bulk_edit_adds_a_second_credit_of_one_creator(
        client, any_added_issue, any_added_issue_rev, searching_indexer):
    """A credit entered for a creator credited already is a new credit."""
    _allow_reserving(searching_indexer)
    client.force_login(searching_indexer)
    credits = _credits_of_one_creator(any_added_issue, any_added_issue_rev,
                                      ['editor'])

    response = _post_bulk_edit(client, added=(credits[0].creator,
                                              'publisher'))

    expected = Counter((credit.id, False, 'editor') for credit in credits)
    expected[(None, False, 'publisher')] = 2
    assert _bulk_credit_revisions() == expected
    assert response.status_code == 302
