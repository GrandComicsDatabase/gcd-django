# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the story-arc serializers."""

from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.api_v2.serializers.story_arcs import (
    StoryArcListSerializer,
    StoryArcSerializer,
)
from apps.gcd.models import Reprint, Story, StoryArc, StoryType


def _create_story_arc(language, *, name='Crisis on Infinite Earths'):
    """Create a story arc row for serializer tests."""
    return StoryArc.objects.create(
        name=name,
        sort_name=name,
        disambiguation='',
        language=language,
        year_first_published=1986,
        description='Story arc description',
        notes='Story arc notes',
    )


def _create_story_type(name='Comic Story', sort_code=19):
    """Create or return a story type row for story-arc tests."""
    story_type, _ = StoryType.objects.get_or_create(
        name=name,
        defaults={'sort_code': sort_code},
    )
    return story_type


def _create_issue(series, *, number, sort_code, key_date='1986-01-01'):
    """Create a minimal issue row for story-arc serializer tests."""
    return series.issue_set.model.objects.create(
        number=number,
        title='',
        volume='',
        isbn='',
        valid_isbn='',
        variant_name='',
        barcode='',
        publication_date='',
        key_date=key_date,
        on_sale_date=key_date,
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


def test_story_arc_list_serializer_exposes_list_contract(language):
    """The story-arc list serializer emits the trimmed Sprint 3 contract."""
    story_arc = _create_story_arc(language)

    data = StoryArcListSerializer(story_arc).data

    assert set(data) == {
        'id',
        'name',
        'notes',
        'created',
        'modified',
    }
    assert data['id'] == story_arc.pk
    assert data['name'] == 'Crisis on Infinite Earths'
    assert data['notes'] == 'Story arc notes'


def test_story_arc_detail_serializer_exposes_ordered_story_membership(
    issue,
    language,
):
    """The detail serializer emits primary ordered story membership."""
    story_arc = _create_story_arc(language)
    second_issue = _create_issue(
        issue.series,
        number='2',
        sort_code=2,
        key_date='1986-02-01',
    )
    first_story = _create_story(
        issue,
        title='First Story',
        sequence_number=1,
    )
    second_story = _create_story(
        second_issue,
        title='Second Story',
        sequence_number=1,
    )
    first_story.story_arc.add(story_arc)
    second_story.story_arc.add(story_arc)

    data = StoryArcSerializer(story_arc).data

    assert set(data) == {
        'id',
        'name',
        'notes',
        'created',
        'modified',
        'stories',
        'keywords',
    }
    assert data['stories'] == [
        {
            'id': first_story.pk,
            'title': 'First Story',
            'issue': {
                'id': issue.pk,
                'descriptor': issue.issue_descriptor,
            },
            'sequence_number': 1,
        },
        {
            'id': second_story.pk,
            'title': 'Second Story',
            'issue': {
                'id': second_issue.pk,
                'descriptor': second_issue.issue_descriptor,
            },
            'sequence_number': 1,
        },
    ]
    assert data['keywords'] == []


def test_story_arc_detail_serializer_omits_reprinted_story_bucket(
    issue,
    language,
):
    """Reprinted story memberships are omitted from the primary list."""
    story_arc = _create_story_arc(language)
    original = _create_story(
        issue,
        title='Original Story',
        sequence_number=1,
    )
    reprinted = _create_story(
        issue,
        title='Reprinted Story',
        sequence_number=2,
    )
    original.story_arc.add(story_arc)
    reprinted.story_arc.add(story_arc)
    Reprint.objects.create(
        origin=original,
        target=reprinted,
        origin_issue=original.issue,
        target_issue=reprinted.issue,
        notes='Story reprinted in same language.',
    )

    data = StoryArcSerializer(story_arc).data

    assert data['stories'] == [
        {
            'id': original.pk,
            'title': 'Original Story',
            'issue': {
                'id': issue.pk,
                'descriptor': issue.issue_descriptor,
            },
            'sequence_number': 1,
        },
    ]


def test_story_arc_detail_serializer_prefetches_fallback_reprint_checks(
    issue,
    language,
):
    """Direct serializer use avoids per-story reprint checks."""
    story_arc = _create_story_arc(language)
    stories = [
        _create_story(
            issue,
            title=f'Primary Story {number}',
            sequence_number=number,
        )
        for number in range(1, 4)
    ]
    for story in stories:
        story.story_arc.add(story_arc)

    with CaptureQueriesContext(connection) as context:
        data = StoryArcSerializer(story_arc).data

    assert [story['id'] for story in data['stories']] == [
        story.pk for story in stories
    ]
    assert len(context) == 2
