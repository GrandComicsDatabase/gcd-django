# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Serializers for v2 group endpoints."""

from rest_framework import serializers

from apps.gcd.models import Group, GroupMembership, GroupNameDetail


class GroupNameDetailSerializer(serializers.ModelSerializer):
    """Serialize trimmed group name-detail rows."""

    class Meta:
        """Serializer metadata for group name-detail fields."""

        model = GroupNameDetail
        fields = (
            'id',
            'name',
            'sort_name',
            'is_official_name',
        )


class GroupMemberSerializer(serializers.Serializer):
    """Serialize a trimmed character reference for group members."""

    id = serializers.IntegerField()
    name = serializers.CharField()


class GroupSerializer(serializers.ModelSerializer):
    """Serialize groups for v2 list and detail endpoints."""

    language = serializers.SlugRelatedField(read_only=True, slug_field='code')
    universe = serializers.SerializerMethodField()
    name_details = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()
    keywords = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
    )

    class Meta:
        """Serializer metadata for group field selection."""

        model = Group
        fields = (
            'id',
            'name',
            'sort_name',
            'disambiguation',
            'year_first_published',
            'language',
            'universe',
            'description',
            'notes',
            'name_details',
            'members',
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
        """Return ordered non-deleted alternate names for the group."""
        name_details = getattr(obj, 'active_name_detail_list', None)
        if name_details is None:
            name_details = obj.group_names.exclude(deleted=True).order_by(
                'sort_name',
                'id',
            )
        return GroupNameDetailSerializer(name_details, many=True).data

    def get_members(self, obj):
        """Return unique trimmed character references for the group."""
        memberships = getattr(obj, 'active_member_link_list', None)
        if memberships is None:
            memberships = (
                obj.members.filter(character__deleted=False)
                .select_related('character')
                .order_by('character__sort_name', 'character__id')
            )

        members = []
        seen_character_ids = set()
        membership: GroupMembership
        for membership in memberships:
            character = membership.character
            if character.pk in seen_character_ids:
                continue
            seen_character_ids.add(character.pk)
            members.append(
                {
                    'id': character.pk,
                    'name': character.name,
                },
            )
        return GroupMemberSerializer(members, many=True).data
