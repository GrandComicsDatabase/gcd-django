# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Serializers for v2 story endpoints."""

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from apps.api_v2.utils.credits import collect_story_credit_entries
from apps.gcd.models import Feature, FeatureLogo, Story


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
    """Serialize trimmed feature references for story detail."""

    feature_type = serializers.SerializerMethodField()

    class Meta:
        """Serializer metadata for feature references."""

        model = Feature
        fields = (
            'id',
            'name',
            'feature_type',
        )

    def get_feature_type(self, obj):
        """Return the minimal nested feature type reference."""
        if obj.feature_type_id is None:
            return None
        try:
            feature_type_name = obj.feature_type.name
        except ObjectDoesNotExist:
            return None
        return {
            'id': obj.feature_type_id,
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
            'synopsis',
            'genre',
            'first_line',
            'notes',
            'keywords',
            'reprint_origins',
            'reprint_targets',
        )

    def get_feature_object(self, obj):
        """Return structured feature references for the story."""
        features = getattr(obj, 'active_feature_list', None)
        if features is None:
            features = (
                obj.feature_object.filter(deleted=False)
                .select_related('feature_type')
                .order_by('sort_name', 'id')
            )
        return FeatureObjectSerializer(features, many=True).data

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

    def get_reprint_origins(self, obj):
        """Return story ids reprinted into this story."""
        reprints = getattr(obj, 'active_reprint_origin_list', None)
        if reprints is None:
            reprints = obj.from_all_reprints.exclude(origin=None).order_by(
                'origin_id',
                'id',
            )
        return [
            reprint.origin_id
            for reprint in reprints
            if reprint.origin_id is not None
        ]

    def get_reprint_targets(self, obj):
        """Return story ids that reprint this story."""
        reprints = getattr(obj, 'active_reprint_target_list', None)
        if reprints is None:
            reprints = obj.to_all_reprints.exclude(target=None).order_by(
                'target_id',
                'id',
            )
        return [
            reprint.target_id
            for reprint in reprints
            if reprint.target_id is not None
        ]
