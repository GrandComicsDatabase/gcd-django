"""URL dispatcher for the v2 API.

The v2 API mirrors the project's existing two-instance deployment
model. Cross-cutting routes (token issuance, schema, Swagger UI, ReDoc)
live in the dispatcher and appear on both surfaces. Exactly one surface
URL conf is included per instance:

* ``apps.api_v2.urls_www`` on the www instance (``MYCOMICS=False``),
  exposing approved GCD data.
* ``apps.api_v2.urls_my`` on the my instance (``MYCOMICS=True``),
  exposing user data (collections, reading orders).

The schema view is per-instance scoped automatically — drf-spectacular
only sees the routes that are loaded in the current Django process, so
each deployment's ``/api/v2/schema/`` documents only its own surface.
"""

from django.conf import settings
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.authentication import (
    BasicAuthentication,
    SessionAuthentication,
    TokenAuthentication,
)
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import AllowAny

from apps.api_v2.throttling import (
    V2AnonRateThrottle,
    V2SessionUserRateThrottle,
    V2TokenUserRateThrottle,
)


class V2CrossCuttingViewMixin:
    """Pin auth, permission and throttling for cross-cutting v2 views."""

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


class V2ObtainAuthTokenView(V2CrossCuttingViewMixin, ObtainAuthToken):
    """Issue DRF auth tokens under the v2 rate-limiting policy."""


class V2SpectacularAPIView(V2CrossCuttingViewMixin, SpectacularAPIView):
    """Serve the v2 schema with v2 auth and throttling defaults."""


class V2SpectacularSwaggerView(
    V2CrossCuttingViewMixin, SpectacularSwaggerView
):
    """Serve the v2 Swagger UI with v2 auth and throttling defaults."""


class V2SpectacularRedocView(V2CrossCuttingViewMixin, SpectacularRedocView):
    """Serve the v2 ReDoc UI with v2 auth and throttling defaults."""

urlpatterns = [
    path(
        'auth/token/',
        V2ObtainAuthTokenView.as_view(),
        name='api-v2-auth-token',
    ),
    path(
        'schema/',
        V2SpectacularAPIView.as_view(
            custom_settings={
                'PREPROCESSING_HOOKS': [
                    'apps.api_v2.utils.spectacular.v2_endpoints_only',
                ],
                'TITLE': 'GCD API v2',
            },
        ),
        name='api-v2-schema',
    ),
    path(
        'schema/swagger-ui/',
        V2SpectacularSwaggerView.as_view(url_name='api-v2-schema'),
        name='api-v2-swagger-ui',
    ),
    path(
        'schema/redoc/',
        V2SpectacularRedocView.as_view(url_name='api-v2-schema'),
        name='api-v2-redoc',
    ),
]

if settings.MYCOMICS:
    urlpatterns.append(path('', include('apps.api_v2.urls_my')))
else:
    urlpatterns.append(path('', include('apps.api_v2.urls_www')))
