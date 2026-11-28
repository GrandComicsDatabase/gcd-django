# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""View base classes for the v2 API."""

from django.db import transaction
from django.utils.decorators import method_decorator
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


def _model_has_deleted_field(model):
    """Return whether ``model`` exposes the standard soft-delete field."""
    return any(field.name == 'deleted' for field in model._meta.fields)


@method_decorator(transaction.non_atomic_requests, name='dispatch')
class GCDBaseViewSet(ReadOnlyModelViewSet):
    """Read-only viewset with the shared v2 API policy.

    All v2 list/detail viewsets inherit from this class. GCD models derived
    from ``GcdData`` have a ``deleted`` boolean; ``get_queryset`` applies
    ``deleted=False`` automatically so subclasses do not have to repeat it.
    Link models derived from ``GcdLink`` have no soft-delete column and are
    returned without that predicate.

    Subclasses are expected to set:

    * ``queryset`` — with explicit ``select_related`` and
      ``prefetch_related`` declarations covering every related field the
      serializer touches (no lazy loading).
    * ``serializer_class``.

    Subclasses that override ``get_queryset`` must call ``super().
    get_queryset()`` to keep shared queryset policy applied.

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
        """Return the configured queryset with shared v2 filtering."""
        queryset = super().get_queryset()
        if _model_has_deleted_field(queryset.model):
            queryset = queryset.filter(deleted=False)
        return queryset
