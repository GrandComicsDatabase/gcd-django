"""Parity and query bounds for the typed Series result page counts."""

import re

import pytest
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django_tables2.paginators import LazyPaginator

from apps.gcd.models import Cover, Issue, Publisher, Series
from apps.gcd.models.series import TypedSeriesPublisherTable
from apps.stddata.models import Country, Language


@pytest.fixture
def count_catalog(db):
    country, _ = Country.objects.get_or_create(
        code='xy', defaults={'name': 'Count test country'})
    language, _ = Language.objects.get_or_create(
        code='zzy', defaults={'name': 'Count test language'})
    publisher = Publisher.objects.create(
        name='Count test publisher', country=country, year_began=1991)

    def make_series(label, *, gallery=True, comics=True):
        return Series.objects.create(
            name=f'Page Count {label}', sort_name=f'Page Count {label}',
            publisher=publisher, country=country, language=language,
            year_began=1991, is_comics_publication=comics, has_gallery=gallery)

    def make_issue(series, number, *, indexed=10, **kwargs):
        issue = Issue.objects.create(
            series=series, number=str(number), sort_code=number,
            publication_date='January 1991', is_indexed=indexed, **kwargs)
        if not issue.deleted:
            series.issue_count += 1
            series.first_issue_id = series.first_issue_id or issue.id
            series.last_issue_id = issue.id
            series.save(update_fields=['issue_count', 'first_issue', 'last_issue'])
        return issue

    gallery = make_series('A Gallery')
    needs = make_series('B Needs')
    add = make_series('C Add', gallery=False)
    noncomic = make_series('D Noncomic', comics=False)
    empty = make_series('E Empty')

    other_base = make_issue(gallery, 1)
    Cover.objects.create(issue=other_base)

    base = make_issue(needs, 1)
    Cover.objects.create(issue=base, marked=True)
    Cover.objects.create(issue=base)
    # Cover.delete() clears marked; legacy/raw marked+deleted rows still
    # count as marked under the existing Series method.
    Cover.objects.create(issue=base, marked=True, deleted=True)
    make_issue(needs, 2, variant_of=base, variant_cover_status=1)
    external_variant = make_issue(needs, 3, indexed=2, variant_of=other_base)
    Cover.objects.create(issue=external_variant, deleted=True)
    hidden_issue = make_issue(needs, 4, deleted=True)
    Cover.objects.create(issue=hidden_issue, marked=True)
    threshold_issue = make_issue(needs, 5, indexed=1)
    Cover.objects.create(issue=threshold_issue)

    make_issue(add, 1)
    Cover.objects.create(issue=make_issue(noncomic, 1))
    return gallery, needs, add, noncomic, empty


def table_for(catalog, *, page=1, per_page=100, order='name'):
    results = Series.objects.filter(pk__in=[series.pk for series in catalog])
    table = TypedSeriesPublisherTable(results, order_by=order)
    table.paginate(paginator_class=LazyPaginator, per_page=per_page, page=page)
    return table


@pytest.mark.django_db
def test_batched_counts_match_legacy_and_all_cover_outcomes(count_catalog):
    gallery, needs, add, noncomic, empty = count_catalog
    table = table_for(count_catalog)
    legacy = {
        record.pk: (record.scan_count, record.cover_status_info(),
                    record.issue_indexed_count)
        for record in Series.objects.filter(
            pk__in=[series.pk for series in count_catalog])
    }
    with CaptureQueriesContext(connection) as captured:
        table.before_render(RequestFactory().get('/'))
        actual = {
            row.record.pk: (row.get_cell_value('covers'), row.get_cell('covers'),
                            row.record.issue_indexed_count)
            for row in table.paginated_rows
        }
    assert actual == legacy
    assert len(captured) == 3
    assert all('GROUP BY' in stat['sql'].upper() for stat in captured)

    assert actual[gallery.pk][0] == 1
    assert '>Gallery (1)</a>' in actual[gallery.pk][1]
    assert actual[needs.pk][0] == 4
    assert '>Have 4</a>' in actual[needs.pk][1]
    assert '>Need 5</a>' in actual[needs.pk][1]
    # Same-series variants, deleted issues and the threshold itself do not
    # count as indexed; base issues and cross-series variants do.
    assert actual[needs.pk][2] == 2
    assert '>Add</a>' in actual[add.pk][1]
    assert actual[noncomic.pk][:2] == (1, 'No Covers')
    assert actual[empty.pk][:2] == (0, 'No Covers')


@pytest.mark.django_db
def test_cover_sort_batches_only_the_displayed_page(count_catalog):
    gallery, needs, add, noncomic, _ = count_catalog
    first = table_for(count_catalog, order='-covers', per_page=2)
    second = table_for(count_catalog, order='-covers', page=2, per_page=2)
    assert [row.record.pk for row in first.paginated_rows] == [needs.pk, gallery.pk]
    expected_ids = {noncomic.pk, add.pk}
    assert [row.record.pk for row in second.paginated_rows] == [noncomic.pk, add.pk]

    with CaptureQueriesContext(connection) as captured:
        second.before_render(RequestFactory().get('/'))
        assert [row.get_cell_value('covers') for row in second.paginated_rows] == [1, 0]
    assert len(captured) == 3
    for stat in captured:
        sql = stat['sql'].lower().replace('`', '').replace('"', '')
        scope = re.search(r'\bseries_id\s+in\s*\(([\d, ]+)\)', sql)
        assert scope and {int(pk) for pk in scope[1].split(',')} <= expected_ids

    # TableExport consumes all rows, not just the current HTML page, and
    # uses numeric counts rather than status text or pagination look-ahead.
    headers, *exported = second.as_values()
    cover_index = headers.index('Covers')
    assert [row[cover_index] for row in exported] == [4, 1, 1, 0, 0]


@pytest.mark.django_db
def test_indexed_count_keeps_variants_of_a_deleted_cross_series_base(count_catalog):
    gallery, _, _, _, other = count_catalog
    base = Issue.objects.create(series=gallery, number='99', sort_code=99,
                                deleted=True)
    Issue.objects.bulk_create([
        Issue(series=other, number=str(number), sort_code=number,
              variant_of=base, is_indexed=indexed, deleted=deleted)
        for number, indexed, deleted in [
            (1, 2, False), (2, 3, False), (3, 1, False), (4, 10, True)
        ]
    ])
    table = table_for([other])
    table.before_render(RequestFactory().get('/'))

    count = table.paginated_rows[0].record.issue_indexed_count
    assert count == Series.objects.get(pk=other.pk).issue_indexed_count == 2


@pytest.mark.django_db
@pytest.mark.parametrize('inline', [False, True])
def test_typed_series_renders_the_optimized_table(
        count_catalog, client, settings, inline):
    settings.USE_ELASTICSEARCH = False
    _, needs, _, _, _ = count_catalog
    if inline:
        response = client.post('/series/search/', {'search': 'Page Count'})
    else:
        response = client.get('/series/name/Page%20Count/sort/alpha/',
                              {'sort': '-covers'})
    assert response.status_code == 200
    assert isinstance(response.context['table'], TypedSeriesPublisherTable)
    if not inline:
        assert response.context['table'].paginated_rows[0].record.pk == needs.pk
    assert b'>Have 4</a>' in response.content
    assert b'>Need 5</a>' in response.content
