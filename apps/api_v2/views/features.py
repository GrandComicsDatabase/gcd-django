# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Viewsets for v2 Feature endpoints."""

from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend

from apps.api_v2.filters.features import FeatureFilterSet
from apps.api_v2.serializers.features import (
    FeatureListSerializer,
    FeatureSerializer,
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
    FeatureNameDetail,
    FeatureRelation,
)


def _feature_filter_queryset(request, *, pk=None, **kwargs):
    """Return Features scoped by request query parameters."""
    del pk, kwargs
    return FeatureFilterSet(
        request.GET,
        queryset=Feature.objects.all(),
        request=request,
    ).qs


feature_last_modified = make_last_modified(
    Feature,
    queryset_getter=_feature_filter_queryset,
)
feature_etag = make_etag(
    Feature,
    queryset_getter=_feature_filter_queryset,
)

ACTIVE_FEATURE_NAME_PREFETCH = Prefetch(
    'feature_names',
    queryset=(
        FeatureNameDetail.objects.filter(deleted=False)
        .prefetch_related(
            Prefetch(
                'featurelogo_set',
                queryset=FeatureLogo.objects.filter(deleted=False).order_by(
                    'sort_name',
                    'id',
                ),
                to_attr='active_feature_logo_list',
            ),
        )
        .order_by('sort_name', 'id')
    ),
    to_attr='active_name_detail_list',
)
OUTGOING_FEATURE_RELATION_PREFETCH = Prefetch(
    'to_related_feature',
    queryset=(
        FeatureRelation.objects.filter(
            from_feature__deleted=False,
            to_feature__deleted=False,
        )
        .select_related('relation_type', 'to_feature__feature_type')
        .order_by(
            'relation_type__name',
            'to_feature__sort_name',
            'id',
        )
    ),
    to_attr='outgoing_feature_relation_list',
)
INCOMING_FEATURE_RELATION_PREFETCH = Prefetch(
    'from_related_feature',
    queryset=(
        FeatureRelation.objects.filter(
            from_feature__deleted=False,
            to_feature__deleted=False,
        )
        .select_related('relation_type', 'from_feature__feature_type')
        .order_by(
            'relation_type__name',
            'from_feature__sort_name',
            'id',
        )
    ),
    to_attr='incoming_feature_relation_list',
)


class FeatureViewSet(GCDBaseViewSet):
    """Read-only Feature endpoints for the public v2 API."""

    queryset = Feature.objects.select_related(
        'feature_type',
        'language',
    ).order_by(
        'sort_name',
        'disambiguation',
        'language__code',
        'id',
    )
    filter_backends = (DjangoFilterBackend,)
    filterset_class = FeatureFilterSet

    def get_queryset(self):
        """Prefetch descriptive detail relationships when required."""
        queryset = super().get_queryset()
        if self.action == 'retrieve':
            queryset = queryset.prefetch_related(
                'keywords',
                ACTIVE_FEATURE_NAME_PREFETCH,
                OUTGOING_FEATURE_RELATION_PREFETCH,
                INCOMING_FEATURE_RELATION_PREFETCH,
            )
        return queryset

    def get_serializer_class(self):
        """Use the full serializer only for detail responses."""
        if self.action == 'retrieve':
            return FeatureSerializer
        return FeatureListSerializer

    @condition(
        etag_func=feature_etag,
        last_modified_func=feature_last_modified,
    )
    def list(self, request, *args, **kwargs):
        """Return a filtered, paginated Feature collection."""
        return super().list(request, *args, **kwargs)

    @condition(
        etag_func=feature_etag,
        last_modified_func=feature_last_modified,
    )
    def retrieve(self, request, *args, **kwargs):
        """Return a single Feature detail record."""
        return super().retrieve(request, *args, **kwargs)
