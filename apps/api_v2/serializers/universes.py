# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Serializers for v2 universe endpoints."""

from rest_framework import serializers

from apps.gcd.models import Universe


class UniverseSerializer(serializers.ModelSerializer):
    """Serialize universes for v2 list and detail endpoints."""

    multiverse = serializers.SerializerMethodField()
    display_name = serializers.ReadOnlyField()

    class Meta:
        """Serializer metadata for universe field selection."""

        model = Universe
        fields = (
            'id',
            'multiverse',
            'name',
            'designation',
            'display_name',
            'year_first_published',
            'year_first_published_uncertain',
            'description',
            'notes',
            'created',
            'modified',
        )

    def get_multiverse(self, obj):
        """Return the public multiverse object for a universe row."""
        if obj.verse_id:
            return {
                'id': obj.verse_id,
                'name': obj.verse.name,
            }
        if obj.multiverse:
            return {
                'id': None,
                'name': obj.multiverse,
            }
        return None
