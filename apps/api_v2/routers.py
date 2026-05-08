# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Custom DRF routers for the v2 API.

Both surface URL confs (``urls_www`` and ``urls_my``) build their
viewset registry on top of ``V2APIRouter``, which swaps in the v2
``APIRootView`` so the browsable root at ``/api/v2/`` stays anon-
readable instead of inheriting the project-wide DRF defaults that v1
relies on.
"""

from rest_framework.authentication import (
    BasicAuthentication,
    SessionAuthentication,
    TokenAuthentication,
)
from rest_framework.permissions import AllowAny
from rest_framework.routers import APIRootView, DefaultRouter

from apps.api_v2.throttling import (
    V2AnonRateThrottle,
    V2SessionUserRateThrottle,
    V2TokenUserRateThrottle,
)


class V2APIRootView(APIRootView):
    """API root view for v2.

    Overrides ``DEFAULT_AUTHENTICATION_CLASSES`` /
    ``DEFAULT_PERMISSION_CLASSES`` / ``DEFAULT_THROTTLE_CLASSES``
    (which v1 still relies on) so the browsable root at ``/api/v2/``
    is anon-readable and uses the v2-specific rate buckets.
    """

    authentication_classes = (
        TokenAuthentication,
        BasicAuthentication,
        SessionAuthentication,
    )
    permission_classes = (AllowAny,)
    throttle_classes = (
        V2AnonRateThrottle,
        V2TokenUserRateThrottle,
        V2SessionUserRateThrottle,
    )


class V2APIRouter(DefaultRouter):
    """``DefaultRouter`` with the v2 root view aligned to v2 auth/perm."""

    APIRootView = V2APIRootView
