# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Viewsets for v2 indicia publisher endpoints."""

from django_filters.rest_framework import DjangoFilterBackend

from apps.api_v2.filters.indicia_publishers import (
    IndiciaPublisherFilterSet,
)
from apps.api_v2.serializers.indicia_publishers import (
    IndiciaPublisherListSerializer,
    IndiciaPublisherSerializer,
)
from apps.api_v2.utils.conditional import (
    condition,
    make_etag,
    make_last_modified,
)
from apps.api_v2.views import GCDBaseViewSet
from apps.gcd.models import IndiciaPublisher


def _indicia_publisher_filter_queryset(request, *, pk=None, **kwargs):
    """Return indicia publishers scoped by request query parameters."""
    del pk, kwargs
    return IndiciaPublisherFilterSet(
        request.GET,
        queryset=IndiciaPublisher.objects.all(),
    ).qs


indicia_publisher_last_modified = make_last_modified(
    IndiciaPublisher,
    queryset_getter=_indicia_publisher_filter_queryset,
)
indicia_publisher_etag = make_etag(
    IndiciaPublisher,
    queryset_getter=_indicia_publisher_filter_queryset,
)


class IndiciaPublisherViewSet(GCDBaseViewSet):
    """Read-only indicia publisher endpoints for the public v2 API."""

    queryset = IndiciaPublisher.objects.select_related(
        'parent',
        'country',
    ).order_by('name', 'id')
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IndiciaPublisherFilterSet

    def get_queryset(self):
        """Prefetch descriptive detail relationships when required."""
        queryset = super().get_queryset()
        if self.action == 'retrieve':
            queryset = queryset.prefetch_related('keywords')
        return queryset

    def get_serializer_class(self):
        """Use the full serializer only for detail responses."""
        if self.action == 'retrieve':
            return IndiciaPublisherSerializer
        return IndiciaPublisherListSerializer

    @condition(
        etag_func=indicia_publisher_etag,
        last_modified_func=indicia_publisher_last_modified,
    )
    def list(self, request, *args, **kwargs):
        """Return a filtered, paginated indicia publisher collection."""
        return super().list(request, *args, **kwargs)

    @condition(
        etag_func=indicia_publisher_etag,
        last_modified_func=indicia_publisher_last_modified,
    )
    def retrieve(self, request, *args, **kwargs):
        """Return a single indicia publisher detail record."""
        return super().retrieve(request, *args, **kwargs)
