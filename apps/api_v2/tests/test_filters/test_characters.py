# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the character filter set."""

from datetime import timedelta

from django.utils import timezone

from apps.api_v2.filters.characters import CharacterFilterSet
from apps.gcd.models import Character, Multiverse, Universe
from apps.stddata.models import Language


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


def _create_language(code, name):
    """Create or return a language row for character tests."""
    obj, _created = Language.objects.get_or_create(
        code=code,
        defaults={'name': name},
    )
    return obj


def _create_character(
    *,
    name,
    sort_name,
    year_first_published,
    language,
    universe=None,
):
    """Create a minimal character row for filter tests."""
    return Character.objects.create(
        name=name,
        sort_name=sort_name,
        disambiguation='',
        universe=universe,
        year_first_published=year_first_published,
        language=language,
        description='',
        notes='',
    )


def _set_timestamps(obj, *, created, modified):
    """Persist explicit created/modified timestamps for filter tests."""
    Character.objects.filter(pk=obj.pk).update(
        created=created,
        modified=modified,
    )
    obj.refresh_from_db()


def test_character_filter_matches_name_icontains(db):
    """The name filter uses case-insensitive containment."""
    english = _create_language('en', 'English')
    marvel = _create_multiverse('Marvel')
    universe = Universe.objects.create(
        multiverse='Marvel',
        verse=marvel,
        name='Mainstream',
        designation='Earth-616',
        year_first_published=1961,
        description='',
        notes='',
    )
    matching = _create_character(
        name='Spider-Man',
        sort_name='Spider-Man',
        year_first_published=1962,
        language=english,
        universe=universe,
    )
    _create_character(
        name='Batman',
        sort_name='Batman',
        year_first_published=1939,
        language=english,
        universe=universe,
    )

    qs = CharacterFilterSet(
        {'name': 'spider'},
        queryset=Character.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [matching]


def test_character_filter_matches_year_first_published_range(db):
    """Year range filters support inclusive lower and upper bounds."""
    english = _create_language('en', 'English')
    marvel = _create_multiverse('Marvel')
    universe = Universe.objects.create(
        multiverse='Marvel',
        verse=marvel,
        name='Mainstream',
        designation='Earth-616',
        year_first_published=1961,
        description='',
        notes='',
    )
    matching = _create_character(
        name='Spider-Man',
        sort_name='Spider-Man',
        year_first_published=1962,
        language=english,
        universe=universe,
    )
    _create_character(
        name='Captain America',
        sort_name='Captain America',
        year_first_published=1941,
        language=english,
        universe=universe,
    )

    qs = CharacterFilterSet(
        {
            'year_first_published__gte': '1960',
            'year_first_published__lte': '1965',
        },
        queryset=Character.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [matching]


def test_character_filter_matches_language_code(db):
    """The language filter uses the related language code."""
    english = _create_language('en', 'English')
    spanish = _create_language('es', 'Spanish')
    marvel = _create_multiverse('Marvel')
    universe = Universe.objects.create(
        multiverse='Marvel',
        verse=marvel,
        name='Mainstream',
        designation='Earth-616',
        year_first_published=1961,
        description='',
        notes='',
    )
    matching = _create_character(
        name='Spider-Man',
        sort_name='Spider-Man',
        year_first_published=1962,
        language=english,
        universe=universe,
    )
    _create_character(
        name='Spider-Man ES',
        sort_name='Spider-Man ES',
        year_first_published=1962,
        language=spanish,
        universe=universe,
    )

    qs = CharacterFilterSet(
        {'language': 'en'},
        queryset=Character.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [matching]


def test_character_filter_matches_universe_id(db):
    """The universe filter scopes results to one universe id."""
    english = _create_language('en', 'English')
    marvel = _create_multiverse('Marvel')
    dc = _create_multiverse('DC')
    marvel_universe = Universe.objects.create(
        multiverse='Marvel',
        verse=marvel,
        name='Mainstream',
        designation='Earth-616',
        year_first_published=1961,
        description='',
        notes='',
    )
    dc_universe = Universe.objects.create(
        multiverse='DC',
        verse=dc,
        name='Mainstream',
        designation='Earth-0',
        year_first_published=1938,
        description='',
        notes='',
    )
    matching = _create_character(
        name='Spider-Man',
        sort_name='Spider-Man',
        year_first_published=1962,
        language=english,
        universe=marvel_universe,
    )
    _create_character(
        name='Batman',
        sort_name='Batman',
        year_first_published=1939,
        language=english,
        universe=dc_universe,
    )

    qs = CharacterFilterSet(
        {'universe': str(marvel_universe.pk)},
        queryset=Character.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [matching]


def test_character_filter_matches_modified_range(db):
    """Modified range filters support delta-style sync queries."""
    english = _create_language('en', 'English')
    marvel = _create_multiverse('Marvel')
    universe = Universe.objects.create(
        multiverse='Marvel',
        verse=marvel,
        name='Mainstream',
        designation='Earth-616',
        year_first_published=1961,
        description='',
        notes='',
    )
    older = _create_character(
        name='Older Character',
        sort_name='Older Character',
        year_first_published=1940,
        language=english,
        universe=universe,
    )
    newer = _create_character(
        name='Newer Character',
        sort_name='Newer Character',
        year_first_published=1962,
        language=english,
        universe=universe,
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

    qs = CharacterFilterSet(
        {'modified__gt': (now - timedelta(days=1)).isoformat()},
        queryset=Character.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [newer]


def test_character_filter_matches_created_range(db):
    """Created range filters support bounded character queries."""
    english = _create_language('en', 'English')
    marvel = _create_multiverse('Marvel')
    universe = Universe.objects.create(
        multiverse='Marvel',
        verse=marvel,
        name='Mainstream',
        designation='Earth-616',
        year_first_published=1961,
        description='',
        notes='',
    )
    older = _create_character(
        name='Older Character',
        sort_name='Older Character',
        year_first_published=1940,
        language=english,
        universe=universe,
    )
    newer = _create_character(
        name='Newer Character',
        sort_name='Newer Character',
        year_first_published=1962,
        language=english,
        universe=universe,
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

    qs = CharacterFilterSet(
        {'created__lte': (now - timedelta(days=1)).isoformat()},
        queryset=Character.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [older]
