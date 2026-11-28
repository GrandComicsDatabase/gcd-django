"""
The credits row of an issue page that the person leaves untouched.

The list of credit types of the row has one choice and no empty one, so a
browser posts the credit type also for a row nobody touched.
"""
from urllib.parse import urlencode

import pytest

from django.contrib.auth.models import Permission
from django.http import QueryDict
from django.urls import reverse

from apps.gcd.models import CreditType
from apps.gcd.models.creator import Creator, CreatorNameDetail
from apps.gcd.models.story import CREDIT_TYPES
from apps.mycomics.models import Collector, ConditionGradeScale
from apps.oi import states
from apps.oi.models import (CTYPES, Changeset, IssueCreditRevision,
                            IssueRevision)
from apps.oi.views import _add_form_data, _add_formset_data
from apps.stddata.models import Date, Script

# What a credits row checked with nothing in it shows: no creator, no
# credit description, and the credit type that its form takes away.
EMPTY_ROW_ERRORS = ['This field is required.', 'This field cannot be null.']
ROW = 'issue_credit_revisions-0-'
FORMSETS = ['credits_formset', 'code_number_formset',
            'external_link_formset']
SEARCH = {'target': 'issue', 'method': 'icontains', 'logic': 'False',
          'series': 'Series for Issues'}
# The pages where the tests post a credits row with something in it. The
# page that adds a variant to a change is in the untouched row test, where
# it comes back for the error of its main form.
CHECKING_PAGES = ['add_multiple_issues', 'add_issue', 'add_variant_issue',
                  'edit_revision', 'edit_issues_in_bulk']
REQUIRED = 'This field is required.'
# A row with something typed in it, the field of its error, and the error.
TYPED_ROWS = [
  pytest.param({'credited_as': 'Some Name'}, '__all__',
               'Is credited needs to be selected when entering a name as '
               'credited.', id='credited-as'),
  pytest.param({'is_credited': 'on'}, 'creator', REQUIRED, id='tick'),
  pytest.param({'sourced_by': 'Some Source'}, 'creator', REQUIRED,
               id='sourced-by'),
  pytest.param({'credit_name': 'x' * 256}, 'credit_name',
               'Ensure this value has at most 255 characters (it has 256).',
               id='long-description'),
  pytest.param({'creator': '999999'}, 'creator',
               'Select a valid choice. That choice is not one of the '
               'available choices.', id='unknown-creator')]


@pytest.fixture
def reserving_client(client, any_indexer, any_language):
    """
    A client logged in as an indexer who can reserve more changes, with
    the collector that a confirmed account gets.
    """
    Collector.objects.create_collector(
      any_indexer,
      grade_system=ConditionGradeScale.objects.create(name='Test scale'),
      default_language=any_language)
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    any_indexer.indexer.max_reservations = 10
    any_indexer.indexer.save()
    client.force_login(any_indexer)
    return client


@pytest.fixture
def issue_revision(any_added_issue, any_indexer):
    """An open change of the indexer to an issue without credits."""
    CreditType.objects.get_or_create(
      id=CREDIT_TYPES['editing'],
      defaults={'name': 'editing', 'sort_code': CREDIT_TYPES['editing']})
    changeset = Changeset.objects.create(
      change_type=CTYPES['issue'], indexer=any_indexer, state=states.OPEN)
    return IssueRevision.clone(any_added_issue, changeset=changeset)


def _page(name, revision):
    """
    Return the address of a page with a credits row, the address it posts
    to, and the values that its form needs.
    """
    edit = {'model_name': 'issue', 'id': revision.id}
    kwargs = {
      'add_multiple_issues': {'series_id': revision.series.id,
                              'method': 'number'},
      'add_issue': {'series_id': revision.series.id},
      'add_variant_issue': {'issue_id': revision.issue.id},
      'add_variant_to_issue_revision': {
        'issue_revision_id': revision.id,
        'changeset_id': revision.changeset.id},
      'edit_revision': edit,
    }.get(name)
    url = reverse(name, kwargs=kwargs)
    if name == 'edit_issues_in_bulk':
        url += '?' + urlencode(SEARCH)
    action = reverse('process_revision', kwargs=edit) \
        if name == 'edit_revision' else url
    values = {
      'add_multiple_issues': {'number_of_issues': '2'},
      'add_issue': {'number': '43'},
      'add_variant_issue': {'variant_name': 'Some Variant'},
      'add_variant_to_issue_revision': {'variant_name': 'Some Variant'},
      'edit_revision': {'save': ''},
    }.get(name, {})
    return url, action, values


def _browser_post(client, url, **values):
    """
    Return what a browser posts for the page at the address as it is
    drawn, with some values changed.
    """
    page = client.get(url)
    assert page.status_code == 200
    data = QueryDict(mutable=True)
    _add_form_data(data, page.context['form'])
    for name in FORMSETS:
        if page.context.get(name) is not None:
            _add_formset_data(data, page.context[name])
    data = dict(data.lists())
    data.update(values)
    return data


def _counts():
    """Return how many changes, issue revisions and credits there are."""
    return (Changeset.objects.count(), IssueRevision.objects.count(),
            IssueCreditRevision.objects.count())


def _creator_name(name):
    """Return a creator name to credit, of a creator of its own."""
    return CreatorNameDetail.objects.create(
      name=name, in_script=Script.objects.get_or_create(
        id=Script.LATIN_PK,
        defaults={'code': 'Latn', 'number': Script.LATIN_PK,
                  'name': 'Latin'})[0],
      creator=Creator.objects.create(
        gcd_official_name=name, sort_name=name,
        birth_date=Date.objects.create()))


@pytest.mark.django_db
@pytest.mark.parametrize('name', CHECKING_PAGES +
                         ['add_variant_to_issue_revision'])
def test_untouched_credits_row_shows_no_errors(reserving_client,
                                               issue_revision, name):
    """
    A page that comes back for an error elsewhere shows no error on the
    credits row the person left untouched.
    """
    url, action, values = _page(name, issue_revision)
    data = _browser_post(reserving_client, url, page_count='abc', **values)
    # besides the change it belongs to, the row posts its credit type only
    row = {key: value for key, value in data.items()
           if key.startswith(ROW) and value != [''] and
           key != ROW + 'issue_revision'}
    assert row == {ROW + 'credit_type': [str(CREDIT_TYPES['editing'])]}
    assert data['issue_credit_revisions-TOTAL_FORMS'] == ['1']

    response = reserving_client.post(action, data)

    assert response.status_code == 200
    assert response.context['form'].errors['page_count'] == \
        ['Enter a number.']
    content = response.content.decode()
    for error in EMPTY_ROW_ERRORS:
        assert error not in content


@pytest.mark.django_db
@pytest.mark.parametrize('name', CHECKING_PAGES)
@pytest.mark.parametrize('credit, field, error', [
  ({}, 'credit_name', 'This field is required.'),
  ({'credit_name': 'associate editor', 'credited_as': 'Some Name'},
   '__all__',
   'Is credited needs to be selected when entering a name as credited.')])
def test_filled_credit_is_still_refused(reserving_client, issue_revision,
                                        name, credit, field, error):
    """
    A credit the person filled in is checked: its error is shown and
    nothing is saved.
    """
    url, action, values = _page(name, issue_revision)
    credit = dict(credit, creator=_creator_name('Some Creator').id)
    data = _browser_post(reserving_client, url, **values)
    data.update({ROW + key: value for key, value in credit.items()})
    before = _counts()

    response = reserving_client.post(action, data)

    assert response.status_code == 200
    assert not response.context['form'].errors
    assert response.context['credits_formset'][0].errors[field] == [error]
    assert error in response.content.decode()
    assert _counts() == before


@pytest.mark.django_db
@pytest.mark.parametrize('name', CHECKING_PAGES)
@pytest.mark.parametrize('typed, field, error', TYPED_ROWS)
def test_typed_row_shows_its_error(reserving_client, issue_revision, name,
                                   typed, field, error):
    """
    A page that comes back for an error elsewhere still shows the error of
    a credits row the person typed something in.
    """
    url, action, values = _page(name, issue_revision)
    data = _browser_post(reserving_client, url, page_count='abc', **values)
    data.update({ROW + key: [value] for key, value in typed.items()})

    response = reserving_client.post(action, data)

    assert response.status_code == 200
    assert response.context['form'].errors['page_count'] == \
        ['Enter a number.']
    assert response.context['credits_formset'][0].errors.get(field) == \
        [error]
    assert error in response.content.decode()


@pytest.mark.django_db
def test_blanked_credit_shows_its_errors(reserving_client, issue_revision):
    """
    A credit of the change whose creator and credit description the person
    blanked still shows its errors when the page comes back.
    """
    credit = IssueCreditRevision.objects.create(
      changeset=issue_revision.changeset, issue_revision=issue_revision,
      creator=_creator_name('Some Creator'),
      credit_type_id=CREDIT_TYPES['editing'], credit_name='associate editor')
    url, action, values = _page('edit_revision', issue_revision)
    data = _browser_post(reserving_client, url, page_count='abc', **values)
    assert data[ROW + 'id'] == [str(credit.id)]
    data.update({ROW + 'creator': [''], ROW + 'credit_name': ['']})

    response = reserving_client.post(action, data)

    assert response.status_code == 200
    errors = response.context['credits_formset'][0].errors
    assert errors.get('creator') == [REQUIRED]
    assert errors.get('credit_name') == [REQUIRED]
    assert REQUIRED in response.content.decode()
