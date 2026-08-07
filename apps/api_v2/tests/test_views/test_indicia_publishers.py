# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the indicia publisher v2 endpoints."""

import pytest
from django.urls import reverse

from apps.gcd.models import IndiciaPublisher, Publisher
from apps.stddata.models import Country


@pytest.fixture
def other_country(db):
    """Return a second country for indicia publisher view tests."""
    obj, _ = Country.objects.get_or_create(
        code='yy',
        defaults={'name': 'Other Country'},
    )
    return obj


def _create_indicia_publisher(
    *,
    publisher,
    country,
    name='Test Indicia Publisher',
    year_began=1960,
    year_ended=None,
    is_surrogate=False,
    deleted=False,
):
    """Create a minimal indicia publisher row for view tests."""
    return IndiciaPublisher.objects.create(
        name=name,
        year_began=year_began,
        year_ended=year_ended,
        notes='',
        parent=publisher,
        country=country,
        is_surrogate=is_surrogate,
        deleted=deleted,
    )


def test_indicia_publisher_list_returns_paginated_results(
    api_client,
    publisher,
    country,
):
    """The list endpoint is anonymous, paginated, and trimmed."""
    indicia_publisher = _create_indicia_publisher(
        publisher=publisher,
        country=country,
    )

    response = api_client.get(reverse('indicia-publisher-list'))

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['next'] is None
    assert response.data['previous'] is None
    assert len(response.data['results']) == 1
    result = response.data['results'][0]
    assert result['id'] == indicia_publisher.pk
    assert result['parent'] == {
        'id': publisher.pk,
        'name': publisher.name,
    }
    assert result['country'] == country.code
    assert 'notes' not in result
    assert 'keywords' not in result


def test_indicia_publisher_detail_returns_expected_payload(
    authenticated_client,
    publisher,
    country,
):
    """The detail endpoint returns descriptive and uncertainty fields."""
    indicia_publisher = _create_indicia_publisher(
        publisher=publisher,
        country=country,
        is_surrogate=True,
    )
    indicia_publisher.year_began_uncertain = True
    indicia_publisher.year_overall_began = 1955
    indicia_publisher.year_overall_ended = 1985
    indicia_publisher.year_overall_ended_uncertain = True
    indicia_publisher.url = 'https://example.com/imprint/'
    indicia_publisher.notes = 'Detail notes'
    indicia_publisher.issue_count = 21
    indicia_publisher.save()
    indicia_publisher.keywords.add('alpha', 'beta')

    response = authenticated_client.get(
        reverse(
            'indicia-publisher-detail',
            kwargs={'pk': indicia_publisher.pk},
        ),
    )

    assert response.status_code == 200
    assert response.data['id'] == indicia_publisher.pk
    assert response.data['parent'] == {
        'id': publisher.pk,
        'name': publisher.name,
    }
    assert response.data['country'] == country.code
    assert response.data['is_surrogate'] is True
    assert response.data['year_began_uncertain'] is True
    assert response.data['year_overall_began'] == 1955
    assert response.data['year_overall_ended'] == 1985
    assert response.data['year_overall_ended_uncertain'] is True
    assert response.data['url'] == 'https://example.com/imprint/'
    assert response.data['notes'] == 'Detail notes'
    assert response.data['issue_count'] == 21
    assert set(response.data['keywords']) == {'alpha', 'beta'}


def test_indicia_publisher_list_applies_filter_query_params(
    authenticated_client,
    publisher,
    country,
    other_country,
):
    """The list endpoint applies the complete filter contract."""
    other_parent = Publisher.objects.create(
        name='Other Publisher',
        year_began=1940,
        notes='',
        country=country,
    )
    matching = _create_indicia_publisher(
        publisher=publisher,
        country=country,
        name='Marvel Comics Group',
        year_began=1960,
        year_ended=1980,
        is_surrogate=True,
    )
    _create_indicia_publisher(
        publisher=other_parent,
        country=other_country,
        name='Different Imprint',
        year_began=1940,
    )

    response = authenticated_client.get(
        reverse('indicia-publisher-list'),
        {
            'name': 'marvel',
            'parent': str(publisher.pk),
            'country': country.code,
            'is_surrogate': 'true',
            'year_began': '1960',
            'year_ended': '1980',
        },
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == matching.pk


def test_indicia_publisher_endpoints_hide_soft_deleted_records(
    api_client,
    publisher,
    country,
):
    """Soft-deleted rows disappear from list and detail responses."""
    visible = _create_indicia_publisher(
        publisher=publisher,
        country=country,
        name='Visible Imprint',
    )
    deleted = _create_indicia_publisher(
        publisher=publisher,
        country=country,
        name='Deleted Imprint',
        deleted=True,
    )

    list_response = api_client.get(reverse('indicia-publisher-list'))
    detail_response = api_client.get(
        reverse(
            'indicia-publisher-detail',
            kwargs={'pk': deleted.pk},
        ),
    )

    assert list_response.status_code == 200
    assert list_response.data['count'] == 1
    assert list_response.data['results'][0]['id'] == visible.pk
    assert detail_response.status_code == 404


def test_indicia_publisher_list_returns_304_for_if_modified_since(
    authenticated_client,
    publisher,
    country,
):
    """List responses support Last-Modified cache validation."""
    _create_indicia_publisher(
        publisher=publisher,
        country=country,
    )

    response = authenticated_client.get(reverse('indicia-publisher-list'))

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('indicia-publisher-list'),
        HTTP_IF_MODIFIED_SINCE=response['Last-Modified'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''


def test_indicia_publisher_detail_returns_304_for_if_none_match(
    authenticated_client,
    publisher,
    country,
):
    """Detail responses support ETag cache validation."""
    indicia_publisher = _create_indicia_publisher(
        publisher=publisher,
        country=country,
    )

    response = authenticated_client.get(
        reverse(
            'indicia-publisher-detail',
            kwargs={'pk': indicia_publisher.pk},
        ),
    )

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse(
            'indicia-publisher-detail',
            kwargs={'pk': indicia_publisher.pk},
        ),
        HTTP_IF_NONE_MATCH=response['ETag'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''
