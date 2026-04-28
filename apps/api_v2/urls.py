"""URL configuration for the v2 API.

Resource viewsets are registered against ``router`` in subsequent
sprints. ``auth/token/`` is wired up here so clients can exchange
basic-auth credentials for a token.
"""

from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
    path('auth/token/', obtain_auth_token, name='api-v2-auth-token'),
]
