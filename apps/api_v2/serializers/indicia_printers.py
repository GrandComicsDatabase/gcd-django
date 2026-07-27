# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Serializers for v2 indicia printer endpoints."""

from rest_framework import serializers

from apps.gcd.models import IndiciaPrinter


class IndiciaPrinterListSerializer(serializers.ModelSerializer):
    """Serialize trimmed indicia printer list rows."""

    parent = serializers.SerializerMethodField()
    country = serializers.SlugRelatedField(
        read_only=True,
        slug_field='code',
    )

    class Meta:
        """Serializer metadata for indicia printer list fields."""

        model = IndiciaPrinter
        fields = (
            'id',
            'name',
            'parent',
            'country',
            'year_began',
            'year_ended',
            'issue_count',
            'created',
            'modified',
        )

    def get_parent(self, obj):
        """Return the minimal nested parent Printer reference."""
        return {
            'id': obj.parent_id,
            'name': obj.parent.name,
        }


class IndiciaPrinterSerializer(IndiciaPrinterListSerializer):
    """Serialize complete indicia printer detail rows."""

    keywords = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
    )

    class Meta(IndiciaPrinterListSerializer.Meta):
        """Serializer metadata for indicia printer detail fields."""

        fields = IndiciaPrinterListSerializer.Meta.fields + (
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
