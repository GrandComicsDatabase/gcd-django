# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 story endpoints."""

import django_filters
from django.db.models import Q

from apps.api_v2.filters.common import (
    TIMESTAMP_FILTER_FIELDS,
    TimestampFilterSet,
)
from apps.gcd.models import Story


class StoryFilterSet(TimestampFilterSet):
    """Filters for story list endpoints."""

    title = django_filters.CharFilter(
        field_name='title',
        lookup_expr='icontains',
    )
    type = django_filters.NumberFilter(field_name='type_id')
    genre = django_filters.CharFilter(method='filter_genre')
    issue = django_filters.NumberFilter(field_name='issue_id')
    issue__series = django_filters.NumberFilter(
        field_name='issue__series_id',
    )

    def filter_genre(self, queryset, name, value):
        """Return stories matching story text or linked feature genres."""
        del name
        return queryset.filter(
            Q(genre__icontains=value)
            | Q(feature_object__genre__icontains=value),
        ).distinct()

    class Meta:
        """FilterSet metadata for story filtering."""

        model = Story
        fields = (
            'title',
            'type',
            'genre',
            'issue',
            'issue__series',
        ) + TIMESTAMP_FILTER_FIELDS
