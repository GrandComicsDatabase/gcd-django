# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Viewsets for v2 brand group endpoints."""

from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend

from apps.api_v2.filters.brand_groups import BrandGroupFilterSet
from apps.api_v2.serializers.brand_groups import (
    BrandGroupListSerializer,
    BrandGroupSerializer,
)
from apps.api_v2.utils.conditional import (
    condition,
    make_etag,
    make_last_modified,
)
from apps.api_v2.views import GCDBaseViewSet
from apps.gcd.models import Brand, BrandGroup


def _brand_group_filter_queryset(request, *, pk=None, **kwargs):
    """Return brand groups scoped by request query parameters."""
    del pk, kwargs
    return BrandGroupFilterSet(
        request.GET,
        queryset=BrandGroup.objects.all(),
    ).qs


brand_group_last_modified = make_last_modified(
    BrandGroup,
    queryset_getter=_brand_group_filter_queryset,
)
brand_group_etag = make_etag(
    BrandGroup,
    queryset_getter=_brand_group_filter_queryset,
)

ACTIVE_BRAND_GROUP_EMBLEM_PREFETCH = Prefetch(
    'brand_set',
    queryset=Brand.objects.filter(deleted=False).order_by('name', 'id'),
    to_attr='active_brand_group_emblem_list',
)


class BrandGroupViewSet(GCDBaseViewSet):
    """Read-only brand group endpoints for the public v2 API."""

    queryset = BrandGroup.objects.select_related('parent').order_by(
        'name',
        'id',
    )
    filter_backends = (DjangoFilterBackend,)
    filterset_class = BrandGroupFilterSet

    def get_queryset(self):
        """Prefetch descriptive detail relationships when required."""
        queryset = super().get_queryset()
        if self.action == 'retrieve':
            queryset = queryset.prefetch_related(
                'keywords',
                ACTIVE_BRAND_GROUP_EMBLEM_PREFETCH,
            )
        return queryset

    def get_serializer_class(self):
        """Use the full serializer only for detail responses."""
        if self.action == 'retrieve':
            return BrandGroupSerializer
        return BrandGroupListSerializer

    @condition(
        etag_func=brand_group_etag,
        last_modified_func=brand_group_last_modified,
    )
    def list(self, request, *args, **kwargs):
        """Return a filtered, paginated brand group collection."""
        return super().list(request, *args, **kwargs)

    @condition(
        etag_func=brand_group_etag,
        last_modified_func=brand_group_last_modified,
    )
    def retrieve(self, request, *args, **kwargs):
        """Return a single brand group detail record."""
        return super().retrieve(request, *args, **kwargs)
