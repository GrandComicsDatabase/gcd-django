# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Viewsets for v2 story-arc endpoints."""

from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action

from apps.api_v2.filters.story_arcs import StoryArcFilterSet
from apps.api_v2.serializers.issues import IssueListSerializer
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
from apps.api_v2.views.issues import IssueViewSet
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
        """Select arc detail or the existing native member-issue shape."""
        if self.action == 'retrieve':
            return StoryArcSerializer
        if self.action == 'issues':
            return IssueListSerializer
        return StoryArcListSerializer

    @extend_schema(
        filters=False,
        responses=IssueListSerializer(many=True),
        description=(
            'Return distinct issues containing active stories associated '
            'with this Story Arc, including reprints. Deleted arcs, '
            'stories, issues, and parent series are excluded. Exact native '
            'issue and parent-series identities and variant_of references '
            'are retained; variants are not replaced with base issues. '
            'Order is by key_date, on_sale_date, series sort_name, issue '
            'sort_code, then issue ID. This is publication sorting, '
            'not a curated reading order; story sequence_number is not a '
            'global position. Count is the number of distinct issues. '
            'Page size defaults to 50 and is capped at 200. An existing '
            'empty arc returns an empty page; an unavailable arc is 404.'
        ),
    )
    @action(detail=True, methods=('get',), filter_backends=())
    def issues(self, request, *args, **kwargs):
        """Return a bounded page of distinct native member issues."""
        arc = self.get_object()
        member_ids = (
            Story.objects.filter(deleted=False, story_arc=arc)
            .order_by()
            .values('issue_id')
        )
        queryset = IssueViewSet.queryset.filter(
            deleted=False,
            series__deleted=False,
            pk__in=member_ids,
        ).order_by(
            'key_date',
            'on_sale_date',
            'series__sort_name',
            'sort_code',
            'id',
        )
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

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
