# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Reusable serializers for nested API v2 response shapes."""

from rest_framework import serializers


class IdNameReferenceSerializer(serializers.Serializer):
    """Describe a minimal database object reference."""

    id = serializers.IntegerField()
    name = serializers.CharField()


class NullableIdNameReferenceSerializer(serializers.Serializer):
    """Describe a legacy name reference whose id may be unavailable."""

    id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()


class PartialDateSerializer(serializers.Serializer):
    """Describe a date whose precision and components may be incomplete."""

    value = serializers.CharField()
    precision = serializers.ChoiceField(choices=('year', 'month', 'day'))
    year = serializers.IntegerField(allow_null=True)
    month = serializers.IntegerField(allow_null=True)
    day = serializers.IntegerField(allow_null=True)
    year_uncertain = serializers.BooleanField(allow_null=True)
    month_uncertain = serializers.BooleanField(allow_null=True)
    day_uncertain = serializers.BooleanField(allow_null=True)


class StoryReferenceSerializer(serializers.Serializer):
    """Describe the story identity nested in reprint responses."""

    id = serializers.IntegerField()
    title = serializers.CharField()


class IssueDescriptorReferenceSerializer(serializers.Serializer):
    """Describe an issue with its public descriptor."""

    id = serializers.IntegerField()
    descriptor = serializers.CharField()


class ReprintIssueReferenceSerializer(IssueDescriptorReferenceSerializer):
    """Describe an issue nested in a reprint response."""

    series_name = serializers.CharField()


class StoryReprintReferenceSerializer(serializers.Serializer):
    """Describe a reprint nested in a story detail response."""

    id = serializers.IntegerField()
    origin_story = StoryReferenceSerializer(allow_null=True)
    origin_issue = ReprintIssueReferenceSerializer()
    target_story = StoryReferenceSerializer(allow_null=True)
    target_issue = ReprintIssueReferenceSerializer()
    notes = serializers.CharField()


class StoryCreditSerializer(serializers.Serializer):
    """Describe a normalized creator credit on a story."""

    creator = IdNameReferenceSerializer()
    role = serializers.CharField()


class StoryCharacterAppearanceSerializer(serializers.Serializer):
    """Describe a character appearance on a story."""

    character = IdNameReferenceSerializer()
    role = serializers.CharField(allow_null=True)


class LegacyTextCreditsSerializer(serializers.Serializer):
    """Describe legacy plain-text credits grouped by role."""

    script = serializers.ListField(child=serializers.CharField())
    pencils = serializers.ListField(child=serializers.CharField())
    inks = serializers.ListField(child=serializers.CharField())
    colors = serializers.ListField(child=serializers.CharField())
    letters = serializers.ListField(child=serializers.CharField())
    editing = serializers.ListField(child=serializers.CharField())


class StoryArcMembershipSerializer(serializers.Serializer):
    """Describe a primary story included in a story arc."""

    id = serializers.IntegerField()
    title = serializers.CharField()
    issue = IssueDescriptorReferenceSerializer()
    sequence_number = serializers.IntegerField()
