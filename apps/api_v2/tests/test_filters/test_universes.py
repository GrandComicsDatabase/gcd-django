# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the universe filter set."""

from datetime import timedelta

from django.utils import timezone

from apps.api_v2.filters.universes import UniverseFilterSet
from apps.gcd.models import Multiverse, Universe


def _create_multiverse(name):
    """Create a multiverse plus a hidden seed universe."""
    seed = Universe.objects.create(
        multiverse=name,
        name='Seed Universe',
        designation='Earth-0',
        year_first_published=1938,
        description='',
        notes='',
        deleted=True,
    )
    multiverse = Multiverse.objects.create(name=name, mainstream=seed)
    seed.verse = multiverse
    seed.save(update_fields=['verse'])
    return multiverse


def _create_universe(
    *,
    multiverse_name,
    verse=None,
    name,
    designation,
    year_first_published,
):
    """Create a minimal universe row for filter tests."""
    return Universe.objects.create(
        multiverse=multiverse_name,
        verse=verse,
        name=name,
        designation=designation,
        year_first_published=year_first_published,
        description='',
        notes='',
    )


def _set_timestamps(obj, *, created, modified):
    """Persist explicit created/modified timestamps for filter tests."""
    Universe.objects.filter(pk=obj.pk).update(
        created=created,
        modified=modified,
    )
    obj.refresh_from_db()


def test_universe_filter_matches_name_and_designation_icontains(db):
    """Name and designation filters use case-insensitive containment."""
    marvel = _create_multiverse('Marvel')
    matching = _create_universe(
        multiverse_name='Marvel',
        verse=marvel,
        name='Ultimate',
        designation='Earth-1610',
        year_first_published=2000,
    )
    _create_universe(
        multiverse_name='Marvel',
        verse=marvel,
        name='Noir',
        designation='Earth-90214',
        year_first_published=2009,
    )

    qs = UniverseFilterSet(
        {'name': 'ulti', 'designation': '1610'},
        queryset=Universe.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [matching]


def test_universe_filter_matches_year_and_multiverse(db):
    """Exact year and multiverse filters narrow universes correctly."""
    marvel = _create_multiverse('Marvel')
    dc = _create_multiverse('DC')
    matching = _create_universe(
        multiverse_name='Marvel',
        verse=marvel,
        name='Mainstream',
        designation='Earth-616',
        year_first_published=1961,
    )
    _create_universe(
        multiverse_name='Marvel',
        verse=marvel,
        name='Future',
        designation='Earth-811',
        year_first_published=1981,
    )
    _create_universe(
        multiverse_name='DC',
        verse=dc,
        name='Mainstream',
        designation='Earth-0',
        year_first_published=1961,
    )

    qs = UniverseFilterSet(
        {
            'year_first_published': '1961',
            'multiverse': str(marvel.pk),
        },
        queryset=Universe.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [matching]


def test_universe_filter_matches_modified_range(db):
    """Modified range filters support delta-style sync queries."""
    marvel = _create_multiverse('Marvel')
    older = _create_universe(
        multiverse_name='Marvel',
        verse=marvel,
        name='Older',
        designation='Earth-1',
        year_first_published=1961,
    )
    newer = _create_universe(
        multiverse_name='Marvel',
        verse=marvel,
        name='Newer',
        designation='Earth-2',
        year_first_published=1962,
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

    qs = UniverseFilterSet(
        {'modified__gt': (now - timedelta(days=1)).isoformat()},
        queryset=Universe.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [newer]


def test_universe_filter_matches_created_range(db):
    """Created range filters support bounded universe queries."""
    marvel = _create_multiverse('Marvel')
    older = _create_universe(
        multiverse_name='Marvel',
        verse=marvel,
        name='Older',
        designation='Earth-1',
        year_first_published=1961,
    )
    newer = _create_universe(
        multiverse_name='Marvel',
        verse=marvel,
        name='Newer',
        designation='Earth-2',
        year_first_published=1962,
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

    qs = UniverseFilterSet(
        {'created__lte': (now - timedelta(days=1)).isoformat()},
        queryset=Universe.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [older]
