# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Viewsets for v2 group endpoints."""

from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend

from apps.api_v2.filters.groups import GroupFilterSet
from apps.api_v2.serializers.groups import GroupSerializer
from apps.api_v2.utils.conditional import (
    condition,
    make_etag,
    make_last_modified,
)
from apps.api_v2.views import GCDBaseViewSet
from apps.gcd.models import Group, GroupMembership, GroupNameDetail


def _group_filter_queryset(request, *, pk=None, **kwargs):
    """Return the group queryset scoped by request query params."""
    del pk, kwargs
    return GroupFilterSet(
        request.GET,
        queryset=Group.objects.all(),
    ).qs


group_last_modified = make_last_modified(
    Group,
    queryset_getter=_group_filter_queryset,
)
group_etag = make_etag(
    Group,
    queryset_getter=_group_filter_queryset,
)

ACTIVE_GROUP_NAME_DETAIL_PREFETCH = Prefetch(
    'group_names',
    queryset=GroupNameDetail.objects.filter(deleted=False)
    .only('id', 'name', 'sort_name', 'is_official_name', 'group_id')
    .order_by('sort_name', 'id'),
    to_attr='active_name_detail_list',
)
ACTIVE_GROUP_MEMBER_PREFETCH = Prefetch(
    'members',
    queryset=GroupMembership.objects.filter(character__deleted=False)
    .select_related('character')
    .only(
        'id',
        'group_id',
        'character_id',
        'character__id',
        'character__name',
        'character__sort_name',
    )
    .order_by('character__sort_name', 'character__id'),
    to_attr='active_member_link_list',
)


class GroupViewSet(GCDBaseViewSet):
    """Read-only group endpoints for the public v2 API surface."""

    queryset = (
        Group.objects.select_related(
            'language',
            'universe',
            'universe__verse',
        )
        .prefetch_related(
            'keywords',
            ACTIVE_GROUP_NAME_DETAIL_PREFETCH,
            ACTIVE_GROUP_MEMBER_PREFETCH,
        )
        .order_by(
            'sort_name',
            'year_first_published',
            'disambiguation',
            'id',
        )
    )
    serializer_class = GroupSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = GroupFilterSet

    @condition(
        etag_func=group_etag,
        last_modified_func=group_last_modified,
    )
    def list(self, request, *args, **kwargs):
        """Return a filtered, paginated group collection."""
        return super().list(request, *args, **kwargs)

    @condition(
        etag_func=group_etag,
        last_modified_func=group_last_modified,
    )
    def retrieve(self, request, *args, **kwargs):
        """Return a single group detail record."""
        return super().retrieve(request, *args, **kwargs)
