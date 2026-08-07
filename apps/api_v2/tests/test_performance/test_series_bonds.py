# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Performance tests for Series Bond endpoints."""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import Series, SeriesBond, SeriesBondType


def _create_target_series(series, *, name, year_began):
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


def _create_bond(origin, target, bond_type, *, origin_issue=None):
    """Create a Series Bond for performance tests."""
    return SeriesBond.objects.create(
        origin=origin,
        origin_issue=origin_issue,
        target=target,
        target_issue=None,
        bond_type=bond_type,
        notes='',
    )


def test_series_bond_list_query_count(api_client, series, issue):
    """The Series Bond list stays on the expected query budget."""
    target = _create_target_series(
        series,
        name='Target Series',
        year_began=2000,
    )
    other_target = _create_target_series(
        series,
        name='Other Target Series',
        year_began=2010,
    )
    bond_type = SeriesBondType.objects.create(
        name='continues',
        description='Continues at',
        notes='',
    )
    _create_bond(series, target, bond_type, origin_issue=issue)
    _create_bond(series, other_target, bond_type, origin_issue=issue)

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(reverse('series-bond-list'))

    assert response.status_code == 200
    assert len(context) == 3


def test_series_bond_detail_query_count(api_client, series, issue):
    """The Series Bond detail avoids lazy-loading regressions."""
    target = _create_target_series(
        series,
        name='Target Series',
        year_began=2000,
    )
    bond_type = SeriesBondType.objects.create(
        name='continues',
        description='Continues at',
        notes='',
    )
    bond = _create_bond(
        series,
        target,
        bond_type,
        origin_issue=issue,
    )

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(
            reverse('series-bond-detail', kwargs={'pk': bond.pk}),
        )

    assert response.status_code == 200
    assert len(context) == 2
