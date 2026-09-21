# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""URL configuration for the public-data (www) v2 API surface.

Mounted on the ``www.comics.org`` instance (``MYCOMICS=False``). Holds
the viewset routers for approved GCD data — publishers, series, issues,
and the rest as they land in subsequent sprints. The dispatcher in
``apps/api_v2/urls.py`` includes this module on the www instance only.
"""

from django.urls import include, path

from apps.api_v2.routers import V2APIRouter
from apps.api_v2.views.awards import AwardViewSet
from apps.api_v2.views.brand_groups import BrandGroupViewSet
from apps.api_v2.views.brands import BrandViewSet
from apps.api_v2.views.characters import CharacterViewSet
from apps.api_v2.views.creators import CreatorViewSet
from apps.api_v2.views.features import FeatureViewSet
from apps.api_v2.views.groups import GroupViewSet
from apps.api_v2.views.indicia_printers import IndiciaPrinterViewSet
from apps.api_v2.views.indicia_publishers import IndiciaPublisherViewSet
from apps.api_v2.views.issues import IssueViewSet
from apps.api_v2.views.publishers import PublisherViewSet
from apps.api_v2.views.reprints import ReprintViewSet
from apps.api_v2.views.series import SeriesViewSet
from apps.api_v2.views.series_bonds import SeriesBondViewSet
from apps.api_v2.views.stories import StoryViewSet
from apps.api_v2.views.story_arcs import StoryArcViewSet
from apps.api_v2.views.universes import UniverseViewSet

router = V2APIRouter()
router.register('awards', AwardViewSet, basename='api-v2-award')
router.register(
    'brand-groups',
    BrandGroupViewSet,
    basename='api-v2-brand-group',
)
router.register('brands', BrandViewSet, basename='api-v2-brand')
router.register('characters', CharacterViewSet, basename='api-v2-character')
router.register('creators', CreatorViewSet, basename='api-v2-creator')
router.register('features', FeatureViewSet, basename='api-v2-feature')
router.register('groups', GroupViewSet, basename='api-v2-group')
router.register(
    'indicia-printers',
    IndiciaPrinterViewSet,
    basename='api-v2-indicia-printer',
)
router.register(
    'indicia-publishers',
    IndiciaPublisherViewSet,
    basename='api-v2-indicia-publisher',
)
router.register('issues', IssueViewSet, basename='api-v2-issue')
router.register('publishers', PublisherViewSet, basename='api-v2-publisher')
router.register('reprints', ReprintViewSet, basename='api-v2-reprint')
router.register('series', SeriesViewSet, basename='api-v2-series')
router.register(
    'series-bonds',
    SeriesBondViewSet,
    basename='api-v2-series-bond',
)
router.register(
    'story-arcs',
    StoryArcViewSet,
    basename='api-v2-story-arc',
)
router.register('stories', StoryViewSet, basename='api-v2-story')
router.register('universes', UniverseViewSet, basename='api-v2-universe')

urlpatterns = [
    path('', include(router.urls)),
]
