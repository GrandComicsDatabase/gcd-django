# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the creator filter set."""

from datetime import timedelta

from django.utils import timezone

from apps.api_v2.filters.creators import CreatorFilterSet
from apps.gcd.models import Creator
from apps.stddata.models import Country, Date


def _create_country(code, name):
    """Create or return a country row for creator tests."""
    obj, _created = Country.objects.get_or_create(
        code=code,
        defaults={'name': name},
    )
    return obj


def _create_date(
    *,
    year='',
    month='',
    day='',
    year_uncertain=False,
    month_uncertain=False,
    day_uncertain=False,
):
    """Create a partial-date row for creator tests."""
    date = Date()
    date.set(
        year=year,
        month=month,
        day=day,
        year_uncertain=year_uncertain,
        month_uncertain=month_uncertain,
        day_uncertain=day_uncertain,
        empty=True,
    )
    date.save()
    return date


def _create_creator(
    *,
    gcd_official_name,
    sort_name,
    birth_date=None,
    death_date=None,
    birth_country=None,
):
    """Create a minimal creator row for filter tests."""
    return Creator.objects.create(
        gcd_official_name=gcd_official_name,
        sort_name=sort_name,
        disambiguation='',
        birth_date=birth_date,
        death_date=death_date,
        birth_country=birth_country,
        birth_province='',
        birth_city='',
        death_province='',
        death_city='',
        bio='',
        notes='',
    )


def _set_timestamps(obj, *, created, modified):
    """Persist explicit created/modified timestamps for filter tests."""
    Creator.objects.filter(pk=obj.pk).update(
        created=created,
        modified=modified,
    )
    obj.refresh_from_db()


def test_creator_filter_matches_name_icontains(db):
    """The name filter uses case-insensitive containment."""
    matching = _create_creator(
        gcd_official_name='Joe Kubert',
        sort_name='Kubert, Joe',
    )
    _create_creator(
        gcd_official_name='Will Eisner',
        sort_name='Eisner, Will',
    )

    qs = CreatorFilterSet(
        {'name': 'kub'},
        queryset=Creator.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [matching]


def test_creator_filter_matches_birth_country_code(db):
    """The birth-country filter uses the related country code."""
    usa = _create_country('us', 'United States')
    canada = _create_country('ca', 'Canada')
    matching = _create_creator(
        gcd_official_name='Joe Kubert',
        sort_name='Kubert, Joe',
        birth_country=usa,
    )
    _create_creator(
        gcd_official_name='Seth',
        sort_name='Seth',
        birth_country=canada,
    )

    qs = CreatorFilterSet(
        {'birth_country': 'us'},
        queryset=Creator.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [matching]


def test_creator_filter_matches_birth_date_range(db):
    """Birth-date range filters use compact partial-date query values."""
    matching = _create_creator(
        gcd_official_name='Joe Kubert',
        sort_name='Kubert, Joe',
        birth_date=_create_date(year='1926', month='09', day='18'),
    )
    _create_creator(
        gcd_official_name='Will Eisner',
        sort_name='Eisner, Will',
        birth_date=_create_date(year='1917'),
    )
    _create_creator(
        gcd_official_name='Seth',
        sort_name='Seth',
        birth_date=_create_date(year='1962', month='09'),
    )

    qs = CreatorFilterSet(
        {
            'birth_date__gte': '1920',
            'birth_date__lte': '1930-12-31',
        },
        queryset=Creator.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [matching]


def test_creator_filter_matches_death_date_range(db):
    """Death-date range filters use compact partial-date query values."""
    matching = _create_creator(
        gcd_official_name='Will Eisner',
        sort_name='Eisner, Will',
        death_date=_create_date(year='2005', month='01', day='03'),
    )
    _create_creator(
        gcd_official_name='Joe Kubert',
        sort_name='Kubert, Joe',
        death_date=_create_date(year='2012'),
    )
    _create_creator(
        gcd_official_name='Seth',
        sort_name='Seth',
        death_date=None,
    )

    qs = CreatorFilterSet(
        {
            'death_date__gte': '2000',
            'death_date__lte': '2009-12-31',
        },
        queryset=Creator.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [matching]


def test_creator_filter_excludes_fully_unknown_birth_years(db):
    """Fully unknown birth years stay out of comparable range filters."""
    matching = _create_creator(
        gcd_official_name='Will Eisner',
        sort_name='Eisner, Will',
        birth_date=_create_date(year='1917'),
    )
    _create_creator(
        gcd_official_name='Joe Kubert',
        sort_name='Kubert, Joe',
        birth_date=_create_date(year='1926', month='09', day='18'),
    )
    _create_creator(
        gcd_official_name='Unknown Creator',
        sort_name='Unknown Creator',
        birth_date=_create_date(year='????'),
    )
    _create_creator(
        gcd_official_name='Approximate Creator',
        sort_name='Approximate Creator',
        birth_date=_create_date(year='19??'),
    )

    qs = CreatorFilterSet(
        {'birth_date__lte': '1917'},
        queryset=Creator.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [matching]


def test_creator_filter_matches_uncertain_birth_year_ranges(db):
    """Year markers like ``19??`` remain usable in bounded date filters."""
    exact_match = _create_creator(
        gcd_official_name='Will Eisner',
        sort_name='Eisner, Will',
        birth_date=_create_date(year='1917'),
    )
    uncertain_match = _create_creator(
        gcd_official_name='Approximate Creator',
        sort_name='Approximate Creator',
        birth_date=_create_date(year='19??'),
    )
    _create_creator(
        gcd_official_name='Joe Kubert',
        sort_name='Kubert, Joe',
        birth_date=_create_date(year='2001'),
    )

    qs = CreatorFilterSet(
        {
            'birth_date__gte': '1900',
            'birth_date__lte': '1999-12-31',
        },
        queryset=Creator.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [uncertain_match, exact_match]


def test_creator_filter_matches_uncertain_death_year_ranges(db):
    """Year markers like ``200?`` remain usable in bounded date filters."""
    matching = _create_creator(
        gcd_official_name='Will Eisner',
        sort_name='Eisner, Will',
        death_date=_create_date(year='2005', month='01', day='03'),
    )
    uncertain_match = _create_creator(
        gcd_official_name='Approximate Creator',
        sort_name='Approximate Creator',
        death_date=_create_date(year='200?'),
    )
    _create_creator(
        gcd_official_name='Joe Kubert',
        sort_name='Kubert, Joe',
        death_date=_create_date(year='1999'),
    )

    qs = CreatorFilterSet(
        {
            'death_date__gte': '2000',
            'death_date__lte': '2009-12-31',
        },
        queryset=Creator.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [uncertain_match, matching]


def test_creator_filter_matches_living_creators(db):
    """The death-date isnull filter matches living creators."""
    matching = _create_creator(
        gcd_official_name='Seth',
        sort_name='Seth',
        death_date=None,
    )
    _create_creator(
        gcd_official_name='Will Eisner',
        sort_name='Eisner, Will',
        death_date=_create_date(year='2005', month='01', day='03'),
    )

    qs = CreatorFilterSet(
        {'death_date__isnull': 'true'},
        queryset=Creator.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [matching]


def test_creator_filter_rejects_invalid_partial_date(db):
    """Malformed partial-date values fail validation."""
    filterset = CreatorFilterSet(
        {'birth_date__gte': '1940-13'},
        queryset=Creator.objects.filter(deleted=False),
    )

    assert filterset.is_valid() is False
    assert filterset.errors == {
        'birth_date__gte': [
            'Enter a valid partial date in '
            'YYYY, YYYY-MM, or YYYY-MM-DD format.',
        ],
    }


def test_creator_filter_matches_modified_range(db):
    """Modified range filters support delta-style sync queries."""
    older = _create_creator(
        gcd_official_name='Older Creator',
        sort_name='Older Creator',
    )
    newer = _create_creator(
        gcd_official_name='Newer Creator',
        sort_name='Newer Creator',
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

    qs = CreatorFilterSet(
        {'modified__gt': (now - timedelta(days=1)).isoformat()},
        queryset=Creator.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [newer]


def test_creator_filter_matches_created_range(db):
    """Created range filters support bounded creator queries."""
    older = _create_creator(
        gcd_official_name='Older Creator',
        sort_name='Older Creator',
    )
    newer = _create_creator(
        gcd_official_name='Newer Creator',
        sort_name='Newer Creator',
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

    qs = CreatorFilterSet(
        {'created__lte': (now - timedelta(days=1)).isoformat()},
        queryset=Creator.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [older]
