"""Viewsets for v2 publisher endpoints."""

from django_filters.rest_framework import DjangoFilterBackend

from apps.api_v2.filters.publishers import PublisherFilterSet
from apps.api_v2.serializers.publishers import PublisherSerializer
from apps.api_v2.utils.conditional import (
    condition,
    make_etag,
    make_last_modified,
)
from apps.api_v2.views import GCDBaseViewSet
from apps.gcd.models import Publisher


def _publisher_filter_queryset(request, *, pk=None, **kwargs):
    """Return the publisher queryset scoped by request query params."""
    del pk, kwargs
    return PublisherFilterSet(
        request.GET,
        queryset=Publisher.objects.all(),
    ).qs


publisher_last_modified = make_last_modified(
    Publisher,
    queryset_getter=_publisher_filter_queryset,
)
publisher_etag = make_etag(
    Publisher,
    queryset_getter=_publisher_filter_queryset,
)


class PublisherViewSet(GCDBaseViewSet):
    """Read-only publisher endpoints for the public v2 API surface."""

    queryset = Publisher.objects.select_related('country').prefetch_related(
        'keywords',
    )
    serializer_class = PublisherSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = PublisherFilterSet

    @condition(
        etag_func=publisher_etag,
        last_modified_func=publisher_last_modified,
    )
    def list(self, request, *args, **kwargs):
        """Return a filtered, paginated publisher collection."""
        return super().list(request, *args, **kwargs)

    @condition(
        etag_func=publisher_etag,
        last_modified_func=publisher_last_modified,
    )
    def retrieve(self, request, *args, **kwargs):
        """Return a single publisher detail record."""
        return super().retrieve(request, *args, **kwargs)
