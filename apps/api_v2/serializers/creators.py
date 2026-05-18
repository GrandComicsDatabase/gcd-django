# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Serializers for v2 creator endpoints."""

from rest_framework import serializers

from apps.gcd.models import (
    Creator,
    CreatorNameDetail,
    CreatorSignature,
    ReceivedAward,
)


def _serialize_date_component(raw_value):
    """Return an integer for a normalized date component when possible."""
    if not raw_value:
        return None
    if raw_value.isdigit():
        return int(raw_value)
    if raw_value.endswith('?') and raw_value[:-1].isdigit():
        return int(raw_value[:-1])
    return None


def serialize_partial_date(date_obj):
    """Return the locked partial-date JSON shape for a ``Date`` row."""
    if date_obj is None or str(date_obj) == '':
        return None

    year = _serialize_date_component(date_obj.year)
    month = _serialize_date_component(date_obj.month)
    day = _serialize_date_component(date_obj.day)
    if date_obj.day:
        precision = 'day'
    elif date_obj.month:
        precision = 'month'
    else:
        precision = 'year'

    return {
        'value': str(date_obj),
        'precision': precision,
        'year': year,
        'month': month,
        'day': day,
        'year_uncertain': (date_obj.year_uncertain if date_obj.year else None),
        'month_uncertain': (
            date_obj.month_uncertain if date_obj.month else None
        ),
        'day_uncertain': date_obj.day_uncertain if date_obj.day else None,
    }


class CreatorNameDetailSerializer(serializers.ModelSerializer):
    """Serialize trimmed creator name-detail rows."""

    class Meta:
        """Serializer metadata for creator name-detail fields."""

        model = CreatorNameDetail
        fields = (
            'id',
            'name',
            'sort_name',
            'is_official_name',
        )


class CreatorSignatureSerializer(serializers.ModelSerializer):
    """Serialize trimmed creator signature rows."""

    class Meta:
        """Serializer metadata for creator signature fields."""

        model = CreatorSignature
        fields = (
            'id',
            'name',
        )


class CreatorAwardSerializer(serializers.Serializer):
    """Serialize trimmed received-award rows."""

    id = serializers.IntegerField()
    award = serializers.DictField(allow_null=True)
    name = serializers.CharField()
    year = serializers.IntegerField(allow_null=True)


class BaseCreatorSerializer(serializers.ModelSerializer):
    """Serialize shared creator fields for the v2 API."""

    birth_date = serializers.SerializerMethodField()
    death_date = serializers.SerializerMethodField()
    birth_country = serializers.SlugRelatedField(
        read_only=True,
        slug_field='code',
    )

    class Meta:
        """Serializer metadata for shared creator fields."""

        model = Creator
        fields = (
            'id',
            'gcd_official_name',
            'sort_name',
            'birth_date',
            'death_date',
            'birth_country',
            'bio',
            'notes',
            'created',
            'modified',
        )

    def get_birth_date(self, obj):
        """Return the creator birth date in locked partial-date form."""
        return serialize_partial_date(obj.birth_date)

    def get_death_date(self, obj):
        """Return the creator death date in locked partial-date form."""
        return serialize_partial_date(obj.death_date)


class CreatorListSerializer(BaseCreatorSerializer):
    """Serialize lightweight creator list rows for the v2 API."""


class CreatorSerializer(BaseCreatorSerializer):
    """Serialize creator detail rows for the v2 API."""

    name_details = serializers.SerializerMethodField()
    signatures = serializers.SerializerMethodField()
    awards = serializers.SerializerMethodField()

    class Meta(BaseCreatorSerializer.Meta):
        """Serializer metadata for creator detail payloads."""

        fields = BaseCreatorSerializer.Meta.fields + (
            'name_details',
            'signatures',
            'awards',
        )

    def get_name_details(self, obj):
        """Return ordered non-deleted alternate names for the creator."""
        name_details = getattr(obj, 'active_name_detail_list', None)
        if name_details is None:
            name_details = obj.creator_names.exclude(deleted=True).order_by(
                'sort_name',
                'id',
            )
        return CreatorNameDetailSerializer(name_details, many=True).data

    def get_signatures(self, obj):
        """Return ordered non-deleted signature rows for the creator."""
        signatures = getattr(obj, 'active_signature_list', None)
        if signatures is None:
            signatures = obj.signatures.exclude(deleted=True).order_by(
                'name',
                'id',
            )
        return CreatorSignatureSerializer(signatures, many=True).data

    def get_awards(self, obj):
        """Return ordered non-deleted received-award rows for the creator."""
        awards = getattr(obj, 'active_award_list', None)
        if awards is None:
            awards = obj.awards.exclude(deleted=True).select_related('award')

        payload = []
        award_row: ReceivedAward
        for award_row in awards:
            payload.append(
                {
                    'id': award_row.pk,
                    'award': (
                        None
                        if award_row.award_id is None
                        else {
                            'id': award_row.award_id,
                            'name': award_row.award.name,
                        }
                    ),
                    'name': award_row.display_name(),
                    'year': award_row.award_year,
                },
            )
        return CreatorAwardSerializer(payload, many=True).data
