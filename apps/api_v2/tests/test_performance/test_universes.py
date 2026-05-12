# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Performance tests for universe endpoints."""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

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


def _create_universe(*, multiverse_name, verse, name, designation, year):
    """Create a minimal universe row for performance tests."""
    return Universe.objects.create(
        multiverse=multiverse_name,
        verse=verse,
        name=name,
        designation=designation,
        year_first_published=year,
        description='',
        notes='',
    )


def test_universe_list_query_count(api_client, db):
    """The universe list stays on the expected query budget."""
    marvel = _create_multiverse('Marvel')
    dc = _create_multiverse('DC')
    _create_universe(
        multiverse_name='Marvel',
        verse=marvel,
        name='Ultimate',
        designation='Earth-1610',
        year=2000,
    )
    _create_universe(
        multiverse_name='DC',
        verse=dc,
        name='Mainstream',
        designation='Earth-0',
        year=1938,
    )

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(reverse('universe-list'))

    assert response.status_code == 200
    assert len(context) == 3


def test_universe_detail_query_count(api_client, db):
    """The universe detail endpoint avoids lazy-loading regressions."""
    marvel = _create_multiverse('Marvel')
    universe = _create_universe(
        multiverse_name='Marvel',
        verse=marvel,
        name='Ultimate',
        designation='Earth-1610',
        year=2000,
    )

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(
            reverse('universe-detail', kwargs={'pk': universe.pk}),
        )

    assert response.status_code == 200
    assert len(context) == 2
