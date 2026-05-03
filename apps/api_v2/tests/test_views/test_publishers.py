"""Tests for the publisher v2 endpoints."""

import pytest
from django.urls import reverse

from apps.gcd.models import Publisher
from apps.stddata.models import Country


@pytest.fixture
def other_country(db):
    """Return a second country for publisher view tests."""
    obj, _ = Country.objects.get_or_create(
        code='yy',
        defaults={'name': 'Other Country'},
    )
    return obj


def test_publisher_list_returns_paginated_results(api_client, publisher):
    """The list endpoint is anon-readable and paginated."""
    publisher.keywords.add('alpha')

    response = api_client.get(reverse('publisher-list'))

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['next'] is None
    assert response.data['previous'] is None
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['id'] == publisher.pk
    assert response.data['results'][0]['country'] == publisher.country.code


def test_publisher_detail_returns_expected_payload(api_client, publisher):
    """The detail endpoint returns the publisher serializer payload."""
    publisher.notes = 'Detail notes'
    publisher.series_count = 7
    publisher.issue_count = 21
    publisher.brand_count = 3
    publisher.indicia_publisher_count = 1
    publisher.save()
    publisher.keywords.add('alpha', 'beta')

    response = api_client.get(
        reverse('publisher-detail', kwargs={'pk': publisher.pk}),
    )

    assert response.status_code == 200
    assert response.data['id'] == publisher.pk
    assert response.data['name'] == publisher.name
    assert response.data['country'] == publisher.country.code
    assert response.data['series_count'] == 7
    assert response.data['issue_count'] == 21
    assert response.data['brand_count'] == 3
    assert response.data['indicia_publisher_count'] == 1
    assert set(response.data['keywords']) == {'alpha', 'beta'}


def test_publisher_list_applies_filter_query_params(
    api_client,
    country,
    other_country,
):
    """The list endpoint applies django-filter query params."""
    matching = Publisher.objects.create(
        name='Marvel Comics',
        year_began=1939,
        notes='',
        country=country,
    )
    Publisher.objects.create(
        name='DC Comics',
        year_began=1934,
        notes='',
        country=other_country,
    )

    response = api_client.get(
        reverse('publisher-list'),
        {'name': 'marvel', 'country': country.code},
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == matching.pk


def test_publisher_endpoints_hide_soft_deleted_records(api_client, country):
    """Soft-deleted publishers disappear from list and detail responses."""
    visible = Publisher.objects.create(
        name='Visible Publisher',
        year_began=1940,
        notes='',
        country=country,
    )
    deleted = Publisher.objects.create(
        name='Deleted Publisher',
        year_began=1950,
        notes='',
        country=country,
        deleted=True,
    )

    list_response = api_client.get(reverse('publisher-list'))
    detail_response = api_client.get(
        reverse('publisher-detail', kwargs={'pk': deleted.pk}),
    )

    assert list_response.status_code == 200
    assert list_response.data['count'] == 1
    assert list_response.data['results'][0]['id'] == visible.pk
    assert detail_response.status_code == 404


def test_publisher_list_returns_304_for_if_modified_since(
    authenticated_client,
    publisher,
):
    """List responses support Last-Modified cache validation."""
    response = authenticated_client.get(reverse('publisher-list'))

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('publisher-list'),
        HTTP_IF_MODIFIED_SINCE=response['Last-Modified'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''


def test_publisher_detail_returns_304_for_if_none_match(
    authenticated_client,
    publisher,
):
    """Detail responses support ETag cache validation."""
    response = authenticated_client.get(
        reverse('publisher-detail', kwargs={'pk': publisher.pk}),
    )

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('publisher-detail', kwargs={'pk': publisher.pk}),
        HTTP_IF_NONE_MATCH=response['ETag'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''
