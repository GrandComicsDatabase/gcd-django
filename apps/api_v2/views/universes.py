# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Viewsets for v2 universe endpoints."""

from django_filters.rest_framework import DjangoFilterBackend

from apps.api_v2.filters.universes import UniverseFilterSet
from apps.api_v2.serializers.universes import UniverseSerializer
from apps.api_v2.utils.conditional import (
    condition,
    make_etag,
    make_last_modified,
)
from apps.api_v2.views import GCDBaseViewSet
from apps.gcd.models import Universe


def _universe_filter_queryset(request, *, pk=None, **kwargs):
    """Return the universe queryset scoped by request query params."""
    del pk, kwargs
    return UniverseFilterSet(
        request.GET,
        queryset=Universe.objects.all(),
    ).qs


universe_last_modified = make_last_modified(
    Universe,
    queryset_getter=_universe_filter_queryset,
)
universe_etag = make_etag(
    Universe,
    queryset_getter=_universe_filter_queryset,
)


class UniverseViewSet(GCDBaseViewSet):
    """Read-only universe endpoints for the public v2 API surface."""

    queryset = Universe.objects.select_related('verse')
    serializer_class = UniverseSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = UniverseFilterSet

    @condition(
        etag_func=universe_etag,
        last_modified_func=universe_last_modified,
    )
    def list(self, request, *args, **kwargs):
        """Return a filtered, paginated universe collection."""
        return super().list(request, *args, **kwargs)

    @condition(
        etag_func=universe_etag,
        last_modified_func=universe_last_modified,
    )
    def retrieve(self, request, *args, **kwargs):
        """Return a single universe detail record."""
        return super().retrieve(request, *args, **kwargs)
