# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Serializers for v2 story-arc endpoints."""

from django.db.models import Prefetch
from rest_framework import serializers

from apps.gcd.models import Reprint, StoryArc


def _issue_reference(issue):
    """Return the minimal nested issue reference for story memberships."""
    return {
        'id': issue.pk,
        'descriptor': issue.issue_descriptor,
    }


def _is_same_language_reprint(story, language_id):
    """Return whether ``story`` is a same-language reprint membership."""
    reprints = getattr(story, 'active_story_arc_reprint_list', None)
    if reprints is None:
        reprints = story.from_all_reprints.select_related(
            'origin_issue__series',
        )
    return any(
        reprint.origin_issue.series.language_id == language_id
        for reprint in reprints
    )


def _primary_stories(story_arc):
    """Return ordered primary story memberships for ``story_arc``."""
    stories = getattr(story_arc, 'active_story_arc_story_list', None)
    if stories is None:
        stories, _reprinted_stories = story_arc.stories()
        stories = stories.prefetch_related(
            Prefetch(
                'from_all_reprints',
                queryset=Reprint.objects.select_related(
                    'origin_issue__series',
                ).order_by('id'),
                to_attr='active_story_arc_reprint_list',
            ),
        )
    return [
        story
        for story in stories
        if not _is_same_language_reprint(story, story_arc.language_id)
    ]


class StoryArcListSerializer(serializers.ModelSerializer):
    """Serialize story-arc list responses for the v2 public API."""

    class Meta:
        """Serializer metadata for story-arc list fields."""

        model = StoryArc
        fields = (
            'id',
            'name',
            'notes',
            'created',
            'modified',
        )


class StoryArcSerializer(StoryArcListSerializer):
    """Serialize story-arc detail responses for the v2 public API."""

    stories = serializers.SerializerMethodField()
    keywords = serializers.SerializerMethodField()

    class Meta(StoryArcListSerializer.Meta):
        """Serializer metadata for story-arc detail fields."""

        fields = StoryArcListSerializer.Meta.fields + (
            'stories',
            'keywords',
        )

    def get_stories(self, obj):
        """Return ordered primary story memberships for the story arc."""
        return [
            {
                'id': story.pk,
                'title': story.title,
                'issue': _issue_reference(story.issue),
                'sequence_number': story.sequence_number,
            }
            for story in _primary_stories(obj)
        ]

    def get_keywords(self, obj):
        """Return story-arc keywords when storage exists for them."""
        del obj
        return []
