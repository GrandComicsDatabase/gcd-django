# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Viewsets for v2 story-arc endpoints."""

from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend

from apps.api_v2.filters.story_arcs import StoryArcFilterSet
from apps.api_v2.serializers.story_arcs import (
    StoryArcListSerializer,
    StoryArcSerializer,
)
from apps.api_v2.utils.conditional import (
    condition,
    make_etag,
    make_last_modified,
)
from apps.api_v2.views import GCDBaseViewSet
from apps.gcd.models import Reprint, Story, StoryArc


def _story_arc_filter_queryset(request, *, pk=None, **kwargs):
    """Return the story-arc queryset scoped by request query params."""
    del pk, kwargs
    return StoryArcFilterSet(
        request.GET,
        queryset=StoryArc.objects.all(),
    ).qs


story_arc_last_modified = make_last_modified(
    StoryArc,
    queryset_getter=_story_arc_filter_queryset,
)
story_arc_etag = make_etag(
    StoryArc,
    queryset_getter=_story_arc_filter_queryset,
)

ACTIVE_STORY_ARC_REPRINT_PREFETCH = Prefetch(
    'from_all_reprints',
    queryset=Reprint.objects.select_related(
        'origin_issue__series',
    ).order_by('id'),
    to_attr='active_story_arc_reprint_list',
)
ACTIVE_STORY_ARC_STORY_PREFETCH = Prefetch(
    'story_set',
    queryset=Story.objects.filter(deleted=False)
    .select_related(
        'issue',
        'issue__series',
    )
    .prefetch_related(ACTIVE_STORY_ARC_REPRINT_PREFETCH)
    .order_by(
        'issue__key_date',
        'issue__on_sale_date',
        'issue__series__sort_name',
        'issue__sort_code',
        'sequence_number',
        'id',
    ),
    to_attr='active_story_arc_story_list',
)


class StoryArcViewSet(GCDBaseViewSet):
    """Read-only story-arc endpoints for the public v2 API surface."""

    queryset = StoryArc.objects.select_related('language').order_by(
        'sort_name',
        'language__name',
        'id',
    )
    filter_backends = (DjangoFilterBackend,)
    filterset_class = StoryArcFilterSet

    def get_queryset(self):
        """Add ordered story membership prefetches on detail requests."""
        queryset = super().get_queryset()
        if self.action == 'retrieve':
            queryset = queryset.prefetch_related(
                ACTIVE_STORY_ARC_STORY_PREFETCH,
            )
        return queryset

    def get_serializer_class(self):
        """Switch to the detail serializer for retrieve requests."""
        if self.action == 'retrieve':
            return StoryArcSerializer
        return StoryArcListSerializer

    @condition(
        etag_func=story_arc_etag,
        last_modified_func=story_arc_last_modified,
    )
    def list(self, request, *args, **kwargs):
        """Return a filtered, paginated story-arc collection."""
        return super().list(request, *args, **kwargs)

    @condition(
        etag_func=story_arc_etag,
        last_modified_func=story_arc_last_modified,
    )
    def retrieve(self, request, *args, **kwargs):
        """Return a single story-arc detail record."""
        return super().retrieve(request, *args, **kwargs)
