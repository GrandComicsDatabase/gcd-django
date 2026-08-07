# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Performance tests for Brand endpoints."""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import Brand, BrandGroup, BrandUse


def _create_brand(*, name):
    """Create a minimal Brand row for performance tests."""
    return Brand.objects.create(
        name=name,
        year_began=1950,
        notes='',
    )


def _create_relationships(brand, *, publisher, count):
    """Attach ``count`` groups and Brand Uses to ``brand``."""
    for number in range(count):
        group = BrandGroup.objects.create(
            name=f'Group {number:03d}',
            year_began=1950,
            notes='',
            parent=publisher,
        )
        brand.group.add(group)
        BrandUse.objects.create(
            emblem=brand,
            publisher=publisher,
            year_began=1950 + number,
            notes='',
        )


def test_brand_list_query_count(api_client, db):
    """The Brand list stays on its query budget."""
    _create_brand(name='Alpha Brand')
    _create_brand(name='Beta Brand')

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(reverse('brand-list'))

    assert response.status_code == 200
    assert len(context) == 3


def test_brand_detail_query_count_is_relationship_count_independent(
    api_client,
    publisher,
):
    """Detail serialization uses bounded relationship prefetches."""
    brand = _create_brand(name='Detail Brand')
    brand.keywords.add('detail')
    _create_relationships(brand, publisher=publisher, count=8)

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(
            reverse('brand-detail', kwargs={'pk': brand.pk}),
        )

    assert response.status_code == 200
    assert len(response.data['groups']) == 8
    assert len(response.data['uses']) == 8
    assert len(context) == 5
