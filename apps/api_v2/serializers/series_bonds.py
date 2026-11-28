# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Serializers for v2 Series Bond endpoints."""

from rest_framework import serializers

from apps.gcd.models import SeriesBond


class SeriesBondSeriesReferenceSerializer(serializers.Serializer):
    """Serialize a Series reference used by Series Bond payloads."""

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    year_began = serializers.IntegerField(read_only=True)


class SeriesBondIssueReferenceSerializer(serializers.Serializer):
    """Serialize an Issue reference used by Series Bond payloads."""

    id = serializers.IntegerField(read_only=True)
    descriptor = serializers.CharField(
        source='issue_descriptor',
        read_only=True,
    )


class SeriesBondTypeReferenceSerializer(serializers.Serializer):
    """Serialize a Series Bond Type reference."""

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)


class SeriesBondListSerializer(serializers.ModelSerializer):
    """Serialize trimmed Series Bond list rows."""

    created = serializers.DateTimeField(
        read_only=True,
        help_text=(
            'Persistent creation timestamp. Legacy rows without approved '
            'revision history use the migration-time timestamp-tracking '
            'baseline.'
        ),
    )
    modified = serializers.DateTimeField(
        read_only=True,
        help_text=(
            'Persistent last-modified timestamp. Legacy rows without '
            'approved revision history use the migration-time '
            'timestamp-tracking baseline.'
        ),
    )
    origin = SeriesBondSeriesReferenceSerializer(read_only=True)
    origin_issue = SeriesBondIssueReferenceSerializer(
        allow_null=True,
        read_only=True,
    )
    target = SeriesBondSeriesReferenceSerializer(read_only=True)
    target_issue = SeriesBondIssueReferenceSerializer(
        allow_null=True,
        read_only=True,
    )
    bond_type = SeriesBondTypeReferenceSerializer(read_only=True)

    class Meta:
        """Serializer metadata for Series Bond list fields."""

        model = SeriesBond
        fields = (
            'id',
            'origin',
            'origin_issue',
            'target',
            'target_issue',
            'bond_type',
            'created',
            'modified',
        )


class SeriesBondSerializer(SeriesBondListSerializer):
    """Serialize complete Series Bond detail rows."""

    class Meta(SeriesBondListSerializer.Meta):
        """Serializer metadata for Series Bond detail fields."""

        fields = SeriesBondListSerializer.Meta.fields + ('notes',)
