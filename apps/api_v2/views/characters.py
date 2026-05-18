# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Viewsets for v2 character endpoints."""

from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend

from apps.api_v2.filters.characters import CharacterFilterSet
from apps.api_v2.serializers.characters import CharacterSerializer
from apps.api_v2.utils.conditional import (
    condition,
    make_etag,
    make_last_modified,
)
from apps.api_v2.views import GCDBaseViewSet
from apps.gcd.models import Character, CharacterNameDetail, GroupMembership


def _character_filter_queryset(request, *, pk=None, **kwargs):
    """Return the character queryset scoped by request query params."""
    del pk, kwargs
    return CharacterFilterSet(
        request.GET,
        queryset=Character.objects.all(),
        request=request,
    ).qs


character_last_modified = make_last_modified(
    Character,
    queryset_getter=_character_filter_queryset,
)
character_etag = make_etag(
    Character,
    queryset_getter=_character_filter_queryset,
)

ACTIVE_CHARACTER_NAME_DETAIL_PREFETCH = Prefetch(
    'character_names',
    queryset=CharacterNameDetail.objects.filter(deleted=False)
    .only('id', 'name', 'sort_name', 'is_official_name', 'character_id')
    .order_by('sort_name', 'id'),
    to_attr='active_name_detail_list',
)
ACTIVE_CHARACTER_GROUP_MEMBERSHIP_PREFETCH = Prefetch(
    'memberships',
    queryset=GroupMembership.objects.filter(group__deleted=False)
    .select_related('group')
    .only(
        'id',
        'character_id',
        'group_id',
        'group__id',
        'group__name',
        'group__sort_name',
    )
    .order_by('group__sort_name', 'group__id'),
    to_attr='active_membership_link_list',
)


class CharacterViewSet(GCDBaseViewSet):
    """Read-only character endpoints for the public v2 API surface."""

    queryset = (
        Character.objects.select_related(
            'language',
            'universe',
            'universe__verse',
        )
        .only(
            'id',
            'created',
            'modified',
            'name',
            'sort_name',
            'disambiguation',
            'universe_id',
            'year_first_published',
            'language_id',
            'description',
            'notes',
            'language__id',
            'language__code',
            'universe__id',
            'universe__name',
            'universe__designation',
            'universe__verse_id',
            'universe__verse__id',
            'universe__verse__name',
        )
        .prefetch_related(
            'keywords',
            ACTIVE_CHARACTER_NAME_DETAIL_PREFETCH,
            ACTIVE_CHARACTER_GROUP_MEMBERSHIP_PREFETCH,
        )
        .order_by(
            'sort_name',
            'year_first_published',
            'disambiguation',
            'id',
        )
    )
    serializer_class = CharacterSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = CharacterFilterSet

    @condition(
        etag_func=character_etag,
        last_modified_func=character_last_modified,
    )
    def list(self, request, *args, **kwargs):
        """Return a filtered, paginated character collection."""
        return super().list(request, *args, **kwargs)

    @condition(
        etag_func=character_etag,
        last_modified_func=character_last_modified,
    )
    def retrieve(self, request, *args, **kwargs):
        """Return a single character detail record."""
        return super().retrieve(request, *args, **kwargs)
