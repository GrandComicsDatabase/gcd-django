# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Viewsets for v2 Series Bond endpoints."""

from django_filters.rest_framework import DjangoFilterBackend

from apps.api_v2.filters.series_bonds import SeriesBondFilterSet
from apps.api_v2.serializers.series_bonds import (
    SeriesBondListSerializer,
    SeriesBondSerializer,
)
from apps.api_v2.utils.conditional import (
    condition,
    make_etag,
    make_last_modified,
)
from apps.api_v2.views import GCDBaseViewSet
from apps.gcd.models import SeriesBond


def _series_bond_filter_queryset(request, *, pk=None, **kwargs):
    """Return Series Bonds scoped by request query parameters."""
    del pk, kwargs
    return SeriesBondFilterSet(
        request.GET,
        queryset=SeriesBond.objects.all(),
    ).qs


series_bond_last_modified = make_last_modified(
    SeriesBond,
    soft_delete=False,
    queryset_getter=_series_bond_filter_queryset,
)
series_bond_etag = make_etag(
    SeriesBond,
    soft_delete=False,
    queryset_getter=_series_bond_filter_queryset,
)


class SeriesBondViewSet(GCDBaseViewSet):
    """Read-only Series Bond endpoints for the public v2 API."""

    queryset = SeriesBond.objects.select_related(
        'origin',
        'origin_issue',
        'target',
        'target_issue',
        'bond_type',
    ).order_by('id')
    filter_backends = (DjangoFilterBackend,)
    filterset_class = SeriesBondFilterSet

    def get_serializer_class(self):
        """Use the full serializer only for detail responses."""
        if self.action == 'retrieve':
            return SeriesBondSerializer
        return SeriesBondListSerializer

    @condition(
        etag_func=series_bond_etag,
        last_modified_func=series_bond_last_modified,
    )
    def list(self, request, *args, **kwargs):
        """Return a filtered, paginated Series Bond collection."""
        return super().list(request, *args, **kwargs)

    @condition(
        etag_func=series_bond_etag,
        last_modified_func=series_bond_last_modified,
    )
    def retrieve(self, request, *args, **kwargs):
        """Return a single Series Bond detail record."""
        return super().retrieve(request, *args, **kwargs)
