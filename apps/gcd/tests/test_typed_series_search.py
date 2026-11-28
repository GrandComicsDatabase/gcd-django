"""Regression checks for batched IDs and rendering typed Series search."""

import re
from unittest.mock import MagicMock

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.gcd.models import Issue, Publisher, Series, SeriesPublicationType
from apps.gcd.views import search
from apps.gcd.views.search_haystack import GcdNameQuery
from apps.stddata.models import Country, Language


class SearchHits:
    def __init__(self, values):
        self.values = values
        self.count_calls = 0
        self.slices = []

    def count(self):
        self.count_calls += 1
        return len(self.values)

    def __getitem__(self, key):
        assert isinstance(key, slice)
        self.slices.append((key.start, key.stop))
        return self.values[key]


def stub_haystack_search(monkeypatch, ids, term):
    hits = SearchHits(ids)
    queryset = MagicMock()
    filtered = queryset.filter.return_value
    modeled = filtered.models.return_value
    modeled.values_list.return_value = hits
    constructor = MagicMock(return_value=queryset)
    monkeypatch.setattr(search, 'SearchQuerySet', constructor)

    def verify_query():
        constructor.assert_called_once_with()
        queryset.filter.assert_called_once()
        query = queryset.filter.call_args.kwargs['name']
        assert isinstance(query, GcdNameQuery)
        assert query.query_string == term
        filtered.models.assert_called_once_with(Series)
        modeled.values_list.assert_called_once_with('pk', flat=True)

    return hits, verify_query


@pytest.mark.parametrize('size', [0, 499, 500, 501, 1000, 10000])
def test_series_search_ids_requests_only_needed_contiguous_batches(
        monkeypatch, size):
    # Haystack exposes text PKs. The first slice also supplies the hit count;
    # only request more slices within the reported count after that.
    ids = [str(i) for i in range(1, size + 1)]
    term = 'Batman'
    hits, verify_query = stub_haystack_search(monkeypatch, ids, term)

    assert list(search._series_search_ids(term)) == ids
    verify_query()
    assert hits.count_calls == 1
    assert hits.slices == [(0, 500)] + [
        (offset, min(offset + 500, size)) for offset in range(500, size, 500)
    ]


@pytest.mark.django_db
def test_typed_es_series_preserves_filters_pages_and_related_columns(
        client, settings, monkeypatch):
    settings.USE_ELASTICSEARCH = True
    country_a, _ = Country.objects.get_or_create(
        code='xa', defaults={'name': 'Typed Series Country A'})
    country_b, _ = Country.objects.get_or_create(
        code='xb', defaults={'name': 'Typed Series Country B'})
    language, _ = Language.objects.get_or_create(
        code='zz', defaults={'name': 'Typed Series Language'})
    publication_type = SeriesPublicationType.objects.create(name='Test type')
    publisher_a = Publisher.objects.create(
        name='Typed Publisher A', country=country_a, year_began=1991)
    publisher_b = Publisher.objects.create(
        name='Typed Publisher B', country=country_b, year_began=1991)
    term = 'Typed Example'
    Series.objects.bulk_create([
        Series(name=name, sort_name=name,
               # Make the Series country different from the publisher flag.
               country=country_a, language=language, year_began=1991,
               publisher=publisher_a if i < 101 else publisher_b,
               publication_type=publication_type)
        for i in range(102) for name in [f'{term} {i:03d}']
    ])
    all_series = list(Series.objects.filter(name__startswith=term)
                      .order_by('sort_name'))
    for series in all_series[-2:]:
        first = Issue.objects.create(series=series, number='1', sort_code=1,
                                     publication_date='April 1991')
        last = Issue.objects.create(series=series, number='2', sort_code=2,
                                    publication_date='March 1992')
        Series.objects.filter(pk=series.pk).update(
            first_issue=first, last_issue=last, issue_count=2)

    # Return reverse relevance order to ensure SQL still applies the UI's
    # alphabetical order to the complete result set before pagination.
    ids = [str(series.pk) for series in reversed(all_series)]
    _, verify_query = stub_haystack_search(monkeypatch, ids, term)
    url = '/series/name/Typed%20Example/sort/alpha/'
    with CaptureQueriesContext(connection) as captured:
        response = client.get(url, {'page': 2})

    verify_query()
    assert response.status_code == 200
    assert response.context['page'].paginator.count == 102
    body = response.content.decode()
    series_urls = [series.get_absolute_url() for series in all_series[-3:]]
    assert f'href="{series_urls[0]}"' not in body
    assert body.index(f'href="{series_urls[1]}"') < body.index(
        f'href="{series_urls[2]}"')
    assert body.count('April 1991 - March 1992') == 2
    assert 'Typed Publisher B' in body and '[T]' in body
    assert '/flags/xb.png' in body

    # The page still uses legitimate filter-choice lists and per-Series
    # counts, but no separately hydrated row FK lookups by primary key.
    for stat in captured:
        sql = stat['sql'].lower().replace('`', '').replace('"', '')
        assert not re.search(
            r'\bfrom (gcd_issue|gcd_series_publication_type|gcd_publisher|'
            r'stddata_country) where\s+\(*\1\.id\s*=', sql)
        # A full Series-row hydration belongs only to the bounded table page,
        # not the initial test for whether filter options should be rendered.
        if re.match(r'\s*select distinct gcd_series\.id, gcd_series\.created,',
                    sql):
            assert re.search(r'\blimit \d+\b', sql)

    filtered = client.get(url, {'publisher': publisher_b.pk})
    assert filtered.status_code == 200
    assert filtered.context['page'].paginator.count == 1
    assert f'href="{series_urls[2]}"'.encode() in filtered.content
    assert f'href="{series_urls[1]}"'.encode() not in filtered.content
