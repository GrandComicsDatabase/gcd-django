# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Serializers for v2 publisher endpoints."""

from rest_framework import serializers

from apps.gcd.models import Publisher


class PublisherSerializer(serializers.ModelSerializer):
    """Serialize publishers for v2 list and detail endpoints."""

    country = serializers.SlugRelatedField(read_only=True, slug_field='code')
    keywords = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
    )

    class Meta:
        """Serializer metadata for publisher field selection."""

        model = Publisher
        fields = (
            'id',
            'name',
            'year_began',
            'year_ended',
            'country',
            'url',
            'notes',
            'series_count',
            'issue_count',
            'brand_count',
            'indicia_publisher_count',
            'keywords',
            'created',
            'modified',
        )
