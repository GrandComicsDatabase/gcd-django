# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Viewsets for v2 story endpoints."""

from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend

from apps.api_v2.filters.stories import StoryFilterSet
from apps.api_v2.serializers.stories import (
    StoryListSerializer,
    StorySerializer,
)
from apps.api_v2.utils.conditional import (
    condition,
    make_etag,
    make_last_modified,
)
from apps.api_v2.views import GCDBaseViewSet
from apps.gcd.models import (
    Feature,
    FeatureLogo,
    Reprint,
    Story,
    StoryCharacter,
    StoryCredit,
)


def _story_filter_queryset(request, *, pk=None, **kwargs):
    """Return the story queryset scoped by request query params."""
    del pk, kwargs
    return StoryFilterSet(
        request.GET,
        queryset=Story.objects.all(),
    ).qs


story_last_modified = make_last_modified(
    Story,
    queryset_getter=_story_filter_queryset,
)
story_etag = make_etag(
    Story,
    queryset_getter=_story_filter_queryset,
)

ACTIVE_STORY_CREDIT_PREFETCH = Prefetch(
    'credits',
    queryset=StoryCredit.objects.filter(deleted=False)
    .select_related(
        'creator__creator',
        'credit_type',
    )
    .order_by(
        'credit_type__sort_code',
        'id',
    ),
    to_attr='active_credit_list',
)
ACTIVE_STORY_CHARACTER_PREFETCH = Prefetch(
    'appearing_characters',
    queryset=StoryCharacter.objects.filter(deleted=False)
    .select_related(
        'character__character',
        'role',
    )
    .order_by(
        'character__sort_name',
        'character__id',
    ),
    to_attr='active_character_list',
)
ACTIVE_FEATURE_PREFETCH = Prefetch(
    'feature_object',
    queryset=Feature.objects.filter(deleted=False)
    .select_related('feature_type')
    .order_by('sort_name', 'id'),
    to_attr='active_feature_list',
)
ACTIVE_FEATURE_LOGO_PREFETCH = Prefetch(
    'feature_logo',
    queryset=FeatureLogo.objects.filter(deleted=False).order_by(
        'sort_name',
        'id',
    ),
    to_attr='active_feature_logo_list',
)
ACTIVE_REPRINT_ORIGIN_PREFETCH = Prefetch(
    'from_all_reprints',
    queryset=Reprint.objects.exclude(origin=None).order_by('origin_id', 'id'),
    to_attr='active_reprint_origin_list',
)
ACTIVE_REPRINT_TARGET_PREFETCH = Prefetch(
    'to_all_reprints',
    queryset=Reprint.objects.exclude(target=None).order_by('target_id', 'id'),
    to_attr='active_reprint_target_list',
)


class StoryViewSet(GCDBaseViewSet):
    """Read-only story endpoints for the public v2 API surface."""

    queryset = Story.objects.select_related(
        'type',
        'issue',
        'issue__series',
    ).order_by(
        'issue_id',
        'sequence_number',
        'id',
    )
    filter_backends = (DjangoFilterBackend,)
    filterset_class = StoryFilterSet

    def get_queryset(self):
        """Add detail-only story relation prefetches."""
        queryset = super().get_queryset()
        if self.action == 'retrieve':
            queryset = queryset.prefetch_related(
                'keywords',
                ACTIVE_FEATURE_PREFETCH,
                ACTIVE_FEATURE_LOGO_PREFETCH,
                ACTIVE_STORY_CREDIT_PREFETCH,
                ACTIVE_STORY_CHARACTER_PREFETCH,
                ACTIVE_REPRINT_ORIGIN_PREFETCH,
                ACTIVE_REPRINT_TARGET_PREFETCH,
            )
        return queryset

    def get_serializer_class(self):
        """Switch to the detail serializer for retrieve requests."""
        if self.action == 'retrieve':
            return StorySerializer
        return StoryListSerializer

    @condition(
        etag_func=story_etag,
        last_modified_func=story_last_modified,
    )
    def list(self, request, *args, **kwargs):
        """Return a filtered, paginated story collection."""
        return super().list(request, *args, **kwargs)

    @condition(
        etag_func=story_etag,
        last_modified_func=story_last_modified,
    )
    def retrieve(self, request, *args, **kwargs):
        """Return a single story detail record."""
        return super().retrieve(request, *args, **kwargs)
