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
from rest_framework.authtoken.views import obtain_auth_token

urlpatterns = [
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

if settings.MYCOMICS:
    urlpatterns.append(path('', include('apps.api_v2.urls_my')))
else:
    urlpatterns.append(path('', include('apps.api_v2.urls_www')))
