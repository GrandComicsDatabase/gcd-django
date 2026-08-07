# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the Series Bond filter set."""

from datetime import timedelta

from django.utils import timezone

from apps.api_v2.filters.series_bonds import SeriesBondFilterSet
from apps.gcd.models import Issue, Series, SeriesBond, SeriesBondType


def _create_series(series, *, name, year_began):
    """Create a Series sharing the fixture Series' reference data."""
    return Series.objects.create(
        name=name,
        sort_name=name,
        year_began=year_began,
        publication_dates=f'{year_began} - present',
        notes='',
        tracking_notes='',
        country=series.country,
        language=series.language,
        publisher=series.publisher,
    )


def _create_issue(series, *, number, sort_code):
    """Create a minimal Issue for Series Bond filter tests."""
    return Issue.objects.create(
        number=number,
        title='',
        volume='',
        isbn='',
        valid_isbn='',
        variant_name='',
        barcode='',
        publication_date='',
        key_date='',
        on_sale_date='',
        sort_code=sort_code,
        indicia_frequency='',
        price='',
        editing='',
        notes='',
        indicia_printer_sourced_by='',
        series=series,
    )


def _create_bond_type(name, description):
    """Create a Series Bond Type for filter tests."""
    return SeriesBondType.objects.create(
        name=name,
        description=description,
        notes='',
    )


def _create_bond(
    origin,
    target,
    bond_type,
    *,
    origin_issue=None,
    target_issue=None,
):
    """Create a Series Bond for filter tests."""
    return SeriesBond.objects.create(
        origin=origin,
        origin_issue=origin_issue,
        target=target,
        target_issue=target_issue,
        bond_type=bond_type,
        notes='',
    )


def _set_timestamps(bond, *, created, modified):
    """Persist explicit Series Bond timestamps for filter tests."""
    SeriesBond.objects.filter(pk=bond.pk).update(
        created=created,
        modified=modified,
    )
    bond.refresh_from_db()


def test_series_bond_filter_matches_relationship_ids(series, issue):
    """Relationship filters combine using direct foreign-key ids."""
    target = _create_series(series, name='Target Series', year_began=2000)
    other_target = _create_series(
        series,
        name='Other Target Series',
        year_began=2010,
    )
    target_issue = _create_issue(target, number='1', sort_code=1)
    other_target_issue = _create_issue(
        other_target,
        number='1',
        sort_code=1,
    )
    continues = _create_bond_type('continues', 'Continues at')
    other_type = _create_bond_type('related', 'Related to')
    matching = _create_bond(
        series,
        target,
        continues,
        origin_issue=issue,
        target_issue=target_issue,
    )
    _create_bond(
        series,
        other_target,
        other_type,
        origin_issue=issue,
        target_issue=other_target_issue,
    )

    queryset = SeriesBondFilterSet(
        {
            'origin': str(series.pk),
            'origin_issue': str(issue.pk),
            'target': str(target.pk),
            'target_issue': str(target_issue.pk),
            'bond_type': str(continues.pk),
        },
        queryset=SeriesBond.objects.all(),
    ).qs

    assert list(queryset) == [matching]


def test_series_bond_filter_matches_modified_range(series):
    """Modified ranges support delta-style Series Bond queries."""
    target = _create_series(series, name='Target Series', year_began=2000)
    bond_type = _create_bond_type('continues', 'Continues at')
    older = _create_bond(series, target, bond_type)
    newer = _create_bond(target, series, bond_type)
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

    queryset = SeriesBondFilterSet(
        {'modified__gt': (now - timedelta(days=1)).isoformat()},
        queryset=SeriesBond.objects.all(),
    ).qs

    assert list(queryset) == [newer]


def test_series_bond_filter_matches_created_range(series):
    """Created ranges support bounded Series Bond queries."""
    target = _create_series(series, name='Target Series', year_began=2000)
    bond_type = _create_bond_type('continues', 'Continues at')
    older = _create_bond(series, target, bond_type)
    newer = _create_bond(target, series, bond_type)
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

    queryset = SeriesBondFilterSet(
        {'created__lte': (now - timedelta(days=1)).isoformat()},
        queryset=SeriesBond.objects.all(),
    ).qs

    assert list(queryset) == [older]
