# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the series filter set."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.api_v2.filters.series import SeriesFilterSet
from apps.gcd.models import Publisher, Series, SeriesPublicationType
from apps.stddata.models import Country, Language


@pytest.fixture
def other_country(db):
    """Return a second country for series filter tests."""
    obj, _ = Country.objects.get_or_create(
        code='yy',
        defaults={'name': 'Other Country'},
    )
    return obj


@pytest.fixture
def other_language(db):
    """Return a second language for series filter tests."""
    obj, _ = Language.objects.get_or_create(
        code='yy',
        defaults={'name': 'Other Language'},
    )
    return obj


@pytest.fixture
def series_publication_type(db):
    """Return a publication type for series filter tests."""
    return SeriesPublicationType.objects.create(
        name='Comic Book',
        notes='',
    )


def _set_timestamps(obj, *, created, modified):
    """Persist explicit created/modified timestamps for filter tests."""
    Series.objects.filter(pk=obj.pk).update(
        created=created,
        modified=modified,
    )
    obj.refresh_from_db()


def _create_series(
    *,
    country,
    language,
    name,
    publication_type,
    publisher,
    year_began,
    year_ended=None,
):
    """Create a minimal series row for filter tests."""
    return Series.objects.create(
        name=name,
        sort_name=name,
        year_began=year_began,
        year_ended=year_ended,
        publication_dates='1990 - present',
        notes='',
        tracking_notes='',
        country=country,
        language=language,
        publisher=publisher,
        publication_type=publication_type,
    )


def test_series_filter_matches_name_icontains(
    country,
    language,
    publisher,
    series_publication_type,
):
    """The name filter uses case-insensitive containment."""
    matching = _create_series(
        country=country,
        language=language,
        name='Batman Adventures',
        publication_type=series_publication_type,
        publisher=publisher,
        year_began=1992,
    )
    _create_series(
        country=country,
        language=language,
        name='Superman Adventures',
        publication_type=series_publication_type,
        publisher=publisher,
        year_began=1992,
    )

    qs = SeriesFilterSet(
        {'name': 'batman'},
        queryset=Series.objects.all(),
    ).qs

    assert list(qs) == [matching]


def test_series_filter_matches_exact_fields(
    country,
    other_country,
    language,
    other_language,
    publisher,
    series_publication_type,
):
    """Exact filters narrow the series collection correctly."""
    other_publisher = Publisher.objects.create(
        name='Other Publisher',
        year_began=1940,
        notes='',
        country=country,
    )
    other_publication_type = SeriesPublicationType.objects.create(
        name='Magazine',
        notes='',
    )
    matching = _create_series(
        country=country,
        language=language,
        name='Matching Series',
        publication_type=series_publication_type,
        publisher=publisher,
        year_began=1985,
        year_ended=1989,
    )
    _create_series(
        country=other_country,
        language=language,
        name='Wrong Country',
        publication_type=series_publication_type,
        publisher=publisher,
        year_began=1985,
        year_ended=1989,
    )
    _create_series(
        country=country,
        language=other_language,
        name='Wrong Language',
        publication_type=series_publication_type,
        publisher=publisher,
        year_began=1985,
        year_ended=1989,
    )
    _create_series(
        country=country,
        language=language,
        name='Wrong Publisher',
        publication_type=series_publication_type,
        publisher=other_publisher,
        year_began=1985,
        year_ended=1989,
    )
    _create_series(
        country=country,
        language=language,
        name='Wrong Type',
        publication_type=other_publication_type,
        publisher=publisher,
        year_began=1985,
        year_ended=1989,
    )
    _create_series(
        country=country,
        language=language,
        name='Wrong Year',
        publication_type=series_publication_type,
        publisher=publisher,
        year_began=1984,
        year_ended=1989,
    )

    qs = SeriesFilterSet(
        {
            'year_began': '1985',
            'year_ended': '1989',
            'country': country.code,
            'language': language.code,
            'publisher': str(publisher.pk),
            'publication_type': str(series_publication_type.pk),
        },
        queryset=Series.objects.all(),
    ).qs

    assert list(qs) == [matching]


def test_series_filter_matches_modified_range(
    country,
    language,
    publisher,
    series_publication_type,
):
    """Modified range filters support delta-style sync queries."""
    older = _create_series(
        country=country,
        language=language,
        name='Older Series',
        publication_type=series_publication_type,
        publisher=publisher,
        year_began=1980,
    )
    newer = _create_series(
        country=country,
        language=language,
        name='Newer Series',
        publication_type=series_publication_type,
        publisher=publisher,
        year_began=1990,
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

    qs = SeriesFilterSet(
        {'modified__gt': (now - timedelta(days=1)).isoformat()},
        queryset=Series.objects.all(),
    ).qs

    assert list(qs) == [newer]


def test_series_filter_matches_created_range(
    country,
    language,
    publisher,
    series_publication_type,
):
    """Created range filters support bounded series queries."""
    older = _create_series(
        country=country,
        language=language,
        name='Older Series',
        publication_type=series_publication_type,
        publisher=publisher,
        year_began=1980,
    )
    newer = _create_series(
        country=country,
        language=language,
        name='Newer Series',
        publication_type=series_publication_type,
        publisher=publisher,
        year_began=1990,
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

    qs = SeriesFilterSet(
        {'created__lte': (now - timedelta(days=1)).isoformat()},
        queryset=Series.objects.all(),
    ).qs

    assert list(qs) == [older]
