# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 story endpoints."""

import django_filters

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
    genre = django_filters.CharFilter(field_name='genre')
    issue = django_filters.NumberFilter(field_name='issue_id')
    issue__series = django_filters.NumberFilter(
        field_name='issue__series_id',
    )

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
