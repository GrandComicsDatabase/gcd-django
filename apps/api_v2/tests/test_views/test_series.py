"""Tests for the series v2 endpoints."""

import pytest
from django.urls import reverse

from apps.gcd.models import Issue, Publisher, Series, SeriesPublicationType
from apps.stddata.models import Country, Language


@pytest.fixture
def other_country(db):
    """Return a second country for series view tests."""
    obj, _ = Country.objects.get_or_create(
        code='yy',
        defaults={'name': 'Other Country'},
    )
    return obj


@pytest.fixture
def other_language(db):
    """Return a second language for series view tests."""
    obj, _ = Language.objects.get_or_create(
        code='yy',
        defaults={'name': 'Other Language'},
    )
    return obj


@pytest.fixture
def series_publication_type(db):
    """Return a publication type for series view tests."""
    return SeriesPublicationType.objects.create(
        name='Comic Book',
        notes='',
    )


def _create_issue(series, *, sort_code, deleted=False):
    """Create a minimal issue row for view tests."""
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


def _create_series(
    *,
    country,
    language,
    name,
    publication_type,
    publisher,
    year_began,
    year_ended=None,
    deleted=False,
):
    """Create a minimal series row for view tests."""
    return Series.objects.create(
        name=name,
        sort_name=name,
        year_began=year_began,
        year_ended=year_ended,
        publication_dates='1990 - present',
        notes='',
        tracking_notes='',
        country=country,
        language=language,
        publisher=publisher,
        publication_type=publication_type,
        deleted=deleted,
    )


def test_series_list_returns_paginated_results(
    api_client,
    series,
    series_publication_type,
):
    """The list endpoint is anon-readable and paginated."""
    series.publication_type = series_publication_type
    series.issue_count = 2
    series.save()
    first_issue = _create_issue(series, sort_code=20)
    second_issue = _create_issue(series, sort_code=10)
    _create_issue(series, sort_code=30, deleted=True)
    series.keywords.add('alpha')

    response = api_client.get(reverse('series-list'))

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['next'] is None
    assert response.data['previous'] is None
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['id'] == series.pk
    assert response.data['results'][0]['country'] == series.country.code
    assert response.data['results'][0]['language'] == series.language.code
    assert response.data['results'][0]['publisher'] == {
        'id': series.publisher_id,
        'name': series.publisher.name,
    }
    assert response.data['results'][0]['publication_type'] == 'Comic Book'
    assert response.data['results'][0]['active_issue_ids'] == [
        second_issue.pk,
        first_issue.pk,
    ]


def test_series_detail_returns_expected_payload(
    api_client,
    series,
    series_publication_type,
):
    """The detail endpoint returns the series serializer payload."""
    series.publication_type = series_publication_type
    series.color = 'Color'
    series.dimensions = '7.25" x 10.5"'
    series.paper_stock = 'Glossy'
    series.binding = 'Saddle-stitched'
    series.publishing_format = 'Ongoing'
    series.notes = 'Detail notes'
    series.issue_count = 2
    series.save()
    first_issue = _create_issue(series, sort_code=20)
    second_issue = _create_issue(series, sort_code=10)
    series.keywords.add('alpha', 'beta')

    response = api_client.get(
        reverse('series-detail', kwargs={'pk': series.pk}),
    )

    assert response.status_code == 200
    assert response.data['id'] == series.pk
    assert response.data['name'] == series.name
    assert response.data['publisher'] == {
        'id': series.publisher_id,
        'name': series.publisher.name,
    }
    assert response.data['publication_type'] == 'Comic Book'
    assert response.data['color'] == 'Color'
    assert response.data['dimensions'] == '7.25" x 10.5"'
    assert response.data['paper_stock'] == 'Glossy'
    assert response.data['binding'] == 'Saddle-stitched'
    assert response.data['publishing_format'] == 'Ongoing'
    assert response.data['issue_count'] == 2
    assert response.data['active_issue_ids'] == [
        second_issue.pk,
        first_issue.pk,
    ]
    assert set(response.data['keywords']) == {'alpha', 'beta'}


def test_series_list_applies_filter_query_params(
    api_client,
    country,
    other_country,
    language,
    other_language,
    publisher,
    series_publication_type,
):
    """The list endpoint applies django-filter query params."""
    other_publisher = Publisher.objects.create(
        name='Other Publisher',
        year_began=1940,
        notes='',
        country=country,
    )
    other_publication_type = SeriesPublicationType.objects.create(
        name='Magazine',
        notes='',
    )
    matching = _create_series(
        country=country,
        language=language,
        name='Batman Adventures',
        publication_type=series_publication_type,
        publisher=publisher,
        year_began=1992,
    )
    _create_series(
        country=other_country,
        language=language,
        name='Batman Adventures',
        publication_type=series_publication_type,
        publisher=publisher,
        year_began=1992,
    )
    _create_series(
        country=country,
        language=other_language,
        name='Batman Adventures',
        publication_type=series_publication_type,
        publisher=publisher,
        year_began=1992,
    )
    _create_series(
        country=country,
        language=language,
        name='Batman Adventures',
        publication_type=series_publication_type,
        publisher=other_publisher,
        year_began=1992,
    )
    _create_series(
        country=country,
        language=language,
        name='Batman Adventures',
        publication_type=other_publication_type,
        publisher=publisher,
        year_began=1992,
    )

    response = api_client.get(
        reverse('series-list'),
        {
            'name': 'batman',
            'country': country.code,
            'language': language.code,
            'publisher': str(publisher.pk),
            'publication_type': str(series_publication_type.pk),
        },
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == matching.pk


def test_series_endpoints_hide_soft_deleted_records(
    api_client,
    country,
    language,
    publisher,
    series_publication_type,
):
    """Soft-deleted series disappear from list and detail responses."""
    visible = _create_series(
        country=country,
        language=language,
        name='Visible Series',
        publication_type=series_publication_type,
        publisher=publisher,
        year_began=1990,
    )
    deleted = _create_series(
        country=country,
        language=language,
        name='Deleted Series',
        publication_type=series_publication_type,
        publisher=publisher,
        year_began=1991,
        deleted=True,
    )

    list_response = api_client.get(reverse('series-list'))
    detail_response = api_client.get(
        reverse('series-detail', kwargs={'pk': deleted.pk}),
    )

    assert list_response.status_code == 200
    assert list_response.data['count'] == 1
    assert list_response.data['results'][0]['id'] == visible.pk
    assert detail_response.status_code == 404


def test_series_list_returns_304_for_if_modified_since(
    authenticated_client,
    series,
):
    """List responses support Last-Modified cache validation."""
    response = authenticated_client.get(reverse('series-list'))

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('series-list'),
        HTTP_IF_MODIFIED_SINCE=response['Last-Modified'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''


def test_series_detail_returns_304_for_if_none_match(
    authenticated_client,
    series,
):
    """Detail responses support ETag cache validation."""
    response = authenticated_client.get(
        reverse('series-detail', kwargs={'pk': series.pk}),
    )

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('series-detail', kwargs={'pk': series.pk}),
        HTTP_IF_NONE_MATCH=response['ETag'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''
