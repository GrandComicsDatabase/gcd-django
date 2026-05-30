# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 group endpoints."""

import django_filters

from apps.api_v2.filters.common import (
    TIMESTAMP_FILTER_FIELDS,
    LanguageCodeFilter,
    TimestampFilterSet,
)
from apps.gcd.models import Group


class GroupFilterSet(TimestampFilterSet):
    """Filters for group list endpoints."""

    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
    )
    year_first_published__gte = django_filters.NumberFilter(
        field_name='year_first_published',
        lookup_expr='gte',
    )
    year_first_published__lte = django_filters.NumberFilter(
        field_name='year_first_published',
        lookup_expr='lte',
    )
    language = LanguageCodeFilter(field_name='language')
    universe = django_filters.NumberFilter(field_name='universe_id')

    class Meta:
        """FilterSet metadata for group filtering."""

        model = Group
        fields = (
            'name',
            'year_first_published__gte',
            'year_first_published__lte',
            'language',
            'universe',
        ) + TIMESTAMP_FILTER_FIELDS
