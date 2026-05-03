"""View base classes for the v2 API."""

from rest_framework.authentication import (
    BasicAuthentication,
    SessionAuthentication,
    TokenAuthentication,
)
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.api_v2.pagination import V2PageNumberPagination
from apps.api_v2.throttling import (
    V2AnonRateThrottle,
    V2SessionUserRateThrottle,
    V2TokenUserRateThrottle,
)


class GCDBaseViewSet(ReadOnlyModelViewSet):
    """Read-only viewset that hides soft-deleted records.

    All v2 list/detail viewsets inherit from this class. Every GCD model
    derived from ``GcdData`` has a ``deleted`` boolean; ``get_queryset``
    applies ``deleted=False`` automatically so subclasses do not have to
    repeat it.

    Subclasses are expected to set:

    * ``queryset`` — with explicit ``select_related`` and
      ``prefetch_related`` declarations covering every related field the
      serializer touches (no lazy loading).
    * ``serializer_class``.

    Subclasses that override ``get_queryset`` must call ``super().
    get_queryset()`` to keep the soft-delete filter applied. This base
    class is intended for ``GcdData``-derived models only; do not use it
    for tables without a ``deleted`` column.

    Authentication, permission, pagination and throttling are pinned at
    the base-class level so they cannot drift between v2 endpoints and
    so v2 stays decoupled from the project-wide DRF defaults (which v1
    relies on).
    """

    authentication_classes = (
        TokenAuthentication,
        BasicAuthentication,
        SessionAuthentication,
    )
    permission_classes = (AllowAny,)
    pagination_class = V2PageNumberPagination
    throttle_classes = (
        V2AnonRateThrottle,
        V2TokenUserRateThrottle,
        V2SessionUserRateThrottle,
    )

    def get_queryset(self):
        """Return the configured queryset filtered to non-deleted rows."""
        return super().get_queryset().filter(deleted=False)
