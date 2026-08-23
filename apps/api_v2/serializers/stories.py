# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Serializers for v2 story endpoints."""

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from apps.api_v2.utils.credits import collect_story_credit_entries
from apps.gcd.models import FeatureLogo, FeatureNameDetail, Story

LEGACY_CREDIT_FIELDS = (
    'script',
    'pencils',
    'inks',
    'colors',
    'letters',
    'editing',
)


def _split_legacy_text(value):
    """Return semicolon-delimited legacy text as clean entries."""
    if not value:
        return []
    return [part.strip() for part in value.split(';') if part.strip()]


def _story_reference(story):
    """Return the minimal nested story reference, preserving nulls."""
    if story is None:
        return None
    return {
        'id': story.pk,
        'title': story.title,
    }


def _issue_reference(issue):
    """Return the minimal nested issue reference for story reprints."""
    return {
        'id': issue.pk,
        'descriptor': issue.issue_descriptor,
        'series_name': issue.series.name,
    }


def _reprint_reference(reprint):
    """Return a nested reprint reference for story detail responses."""
    return {
        'id': reprint.pk,
        'origin_story': _story_reference(reprint.origin),
        'origin_issue': _issue_reference(reprint.origin_issue),
        'target_story': _story_reference(reprint.target),
        'target_issue': _issue_reference(reprint.target_issue),
        'notes': reprint.notes,
    }


def _select_reprint_related(queryset, *ordering):
    """Return reprints with the related rows needed by story detail."""
    return queryset.select_related(
        'origin',
        'origin_issue',
        'origin_issue__series',
        'target',
        'target_issue',
        'target_issue__series',
    ).order_by(*ordering)


class StoryListSerializer(serializers.ModelSerializer):
    """Serialize story list responses for the v2 public API."""

    type = serializers.SerializerMethodField()
    issue = serializers.SerializerMethodField()

    class Meta:
        """Serializer metadata for story list fields."""

        model = Story
        fields = (
            'id',
            'title',
            'type',
            'feature',
            'sequence_number',
            'page_count',
            'issue',
            'created',
            'modified',
        )

    def get_type(self, obj):
        """Return the minimal nested story type reference."""
        return {
            'id': obj.type_id,
            'name': obj.type.name,
        }

    def get_issue(self, obj):
        """Return the minimal nested issue reference."""
        return {
            'id': obj.issue_id,
            'descriptor': obj.issue.issue_descriptor,
        }


class FeatureObjectSerializer(serializers.ModelSerializer):
    """Serialize selected feature names as parent Feature references."""

    id = serializers.IntegerField(source='feature_id')
    feature_type = serializers.SerializerMethodField()

    class Meta:
        """Serializer metadata for feature references."""

        model = FeatureNameDetail
        fields = (
            'id',
            'name',
            'feature_type',
        )

    def get_feature_type(self, obj):
        """Return the minimal nested feature type reference."""
        if obj.feature.feature_type_id is None:
            return None
        try:
            feature_type_name = obj.feature.feature_type.name
        except ObjectDoesNotExist:
            return None
        return {
            'id': obj.feature.feature_type_id,
            'name': feature_type_name,
        }


class FeatureLogoSerializer(serializers.ModelSerializer):
    """Serialize trimmed feature-logo references for story detail."""

    class Meta:
        """Serializer metadata for feature-logo references."""

        model = FeatureLogo
        fields = (
            'id',
            'name',
            'year_began',
            'year_ended',
        )


class StorySerializer(StoryListSerializer):
    """Serialize story detail responses for the v2 public API."""

    feature_object = serializers.SerializerMethodField()
    feature_logo = serializers.SerializerMethodField()
    credits = serializers.SerializerMethodField()
    characters = serializers.SerializerMethodField()
    text_credits = serializers.SerializerMethodField()
    text_characters = serializers.CharField(
        source='characters',
        read_only=True,
    )
    keywords = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
    )
    reprint_origins = serializers.SerializerMethodField()
    reprint_targets = serializers.SerializerMethodField()

    class Meta(StoryListSerializer.Meta):
        """Serializer metadata for story detail fields."""

        fields = StoryListSerializer.Meta.fields + (
            'feature_object',
            'feature_logo',
            'credits',
            'characters',
            'text_credits',
            'text_characters',
            'synopsis',
            'genre',
            'first_line',
            'notes',
            'keywords',
            'reprint_origins',
            'reprint_targets',
        )

    def get_feature_object(self, obj):
        """Return selected feature names with parent Feature identities."""
        feature_names = getattr(obj, 'active_feature_name_list', None)
        if feature_names is None:
            feature_names = (
                obj.feature_name.filter(
                    deleted=False,
                    feature__deleted=False,
                )
                .select_related('feature', 'feature__feature_type')
                .order_by('sort_name', 'id')
            )
        return FeatureObjectSerializer(feature_names, many=True).data

    def get_feature_logo(self, obj):
        """Return structured feature-logo references for the story."""
        logos = getattr(obj, 'active_feature_logo_list', None)
        if logos is None:
            logos = obj.feature_logo.filter(deleted=False).order_by(
                'sort_name',
                'id',
            )
        return FeatureLogoSerializer(logos, many=True).data

    def get_credits(self, obj):
        """Return structured creator credits for the story."""
        return collect_story_credit_entries(
            obj,
            prefetched_attr='active_credit_list',
        )

    def get_characters(self, obj):
        """Return structured character appearances for the story."""
        appearances = getattr(obj, 'active_character_list', None)
        if appearances is None:
            appearances = (
                obj.appearing_characters.filter(deleted=False)
                .select_related(
                    'character',
                    'role',
                )
                .order_by('character__sort_name', 'character__id')
            )
        return [
            {
                'character': {
                    'id': appearance.character.character_id,
                    'name': appearance.character.name,
                },
                'role': (
                    appearance.role.name
                    if appearance.role_id is not None
                    else None
                ),
            }
            for appearance in appearances
        ]

    def get_text_credits(self, obj):
        """Return legacy plain-text credit fields grouped by role."""
        return {
            credit_field: _split_legacy_text(getattr(obj, credit_field))
            for credit_field in LEGACY_CREDIT_FIELDS
        }

    def get_reprint_origins(self, obj):
        """Return reprints of source material into this story."""
        reprints = getattr(obj, 'active_reprint_origin_list', None)
        if reprints is None:
            reprints = _select_reprint_related(
                obj.from_all_reprints,
                'origin_issue_id',
                'origin_id',
                'id',
            )
        return [_reprint_reference(reprint) for reprint in reprints]

    def get_reprint_targets(self, obj):
        """Return reprints whose target includes this story."""
        reprints = getattr(obj, 'active_reprint_target_list', None)
        if reprints is None:
            reprints = _select_reprint_related(
                obj.to_all_reprints,
                'target_issue_id',
                'target_id',
                'id',
            )
        return [_reprint_reference(reprint) for reprint in reprints]
