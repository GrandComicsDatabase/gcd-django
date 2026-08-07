# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 indicia publisher endpoints."""

import django_filters

from apps.api_v2.filters.common import (
    TIMESTAMP_FILTER_FIELDS,
    TimestampFilterSet,
)
from apps.gcd.models import IndiciaPublisher


class IndiciaPublisherFilterSet(TimestampFilterSet):
    """Filters for indicia publisher list endpoints."""

    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
    )
    parent = django_filters.NumberFilter(field_name='parent_id')
    country = django_filters.CharFilter(field_name='country__code')
    is_surrogate = django_filters.BooleanFilter(field_name='is_surrogate')

    class Meta:
        """FilterSet metadata for indicia publisher filtering."""

        model = IndiciaPublisher
        fields = (
            'name',
            'parent',
            'country',
            'is_surrogate',
            'year_began',
            'year_ended',
        ) + TIMESTAMP_FILTER_FIELDS
