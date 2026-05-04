# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Viewsets for v2 issue endpoints."""

from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend

from apps.api_v2.filters.issues import IssueFilterSet
from apps.api_v2.serializers.issues import (
    IssueDetailSerializer,
    IssueListSerializer,
)
from apps.api_v2.utils.conditional import (
    condition,
    make_etag,
    make_last_modified,
)
from apps.api_v2.views import GCDBaseViewSet
from apps.gcd.models import Cover, Issue, IssueCredit, Story, StoryCredit


def _issue_filter_queryset(request, *, pk=None, **kwargs):
    """Return the issue queryset scoped by request query params."""
    del pk, kwargs
    return IssueFilterSet(
        request.GET,
        queryset=Issue.objects.all(),
    ).qs


issue_last_modified = make_last_modified(
    Issue,
    queryset_getter=_issue_filter_queryset,
)
issue_etag = make_etag(
    Issue,
    queryset_getter=_issue_filter_queryset,
)

ACTIVE_ISSUE_CREDIT_PREFETCH = Prefetch(
    'credits',
    queryset=IssueCredit.objects.filter(deleted=False).select_related(
        'creator',
        'credit_type',
    ),
    to_attr='active_credit_list',
)
ACTIVE_COVER_PREFETCH = Prefetch(
    'cover_set',
    queryset=Cover.objects.filter(deleted=False).order_by('id'),
    to_attr='active_cover_list',
)
ACTIVE_STORY_CREDIT_PREFETCH = Prefetch(
    'credits',
    queryset=StoryCredit.objects.filter(deleted=False).select_related(
        'creator',
        'credit_type',
    ),
    to_attr='active_credit_list',
)
ACTIVE_STORY_PREFETCH = Prefetch(
    'story_set',
    queryset=Story.objects.filter(deleted=False)
    .select_related('type')
    .prefetch_related(
        'keywords',
        ACTIVE_STORY_CREDIT_PREFETCH,
    )
    .order_by('sequence_number', 'id'),
    to_attr='active_story_list',
)


class IssueViewSet(GCDBaseViewSet):
    """Read-only issue endpoints for the public v2 API surface."""

    queryset = (
        Issue.objects.select_related(
            'series',
            'indicia_publisher',
            'variant_of',
        )
        .prefetch_related(
            'brand_emblem',
            'keywords',
            ACTIVE_ISSUE_CREDIT_PREFETCH,
            ACTIVE_COVER_PREFETCH,
            'variant_of__cover_set',
        )
        .order_by(
            # ``Issue.Meta.ordering`` uses the related Series default
            # ordering, which forces a wide join-based sort on large tables.
            'series_id',
            'sort_code',
            'id',
        )
    )
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IssueFilterSet

    def get_queryset(self):
        """Add the nested story prefetch for detail requests only."""
        queryset = super().get_queryset()
        if self.action == 'retrieve':
            queryset = queryset.prefetch_related(ACTIVE_STORY_PREFETCH)
        return queryset

    def get_serializer_class(self):
        """Switch to the detail serializer for retrieve requests."""
        if self.action == 'retrieve':
            return IssueDetailSerializer
        return IssueListSerializer

    @condition(
        etag_func=issue_etag,
        last_modified_func=issue_last_modified,
    )
    def list(self, request, *args, **kwargs):
        """Return a filtered, paginated issue collection."""
        return super().list(request, *args, **kwargs)

    @condition(
        etag_func=issue_etag,
        last_modified_func=issue_last_modified,
    )
    def retrieve(self, request, *args, **kwargs):
        """Return a single issue detail record."""
        return super().retrieve(request, *args, **kwargs)
