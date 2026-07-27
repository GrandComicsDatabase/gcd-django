# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the Brand v2 endpoints."""

from django.urls import reverse

from apps.gcd.models import Brand, BrandGroup, BrandUse, Publisher


def _create_brand(
    *,
    name='Test Brand',
    generic=False,
    year_began=1960,
    year_ended=None,
    deleted=False,
):
    """Create a minimal Brand row for view tests."""
    return Brand.objects.create(
        name=name,
        generic=generic,
        year_began=year_began,
        year_ended=year_ended,
        notes='',
        deleted=deleted,
    )


def _create_brand_group(*, publisher, name, deleted=False):
    """Create a Brand Group for view relationship tests."""
    return BrandGroup.objects.create(
        name=name,
        year_began=1950,
        notes='',
        parent=publisher,
        deleted=deleted,
    )


def test_brand_list_returns_paginated_results(api_client, db):
    """The list endpoint is anonymous, paginated, and trimmed."""
    brand = _create_brand(generic=True)

    response = api_client.get(reverse('brand-list'))

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['next'] is None
    assert response.data['previous'] is None
    assert len(response.data['results']) == 1
    result = response.data['results'][0]
    assert result['id'] == brand.pk
    assert result['generic'] is True
    assert 'notes' not in result
    assert 'keywords' not in result
    assert 'groups' not in result
    assert 'uses' not in result


def test_brand_detail_returns_expected_payload(
    authenticated_client,
    publisher,
    country,
):
    """The detail endpoint returns descriptive and relationship fields."""
    brand = _create_brand(generic=True)
    brand.year_began_uncertain = True
    brand.year_overall_began = 1955
    brand.year_overall_ended = 1985
    brand.year_overall_ended_uncertain = True
    brand.url = 'https://example.com/brand/'
    brand.notes = 'Detail notes'
    brand.issue_count = 21
    brand.save()
    brand.keywords.add('alpha', 'beta')
    alpha_publisher = Publisher.objects.create(
        name='Alpha Publisher',
        year_began=1940,
        notes='',
        country=country,
    )
    deleted_publisher = Publisher.objects.create(
        name='Deleted Publisher',
        year_began=1940,
        notes='',
        country=country,
        deleted=True,
    )
    alpha_group = _create_brand_group(
        publisher=alpha_publisher,
        name='Alpha Group',
    )
    beta_group = _create_brand_group(
        publisher=publisher,
        name='Beta Group',
    )
    deleted_group = _create_brand_group(
        publisher=publisher,
        name='Deleted Group',
        deleted=True,
    )
    brand.group.add(beta_group, deleted_group, alpha_group)
    alpha_use = BrandUse.objects.create(
        emblem=brand,
        publisher=alpha_publisher,
        year_began=1970,
        notes='Alpha use',
    )
    test_use = BrandUse.objects.create(
        emblem=brand,
        publisher=publisher,
        year_began=1960,
        notes='Test use',
    )
    BrandUse.objects.create(
        emblem=brand,
        publisher=deleted_publisher,
        notes='Deleted publisher use',
    )

    response = authenticated_client.get(
        reverse('brand-detail', kwargs={'pk': brand.pk}),
    )

    assert response.status_code == 200
    assert response.data['id'] == brand.pk
    assert response.data['generic'] is True
    assert response.data['year_began_uncertain'] is True
    assert response.data['year_overall_began'] == 1955
    assert response.data['year_overall_ended'] == 1985
    assert response.data['year_overall_ended_uncertain'] is True
    assert response.data['url'] == 'https://example.com/brand/'
    assert response.data['notes'] == 'Detail notes'
    assert response.data['issue_count'] == 21
    assert set(response.data['keywords']) == {'alpha', 'beta'}
    assert [group['id'] for group in response.data['groups']] == [
        alpha_group.pk,
        beta_group.pk,
    ]
    assert [use['id'] for use in response.data['uses']] == [
        alpha_use.pk,
        test_use.pk,
    ]


def test_brand_list_applies_distinct_relationship_filters(
    authenticated_client,
    publisher,
):
    """The list endpoint applies all filters without duplicate Brands."""
    brand_group = _create_brand_group(
        publisher=publisher,
        name='Marvel Group',
    )
    matching = _create_brand(
        name='Marvel Comics',
        generic=True,
        year_began=1960,
        year_ended=1980,
    )
    matching.group.add(brand_group)
    BrandUse.objects.create(
        emblem=matching,
        publisher=publisher,
        year_began=1960,
        notes='',
    )
    BrandUse.objects.create(
        emblem=matching,
        publisher=publisher,
        year_began=1970,
        notes='',
    )
    _create_brand(name='Different Brand', year_began=1940)

    response = authenticated_client.get(
        reverse('brand-list'),
        {
            'name': 'marvel',
            'generic': 'true',
            'group': str(brand_group.pk),
            'publisher': str(publisher.pk),
            'year_began': '1960',
            'year_ended': '1980',
        },
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == matching.pk


def test_brand_endpoints_hide_soft_deleted_records(api_client, db):
    """Soft-deleted rows disappear from list and detail responses."""
    visible = _create_brand(name='Visible Brand')
    deleted = _create_brand(name='Deleted Brand', deleted=True)

    list_response = api_client.get(reverse('brand-list'))
    detail_response = api_client.get(
        reverse('brand-detail', kwargs={'pk': deleted.pk}),
    )

    assert list_response.status_code == 200
    assert list_response.data['count'] == 1
    assert list_response.data['results'][0]['id'] == visible.pk
    assert detail_response.status_code == 404


def test_brand_list_returns_304_for_if_modified_since(
    authenticated_client,
):
    """List responses support Last-Modified cache validation."""
    _create_brand()

    response = authenticated_client.get(reverse('brand-list'))

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('brand-list'),
        HTTP_IF_MODIFIED_SINCE=response['Last-Modified'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''


def test_brand_detail_returns_304_for_if_none_match(
    authenticated_client,
):
    """Detail responses support ETag cache validation."""
    brand = _create_brand()

    response = authenticated_client.get(
        reverse('brand-detail', kwargs={'pk': brand.pk}),
    )

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('brand-detail', kwargs={'pk': brand.pk}),
        HTTP_IF_NONE_MATCH=response['ETag'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''
