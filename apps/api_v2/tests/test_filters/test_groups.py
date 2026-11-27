# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the group filter set."""

from datetime import timedelta

from django.utils import timezone

from apps.api_v2.filters.groups import GroupFilterSet
from apps.gcd.models import Group, Multiverse, Universe
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
    """Create or return a language row for group tests."""
    obj, _created = Language.objects.get_or_create(
        code=code,
        defaults={'name': name},
    )
    return obj


def _create_group(
    *,
    name,
    sort_name,
    year_first_published,
    language,
    universe=None,
):
    """Create a minimal group row for filter tests."""
    return Group.objects.create(
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
    Group.objects.filter(pk=obj.pk).update(
        created=created,
        modified=modified,
    )
    obj.refresh_from_db()


def test_group_filter_matches_name_icontains(db):
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
    matching = _create_group(
        name='Justice League',
        sort_name='Justice League',
        year_first_published=1960,
        language=english,
        universe=universe,
    )
    _create_group(
        name='Legion of Super-Heroes',
        sort_name='Legion of Super-Heroes',
        year_first_published=1958,
        language=english,
        universe=universe,
    )

    qs = GroupFilterSet(
        {'name': 'justice'},
        queryset=Group.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [matching]


def test_group_filter_matches_year_language_and_universe(db):
    """Range, language, and universe filters narrow groups correctly."""
    english = _create_language('en', 'English')
    spanish = _create_language('es', 'Spanish')
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
    matching = _create_group(
        name='X-Men',
        sort_name='X-Men',
        year_first_published=1963,
        language=english,
        universe=marvel_universe,
    )
    _create_group(
        name='X-Men ES',
        sort_name='X-Men ES',
        year_first_published=1963,
        language=spanish,
        universe=marvel_universe,
    )
    _create_group(
        name='Justice League',
        sort_name='Justice League',
        year_first_published=1960,
        language=english,
        universe=dc_universe,
    )

    qs = GroupFilterSet(
        {
            'year_first_published__gte': '1960',
            'year_first_published__lte': '1965',
            'language': 'en',
            'universe': str(marvel_universe.pk),
        },
        queryset=Group.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [matching]


def test_group_filter_language_avoids_language_table_join(db):
    """The shared language-code filter resolves to language_id."""
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
    _create_group(
        name='X-Men',
        sort_name='X-Men',
        year_first_published=1963,
        language=english,
        universe=universe,
    )

    qs = GroupFilterSet(
        {'language': 'en'},
        queryset=Group.objects.filter(deleted=False),
    ).qs
    sql = str(qs.query).lower()

    assert 'stddata_language' not in sql
    assert 'language_id' in sql


def test_group_filter_matches_modified_range(db):
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
    older = _create_group(
        name='Older Group',
        sort_name='Older Group',
        year_first_published=1960,
        language=english,
        universe=universe,
    )
    newer = _create_group(
        name='Newer Group',
        sort_name='Newer Group',
        year_first_published=1965,
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

    qs = GroupFilterSet(
        {'modified__gt': (now - timedelta(days=1)).isoformat()},
        queryset=Group.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [newer]


def test_group_filter_matches_created_range(db):
    """Created range filters support bounded group queries."""
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
    older = _create_group(
        name='Older Group',
        sort_name='Older Group',
        year_first_published=1960,
        language=english,
        universe=universe,
    )
    newer = _create_group(
        name='Newer Group',
        sort_name='Newer Group',
        year_first_published=1965,
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

    qs = GroupFilterSet(
        {'created__lte': (now - timedelta(days=1)).isoformat()},
        queryset=Group.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [older]
