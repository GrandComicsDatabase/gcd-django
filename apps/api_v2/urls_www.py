"""URL configuration for the public-data (www) v2 API surface.

Mounted on the ``www.comics.org`` instance (``MYCOMICS=False``). Holds
the viewset routers for approved GCD data — publishers, series, issues,
and the rest as they land in subsequent sprints. The dispatcher in
``apps/api_v2/urls.py`` includes this module on the www instance only.
"""

from django.urls import include, path

from apps.api_v2.routers import V2APIRouter

router = V2APIRouter()

urlpatterns = [
    path('', include(router.urls)),
]
