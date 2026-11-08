"""The indicia publisher and brand emblem lists of the multiple issue add."""
import json
import re

import pytest

from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.gcd.models import Brand, BrandUse, IndiciaPublisher
from apps.oi.forms import get_bulk_issue_revision_form
from apps.oi.models import IssueRevision

METHODS = ['number', 'volume', 'year', 'year_volume']

# For a series from 1990 to 1995.
DATED = [('before', 1970, 1985),
         ('during', 1985, 1992),
         ('after', 2000, None),
         ('undated', None, None)]


@pytest.fixture
def dated_choices(any_added_publisher, any_country):
    """Indicia publishers and brand emblems with the years in DATED."""
    for name, began, ended in DATED:
        IndiciaPublisher.objects.create(
          name=name, parent=any_added_publisher, country=any_country,
          year_began=began, year_ended=ended)
        brand = Brand.objects.create(name=name, year_began=began,
                                     year_ended=ended)
        BrandUse.objects.create(
          publisher=any_added_publisher, emblem=brand,
          year_began=began, year_ended=ended)


@pytest.fixture
def adding_client(client, any_indexer):
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)
    return client


def _end_series(series, year_ended):
    series.year_ended = year_ended
    series.save()
    return series


def _url(series, method='number'):
    return reverse('add_multiple_issues',
                   kwargs={'series_id': series.id, 'method': method})


def _page(client, series, method='number'):
    response = client.get(_url(series, method))
    assert response.status_code == 200
    return response


def _indicia_listing(response):
    field = response.context['form'].fields['indicia_publisher']
    return set(field.queryset.values_list('name', flat=True))


def _brand_listing(client, response):
    """Ask the autocomplete for the brand emblems as the browser does."""
    content = response.content.decode()
    conf = re.search(r'id="dal-forward-conf-for_id_brand_emblem">'
                     r'<script type="text/dal-forward-conf">(.*?)</script>',
                     content).group(1)
    forwarded = {}
    for field in json.loads(conf):
        hidden = re.search(r'<input[^>]*name="%s"[^>]*>' % field['src'],
                           content)
        # The browser skips a forwarded field which is not on the page.
        if hidden:
            forwarded[field['src']] = re.search(r'value="([^"]*)"',
                                                hidden.group(0)).group(1)
    listing = client.get(reverse('brand_emblem_autocomplete'),
                         {'forward': json.dumps(forwarded)})
    return {result['text'] for result in listing.json()['results']}


@pytest.mark.django_db
@pytest.mark.parametrize('method', METHODS)
def test_indicia_publishers_limited_to_series_years(
      adding_client, any_added_series, dated_choices, method):
    series = _end_series(any_added_series, 1995)

    response = _page(adding_client, series, method)

    assert _indicia_listing(response) == {'during', 'undated'}


@pytest.mark.django_db
@pytest.mark.parametrize('method', METHODS)
def test_brand_emblems_limited_to_series_years(
      adding_client, any_added_series, dated_choices, method):
    series = _end_series(any_added_series, 1995)

    response = _page(adding_client, series, method)

    assert _brand_listing(adding_client, response) == {'during', 'undated'}


@pytest.mark.django_db
def test_brand_emblems_of_single_year_series(
      adding_client, any_added_series, dated_choices):
    series = _end_series(any_added_series, 1990)

    response = _page(adding_client, series)

    assert _brand_listing(adding_client, response) == {'during', 'undated'}


@pytest.mark.django_db
@pytest.mark.parametrize('method', METHODS)
def test_ongoing_series_is_limited_by_its_start_only(
      adding_client, any_added_series, dated_choices, method):
    response = _page(adding_client, any_added_series, method)

    expected = {'during', 'after', 'undated'}
    assert _indicia_listing(response) == expected
    assert _brand_listing(adding_client, response) == expected


@pytest.mark.django_db
@pytest.mark.parametrize('name, added', [('during', 2), ('before', 0)])
def test_add_accepts_only_a_listed_indicia_publisher(
      adding_client, any_added_series, dated_choices, name, added):
    series = _end_series(any_added_series, 1995)
    indicia_publisher = IndiciaPublisher.objects.get(name=name)

    adding_client.post(_url(series), {
      'number_of_issues': 2,
      'indicia_publisher': indicia_publisher.id,
      'publisher_id': series.publisher.id,
      'year_began': series.year_began,
      'year_ended': series.year_ended,
      'comments': 'test',
      'issue_credit_revisions-TOTAL_FORMS': 0,
      'issue_credit_revisions-INITIAL_FORMS': 0,
    })

    assert IssueRevision.objects.filter(
      indicia_publisher=indicia_publisher).count() == added


@pytest.mark.django_db
def test_bulk_edit_lists_are_not_limited(any_added_series, dated_choices):
    """The issues of a bulk edit can be from other years than the series."""
    series = _end_series(any_added_series, 1995)

    form = get_bulk_issue_revision_form(series, 'bulk_edit')()

    assert (set(form.fields['indicia_publisher'].queryset
                .values_list('name', flat=True)) ==
            {'before', 'during', 'after', 'undated'})
    assert 'year_ended' not in form.fields
