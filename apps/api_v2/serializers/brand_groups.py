# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Serializers for v2 brand group endpoints."""

from rest_framework import serializers

from apps.gcd.models import BrandGroup


class BrandGroupListSerializer(serializers.ModelSerializer):
    """Serialize trimmed brand group list rows."""

    parent = serializers.SerializerMethodField()

    class Meta:
        """Serializer metadata for brand group list fields."""

        model = BrandGroup
        fields = (
            'id',
            'name',
            'parent',
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


class BrandGroupSerializer(BrandGroupListSerializer):
    """Serialize complete brand group detail rows."""

    keywords = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
    )
    emblems = serializers.SerializerMethodField()

    class Meta(BrandGroupListSerializer.Meta):
        """Serializer metadata for brand group detail fields."""

        fields = BrandGroupListSerializer.Meta.fields + (
            'year_began_uncertain',
            'year_ended_uncertain',
            'year_overall_began',
            'year_overall_ended',
            'year_overall_began_uncertain',
            'year_overall_ended_uncertain',
            'url',
            'notes',
            'keywords',
            'emblems',
        )

    def get_emblems(self, obj):
        """Return ordered active Brand emblems for this group."""
        emblems = getattr(obj, 'active_brand_group_emblem_list', None)
        if emblems is None:
            emblems = obj.brand_set.filter(deleted=False).order_by(
                'name',
                'id',
            )
        return [
            {
                'id': emblem.pk,
                'name': emblem.name,
                'generic': emblem.generic,
                'year_began': emblem.year_began,
                'year_ended': emblem.year_ended,
            }
            for emblem in emblems
        ]
