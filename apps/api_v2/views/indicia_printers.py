# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Viewsets for v2 indicia printer endpoints."""

from django_filters.rest_framework import DjangoFilterBackend

from apps.api_v2.filters.indicia_printers import IndiciaPrinterFilterSet
from apps.api_v2.serializers.indicia_printers import (
    IndiciaPrinterListSerializer,
    IndiciaPrinterSerializer,
)
from apps.api_v2.utils.conditional import (
    condition,
    make_etag,
    make_last_modified,
)
from apps.api_v2.views import GCDBaseViewSet
from apps.gcd.models import IndiciaPrinter


def _indicia_printer_filter_queryset(request, *, pk=None, **kwargs):
    """Return indicia printers scoped by request query parameters."""
    del pk, kwargs
    return IndiciaPrinterFilterSet(
        request.GET,
        queryset=IndiciaPrinter.objects.all(),
    ).qs


indicia_printer_last_modified = make_last_modified(
    IndiciaPrinter,
    queryset_getter=_indicia_printer_filter_queryset,
)
indicia_printer_etag = make_etag(
    IndiciaPrinter,
    queryset_getter=_indicia_printer_filter_queryset,
)


class IndiciaPrinterViewSet(GCDBaseViewSet):
    """Read-only indicia printer endpoints for the public v2 API."""

    queryset = IndiciaPrinter.objects.select_related(
        'parent',
        'country',
    ).order_by('name', 'id')
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IndiciaPrinterFilterSet

    def get_queryset(self):
        """Prefetch descriptive detail relationships when required."""
        queryset = super().get_queryset()
        if self.action == 'retrieve':
            queryset = queryset.prefetch_related('keywords')
        return queryset

    def get_serializer_class(self):
        """Use the full serializer only for detail responses."""
        if self.action == 'retrieve':
            return IndiciaPrinterSerializer
        return IndiciaPrinterListSerializer

    @condition(
        etag_func=indicia_printer_etag,
        last_modified_func=indicia_printer_last_modified,
    )
    def list(self, request, *args, **kwargs):
        """Return a filtered, paginated indicia printer collection."""
        return super().list(request, *args, **kwargs)

    @condition(
        etag_func=indicia_printer_etag,
        last_modified_func=indicia_printer_last_modified,
    )
    def retrieve(self, request, *args, **kwargs):
        """Return a single indicia printer detail record."""
        return super().retrieve(request, *args, **kwargs)
