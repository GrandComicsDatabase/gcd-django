# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Serializers for v2 series endpoints."""

from rest_framework import serializers

from apps.gcd.models import Series


class BaseSeriesSerializer(serializers.ModelSerializer):
    """Serialize shared series fields for the v2 API."""

    country = serializers.SlugRelatedField(read_only=True, slug_field='code')
    language = serializers.SlugRelatedField(read_only=True, slug_field='code')
    publication_type = serializers.CharField(
        source='publication_type.name',
        read_only=True,
        allow_null=True,
    )
    publisher = serializers.SerializerMethodField()
    keywords = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
    )

    class Meta:
        """Serializer metadata for shared series fields."""

        model = Series
        fields = (
            'id',
            'name',
            'sort_name',
            'year_began',
            'year_ended',
            'country',
            'language',
            'publisher',
            'publication_type',
            'color',
            'dimensions',
            'paper_stock',
            'binding',
            'publishing_format',
            'notes',
            'issue_count',
            'keywords',
            'created',
            'modified',
        )

    def get_publisher(self, obj):
        """Return the minimal nested publisher reference."""
        return {
            'id': obj.publisher_id,
            'name': obj.publisher.name,
        }


class SeriesListSerializer(BaseSeriesSerializer):
    """Serialize lightweight series list rows for the v2 API."""


class SeriesSerializer(BaseSeriesSerializer):
    """Serialize series detail rows for the v2 API."""

    active_issue_ids = serializers.SerializerMethodField()

    class Meta(BaseSeriesSerializer.Meta):
        """Serializer metadata for series detail payloads."""

        fields = BaseSeriesSerializer.Meta.fields + ('active_issue_ids',)

    def get_active_issue_ids(self, obj):
        """Return ordered non-deleted issue ids for the series."""
        active_issues = getattr(obj, 'active_issue_list', None)
        if active_issues is None:
            return list(
                obj.active_issues()
                .order_by('sort_code', 'id')
                .values_list('id', flat=True)
            )
        return [issue.id for issue in active_issues]
