# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Viewsets for v2 Award endpoints."""

import hashlib

from django.contrib.contenttypes.prefetch import GenericPrefetch
from django.db.models import Q, Subquery
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

from apps.api_v2.filters.awards import (
    AWARD_RECIPIENT_TYPES,
    AwardFilterSet,
    AwardRecipientFilterSet,
)
from apps.api_v2.serializers.awards import (
    AwardListSerializer,
    AwardRecipientSerializer,
    AwardSerializer,
)
from apps.api_v2.utils.conditional import (
    condition,
    make_etag,
    make_last_modified,
)
from apps.api_v2.views import GCDBaseViewSet
from apps.gcd.models import (
    Award,
    Creator,
    Issue,
    ReceivedAward,
    Series,
    Story,
)

SUPPORTED_AWARD_RECIPIENT_TYPES = tuple(
    value for value, _label in AWARD_RECIPIENT_TYPES
)


def _award_filter_queryset(request, *, pk=None, **kwargs):
    """Return Awards scoped by request query parameters."""
    del pk, kwargs
    return AwardFilterSet(
        request.GET,
        queryset=Award.objects.all(),
        request=request,
    ).qs


def _award_recipient_queryset(award_id):
    """Return active supported recipient rows for one active Award."""
    active_recipient = (
        Q(
            content_type__model='creator',
            object_id__in=Creator.objects.filter(deleted=False).values('pk'),
        )
        | Q(
            content_type__model='issue',
            object_id__in=Issue.objects.filter(deleted=False).values('pk'),
        )
        | Q(
            content_type__model='series',
            object_id__in=Series.objects.filter(deleted=False).values('pk'),
        )
        | Q(
            content_type__model='story',
            object_id__in=Story.objects.filter(deleted=False).values('pk'),
        )
    )
    return ReceivedAward.objects.filter(
        active_recipient,
        award_id=award_id,
        award__deleted=False,
        deleted=False,
        content_type__app_label='gcd',
    )


def _award_recipient_filter_queryset(request, *, pk=None, **kwargs):
    """Return recipient rows scoped by Award and request filters."""
    del kwargs
    if pk is None:
        return ReceivedAward.objects.none()
    return AwardRecipientFilterSet(
        request.GET,
        queryset=_award_recipient_queryset(pk),
        request=request,
    ).qs


award_last_modified = make_last_modified(
    Award,
    queryset_getter=_award_filter_queryset,
)
award_etag = make_etag(
    Award,
    queryset_getter=_award_filter_queryset,
)


def _award_recipient_conditional_state(request, *, pk=None, **kwargs):
    """Return cached parent existence and recipient modification state."""
    del kwargs
    if pk is None:
        return None
    cache = getattr(request, '_gcd_v2_award_recipient_condition', None)
    cache_key = (request.get_full_path(), pk)
    if cache is not None and cache_key in cache:
        return cache[cache_key]

    latest_recipient = (
        _award_recipient_filter_queryset(request, pk=pk)
        .order_by('-modified')
        .values('modified')[:1]
    )
    state = (
        Award.objects.filter(pk=pk, deleted=False)
        .annotate(recipient_modified=Subquery(latest_recipient))
        .values('recipient_modified')
        .first()
    )
    if cache is None:
        cache = {}
        request._gcd_v2_award_recipient_condition = cache
    cache[cache_key] = state
    return state


def award_recipient_last_modified(request, *, pk=None, **kwargs):
    """Return the latest filtered recipient timestamp for an Award."""
    state = _award_recipient_conditional_state(
        request,
        pk=pk,
        **kwargs,
    )
    if state is None:
        return None
    return state['recipient_modified']


def award_recipient_etag(request, *, pk=None, **kwargs):
    """Return an ETag for one filtered Award recipient page."""
    state = _award_recipient_conditional_state(
        request,
        pk=pk,
        **kwargs,
    )
    if state is None:
        return None
    latest = state['recipient_modified']
    latest_repr = 'empty' if latest is None else latest.isoformat()
    payload = f'{request.get_full_path()}::{latest_repr}'
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


AWARD_RECIPIENT_PREFETCH = GenericPrefetch(
    'recipient',
    (
        Creator.objects.filter(deleted=False),
        Issue.objects.filter(deleted=False).select_related('series'),
        Series.objects.filter(deleted=False),
        Story.objects.filter(deleted=False).select_related(
            'issue',
            'issue__series',
        ),
    ),
)

AWARD_RECIPIENT_SCHEMA_PARAMETERS = [
    OpenApiParameter(
        name='recipient_type',
        type=str,
        location=OpenApiParameter.QUERY,
        enum=SUPPORTED_AWARD_RECIPIENT_TYPES,
        description='Filter by generic recipient type.',
    ),
    OpenApiParameter(
        name='award_year',
        type=int,
        location=OpenApiParameter.QUERY,
        description='Filter by exact Award year.',
    ),
]


class AwardViewSet(GCDBaseViewSet):
    """Read-only Award endpoints for the public v2 API."""

    queryset = Award.objects.order_by('name', 'id')
    filter_backends = (DjangoFilterBackend,)
    filterset_class = AwardFilterSet

    def get_serializer_class(self):
        """Select the list, detail, or recipient serializer by action."""
        if self.action == 'retrieve':
            return AwardSerializer
        if self.action == 'recipients':
            return AwardRecipientSerializer
        return AwardListSerializer

    @condition(
        etag_func=award_etag,
        last_modified_func=award_last_modified,
    )
    def list(self, request, *args, **kwargs):
        """Return a filtered, paginated Award collection."""
        return super().list(request, *args, **kwargs)

    @condition(
        etag_func=award_etag,
        last_modified_func=award_last_modified,
    )
    def retrieve(self, request, *args, **kwargs):
        """Return a single Award detail record."""
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        parameters=AWARD_RECIPIENT_SCHEMA_PARAMETERS,
        responses=AwardRecipientSerializer(many=True),
    )
    @action(detail=True, methods=('get',))
    @condition(
        etag_func=award_recipient_etag,
        last_modified_func=award_recipient_last_modified,
    )
    def recipients(self, request, *args, **kwargs):
        """Return a filtered, paginated page of typed Award recipients."""
        award = self.get_object()
        queryset = (
            _award_recipient_queryset(award.pk)
            .select_related('content_type')
            .prefetch_related(AWARD_RECIPIENT_PREFETCH)
            .order_by('award_year', 'award_name', 'id')
        )
        filterset = AwardRecipientFilterSet(
            request.query_params,
            queryset=queryset,
            request=request,
        )
        if not filterset.is_valid():
            raise ValidationError(filterset.errors)

        page = self.paginate_queryset(filterset.qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)
