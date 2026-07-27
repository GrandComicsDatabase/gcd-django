# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 Brand endpoints."""

import django_filters

from apps.api_v2.filters.common import (
    TIMESTAMP_FILTER_FIELDS,
    TimestampFilterSet,
)
from apps.gcd.models import Brand


class BrandFilterSet(TimestampFilterSet):
    """Filters for Brand list endpoints."""

    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
    )
    generic = django_filters.BooleanFilter(field_name='generic')
    group = django_filters.NumberFilter(method='filter_group')
    publisher = django_filters.NumberFilter(method='filter_publisher')

    def filter_group(self, queryset, name, value):
        """Filter by an active Brand Group without duplicate rows."""
        del name
        return queryset.filter(
            group__id=value,
            group__deleted=False,
            group__parent__deleted=False,
        ).distinct()

    def filter_publisher(self, queryset, name, value):
        """Filter by active Brand Uses without duplicate rows."""
        del name
        return queryset.filter(
            in_use__publisher_id=value,
            in_use__publisher__deleted=False,
        ).distinct()

    class Meta:
        """FilterSet metadata for Brand filtering."""

        model = Brand
        fields = (
            'name',
            'generic',
            'group',
            'publisher',
            'year_began',
            'year_ended',
        ) + TIMESTAMP_FILTER_FIELDS
