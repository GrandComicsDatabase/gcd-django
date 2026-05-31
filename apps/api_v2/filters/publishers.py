# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 publisher endpoints."""

import django_filters

from apps.api_v2.filters.common import (
    TIMESTAMP_FILTER_FIELDS,
    TimestampFilterSet,
)
from apps.gcd.models import Publisher


class PublisherFilterSet(TimestampFilterSet):
    """Filters for publisher list endpoints."""

    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
    )
    country = django_filters.CharFilter(field_name='country__code')

    class Meta:
        """FilterSet metadata for publisher filtering."""

        model = Publisher
        fields = (
            'name',
            'year_began',
            'year_ended',
            'country',
        ) + TIMESTAMP_FILTER_FIELDS
