"""Tests for the series serializer."""

import pytest

from apps.api_v2.serializers.series import SeriesSerializer
from apps.gcd.models import Issue, SeriesPublicationType


@pytest.fixture
def series_publication_type(db):
    """Return a publication type for series serializer tests."""
    return SeriesPublicationType.objects.create(
        name='Comic Book',
        notes='',
    )


def _create_issue(series, *, sort_code, deleted=False):
    """Create a minimal issue row for serializer tests."""
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
        deleted=deleted,
    )


def test_series_serializer_exposes_prd_fields(
    series,
    country,
    language,
    publisher,
    series_publication_type,
):
    """The series serializer emits the Sprint 1 series contract."""
    series.publication_type = series_publication_type
    series.color = 'Color'
    series.dimensions = '7.25" x 10.5"'
    series.paper_stock = 'Glossy'
    series.binding = 'Saddle-stitched'
    series.publishing_format = 'Ongoing'
    series.notes = 'Series notes'
    series.issue_count = 2
    series.save()
    first_issue = _create_issue(series, sort_code=20)
    second_issue = _create_issue(series, sort_code=10)
    _create_issue(series, sort_code=30, deleted=True)
    series.keywords.add('alpha', 'beta')

    data = SeriesSerializer(series).data

    assert set(data) == {
        'id',
        'name',
        'sort_name',
        'year_began',
        'year_ended',
        'country',
        'language',
        'publisher',
        'publication_type',
        'color',
        'dimensions',
        'paper_stock',
        'binding',
        'publishing_format',
        'notes',
        'issue_count',
        'active_issue_ids',
        'keywords',
        'created',
        'modified',
    }
    assert data['id'] == series.pk
    assert data['name'] == 'Test Series'
    assert data['sort_name'] == 'Test Series'
    assert data['country'] == country.code
    assert data['language'] == language.code
    assert data['publisher'] == {
        'id': publisher.pk,
        'name': publisher.name,
    }
    assert data['publication_type'] == 'Comic Book'
    assert data['color'] == 'Color'
    assert data['dimensions'] == '7.25" x 10.5"'
    assert data['paper_stock'] == 'Glossy'
    assert data['binding'] == 'Saddle-stitched'
    assert data['publishing_format'] == 'Ongoing'
    assert data['notes'] == 'Series notes'
    assert data['issue_count'] == 2
    assert data['active_issue_ids'] == [second_issue.pk, first_issue.pk]
    assert set(data['keywords']) == {'alpha', 'beta'}
    assert data['created']
    assert data['modified']
