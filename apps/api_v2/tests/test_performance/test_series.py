"""Performance tests for series endpoints."""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import Issue, Series


def _create_issue(series, *, sort_code):
    """Create a minimal issue row for performance tests."""
    return Issue.objects.create(
        number=str(sort_code),
        title='',
        volume='',
        isbn='',
        valid_isbn='',
        variant_name='',
        barcode='',
        publication_date='',
        key_date='',
        on_sale_date='',
        sort_code=sort_code,
        indicia_frequency='',
        price='',
        editing='',
        notes='',
        indicia_printer_sourced_by='',
        series=series,
    )


def test_series_list_query_count(api_client, publisher, country, language):
    """The series list stays on the expected query budget."""
    first = Series.objects.create(
        name='Alpha Series',
        sort_name='Alpha Series',
        year_began=1990,
        publication_dates='1990 - present',
        notes='',
        tracking_notes='',
        country=country,
        language=language,
        publisher=publisher,
    )
    second = Series.objects.create(
        name='Beta Series',
        sort_name='Beta Series',
        year_began=1991,
        publication_dates='1991 - present',
        notes='',
        tracking_notes='',
        country=country,
        language=language,
        publisher=publisher,
    )
    first.keywords.add('alpha')
    second.keywords.add('beta')
    _create_issue(first, sort_code=10)
    _create_issue(second, sort_code=20)

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(reverse('series-list'))

    assert response.status_code == 200
    assert len(context) == 5


def test_series_detail_query_count(api_client, series):
    """The series detail endpoint avoids lazy-loading regressions."""
    series.keywords.add('detail')
    _create_issue(series, sort_code=10)

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(
            reverse('series-detail', kwargs={'pk': series.pk}),
        )

    assert response.status_code == 200
    assert len(context) == 4
