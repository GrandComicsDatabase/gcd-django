"""
The rows of a variant added to an issue of an open change.

A credit, an external link or a publisher code number with an error comes
back with its error on its row and with what was typed, as on the page
that adds an issue, and nothing is saved.
"""
import pytest

from django.http import QueryDict
from django.urls import reverse

from apps.gcd.models import CodeNumberType, CreditType, ExternalSite, Series
from apps.gcd.models.creator import Creator, CreatorNameDetail
from apps.gcd.models.story import CREDIT_TYPES
from apps.oi import states
from apps.oi.models import (CTYPES, Changeset, ExternalLinkRevision,
                            IssueCreditRevision, IssueRevision,
                            PublisherCodeNumberRevision)
from apps.oi.views import _add_form_data, _add_formset_data
from apps.stddata.models import Date, Script

FORMSETS = ['credits_formset', 'code_number_formset',
            'external_link_formset']
LINK = 'https://example.com/some-page'


@pytest.fixture
def variant_page(client, any_indexer, any_added_issue):
    """
    The address of the page that adds a variant to an issue of an open
    change, with the indexer of the change logged in.
    """
    CreditType.objects.get_or_create(
      id=CREDIT_TYPES['editing'],
      defaults={'name': 'editing', 'sort_code': CREDIT_TYPES['editing']})
    changeset = Changeset.objects.create(
      change_type=CTYPES['issue'], indexer=any_indexer, state=states.OPEN)
    revision = IssueRevision.clone(any_added_issue, changeset=changeset)
    client.force_login(any_indexer)
    return reverse('add_variant_to_issue_revision',
                   kwargs={'changeset_id': changeset.id,
                           'issue_revision_id': revision.id})


@pytest.fixture
def code_numbers(any_added_issue):
    """The series of the issue has publisher code numbers."""
    Series.objects.filter(id=any_added_issue.series.id).update(
      has_publisher_code_number=True)


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


def _browser_post(client, url, rows):
    """
    Return what a browser posts for the page at the address, with a
    variant name and, for each list in rows, the values of its first row.
    """
    page = client.get(url)
    assert page.status_code == 200
    data = QueryDict(mutable=True)
    _add_form_data(data, page.context['form'])
    for name in FORMSETS:
        if page.context.get(name) is not None:
            _add_formset_data(data, page.context[name])
    data['variant_name'] = 'Some Variant'
    for name, values in rows.items():
        for key, value in values.items():
            data['%s-0-%s' % (page.context[name].prefix, key)] = value
    return data


def _first_row(response, name):
    """Return the first row of the list with the name, as it is drawn."""
    marker = 'formset_row-' + response.context[name].prefix
    row = response.content.decode().split(marker, 2)[1]
    return row.split('<script', 1)[0]


def _counts():
    """Return how many changes and revisions of issues and rows there are."""
    return (Changeset.objects.count(), IssueRevision.objects.count(),
            IssueCreditRevision.objects.count(),
            ExternalLinkRevision.objects.count(),
            PublisherCodeNumberRevision.objects.count())


def _check_refused(client, url, data, name, field, error, typed):
    """
    Post the data and check that the page comes back with the variant name
    and, on the first row of the list with the name, the error and the
    typed values; and that nothing is saved.
    """
    before = _counts()

    response = client.post(url, data)

    assert response.status_code == 200
    assert not response.context['form'].errors
    assert response.context[name][0].errors[field] == [error]
    assert 'value="Some Variant"' in response.content.decode()
    row = _first_row(response, name)
    for text in [error] + typed:
        assert text in row
    assert _counts() == before


@pytest.mark.django_db
@pytest.mark.parametrize('credit, field, error, typed', [
  ({}, 'credit_name', 'This field is required.', []),
  ({'credit_name': 'associate editor', 'credited_as': 'Some Name'},
   '__all__',
   'Is credited needs to be selected when entering a name as credited.',
   ['value="associate editor"', 'value="Some Name"'])])
def test_credit_error_is_shown(client, variant_page, credit, field, error,
                               typed):
    """
    A credit with an error comes back with its error on the credits row,
    and neither the variant nor the credit is saved.
    """
    credit = dict(credit, creator=_creator_name('Some Creator').id)
    data = _browser_post(client, variant_page, {'credits_formset': credit})
    _check_refused(client, variant_page, data, 'credits_formset', field,
                   error, typed + ['Some Creator'])


@pytest.mark.django_db
def test_link_error_is_shown(client, variant_page):
    """
    An external link without its site comes back with the error on the
    link row, and neither the variant nor the link is saved.
    """
    data = _browser_post(client, variant_page,
                         {'external_link_formset': {'link': LINK}})
    _check_refused(client, variant_page, data, 'external_link_formset',
                   'site', 'This field is required.', ['value="%s"' % LINK])


@pytest.mark.django_db
def test_code_number_error_is_shown(client, code_numbers, variant_page):
    """
    A publisher code number without its type comes back with the error on
    its row, and neither the variant nor the number is saved.
    """
    data = _browser_post(client, variant_page,
                         {'code_number_formset': {'number': '123'}})
    _check_refused(client, variant_page, data, 'code_number_formset',
                   'number_type', 'This field is required.',
                   ['value="123"'])


@pytest.mark.django_db
def test_correct_credit_is_saved(client, variant_page, any_added_issue):
    """A correct credit is saved with the variant."""
    name = _creator_name('Some Creator')
    data = _browser_post(client, variant_page,
                         {'credits_formset': {
                           'creator': name.id,
                           'credit_name': 'associate editor'}})

    response = client.post(variant_page, data)

    assert response.status_code == 302
    variant = IssueRevision.objects.get(variant_of=any_added_issue,
                                        issue=None)
    credit = variant.issue_credit_revisions.get()
    assert (credit.creator, credit.credit_name) == \
        (name, 'associate editor')


@pytest.mark.django_db
def test_correct_link_is_saved(client, variant_page, any_added_issue):
    """A correct external link is saved with the variant."""
    site = ExternalSite.objects.create(site='Some Site', matching='example')
    data = _browser_post(client, variant_page,
                         {'external_link_formset': {'site': site.id,
                                                    'link': LINK}})

    response = client.post(variant_page, data)

    assert response.status_code == 302
    variant = IssueRevision.objects.get(variant_of=any_added_issue,
                                        issue=None)
    link = variant.external_link_revisions.get()
    assert (link.site, link.link) == (site, LINK)


@pytest.mark.django_db
def test_correct_code_number_is_saved(client, code_numbers, variant_page,
                                      any_added_issue):
    """A correct publisher code number is saved with the variant."""
    number_type = CodeNumberType.objects.create(name='Some Type')
    data = _browser_post(client, variant_page,
                         {'code_number_formset': {
                           'number': '123', 'number_type': number_type.id}})

    response = client.post(variant_page, data)

    assert response.status_code == 302
    variant = IssueRevision.objects.get(variant_of=any_added_issue,
                                        issue=None)
    code_number = variant.publisher_code_number_revisions.get()
    assert (code_number.number, code_number.number_type) == \
        ('123', number_type)
