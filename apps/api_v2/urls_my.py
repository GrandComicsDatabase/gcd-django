"""URL configuration for the user-data (my) v2 API surface.

Mounted on the ``my.comics.org`` instance (``MYCOMICS=True``). Holds
the viewset routers for user data — collections and reading orders —
once those endpoints land in later sprints. The dispatcher in
``apps/api_v2/urls.py`` includes this module on the my instance only.
"""

from django.urls import include, path

from apps.api_v2.routers import V2APIRouter

router = V2APIRouter()

urlpatterns = [
    path('', include(router.urls)),
]
