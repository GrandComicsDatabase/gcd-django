# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Viewsets for v2 creator endpoints."""

from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend

from apps.api_v2.filters.creators import CreatorFilterSet
from apps.api_v2.serializers.creators import (
    CreatorListSerializer,
    CreatorSerializer,
)
from apps.api_v2.utils.conditional import (
    condition,
    make_etag,
    make_last_modified,
)
from apps.api_v2.views import GCDBaseViewSet
from apps.gcd.models import (
    Creator,
    CreatorNameDetail,
    CreatorSignature,
    ReceivedAward,
)


def _creator_filter_queryset(request, *, pk=None, **kwargs):
    """Return the creator queryset scoped by request query params."""
    del pk, kwargs
    return CreatorFilterSet(
        request.GET,
        queryset=Creator.objects.all(),
    ).qs


creator_last_modified = make_last_modified(
    Creator,
    queryset_getter=_creator_filter_queryset,
)
creator_etag = make_etag(
    Creator,
    queryset_getter=_creator_filter_queryset,
)

ACTIVE_CREATOR_NAME_DETAIL_PREFETCH = Prefetch(
    'creator_names',
    queryset=CreatorNameDetail.objects.filter(deleted=False).order_by(
        'sort_name',
        'id',
    ),
    to_attr='active_name_detail_list',
)
ACTIVE_CREATOR_SIGNATURE_PREFETCH = Prefetch(
    'signatures',
    queryset=CreatorSignature.objects.filter(deleted=False).order_by(
        'name',
        'id',
    ),
    to_attr='active_signature_list',
)
ACTIVE_CREATOR_AWARD_PREFETCH = Prefetch(
    'awards',
    queryset=ReceivedAward.objects.filter(deleted=False)
    .select_related('award')
    .order_by('award_year', 'id'),
    to_attr='active_award_list',
)

BASE_CREATOR_QUERYSET = Creator.objects.select_related(
    'birth_date',
    'death_date',
    'birth_country',
)


class CreatorViewSet(GCDBaseViewSet):
    """Read-only creator endpoints for the public v2 API surface."""

    queryset = BASE_CREATOR_QUERYSET
    serializer_class = CreatorSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = CreatorFilterSet

    def get_queryset(self):
        """Return the queryset tuned for the current creator action."""
        queryset = super().get_queryset()
        if self.action == 'retrieve':
            return queryset.prefetch_related(
                ACTIVE_CREATOR_NAME_DETAIL_PREFETCH,
                ACTIVE_CREATOR_SIGNATURE_PREFETCH,
                ACTIVE_CREATOR_AWARD_PREFETCH,
            )
        return queryset.order_by('sort_name', 'id')

    def get_serializer_class(self):
        """Return the serializer class for the current creator action."""
        if self.action == 'list':
            return CreatorListSerializer
        return CreatorSerializer

    @condition(
        etag_func=creator_etag,
        last_modified_func=creator_last_modified,
    )
    def list(self, request, *args, **kwargs):
        """Return a filtered, paginated creator collection."""
        return super().list(request, *args, **kwargs)

    @condition(
        etag_func=creator_etag,
        last_modified_func=creator_last_modified,
    )
    def retrieve(self, request, *args, **kwargs):
        """Return a single creator detail record."""
        return super().retrieve(request, *args, **kwargs)
