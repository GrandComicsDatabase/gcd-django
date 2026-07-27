# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Serializers for v2 Brand endpoints."""

from rest_framework import serializers

from apps.gcd.models import Brand, BrandGroup, BrandUse


class BrandGroupReferenceSerializer(serializers.ModelSerializer):
    """Serialize an active Brand Group reference with its parent."""

    parent = serializers.SerializerMethodField()

    class Meta:
        """Serializer metadata for Brand Group references."""

        model = BrandGroup
        fields = ('id', 'name', 'parent')

    def get_parent(self, obj):
        """Return the minimal nested parent Publisher reference."""
        return {
            'id': obj.parent_id,
            'name': obj.parent.name,
        }


class BrandUseSerializer(serializers.ModelSerializer):
    """Serialize a Brand Use relationship for Brand detail responses."""

    publisher = serializers.SerializerMethodField()

    class Meta:
        """Serializer metadata for Brand Use fields."""

        model = BrandUse
        fields = (
            'id',
            'publisher',
            'year_began',
            'year_ended',
            'year_began_uncertain',
            'year_ended_uncertain',
            'notes',
            'created',
            'modified',
        )

    def get_publisher(self, obj):
        """Return the minimal nested Publisher reference."""
        return {
            'id': obj.publisher_id,
            'name': obj.publisher.name,
        }


class BrandListSerializer(serializers.ModelSerializer):
    """Serialize trimmed Brand list rows."""

    class Meta:
        """Serializer metadata for Brand list fields."""

        model = Brand
        fields = (
            'id',
            'name',
            'generic',
            'year_began',
            'year_ended',
            'issue_count',
            'created',
            'modified',
        )


class BrandSerializer(BrandListSerializer):
    """Serialize complete Brand detail rows."""

    keywords = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
    )
    groups = serializers.SerializerMethodField()
    uses = serializers.SerializerMethodField()

    class Meta(BrandListSerializer.Meta):
        """Serializer metadata for Brand detail fields."""

        fields = BrandListSerializer.Meta.fields + (
            'year_began_uncertain',
            'year_ended_uncertain',
            'year_overall_began',
            'year_overall_ended',
            'year_overall_began_uncertain',
            'year_overall_ended_uncertain',
            'url',
            'notes',
            'keywords',
            'groups',
            'uses',
        )

    def get_groups(self, obj):
        """Return ordered active Brand Group references."""
        groups = getattr(obj, 'active_brand_group_list', None)
        if groups is None:
            groups = (
                obj.group.filter(
                    deleted=False,
                    parent__deleted=False,
                )
                .select_related('parent')
                .order_by('parent__name', 'name', 'id')
            )
        return BrandGroupReferenceSerializer(groups, many=True).data

    def get_uses(self, obj):
        """Return ordered Brand Uses tied to active Publishers."""
        uses = getattr(obj, 'active_brand_use_list', None)
        if uses is None:
            uses = (
                obj.in_use.filter(publisher__deleted=False)
                .select_related('publisher')
                .order_by('publisher__name', 'year_began', 'id')
            )
        return BrandUseSerializer(uses, many=True).data
