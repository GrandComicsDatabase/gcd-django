# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Viewsets for v2 Brand endpoints."""

from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend

from apps.api_v2.filters.brands import BrandFilterSet
from apps.api_v2.serializers.brands import (
    BrandListSerializer,
    BrandSerializer,
)
from apps.api_v2.utils.conditional import (
    condition,
    make_etag,
    make_last_modified,
)
from apps.api_v2.views import GCDBaseViewSet
from apps.gcd.models import Brand, BrandGroup, BrandUse


def _brand_filter_queryset(request, *, pk=None, **kwargs):
    """Return Brands scoped by request query parameters."""
    del pk, kwargs
    return BrandFilterSet(
        request.GET,
        queryset=Brand.objects.all(),
    ).qs


brand_last_modified = make_last_modified(
    Brand,
    queryset_getter=_brand_filter_queryset,
)
brand_etag = make_etag(
    Brand,
    queryset_getter=_brand_filter_queryset,
)

ACTIVE_BRAND_GROUP_PREFETCH = Prefetch(
    'group',
    queryset=(
        BrandGroup.objects.filter(
            deleted=False,
            parent__deleted=False,
        )
        .select_related('parent')
        .order_by('parent__name', 'name', 'id')
    ),
    to_attr='active_brand_group_list',
)
ACTIVE_BRAND_USE_PREFETCH = Prefetch(
    'in_use',
    queryset=(
        BrandUse.objects.filter(publisher__deleted=False)
        .select_related('publisher')
        .order_by('publisher__name', 'year_began', 'id')
    ),
    to_attr='active_brand_use_list',
)


class BrandViewSet(GCDBaseViewSet):
    """Read-only Brand endpoints for the public v2 API."""

    queryset = Brand.objects.order_by('name', 'id')
    filter_backends = (DjangoFilterBackend,)
    filterset_class = BrandFilterSet

    def get_queryset(self):
        """Prefetch descriptive detail relationships when required."""
        queryset = super().get_queryset()
        if self.action == 'retrieve':
            queryset = queryset.prefetch_related(
                'keywords',
                ACTIVE_BRAND_GROUP_PREFETCH,
                ACTIVE_BRAND_USE_PREFETCH,
            )
        return queryset

    def get_serializer_class(self):
        """Use the full serializer only for detail responses."""
        if self.action == 'retrieve':
            return BrandSerializer
        return BrandListSerializer

    @condition(
        etag_func=brand_etag,
        last_modified_func=brand_last_modified,
    )
    def list(self, request, *args, **kwargs):
        """Return a filtered, paginated Brand collection."""
        return super().list(request, *args, **kwargs)

    @condition(
        etag_func=brand_etag,
        last_modified_func=brand_last_modified,
    )
    def retrieve(self, request, *args, **kwargs):
        """Return a single Brand detail record."""
        return super().retrieve(request, *args, **kwargs)
