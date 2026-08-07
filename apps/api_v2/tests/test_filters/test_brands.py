# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the brand filter set."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.api_v2.filters.brands import BrandFilterSet
from apps.gcd.models import Brand, BrandGroup, BrandUse, Publisher

pytestmark = pytest.mark.django_db


def _create_brand(
    *,
    name,
    generic=False,
    year_began=1950,
    year_ended=None,
):
    """Create a minimal Brand row for filter tests."""
    return Brand.objects.create(
        name=name,
        generic=generic,
        year_began=year_began,
        year_ended=year_ended,
        notes='',
    )


def _create_brand_group(*, publisher, name, deleted=False):
    """Create a minimal Brand Group row for relationship filters."""
    return BrandGroup.objects.create(
        name=name,
        year_began=1950,
        notes='',
        parent=publisher,
        deleted=deleted,
    )


def _set_timestamps(obj, *, created, modified):
    """Persist explicit created/modified timestamps for filter tests."""
    Brand.objects.filter(pk=obj.pk).update(
        created=created,
        modified=modified,
    )
    obj.refresh_from_db()


def test_brand_filter_matches_name_icontains():
    """The name filter uses case-insensitive containment."""
    matching = _create_brand(name='Marvel Comics')
    _create_brand(name='National Periodical Publications')

    queryset = BrandFilterSet(
        {'name': 'marvel'},
        queryset=Brand.objects.all(),
    ).qs

    assert list(queryset) == [matching]


def test_brand_filter_matches_generic_and_exact_years():
    """Generic and exact year filters narrow Brand results."""
    matching = _create_brand(
        name='Matching Brand',
        generic=True,
        year_began=1960,
        year_ended=1980,
    )
    _create_brand(
        name='Wrong Generic Flag',
        year_began=1960,
        year_ended=1980,
    )
    _create_brand(
        name='Wrong Years',
        generic=True,
        year_began=1970,
        year_ended=1990,
    )

    queryset = BrandFilterSet(
        {
            'generic': 'true',
            'year_began': '1960',
            'year_ended': '1980',
        },
        queryset=Brand.objects.all(),
    ).qs

    assert list(queryset) == [matching]


def test_brand_relationship_filters_return_distinct_results(
    publisher,
    country,
):
    """Group and publisher joins never duplicate matching Brands."""
    brand_group = _create_brand_group(
        publisher=publisher,
        name='Matching Group',
    )
    other_group = _create_brand_group(
        publisher=publisher,
        name='Other Group',
    )
    other_publisher = Publisher.objects.create(
        name='Other Publisher',
        year_began=1940,
        notes='',
        country=country,
    )
    matching = _create_brand(name='Matching Brand')
    matching.group.add(brand_group, other_group)
    BrandUse.objects.create(
        emblem=matching,
        publisher=publisher,
        year_began=1960,
        notes='First use',
    )
    BrandUse.objects.create(
        emblem=matching,
        publisher=publisher,
        year_began=1970,
        notes='Second use',
    )
    wrong_publisher = _create_brand(name='Wrong Publisher')
    wrong_publisher.group.add(brand_group)
    BrandUse.objects.create(
        emblem=wrong_publisher,
        publisher=other_publisher,
        notes='',
    )

    queryset = BrandFilterSet(
        {
            'group': str(brand_group.pk),
            'publisher': str(publisher.pk),
        },
        queryset=Brand.objects.all(),
    ).qs

    assert list(queryset) == [matching]


def test_brand_relationship_filters_ignore_deleted_relations(
    publisher,
    country,
):
    """Deleted groups and publishers cannot expose Brands through filters."""
    deleted_group = _create_brand_group(
        publisher=publisher,
        name='Deleted Group',
        deleted=True,
    )
    deleted_publisher = Publisher.objects.create(
        name='Deleted Publisher',
        year_began=1940,
        notes='',
        country=country,
        deleted=True,
    )
    brand = _create_brand(name='Hidden Relationship Brand')
    brand.group.add(deleted_group)
    BrandUse.objects.create(
        emblem=brand,
        publisher=deleted_publisher,
        notes='',
    )

    group_queryset = BrandFilterSet(
        {'group': str(deleted_group.pk)},
        queryset=Brand.objects.all(),
    ).qs
    publisher_queryset = BrandFilterSet(
        {'publisher': str(deleted_publisher.pk)},
        queryset=Brand.objects.all(),
    ).qs

    assert list(group_queryset) == []
    assert list(publisher_queryset) == []


def test_brand_filter_matches_modified_range():
    """Modified range filters support delta-style sync queries."""
    older = _create_brand(name='Older Brand')
    newer = _create_brand(name='Newer Brand')
    now = timezone.now()
    _set_timestamps(
        older,
        created=now - timedelta(days=3),
        modified=now - timedelta(days=2),
    )
    _set_timestamps(
        newer,
        created=now - timedelta(days=1),
        modified=now - timedelta(hours=1),
    )

    queryset = BrandFilterSet(
        {'modified__gt': (now - timedelta(days=1)).isoformat()},
        queryset=Brand.objects.all(),
    ).qs

    assert list(queryset) == [newer]


def test_brand_filter_matches_created_range():
    """Created range filters support bounded Brand queries."""
    older = _create_brand(name='Older Brand')
    newer = _create_brand(name='Newer Brand')
    now = timezone.now()
    older_created = now - timedelta(days=3)
    newer_created = now - timedelta(hours=1)
    _set_timestamps(
        older,
        created=older_created,
        modified=older_created,
    )
    _set_timestamps(
        newer,
        created=newer_created,
        modified=newer_created,
    )

    queryset = BrandFilterSet(
        {'created__lte': (now - timedelta(days=1)).isoformat()},
        queryset=Brand.objects.all(),
    ).qs

    assert list(queryset) == [older]
