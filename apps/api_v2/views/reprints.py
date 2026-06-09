# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Viewsets for v2 reprint endpoints."""

from django_filters.rest_framework import DjangoFilterBackend

from apps.api_v2.filters.reprints import ReprintFilterSet
from apps.api_v2.serializers.reprints import ReprintSerializer
from apps.api_v2.utils.conditional import (
    condition,
    make_etag,
    make_last_modified,
)
from apps.api_v2.views import GCDBaseViewSet
from apps.gcd.models import Reprint


def _reprint_filter_queryset(request, *, pk=None, **kwargs):
    """Return the reprint queryset scoped by request query params."""
    del pk, kwargs
    return ReprintFilterSet(
        request.GET,
        queryset=Reprint.objects.all(),
    ).qs


reprint_last_modified = make_last_modified(
    Reprint,
    soft_delete=False,
    queryset_getter=_reprint_filter_queryset,
)
reprint_etag = make_etag(
    Reprint,
    soft_delete=False,
    queryset_getter=_reprint_filter_queryset,
)


class ReprintViewSet(GCDBaseViewSet):
    """Read-only reprint endpoints for the public v2 API surface."""

    queryset = Reprint.objects.select_related(
        'origin',
        'origin_issue',
        'origin_issue__series',
        'target',
        'target_issue',
        'target_issue__series',
    ).order_by(
        'origin_issue_id',
        'target_issue_id',
        'id',
    )
    serializer_class = ReprintSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ReprintFilterSet

    @condition(
        etag_func=reprint_etag,
        last_modified_func=reprint_last_modified,
    )
    def list(self, request, *args, **kwargs):
        """Return a filtered, paginated reprint collection."""
        return super().list(request, *args, **kwargs)

    @condition(
        etag_func=reprint_etag,
        last_modified_func=reprint_last_modified,
    )
    def retrieve(self, request, *args, **kwargs):
        """Return a single reprint detail record."""
        return super().retrieve(request, *args, **kwargs)
