"""URL configuration for the v2 API.

Resource viewsets are registered against ``router`` in subsequent
sprints. ``auth/token/`` is wired up here so clients can exchange
basic-auth credentials for a token. ``schema/`` serves a v2-scoped
OpenAPI document filtered down from the project urlconf, with Swagger
UI and ReDoc renderers alongside.
"""

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
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.permissions import AllowAny
from rest_framework.routers import APIRootView, DefaultRouter


class V2APIRootView(APIRootView):
    """API root view for v2.

    Overrides ``DEFAULT_AUTHENTICATION_CLASSES`` /
    ``DEFAULT_PERMISSION_CLASSES`` (which v1 still relies on) so the
    browsable root at ``/api/v2/`` is anon-readable, matching the rest
    of v2's read-only public surface.
    """

    authentication_classes = (
        TokenAuthentication,
        BasicAuthentication,
        SessionAuthentication,
    )
    permission_classes = (AllowAny,)


class V2APIRouter(DefaultRouter):
    """``DefaultRouter`` with the v2 root view aligned to v2 auth/perm."""

    APIRootView = V2APIRootView


router = V2APIRouter()

urlpatterns = [
    path('', include(router.urls)),
    path('auth/token/', obtain_auth_token, name='api-v2-auth-token'),
    path(
        'schema/',
        SpectacularAPIView.as_view(
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
        SpectacularSwaggerView.as_view(url_name='api-v2-schema'),
        name='api-v2-swagger-ui',
    ),
    path(
        'schema/redoc/',
        SpectacularRedocView.as_view(url_name='api-v2-schema'),
        name='api-v2-redoc',
    ),
]
