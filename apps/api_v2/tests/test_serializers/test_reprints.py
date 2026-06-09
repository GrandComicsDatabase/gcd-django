# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the reprint serializer."""

from decimal import Decimal

from apps.api_v2.serializers.reprints import ReprintSerializer
from apps.gcd.models import Reprint, Story, StoryType


def _create_story_type(name='Comic Story', sort_code=19):
    """Create or return a story type row for reprint tests."""
    story_type, _ = StoryType.objects.get_or_create(
        name=name,
        defaults={'sort_code': sort_code},
    )
    return story_type


def _create_issue(series, *, number, sort_code):
    """Create a minimal issue row for reprint serializer tests."""
    return series.issue_set.model.objects.create(
        number=number,
        title='',
        volume='',
        isbn='',
        valid_isbn='',
        variant_name='',
        barcode='',
        publication_date='',
        key_date='2024-01-01',
        on_sale_date='2024-01-08',
        sort_code=sort_code,
        indicia_frequency='',
        price='',
        editing='',
        notes='',
        indicia_printer_sourced_by='',
        series=series,
    )


def _create_story(issue, *, title, sequence_number):
    """Create a story row for serializer tests."""
    return Story.objects.create(
        title=title,
        feature='Feature Text',
        sequence_number=sequence_number,
        page_count=Decimal('10.000'),
        script='',
        pencils='',
        inks='',
        colors='',
        letters='',
        editing='',
        job_number='',
        genre='',
        characters='',
        synopsis='',
        reprint_notes='',
        notes='',
        issue=issue,
        type=_create_story_type(),
    )


def test_reprint_serializer_exposes_contract(issue):
    """The reprint serializer emits the Sprint 3 reprint contract."""
    target_issue = _create_issue(issue.series, number='2', sort_code=2)
    origin = _create_story(issue, title='Original Story', sequence_number=1)
    target = _create_story(
        target_issue,
        title='Target Story',
        sequence_number=1,
    )
    reprint = Reprint.objects.create(
        origin=origin,
        target=target,
        origin_issue=origin.issue,
        target_issue=target.issue,
        notes='Translated and recolored.',
    )

    data = ReprintSerializer(reprint).data

    assert set(data) == {
        'id',
        'origin_story',
        'origin_issue',
        'target_story',
        'target_issue',
        'notes',
        'created',
        'modified',
    }
    assert data['id'] == reprint.pk
    assert data['origin_story'] == {
        'id': origin.pk,
        'title': 'Original Story',
    }
    assert data['target_story'] == {
        'id': target.pk,
        'title': 'Target Story',
    }
    assert data['origin_issue'] == {
        'id': issue.pk,
        'descriptor': issue.issue_descriptor,
        'series_name': issue.series.name,
    }
    assert data['target_issue'] == {
        'id': target_issue.pk,
        'descriptor': target_issue.issue_descriptor,
        'series_name': target_issue.series.name,
    }
    assert data['notes'] == 'Translated and recolored.'


def test_reprint_serializer_handles_issue_level_null_stories(issue):
    """Issue-level reprints serialize nullable story references cleanly."""
    target_issue = _create_issue(issue.series, number='2', sort_code=2)
    target = _create_story(
        target_issue,
        title='Target Story',
        sequence_number=1,
    )
    reprint = Reprint.objects.create(
        origin=None,
        target=target,
        origin_issue=issue,
        target_issue=target.issue,
        notes='Issue-level origin.',
    )

    data = ReprintSerializer(reprint).data

    assert data['origin_story'] is None
    assert data['target_story'] == {
        'id': target.pk,
        'title': 'Target Story',
    }
    assert data['origin_issue'] == {
        'id': issue.pk,
        'descriptor': issue.issue_descriptor,
        'series_name': issue.series.name,
    }
    assert data['target_issue'] == {
        'id': target_issue.pk,
        'descriptor': target_issue.issue_descriptor,
        'series_name': target_issue.series.name,
    }
