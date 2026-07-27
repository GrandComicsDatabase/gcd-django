# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Performance tests for brand group endpoints."""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import Brand, BrandGroup


def _create_brand_group(*, publisher, name):
    """Create a minimal brand group row for performance tests."""
    return BrandGroup.objects.create(
        name=name,
        year_began=1950,
        notes='',
        parent=publisher,
    )


def _create_emblems(brand_group, *, count):
    """Attach ``count`` active emblems to ``brand_group``."""
    for number in range(count):
        emblem = Brand.objects.create(
            name=f'Emblem {number:03d}',
            year_began=1950,
            notes='',
        )
        emblem.group.add(brand_group)


def test_brand_group_list_query_count(api_client, publisher):
    """The brand group list stays on its query budget."""
    _create_brand_group(publisher=publisher, name='Alpha Group')
    _create_brand_group(publisher=publisher, name='Beta Group')

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(reverse('brand-group-list'))

    assert response.status_code == 200
    assert len(context) == 3


def test_brand_group_detail_query_count_is_emblem_count_independent(
    api_client,
    publisher,
):
    """Detail serialization uses one bounded emblem prefetch query."""
    brand_group = _create_brand_group(
        publisher=publisher,
        name='Detail Group',
    )
    brand_group.keywords.add('detail')
    _create_emblems(brand_group, count=8)

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(
            reverse(
                'brand-group-detail',
                kwargs={'pk': brand_group.pk},
            ),
        )

    assert response.status_code == 200
    assert len(response.data['emblems']) == 8
    assert len(context) == 4
