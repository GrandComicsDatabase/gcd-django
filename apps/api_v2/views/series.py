"""Viewsets for v2 series endpoints."""

from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend

from apps.api_v2.filters.series import SeriesFilterSet
from apps.api_v2.serializers.series import SeriesSerializer
from apps.api_v2.utils.conditional import (
    condition,
    make_etag,
    make_last_modified,
)
from apps.api_v2.views import GCDBaseViewSet
from apps.gcd.models import Issue, Series


def _series_filter_queryset(request, *, pk=None, **kwargs):
    """Return the series queryset scoped by request query params."""
    del pk, kwargs
    return SeriesFilterSet(
        request.GET,
        queryset=Series.objects.all(),
    ).qs


series_last_modified = make_last_modified(
    Series,
    queryset_getter=_series_filter_queryset,
)
series_etag = make_etag(
    Series,
    queryset_getter=_series_filter_queryset,
)

ACTIVE_ISSUE_PREFETCH = Prefetch(
    'issue_set',
    queryset=Issue.objects.filter(deleted=False)
    .only('id', 'series_id', 'sort_code')
    .order_by('sort_code', 'id'),
    to_attr='active_issue_list',
)


class SeriesViewSet(GCDBaseViewSet):
    """Read-only series endpoints for the public v2 API surface."""

    queryset = (
        Series.objects.select_related(
            'country',
            'language',
            'publisher',
            'publication_type',
        )
        .only(
            'id',
            'created',
            'modified',
            'deleted',
            'name',
            'sort_name',
            'year_began',
            'year_ended',
            'color',
            'dimensions',
            'paper_stock',
            'binding',
            'publishing_format',
            'notes',
            'issue_count',
            'country_id',
            'language_id',
            'publisher_id',
            'publication_type_id',
            'country__id',
            'country__code',
            'language__id',
            'language__code',
            'publisher__id',
            'publisher__name',
            'publication_type__id',
            'publication_type__name',
        )
        .prefetch_related(
            'keywords',
            ACTIVE_ISSUE_PREFETCH,
        )
    )
    serializer_class = SeriesSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = SeriesFilterSet

    @condition(
        etag_func=series_etag,
        last_modified_func=series_last_modified,
    )
    def list(self, request, *args, **kwargs):
        """Return a filtered, paginated series collection."""
        return super().list(request, *args, **kwargs)

    @condition(
        etag_func=series_etag,
        last_modified_func=series_last_modified,
    )
    def retrieve(self, request, *args, **kwargs):
        """Return a single series detail record."""
        return super().retrieve(request, *args, **kwargs)
