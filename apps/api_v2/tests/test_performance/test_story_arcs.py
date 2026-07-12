# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Performance tests for story-arc endpoints."""

from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import Story, StoryArc, StoryType


def _create_story_arc(language, *, name='Crisis on Infinite Earths'):
    """Create a story arc row for performance tests."""
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
    """Create or return a story type row for performance tests."""
    story_type, _ = StoryType.objects.get_or_create(
        name=name,
        defaults={'sort_code': sort_code},
    )
    return story_type


def _create_story(issue, *, title, sequence_number):
    """Create a story row for performance tests."""
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


def test_story_arc_list_query_count(api_client, language):
    """The story-arc list stays on the expected query budget."""
    _create_story_arc(language, name='Crisis on Infinite Earths')
    _create_story_arc(language, name='Secret Wars')

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(reverse('story-arc-list'))

    assert response.status_code == 200
    assert len(context) == 3


def test_story_arc_detail_query_count(api_client, issue, language):
    """The story-arc detail endpoint avoids lazy-loading regressions."""
    story_arc = _create_story_arc(language)
    story = _create_story(issue, title='First Story', sequence_number=1)
    story.story_arc.add(story_arc)

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(
            reverse('story-arc-detail', kwargs={'pk': story_arc.pk}),
        )

    assert response.status_code == 200
    assert len(context) == 4
