# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the Series Bond serializers."""

from datetime import timedelta

from django.utils import timezone

from apps.api_v2.serializers.series_bonds import (
    SeriesBondListSerializer,
    SeriesBondSerializer,
)
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
    """Create a minimal Issue for Series Bond serializer tests."""
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


def _create_bond(series, issue, *, include_issues=True):
    """Create a complete Series Bond serializer fixture."""
    target = _create_series(series, name='Target Series', year_began=2000)
    target_issue = _create_issue(target, number='1', sort_code=1)
    bond_type = SeriesBondType.objects.create(
        name='continues',
        description='Continues at',
        notes='',
    )
    bond = SeriesBond.objects.create(
        origin=series,
        origin_issue=issue if include_issues else None,
        target=target,
        target_issue=target_issue if include_issues else None,
        bond_type=bond_type,
        notes='The numbering continues in the target Series.',
    )
    return bond, target, target_issue, bond_type


def test_series_bond_list_serializer_exposes_trimmed_contract(series, issue):
    """List rows include useful references and persistent timestamps."""
    bond, target, target_issue, bond_type = _create_bond(series, issue)

    data = SeriesBondListSerializer(bond).data

    assert set(data) == {
        'id',
        'origin',
        'origin_issue',
        'target',
        'target_issue',
        'bond_type',
        'created',
        'modified',
    }
    assert data['origin'] == {
        'id': series.pk,
        'name': 'Test Series',
        'year_began': 1990,
    }
    assert data['origin_issue'] == {
        'id': issue.pk,
        'descriptor': issue.issue_descriptor,
    }
    assert data['target'] == {
        'id': target.pk,
        'name': 'Target Series',
        'year_began': 2000,
    }
    assert data['target_issue'] == {
        'id': target_issue.pk,
        'descriptor': target_issue.issue_descriptor,
    }
    assert data['bond_type'] == {
        'id': bond_type.pk,
        'name': 'continues',
        'description': 'Continues at',
    }
    assert data['created']
    assert data['modified']
    assert 'notes' not in data
    assert 'reserved' not in data


def test_series_bond_detail_serializer_adds_notes_and_handles_null_issues(
    series,
    issue,
):
    """Detail rows add notes and preserve nullable Issue references."""
    bond, _target, _target_issue, _bond_type = _create_bond(
        series,
        issue,
        include_issues=False,
    )

    data = SeriesBondSerializer(bond).data

    assert set(data) == {
        'id',
        'origin',
        'origin_issue',
        'target',
        'target_issue',
        'bond_type',
        'created',
        'modified',
        'notes',
    }
    assert data['origin_issue'] is None
    assert data['target_issue'] is None
    assert data['notes'] == 'The numbering continues in the target Series.'
    assert 'reserved' not in data


def test_series_bond_save_updates_persistent_modified_timestamp(series):
    """Saving an existing Series Bond advances its stored timestamp."""
    bond, _target, _target_issue, _bond_type = _create_bond(
        series,
        None,
        include_issues=False,
    )
    old_modified = timezone.now() - timedelta(days=1)
    SeriesBond.objects.filter(pk=bond.pk).update(modified=old_modified)
    bond.refresh_from_db()
    bond.notes = 'Updated notes.'

    bond.save()
    bond.refresh_from_db()

    assert bond.modified > old_modified
