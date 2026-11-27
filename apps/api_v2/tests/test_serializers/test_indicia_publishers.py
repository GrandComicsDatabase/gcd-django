# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the indicia publisher serializers."""

from apps.api_v2.serializers.indicia_publishers import (
    IndiciaPublisherListSerializer,
    IndiciaPublisherSerializer,
)
from apps.gcd.models import IndiciaPublisher


def _create_indicia_publisher(publisher, country):
    """Create an indicia publisher with complete contract data."""
    indicia_publisher = IndiciaPublisher.objects.create(
        name='Test Indicia Publisher',
        year_began=1960,
        year_ended=1980,
        year_began_uncertain=True,
        year_ended_uncertain=False,
        year_overall_began=1955,
        year_overall_ended=1985,
        year_overall_began_uncertain=False,
        year_overall_ended_uncertain=True,
        notes='Indicia publisher notes',
        url='https://example.com/indicia-publisher/',
        parent=publisher,
        country=country,
        is_surrogate=True,
        issue_count=42,
    )
    indicia_publisher.keywords.add('alpha', 'beta')
    return indicia_publisher


def test_indicia_publisher_list_serializer_exposes_trimmed_contract(
    publisher,
    country,
):
    """List rows include identity, browse, count, and timestamp fields."""
    indicia_publisher = _create_indicia_publisher(publisher, country)

    data = IndiciaPublisherListSerializer(indicia_publisher).data

    assert set(data) == {
        'id',
        'name',
        'parent',
        'country',
        'is_surrogate',
        'year_began',
        'year_ended',
        'issue_count',
        'created',
        'modified',
    }
    assert data['id'] == indicia_publisher.pk
    assert data['name'] == indicia_publisher.name
    assert data['parent'] == {
        'id': publisher.pk,
        'name': publisher.name,
    }
    assert data['country'] == country.code
    assert data['is_surrogate'] is True
    assert data['year_began'] == 1960
    assert data['year_ended'] == 1980
    assert data['issue_count'] == 42
    assert data['created']
    assert data['modified']


def test_indicia_publisher_detail_serializer_exposes_full_contract(
    publisher,
    country,
):
    """Detail rows add uncertainty, overall-year, and descriptive fields."""
    indicia_publisher = _create_indicia_publisher(publisher, country)

    data = IndiciaPublisherSerializer(indicia_publisher).data

    assert set(data) == {
        'id',
        'name',
        'parent',
        'country',
        'is_surrogate',
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
    }
    assert data['parent'] == {
        'id': publisher.pk,
        'name': publisher.name,
    }
    assert data['country'] == country.code
    assert data['year_began_uncertain'] is True
    assert data['year_ended_uncertain'] is False
    assert data['year_overall_began'] == 1955
    assert data['year_overall_ended'] == 1985
    assert data['year_overall_began_uncertain'] is False
    assert data['year_overall_ended_uncertain'] is True
    assert data['url'] == 'https://example.com/indicia-publisher/'
    assert data['notes'] == 'Indicia publisher notes'
    assert set(data['keywords']) == {'alpha', 'beta'}
