# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the Brand serializers."""

import pytest

from apps.api_v2.serializers.brands import (
    BrandListSerializer,
    BrandSerializer,
)
from apps.gcd.models import Brand, BrandGroup, BrandUse, Publisher

pytestmark = pytest.mark.django_db


def _create_brand():
    """Create a Brand with complete contract data."""
    brand = Brand.objects.create(
        name='Test Brand',
        generic=True,
        year_began=1960,
        year_ended=1980,
        year_began_uncertain=True,
        year_ended_uncertain=False,
        year_overall_began=1955,
        year_overall_ended=1985,
        year_overall_began_uncertain=False,
        year_overall_ended_uncertain=True,
        notes='Brand notes',
        url='https://example.com/brand/',
        issue_count=42,
    )
    brand.keywords.add('alpha', 'beta')
    return brand


def _create_brand_group(*, publisher, name, deleted=False):
    """Create a Brand Group for nested relationship tests."""
    return BrandGroup.objects.create(
        name=name,
        year_began=1950,
        notes='',
        parent=publisher,
        deleted=deleted,
    )


def test_brand_list_serializer_exposes_trimmed_contract():
    """List rows include identity, browse, count, and timestamp fields."""
    brand = _create_brand()

    data = BrandListSerializer(brand).data

    assert set(data) == {
        'id',
        'name',
        'generic',
        'year_began',
        'year_ended',
        'issue_count',
        'created',
        'modified',
    }
    assert data['id'] == brand.pk
    assert data['name'] == brand.name
    assert data['generic'] is True
    assert data['year_began'] == 1960
    assert data['year_ended'] == 1980
    assert data['issue_count'] == 42
    assert data['created']
    assert data['modified']


def test_brand_detail_serializer_exposes_full_contract(
    publisher,
    country,
):
    """Detail rows add descriptive fields, groups, and Brand Uses."""
    brand = _create_brand()
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
        year_ended=1975,
        year_began_uncertain=True,
        year_ended_uncertain=False,
        notes='Alpha use',
    )
    test_use = BrandUse.objects.create(
        emblem=brand,
        publisher=publisher,
        year_began=1960,
        year_ended=1965,
        year_began_uncertain=False,
        year_ended_uncertain=True,
        notes='Test use',
    )
    BrandUse.objects.create(
        emblem=brand,
        publisher=deleted_publisher,
        notes='Deleted publisher use',
    )

    data = BrandSerializer(brand).data

    assert set(data) == {
        'id',
        'name',
        'generic',
        'year_began',
        'year_ended',
        'issue_count',
        'created',
        'modified',
        'year_began_uncertain',
        'year_ended_uncertain',
        'year_overall_began',
        'year_overall_ended',
        'year_overall_began_uncertain',
        'year_overall_ended_uncertain',
        'url',
        'notes',
        'keywords',
        'groups',
        'uses',
    }
    assert data['year_began_uncertain'] is True
    assert data['year_ended_uncertain'] is False
    assert data['year_overall_began'] == 1955
    assert data['year_overall_ended'] == 1985
    assert data['year_overall_began_uncertain'] is False
    assert data['year_overall_ended_uncertain'] is True
    assert data['url'] == 'https://example.com/brand/'
    assert data['notes'] == 'Brand notes'
    assert set(data['keywords']) == {'alpha', 'beta'}
    assert data['groups'] == [
        {
            'id': alpha_group.pk,
            'name': 'Alpha Group',
            'parent': {
                'id': alpha_publisher.pk,
                'name': 'Alpha Publisher',
            },
        },
        {
            'id': beta_group.pk,
            'name': 'Beta Group',
            'parent': {
                'id': publisher.pk,
                'name': publisher.name,
            },
        },
    ]
    assert [use['id'] for use in data['uses']] == [
        alpha_use.pk,
        test_use.pk,
    ]
    assert set(data['uses'][0]) == {
        'id',
        'publisher',
        'year_began',
        'year_ended',
        'year_began_uncertain',
        'year_ended_uncertain',
        'notes',
        'created',
        'modified',
    }
    assert data['uses'][0]['publisher'] == {
        'id': alpha_publisher.pk,
        'name': 'Alpha Publisher',
    }
    assert data['uses'][0]['year_began'] == 1970
    assert data['uses'][0]['year_ended'] == 1975
    assert data['uses'][0]['year_began_uncertain'] is True
    assert data['uses'][0]['year_ended_uncertain'] is False
    assert data['uses'][0]['notes'] == 'Alpha use'
    assert data['uses'][0]['created']
    assert data['uses'][0]['modified']
