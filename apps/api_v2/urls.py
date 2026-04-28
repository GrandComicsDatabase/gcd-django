"""URL configuration for the v2 API.

Endpoints are registered against ``router`` in subsequent sprints.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
]
