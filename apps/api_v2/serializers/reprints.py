# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Serializers for v2 reprint endpoints."""

from rest_framework import serializers

from apps.gcd.models import Reprint


def _story_reference(story):
    """Return the minimal nested story reference, preserving nulls."""
    if story is None:
        return None
    return {
        'id': story.pk,
        'title': story.title,
    }


def _issue_reference(issue):
    """Return the minimal nested issue reference for reprints."""
    return {
        'id': issue.pk,
        'descriptor': issue.issue_descriptor,
        'series_name': issue.series.name,
    }


class ReprintSerializer(serializers.ModelSerializer):
    """Serialize reprint list and detail responses for the v2 public API."""

    origin_story = serializers.SerializerMethodField()
    origin_issue = serializers.SerializerMethodField()
    target_story = serializers.SerializerMethodField()
    target_issue = serializers.SerializerMethodField()

    class Meta:
        """Serializer metadata for reprint fields."""

        model = Reprint
        fields = (
            'id',
            'origin_story',
            'origin_issue',
            'target_story',
            'target_issue',
            'notes',
            'created',
            'modified',
        )

    def get_origin_story(self, obj):
        """Return the nullable origin story reference."""
        return _story_reference(obj.origin)

    def get_origin_issue(self, obj):
        """Return the origin issue reference."""
        return _issue_reference(obj.origin_issue)

    def get_target_story(self, obj):
        """Return the nullable target story reference."""
        return _story_reference(obj.target)

    def get_target_issue(self, obj):
        """Return the target issue reference."""
        return _issue_reference(obj.target_issue)
