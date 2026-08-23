# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Migration tests for persistent Series Bond timestamps."""

from datetime import UTC, datetime

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.gcd.models import Series, SeriesBond, SeriesBondType
from apps.oi.models import CTYPES, Changeset, SeriesBondRevision


def _create_target_series(series):
    """Create a target Series sharing the fixture reference data."""
    return Series.objects.create(
        name='Target Series',
        sort_name='Target Series',
        year_began=2000,
        publication_dates='2000 - present',
        notes='',
        tracking_notes='',
        country=series.country,
        language=series.language,
        publisher=series.publisher,
    )


def _create_revision(bond, user, *, state, name):
    """Create a Series Bond revision in the requested changeset state."""
    changeset = Changeset.objects.create(
        state=state,
        indexer=user,
        change_type=CTYPES['series_bond'],
    )
    return SeriesBondRevision.objects.create(
        changeset=changeset,
        series_bond=bond,
        origin=bond.origin,
        target=bond.target,
        bond_type=bond.bond_type,
        notes=name,
    )


@pytest.mark.django_db(transaction=True)
def test_series_bond_timestamp_migration_uses_history_or_shared_baseline(
    series,
):
    """Approved history wins while missing history receives one baseline."""
    target = _create_target_series(series)
    bond_type = SeriesBondType.objects.create(
        name='continues',
        description='Continues at',
        notes='',
    )
    historical_bond = SeriesBond.objects.create(
        origin=series,
        target=target,
        bond_type=bond_type,
        notes='',
    )
    baseline_bond = SeriesBond.objects.create(
        origin=target,
        target=series,
        bond_type=bond_type,
        notes='',
    )
    user = get_user_model().objects.create_user(username='bond_migrator')
    earliest = _create_revision(
        historical_bond,
        user,
        state=5,
        name='earliest',
    )
    latest = _create_revision(
        historical_bond,
        user,
        state=5,
        name='latest',
    )
    ignored = _create_revision(
        historical_bond,
        user,
        state=1,
        name='unapproved',
    )
    earliest_created = datetime(2010, 1, 1, tzinfo=UTC)
    earliest_modified = datetime(2010, 1, 2, tzinfo=UTC)
    latest_created = datetime(2020, 1, 1, tzinfo=UTC)
    latest_modified = datetime(2020, 1, 2, tzinfo=UTC)
    ignored_created = datetime(2025, 1, 1, tzinfo=UTC)
    SeriesBondRevision.objects.filter(pk=earliest.pk).update(
        created=earliest_created,
        modified=earliest_modified,
    )
    SeriesBondRevision.objects.filter(pk=latest.pk).update(
        created=latest_created,
        modified=latest_modified,
    )
    SeriesBondRevision.objects.filter(pk=ignored.pk).update(
        created=ignored_created,
        modified=ignored_created,
    )

    executor = MigrationExecutor(connection)
    latest_targets = executor.loader.graph.leaf_nodes()
    previous_targets = [
        ('gcd', '0073_merge_api_v2_beta'),
        ('oi', '0062_add_character_order'),
    ]

    try:
        executor.migrate(previous_targets)
        executor = MigrationExecutor(connection)
        executor.migrate([('gcd', '0074_series_bond_timestamps')])
        migrated_apps = executor.loader.project_state(
            [('gcd', '0074_series_bond_timestamps')]
        ).apps
        migrated_bond = migrated_apps.get_model('gcd', 'SeriesBond')
        historical = migrated_bond.objects.get(pk=historical_bond.pk)
        baseline = migrated_bond.objects.get(pk=baseline_bond.pk)

        assert historical.created == earliest_created
        assert historical.modified == latest_modified
        assert baseline.created == baseline.modified
        assert baseline.created > ignored_created
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(latest_targets)
