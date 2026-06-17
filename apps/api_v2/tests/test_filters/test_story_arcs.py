# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the story-arc filter set."""

from datetime import timedelta

from django.utils import timezone

from apps.api_v2.filters.story_arcs import StoryArcFilterSet
from apps.gcd.models import StoryArc


def _create_story_arc(
    language,
    *,
    name,
    sort_name=None,
    year_first_published=1986,
    deleted=False,
):
    """Create a story arc row for filter tests."""
    return StoryArc.objects.create(
        name=name,
        sort_name=sort_name or name,
        disambiguation='',
        language=language,
        year_first_published=year_first_published,
        description='Story arc description',
        notes='Story arc notes',
        deleted=deleted,
    )


def _set_timestamps(obj, *, created, modified):
    """Persist explicit created/modified timestamps for filter tests."""
    StoryArc.objects.filter(pk=obj.pk).update(
        created=created,
        modified=modified,
    )
    obj.refresh_from_db()


def test_story_arc_filter_matches_name_icontains(language):
    """The name filter uses case-insensitive containment."""
    matching = _create_story_arc(language, name='Crisis on Infinite Earths')
    _create_story_arc(language, name='Secret Wars')

    qs = StoryArcFilterSet(
        {'name': 'crisis'},
        queryset=StoryArc.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [matching]


def test_story_arc_filter_matches_modified_range(language):
    """Modified range filters support delta-style story-arc sync queries."""
    older = _create_story_arc(language, name='Older Arc')
    newer = _create_story_arc(language, name='Newer Arc')
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

    qs = StoryArcFilterSet(
        {'modified__gt': (now - timedelta(days=1)).isoformat()},
        queryset=StoryArc.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [newer]


def test_story_arc_filter_matches_created_range(language):
    """Created range filters support bounded story-arc queries."""
    older = _create_story_arc(language, name='Older Arc')
    newer = _create_story_arc(language, name='Newer Arc')
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

    qs = StoryArcFilterSet(
        {'created__lte': (now - timedelta(days=1)).isoformat()},
        queryset=StoryArc.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [older]
