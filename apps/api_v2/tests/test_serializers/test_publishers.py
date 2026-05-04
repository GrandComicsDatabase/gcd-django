# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the publisher serializer."""

from apps.api_v2.serializers.publishers import PublisherSerializer


def test_publisher_serializer_exposes_prd_fields(publisher, country):
    """The publisher serializer emits the Sprint 1 publisher contract."""
    publisher.url = 'https://example.com/publishers/test-publisher/'
    publisher.notes = 'Publisher notes'
    publisher.series_count = 12
    publisher.issue_count = 34
    publisher.brand_count = 5
    publisher.indicia_publisher_count = 2
    publisher.save()
    publisher.keywords.add('alpha', 'beta')

    data = PublisherSerializer(publisher).data

    assert set(data) == {
        'id',
        'name',
        'year_began',
        'year_ended',
        'country',
        'url',
        'notes',
        'series_count',
        'issue_count',
        'brand_count',
        'indicia_publisher_count',
        'keywords',
        'created',
        'modified',
    }
    assert data['id'] == publisher.pk
    assert data['name'] == 'Test Publisher'
    assert data['country'] == country.code
    assert data['url'] == publisher.url
    assert data['notes'] == 'Publisher notes'
    assert data['series_count'] == 12
    assert data['issue_count'] == 34
    assert data['brand_count'] == 5
    assert data['indicia_publisher_count'] == 2
    assert set(data['keywords']) == {'alpha', 'beta'}
    assert data['created']
    assert data['modified']
