# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Serializers for v2 character endpoints."""

from rest_framework import serializers

from apps.gcd.models import Character, CharacterNameDetail, GroupMembership


class CharacterNameDetailSerializer(serializers.ModelSerializer):
    """Serialize trimmed character name-detail rows."""

    class Meta:
        """Serializer metadata for character name-detail fields."""

        model = CharacterNameDetail
        fields = (
            'id',
            'name',
            'sort_name',
            'is_official_name',
        )


class CharacterGroupMembershipSerializer(serializers.Serializer):
    """Serialize a trimmed group reference for memberships."""

    id = serializers.IntegerField()
    name = serializers.CharField()


class CharacterSerializer(serializers.ModelSerializer):
    """Serialize characters for v2 list and detail endpoints."""

    language = serializers.SlugRelatedField(read_only=True, slug_field='code')
    universe = serializers.SerializerMethodField()
    name_details = serializers.SerializerMethodField()
    group_memberships = serializers.SerializerMethodField()
    keywords = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
    )

    class Meta:
        """Serializer metadata for character field selection."""

        model = Character
        fields = (
            'id',
            'name',
            'sort_name',
            'disambiguation',
            'year_first_published',
            'language',
            'description',
            'notes',
            'universe',
            'name_details',
            'group_memberships',
            'keywords',
            'created',
            'modified',
        )

    def get_universe(self, obj):
        """Return the minimal nested universe reference."""
        if obj.universe_id is None:
            return None
        return {
            'id': obj.universe_id,
            'name': obj.universe.display_name,
        }

    def get_name_details(self, obj):
        """Return ordered non-deleted alternate names for the character."""
        name_details = getattr(obj, 'active_name_detail_list', None)
        if name_details is None:
            name_details = obj.character_names.exclude(deleted=True).order_by(
                'sort_name',
                'id',
            )
        return CharacterNameDetailSerializer(name_details, many=True).data

    def get_group_memberships(self, obj):
        """Return unique trimmed group references for the character."""
        memberships = getattr(obj, 'active_membership_link_list', None)
        if memberships is None:
            memberships = (
                obj.memberships.filter(group__deleted=False)
                .select_related('group')
                .order_by('group__sort_name', 'group__id')
            )

        group_memberships = []
        seen_group_ids = set()
        membership: GroupMembership
        for membership in memberships:
            group = membership.group
            if group.pk in seen_group_ids:
                continue
            seen_group_ids.add(group.pk)
            group_memberships.append(
                {
                    'id': group.pk,
                    'name': group.name,
                },
            )
        return CharacterGroupMembershipSerializer(
            group_memberships,
            many=True,
        ).data
