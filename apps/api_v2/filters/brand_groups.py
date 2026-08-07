# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 brand group endpoints."""

import django_filters

from apps.api_v2.filters.common import (
    TIMESTAMP_FILTER_FIELDS,
    TimestampFilterSet,
)
from apps.gcd.models import BrandGroup


class BrandGroupFilterSet(TimestampFilterSet):
    """Filters for brand group list endpoints."""

    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
    )
    parent = django_filters.NumberFilter(field_name='parent_id')

    class Meta:
        """FilterSet metadata for brand group filtering."""

        model = BrandGroup
        fields = (
            'name',
            'parent',
            'year_began',
            'year_ended',
        ) + TIMESTAMP_FILTER_FIELDS
