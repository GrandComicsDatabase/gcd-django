"""
The publisher code numbers of an issue or a variant that is added.

A code number with an error comes back with its error on its row and
with what was typed, and nothing is saved.
"""
import pytest

from django.contrib.auth.models import Permission
from django.http import QueryDict
from django.urls import reverse

from apps.gcd.models import CodeNumberType, CreditType, Series
from apps.gcd.models.story import CREDIT_TYPES
from apps.oi.models import (Changeset, IssueRevision,
                            PublisherCodeNumberRevision)
from apps.oi.views import _add_form_data, _add_formset_data

FORMSETS = ['credits_formset', 'code_number_formset',
            'external_link_formset']
# An issue added to the series, a variant of one of its issues, and a
# variant saved together with a change of its issue.
WAYS = ['issue', 'variant', 'variant_with_base']


@pytest.fixture
def adding_client(client, any_indexer, any_added_issue):
    """
    A client logged in as an indexer who can reserve changes, for a series
    with publisher code numbers.
    """
    CreditType.objects.get_or_create(
      id=CREDIT_TYPES['editing'],
      defaults={'name': 'editing', 'sort_code': CREDIT_TYPES['editing']})
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    any_indexer.indexer.max_reservations = 10
    any_indexer.indexer.save()
    Series.objects.filter(id=any_added_issue.series.id).update(
      has_publisher_code_number=True)
    client.force_login(any_indexer)
    return client


def _add_page(way, issue):
    """
    Return the address of the page for the way of adding, the values its
    form needs, and the one of them that the page shows in a text box.
    """
    if way == 'issue':
        return (reverse('add_issue', kwargs={'series_id': issue.series.id}),
                {'number': '43'}, '43')
    values = {'variant_name': 'Some Variant'}
    if way == 'variant_with_base':
        values['edit_with_base'] = 'Save New Variant Issue And Edit Both'
    return (reverse('add_variant_issue', kwargs={'issue_id': issue.id}),
            values, 'Some Variant')


def _browser_post(client, url, values, code_number):
    """
    Return what a browser posts for the page at the address, with the
    values and the code number in the first code number row.
    """
    page = client.get(url)
    assert page.status_code == 200
    data = QueryDict(mutable=True)
    _add_form_data(data, page.context['form'])
    for name in FORMSETS:
        if page.context.get(name) is not None:
            _add_formset_data(data, page.context[name])
    for key, value in values.items():
        data[key] = value
    prefix = page.context['code_number_formset'].prefix
    for key, value in code_number.items():
        data['%s-0-%s' % (prefix, key)] = value
    return data


def _first_row(response):
    """Return the first code number row, as it is drawn."""
    marker = 'formset_row-' + response.context['code_number_formset'].prefix
    row = response.content.decode().split(marker, 2)[1]
    return row.split('<script', 1)[0]


def _counts():
    """Return how many changes, issue revisions and code numbers there are."""
    return (Changeset.objects.count(), IssueRevision.objects.count(),
            PublisherCodeNumberRevision.objects.count())


@pytest.mark.django_db
@pytest.mark.parametrize('way', WAYS)
def test_code_number_error_is_shown(adding_client, any_added_issue, way):
    """
    A code number without its type comes back with the error on its row
    and with what was typed, and nothing is saved.
    """
    url, values, typed = _add_page(way, any_added_issue)
    data = _browser_post(adding_client, url, values, {'number': '123'})
    before = _counts()

    response = adding_client.post(url, data)

    assert response.status_code == 200
    assert not response.context['form'].errors
    assert response.context['code_number_formset'][0].errors[
      'number_type'] == ['This field is required.']
    assert 'value="%s"' % typed in response.content.decode()
    row = _first_row(response)
    assert 'This field is required.' in row
    assert 'value="123"' in row
    assert _counts() == before


@pytest.mark.django_db
@pytest.mark.parametrize('way', WAYS)
def test_correct_code_number_is_saved(adding_client, any_added_issue, way):
    """A correct code number is saved with the added issue."""
    number_type = CodeNumberType.objects.create(name='Some Type')
    url, values, _ = _add_page(way, any_added_issue)
    data = _browser_post(adding_client, url, values,
                         {'number': '123', 'number_type': number_type.id})

    adding_client.post(url, data)

    code_number = PublisherCodeNumberRevision.objects.get()
    assert (code_number.number, code_number.number_type) == \
        ('123', number_type)
    assert code_number.issue_revision.issue is None
