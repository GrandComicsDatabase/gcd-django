"""URL configuration for the v2 API.

Resource viewsets are registered against ``router`` in subsequent
sprints. ``auth/token/`` is wired up here so clients can exchange
basic-auth credentials for a token. ``schema/`` serves a v2-scoped
OpenAPI document filtered down from the project urlconf.
"""

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

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
]
