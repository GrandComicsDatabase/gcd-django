# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the indicia publisher filter set."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.api_v2.filters.indicia_publishers import (
    IndiciaPublisherFilterSet,
)
from apps.gcd.models import IndiciaPublisher, Publisher
from apps.stddata.models import Country


@pytest.fixture
def other_country(db):
    """Return a second country for indicia publisher filter tests."""
    obj, _ = Country.objects.get_or_create(
        code='yy',
        defaults={'name': 'Other Country'},
    )
    return obj


def _create_indicia_publisher(
    *,
    publisher,
    country,
    name,
    year_began=1950,
    year_ended=None,
    is_surrogate=False,
):
    """Create a minimal indicia publisher row for filter tests."""
    return IndiciaPublisher.objects.create(
        name=name,
        year_began=year_began,
        year_ended=year_ended,
        notes='',
        parent=publisher,
        country=country,
        is_surrogate=is_surrogate,
    )


def _set_timestamps(obj, *, created, modified):
    """Persist explicit created/modified timestamps for filter tests."""
    IndiciaPublisher.objects.filter(pk=obj.pk).update(
        created=created,
        modified=modified,
    )
    obj.refresh_from_db()


def test_indicia_publisher_filter_matches_name_icontains(
    publisher,
    country,
):
    """The name filter uses case-insensitive containment."""
    matching = _create_indicia_publisher(
        publisher=publisher,
        country=country,
        name='Marvel Comics Group',
    )
    _create_indicia_publisher(
        publisher=publisher,
        country=country,
        name='National Periodical Publications',
    )

    queryset = IndiciaPublisherFilterSet(
        {'name': 'marvel comics'},
        queryset=IndiciaPublisher.objects.all(),
    ).qs

    assert list(queryset) == [matching]


def test_indicia_publisher_filter_matches_exact_fields(
    publisher,
    country,
    other_country,
):
    """Parent, country, surrogate, and year filters narrow results."""
    other_parent = Publisher.objects.create(
        name='Other Publisher',
        year_began=1940,
        notes='',
        country=country,
    )
    matching = _create_indicia_publisher(
        publisher=publisher,
        country=country,
        name='Matching Imprint',
        year_began=1960,
        year_ended=1980,
        is_surrogate=True,
    )
    _create_indicia_publisher(
        publisher=other_parent,
        country=country,
        name='Wrong Parent',
        year_began=1960,
        year_ended=1980,
        is_surrogate=True,
    )
    _create_indicia_publisher(
        publisher=publisher,
        country=other_country,
        name='Wrong Country',
        year_began=1960,
        year_ended=1980,
        is_surrogate=True,
    )
    _create_indicia_publisher(
        publisher=publisher,
        country=country,
        name='Wrong Surrogate Flag',
        year_began=1960,
        year_ended=1980,
    )

    queryset = IndiciaPublisherFilterSet(
        {
            'parent': str(publisher.pk),
            'country': country.code,
            'is_surrogate': 'true',
            'year_began': '1960',
            'year_ended': '1980',
        },
        queryset=IndiciaPublisher.objects.all(),
    ).qs

    assert list(queryset) == [matching]


def test_indicia_publisher_filter_matches_modified_range(
    publisher,
    country,
):
    """Modified range filters support delta-style sync queries."""
    older = _create_indicia_publisher(
        publisher=publisher,
        country=country,
        name='Older Imprint',
    )
    newer = _create_indicia_publisher(
        publisher=publisher,
        country=country,
        name='Newer Imprint',
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

    queryset = IndiciaPublisherFilterSet(
        {'modified__gt': (now - timedelta(days=1)).isoformat()},
        queryset=IndiciaPublisher.objects.all(),
    ).qs

    assert list(queryset) == [newer]


def test_indicia_publisher_filter_matches_created_range(
    publisher,
    country,
):
    """Created range filters support bounded indicia publisher queries."""
    older = _create_indicia_publisher(
        publisher=publisher,
        country=country,
        name='Older Imprint',
    )
    newer = _create_indicia_publisher(
        publisher=publisher,
        country=country,
        name='Newer Imprint',
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

    queryset = IndiciaPublisherFilterSet(
        {'created__lte': (now - timedelta(days=1)).isoformat()},
        queryset=IndiciaPublisher.objects.all(),
    ).qs

    assert list(queryset) == [older]
