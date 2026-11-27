# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the brand group serializers."""

from apps.api_v2.serializers.brand_groups import (
    BrandGroupListSerializer,
    BrandGroupSerializer,
)
from apps.gcd.models import Brand, BrandGroup


def _create_brand_group(publisher):
    """Create a brand group with complete contract data."""
    brand_group = BrandGroup.objects.create(
        name='Test Brand Group',
        year_began=1960,
        year_ended=1980,
        year_began_uncertain=True,
        year_ended_uncertain=False,
        year_overall_began=1955,
        year_overall_ended=1985,
        year_overall_began_uncertain=False,
        year_overall_ended_uncertain=True,
        notes='Brand group notes',
        url='https://example.com/brand-group/',
        parent=publisher,
        issue_count=42,
    )
    brand_group.keywords.add('alpha', 'beta')
    return brand_group


def _create_emblem(
    brand_group,
    *,
    name,
    generic=False,
    deleted=False,
    year_began=1970,
    year_ended=None,
):
    """Create a Brand attached as an emblem of ``brand_group``."""
    emblem = Brand.objects.create(
        name=name,
        generic=generic,
        year_began=year_began,
        year_ended=year_ended,
        notes='',
        deleted=deleted,
    )
    emblem.group.add(brand_group)
    return emblem


def test_brand_group_list_serializer_exposes_trimmed_contract(publisher):
    """List rows include identity, browse, count, and timestamp fields."""
    brand_group = _create_brand_group(publisher)

    data = BrandGroupListSerializer(brand_group).data

    assert set(data) == {
        'id',
        'name',
        'parent',
        'year_began',
        'year_ended',
        'issue_count',
        'created',
        'modified',
    }
    assert data['id'] == brand_group.pk
    assert data['name'] == brand_group.name
    assert data['parent'] == {
        'id': publisher.pk,
        'name': publisher.name,
    }
    assert data['year_began'] == 1960
    assert data['year_ended'] == 1980
    assert data['issue_count'] == 42
    assert data['created']
    assert data['modified']


def test_brand_group_detail_serializer_exposes_full_contract(publisher):
    """Detail rows add descriptive fields and ordered active emblems."""
    brand_group = _create_brand_group(publisher)
    beta = _create_emblem(
        brand_group,
        name='Beta Emblem',
        generic=True,
        year_began=1975,
        year_ended=1980,
    )
    alpha = _create_emblem(
        brand_group,
        name='Alpha Emblem',
        year_began=1965,
        year_ended=1970,
    )
    _create_emblem(
        brand_group,
        name='Deleted Emblem',
        deleted=True,
    )

    data = BrandGroupSerializer(brand_group).data

    assert set(data) == {
        'id',
        'name',
        'parent',
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
        'emblems',
    }
    assert data['parent'] == {
        'id': publisher.pk,
        'name': publisher.name,
    }
    assert data['year_began_uncertain'] is True
    assert data['year_ended_uncertain'] is False
    assert data['year_overall_began'] == 1955
    assert data['year_overall_ended'] == 1985
    assert data['year_overall_began_uncertain'] is False
    assert data['year_overall_ended_uncertain'] is True
    assert data['url'] == 'https://example.com/brand-group/'
    assert data['notes'] == 'Brand group notes'
    assert set(data['keywords']) == {'alpha', 'beta'}
    assert data['emblems'] == [
        {
            'id': alpha.pk,
            'name': 'Alpha Emblem',
            'generic': False,
            'year_began': 1965,
            'year_ended': 1970,
        },
        {
            'id': beta.pk,
            'name': 'Beta Emblem',
            'generic': True,
            'year_began': 1975,
            'year_ended': 1980,
        },
    ]
