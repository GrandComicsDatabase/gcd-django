# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Serializers for v2 indicia publisher endpoints."""

from rest_framework import serializers

from apps.gcd.models import IndiciaPublisher


class IndiciaPublisherListSerializer(serializers.ModelSerializer):
    """Serialize trimmed indicia publisher list rows."""

    parent = serializers.SerializerMethodField()
    country = serializers.SlugRelatedField(
        read_only=True,
        slug_field='code',
    )

    class Meta:
        """Serializer metadata for indicia publisher list fields."""

        model = IndiciaPublisher
        fields = (
            'id',
            'name',
            'parent',
            'country',
            'is_surrogate',
            'year_began',
            'year_ended',
            'issue_count',
            'created',
            'modified',
        )

    def get_parent(self, obj):
        """Return the minimal nested parent Publisher reference."""
        return {
            'id': obj.parent_id,
            'name': obj.parent.name,
        }


class IndiciaPublisherSerializer(IndiciaPublisherListSerializer):
    """Serialize complete indicia publisher detail rows."""

    keywords = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
    )

    class Meta(IndiciaPublisherListSerializer.Meta):
        """Serializer metadata for indicia publisher detail fields."""

        fields = IndiciaPublisherListSerializer.Meta.fields + (
            'year_began_uncertain',
            'year_ended_uncertain',
            'year_overall_began',
            'year_overall_ended',
            'year_overall_began_uncertain',
            'year_overall_ended_uncertain',
            'url',
            'notes',
            'keywords',
        )
