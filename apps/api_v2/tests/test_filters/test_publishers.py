# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the publisher filter set."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.api_v2.filters.publishers import PublisherFilterSet
from apps.gcd.models import Publisher
from apps.stddata.models import Country


@pytest.fixture
def other_country(db):
    """Return a second country for publisher filter tests."""
    obj, _ = Country.objects.get_or_create(
        code='yy',
        defaults={'name': 'Other Country'},
    )
    return obj


def _set_timestamps(obj, *, created, modified):
    """Persist explicit created/modified timestamps for filter tests."""
    Publisher.objects.filter(pk=obj.pk).update(
        created=created,
        modified=modified,
    )
    obj.refresh_from_db()


def test_publisher_filter_matches_name_icontains(country):
    """The name filter uses case-insensitive containment."""
    matching = Publisher.objects.create(
        name='Marvel Comics',
        year_began=1939,
        notes='',
        country=country,
    )
    Publisher.objects.create(
        name='DC Comics',
        year_began=1934,
        notes='',
        country=country,
    )

    qs = PublisherFilterSet(
        {'name': 'marvel'},
        queryset=Publisher.objects.all(),
    ).qs

    assert list(qs) == [matching]


def test_publisher_filter_matches_year_fields_and_country(
    country,
    other_country,
):
    """Exact year and country filters narrow publishers correctly."""
    matching = Publisher.objects.create(
        name='Matching Publisher',
        year_began=1950,
        year_ended=1980,
        notes='',
        country=country,
    )
    Publisher.objects.create(
        name='Wrong Country',
        year_began=1950,
        year_ended=1980,
        notes='',
        country=other_country,
    )
    Publisher.objects.create(
        name='Wrong Year',
        year_began=1949,
        year_ended=1980,
        notes='',
        country=country,
    )

    qs = PublisherFilterSet(
        {
            'year_began': '1950',
            'year_ended': '1980',
            'country': country.code,
        },
        queryset=Publisher.objects.all(),
    ).qs

    assert list(qs) == [matching]


def test_publisher_filter_matches_modified_range(country):
    """Modified range filters support delta-style sync queries."""
    older = Publisher.objects.create(
        name='Older Publisher',
        year_began=1940,
        notes='',
        country=country,
    )
    newer = Publisher.objects.create(
        name='Newer Publisher',
        year_began=1950,
        notes='',
        country=country,
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

    qs = PublisherFilterSet(
        {'modified__gt': (now - timedelta(days=1)).isoformat()},
        queryset=Publisher.objects.all(),
    ).qs

    assert list(qs) == [newer]


def test_publisher_filter_matches_created_range(country):
    """Created range filters support bounded publisher queries."""
    older = Publisher.objects.create(
        name='Older Publisher',
        year_began=1940,
        notes='',
        country=country,
    )
    newer = Publisher.objects.create(
        name='Newer Publisher',
        year_began=1950,
        notes='',
        country=country,
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

    qs = PublisherFilterSet(
        {'created__lte': (now - timedelta(days=1)).isoformat()},
        queryset=Publisher.objects.all(),
    ).qs

    assert list(qs) == [older]
