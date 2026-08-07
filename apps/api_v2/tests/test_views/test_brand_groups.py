# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the brand group v2 endpoints."""

from django.urls import reverse

from apps.gcd.models import Brand, BrandGroup, Publisher


def _create_brand_group(
    *,
    publisher,
    name='Test Brand Group',
    year_began=1960,
    year_ended=None,
    deleted=False,
):
    """Create a minimal brand group row for view tests."""
    return BrandGroup.objects.create(
        name=name,
        year_began=year_began,
        year_ended=year_ended,
        notes='',
        parent=publisher,
        deleted=deleted,
    )


def _create_emblem(
    brand_group,
    *,
    name,
    generic=False,
    deleted=False,
):
    """Create a Brand attached as an emblem of ``brand_group``."""
    emblem = Brand.objects.create(
        name=name,
        generic=generic,
        year_began=1970,
        notes='',
        deleted=deleted,
    )
    emblem.group.add(brand_group)
    return emblem


def test_brand_group_list_returns_paginated_results(
    api_client,
    publisher,
):
    """The list endpoint is anonymous, paginated, and trimmed."""
    brand_group = _create_brand_group(publisher=publisher)

    response = api_client.get(reverse('brand-group-list'))

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['next'] is None
    assert response.data['previous'] is None
    assert len(response.data['results']) == 1
    result = response.data['results'][0]
    assert result['id'] == brand_group.pk
    assert result['parent'] == {
        'id': publisher.pk,
        'name': publisher.name,
    }
    assert 'notes' not in result
    assert 'keywords' not in result
    assert 'emblems' not in result


def test_brand_group_detail_returns_expected_payload(
    authenticated_client,
    publisher,
):
    """The detail endpoint returns descriptive fields and active emblems."""
    brand_group = _create_brand_group(publisher=publisher)
    brand_group.year_began_uncertain = True
    brand_group.year_overall_began = 1955
    brand_group.year_overall_ended = 1985
    brand_group.year_overall_ended_uncertain = True
    brand_group.url = 'https://example.com/group/'
    brand_group.notes = 'Detail notes'
    brand_group.issue_count = 21
    brand_group.save()
    brand_group.keywords.add('alpha', 'beta')
    beta = _create_emblem(
        brand_group,
        name='Beta Emblem',
        generic=True,
    )
    alpha = _create_emblem(brand_group, name='Alpha Emblem')
    _create_emblem(
        brand_group,
        name='Deleted Emblem',
        deleted=True,
    )

    response = authenticated_client.get(
        reverse(
            'brand-group-detail',
            kwargs={'pk': brand_group.pk},
        ),
    )

    assert response.status_code == 200
    assert response.data['id'] == brand_group.pk
    assert response.data['parent'] == {
        'id': publisher.pk,
        'name': publisher.name,
    }
    assert response.data['year_began_uncertain'] is True
    assert response.data['year_overall_began'] == 1955
    assert response.data['year_overall_ended'] == 1985
    assert response.data['year_overall_ended_uncertain'] is True
    assert response.data['url'] == 'https://example.com/group/'
    assert response.data['notes'] == 'Detail notes'
    assert response.data['issue_count'] == 21
    assert set(response.data['keywords']) == {'alpha', 'beta'}
    assert [emblem['id'] for emblem in response.data['emblems']] == [
        alpha.pk,
        beta.pk,
    ]


def test_brand_group_list_applies_filter_query_params(
    authenticated_client,
    publisher,
    country,
):
    """The list endpoint applies the complete filter contract."""
    other_parent = Publisher.objects.create(
        name='Other Publisher',
        year_began=1940,
        notes='',
        country=country,
    )
    matching = _create_brand_group(
        publisher=publisher,
        name='Marvel Comics Group',
        year_began=1960,
        year_ended=1980,
    )
    _create_brand_group(
        publisher=other_parent,
        name='Different Group',
        year_began=1940,
    )

    response = authenticated_client.get(
        reverse('brand-group-list'),
        {
            'name': 'marvel',
            'parent': str(publisher.pk),
            'year_began': '1960',
            'year_ended': '1980',
        },
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == matching.pk


def test_brand_group_endpoints_hide_soft_deleted_records(
    api_client,
    publisher,
):
    """Soft-deleted rows disappear from list and detail responses."""
    visible = _create_brand_group(
        publisher=publisher,
        name='Visible Group',
    )
    deleted = _create_brand_group(
        publisher=publisher,
        name='Deleted Group',
        deleted=True,
    )

    list_response = api_client.get(reverse('brand-group-list'))
    detail_response = api_client.get(
        reverse(
            'brand-group-detail',
            kwargs={'pk': deleted.pk},
        ),
    )

    assert list_response.status_code == 200
    assert list_response.data['count'] == 1
    assert list_response.data['results'][0]['id'] == visible.pk
    assert detail_response.status_code == 404


def test_brand_group_list_returns_304_for_if_modified_since(
    authenticated_client,
    publisher,
):
    """List responses support Last-Modified cache validation."""
    _create_brand_group(publisher=publisher)

    response = authenticated_client.get(reverse('brand-group-list'))

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('brand-group-list'),
        HTTP_IF_MODIFIED_SINCE=response['Last-Modified'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''


def test_brand_group_detail_returns_304_for_if_none_match(
    authenticated_client,
    publisher,
):
    """Detail responses support ETag cache validation."""
    brand_group = _create_brand_group(publisher=publisher)

    response = authenticated_client.get(
        reverse(
            'brand-group-detail',
            kwargs={'pk': brand_group.pk},
        ),
    )

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse(
            'brand-group-detail',
            kwargs={'pk': brand_group.pk},
        ),
        HTTP_IF_NONE_MATCH=response['ETag'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''
