# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Serializers for v2 Award endpoints."""

from drf_spectacular.utils import (
    PolymorphicProxySerializer,
    extend_schema_field,
)
from rest_framework import serializers

from apps.gcd.models import Award, ReceivedAward


def _series_reference(series):
    """Return a minimal Series reference."""
    return {
        'id': series.pk,
        'name': series.name,
    }


def _issue_reference(issue):
    """Return a useful Issue recipient reference."""
    return {
        'id': issue.pk,
        'number': issue.number,
        'volume': issue.volume,
        'title': issue.title,
        'series': _series_reference(issue.series),
    }


def _recipient_reference(recipient_type, recipient):
    """Return the supported type-specific generic recipient shape."""
    if recipient is None:
        return None
    if recipient_type == 'creator':
        return {
            'id': recipient.pk,
            'name': recipient.gcd_official_name,
            'sort_name': recipient.sort_name,
            'disambiguation': recipient.disambiguation,
        }
    if recipient_type == 'issue':
        return _issue_reference(recipient)
    if recipient_type == 'series':
        return {
            'id': recipient.pk,
            'name': recipient.name,
            'sort_name': recipient.sort_name,
            'year_began': recipient.year_began,
        }
    if recipient_type == 'story':
        return {
            'id': recipient.pk,
            'title': recipient.title,
            'feature': recipient.feature,
            'sequence_number': recipient.sequence_number,
            'issue': {
                'id': recipient.issue.pk,
                'number': recipient.issue.number,
                'series': _series_reference(recipient.issue.series),
            },
        }
    return None


class AwardSeriesNameReferenceSerializer(serializers.Serializer):
    """Describe the Series identity nested in Issue references."""

    id = serializers.IntegerField()
    name = serializers.CharField()


class AwardCreatorRecipientReferenceSerializer(serializers.Serializer):
    """Describe a Creator Award recipient."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    sort_name = serializers.CharField()
    disambiguation = serializers.CharField()


class AwardIssueRecipientReferenceSerializer(serializers.Serializer):
    """Describe an Issue Award recipient."""

    id = serializers.IntegerField()
    number = serializers.CharField()
    volume = serializers.CharField()
    title = serializers.CharField()
    series = AwardSeriesNameReferenceSerializer()


class AwardSeriesRecipientReferenceSerializer(serializers.Serializer):
    """Describe a Series Award recipient."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    sort_name = serializers.CharField()
    year_began = serializers.IntegerField()


class AwardStoryIssueReferenceSerializer(serializers.Serializer):
    """Describe the Issue identity nested in Story references."""

    id = serializers.IntegerField()
    number = serializers.CharField()
    series = AwardSeriesNameReferenceSerializer()


class AwardStoryRecipientReferenceSerializer(serializers.Serializer):
    """Describe a Story Award recipient."""

    id = serializers.IntegerField()
    title = serializers.CharField()
    feature = serializers.CharField()
    sequence_number = serializers.IntegerField()
    issue = AwardStoryIssueReferenceSerializer()


class AwardListSerializer(serializers.ModelSerializer):
    """Serialize trimmed Award list rows."""

    class Meta:
        """Serializer metadata for Award list fields."""

        model = Award
        fields = (
            'id',
            'name',
            'created',
            'modified',
        )


class AwardSerializer(AwardListSerializer):
    """Serialize complete Award detail rows."""

    class Meta(AwardListSerializer.Meta):
        """Serializer metadata for Award detail fields."""

        fields = AwardListSerializer.Meta.fields + ('notes',)


class AwardRecipientSerializer(serializers.ModelSerializer):
    """Serialize a received Award with its typed generic recipient."""

    recipient_type = serializers.SerializerMethodField()
    recipient = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    year = serializers.IntegerField(
        source='award_year',
        read_only=True,
        allow_null=True,
    )
    year_uncertain = serializers.BooleanField(
        source='award_year_uncertain',
        read_only=True,
    )

    class Meta:
        """Serializer metadata for received Award rows."""

        model = ReceivedAward
        fields = (
            'id',
            'recipient_type',
            'recipient',
            'name',
            'year',
            'year_uncertain',
            'notes',
            'created',
            'modified',
        )

    def get_recipient_type(self, obj) -> str:
        """Return the stable public name for the generic recipient type."""
        return obj.content_type.model

    @extend_schema_field(
        PolymorphicProxySerializer(
            component_name='AwardRecipientReference',
            serializers=(
                AwardCreatorRecipientReferenceSerializer,
                AwardIssueRecipientReferenceSerializer,
                AwardSeriesRecipientReferenceSerializer,
                AwardStoryRecipientReferenceSerializer,
            ),
            resource_type_field_name=None,
        ),
    )
    def get_recipient(self, obj):
        """Return a type-aware generic recipient reference."""
        return _recipient_reference(
            self.get_recipient_type(obj),
            obj.recipient,
        )

    def get_name(self, obj) -> str:
        """Return the Received Award display name."""
        return obj.display_name()
