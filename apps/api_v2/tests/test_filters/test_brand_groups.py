# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the brand group filter set."""

from datetime import timedelta

from django.utils import timezone

from apps.api_v2.filters.brand_groups import BrandGroupFilterSet
from apps.gcd.models import BrandGroup, Publisher


def _create_brand_group(
    *,
    publisher,
    name,
    year_began=1950,
    year_ended=None,
):
    """Create a minimal brand group row for filter tests."""
    return BrandGroup.objects.create(
        name=name,
        year_began=year_began,
        year_ended=year_ended,
        notes='',
        parent=publisher,
    )


def _set_timestamps(obj, *, created, modified):
    """Persist explicit created/modified timestamps for filter tests."""
    BrandGroup.objects.filter(pk=obj.pk).update(
        created=created,
        modified=modified,
    )
    obj.refresh_from_db()


def test_brand_group_filter_matches_name_icontains(publisher):
    """The name filter uses case-insensitive containment."""
    matching = _create_brand_group(
        publisher=publisher,
        name='Marvel Comics Group',
    )
    _create_brand_group(
        publisher=publisher,
        name='National Periodical Publications',
    )

    queryset = BrandGroupFilterSet(
        {'name': 'marvel comics'},
        queryset=BrandGroup.objects.all(),
    ).qs

    assert list(queryset) == [matching]


def test_brand_group_filter_matches_exact_fields(publisher, country):
    """Parent and exact year filters narrow brand group results."""
    other_parent = Publisher.objects.create(
        name='Other Publisher',
        year_began=1940,
        notes='',
        country=country,
    )
    matching = _create_brand_group(
        publisher=publisher,
        name='Matching Group',
        year_began=1960,
        year_ended=1980,
    )
    _create_brand_group(
        publisher=other_parent,
        name='Wrong Parent',
        year_began=1960,
        year_ended=1980,
    )
    _create_brand_group(
        publisher=publisher,
        name='Wrong Years',
        year_began=1970,
        year_ended=1990,
    )

    queryset = BrandGroupFilterSet(
        {
            'parent': str(publisher.pk),
            'year_began': '1960',
            'year_ended': '1980',
        },
        queryset=BrandGroup.objects.all(),
    ).qs

    assert list(queryset) == [matching]


def test_brand_group_filter_matches_modified_range(publisher):
    """Modified range filters support delta-style sync queries."""
    older = _create_brand_group(
        publisher=publisher,
        name='Older Group',
    )
    newer = _create_brand_group(
        publisher=publisher,
        name='Newer Group',
    )
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

    queryset = BrandGroupFilterSet(
        {'modified__gt': (now - timedelta(days=1)).isoformat()},
        queryset=BrandGroup.objects.all(),
    ).qs

    assert list(queryset) == [newer]


def test_brand_group_filter_matches_created_range(publisher):
    """Created range filters support bounded brand group queries."""
    older = _create_brand_group(
        publisher=publisher,
        name='Older Group',
    )
    newer = _create_brand_group(
        publisher=publisher,
        name='Newer Group',
    )
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

    queryset = BrandGroupFilterSet(
        {'created__lte': (now - timedelta(days=1)).isoformat()},
        queryset=BrandGroup.objects.all(),
    ).qs

    assert list(queryset) == [older]
