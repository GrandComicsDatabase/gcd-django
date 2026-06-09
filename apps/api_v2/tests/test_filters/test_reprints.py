# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the reprint filter set."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.api_v2.filters.reprints import ReprintFilterSet
from apps.gcd.models import Reprint, Story, StoryType


def _create_story_type(name='Comic Story', sort_code=19):
    """Create or return a story type row for reprint tests."""
    story_type, _ = StoryType.objects.get_or_create(
        name=name,
        defaults={'sort_code': sort_code},
    )
    return story_type


def _create_issue(series, *, number, sort_code):
    """Create a minimal issue row for reprint filter tests."""
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
    """Create a minimal story row for reprint filter tests."""
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


def _create_reprint(origin, target, *, notes=''):
    """Create a reprint row for filter tests."""
    return Reprint.objects.create(
        origin=origin,
        target=target,
        origin_issue=origin.issue,
        target_issue=target.issue,
        notes=notes,
    )


def _set_timestamps(obj, *, created, modified):
    """Persist explicit created/modified timestamps for filter tests."""
    Reprint.objects.filter(pk=obj.pk).update(
        created=created,
        modified=modified,
    )
    obj.refresh_from_db()


def test_reprint_filter_matches_origin_and_target_story(issue):
    """Story id filters narrow reprint results correctly."""
    origin = _create_story(issue, title='Original Story', sequence_number=1)
    target = _create_story(issue, title='Target Story', sequence_number=2)
    other_target = _create_story(
        issue,
        title='Other Target Story',
        sequence_number=3,
    )
    matching = _create_reprint(origin, target, notes='matched')
    _create_reprint(origin, other_target, notes='other')

    qs = ReprintFilterSet(
        {
            'origin_story': str(origin.pk),
            'target_story': str(target.pk),
        },
        queryset=Reprint.objects.all(),
    ).qs

    assert list(qs) == [matching]


def test_reprint_filter_matches_issue_and_series(
    issue,
    publisher,
):
    """Issue and series filters narrow reprint results correctly."""
    other_series = issue.series.__class__.objects.create(
        name='Other Series',
        sort_name='Other Series',
        year_began=1991,
        publication_dates='1991 - present',
        notes='',
        tracking_notes='',
        country=issue.series.country,
        language=issue.series.language,
        publisher=publisher,
    )
    target_issue = _create_issue(
        issue.series,
        number='2',
        sort_code=2,
    )
    other_issue = _create_issue(other_series, number='1', sort_code=1)
    origin = _create_story(issue, title='Original Story', sequence_number=1)
    target = _create_story(
        target_issue,
        title='Target Story',
        sequence_number=1,
    )
    other_target = _create_story(
        other_issue,
        title='Other Target Story',
        sequence_number=1,
    )
    matching = _create_reprint(origin, target, notes='matched')
    _create_reprint(origin, other_target, notes='other')

    qs = ReprintFilterSet(
        {
            'origin_issue': str(issue.pk),
            'target_issue': str(target_issue.pk),
            'origin_issue__series': str(issue.series_id),
            'target_issue__series': str(target_issue.series_id),
        },
        queryset=Reprint.objects.all(),
    ).qs

    assert list(qs) == [matching]


def test_reprint_filter_matches_modified_range(issue):
    """Modified range filters support delta-style reprint sync queries."""
    origin = _create_story(issue, title='Original Story', sequence_number=1)
    older_target = _create_story(
        issue,
        title='Older Target Story',
        sequence_number=2,
    )
    newer_target = _create_story(
        issue,
        title='Newer Target Story',
        sequence_number=3,
    )
    older = _create_reprint(origin, older_target, notes='older')
    newer = _create_reprint(origin, newer_target, notes='newer')
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

    qs = ReprintFilterSet(
        {'modified__gt': (now - timedelta(days=1)).isoformat()},
        queryset=Reprint.objects.all(),
    ).qs

    assert list(qs) == [newer]


def test_reprint_filter_matches_created_range(issue):
    """Created range filters support bounded reprint queries."""
    origin = _create_story(issue, title='Original Story', sequence_number=1)
    older_target = _create_story(
        issue,
        title='Older Target Story',
        sequence_number=2,
    )
    newer_target = _create_story(
        issue,
        title='Newer Target Story',
        sequence_number=3,
    )
    older = _create_reprint(origin, older_target, notes='older')
    newer = _create_reprint(origin, newer_target, notes='newer')
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

    qs = ReprintFilterSet(
        {'created__lte': (now - timedelta(days=1)).isoformat()},
        queryset=Reprint.objects.all(),
    ).qs

    assert list(qs) == [older]
