# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 universe endpoints."""

import django_filters

from apps.api_v2.filters.common import (
    TIMESTAMP_FILTER_FIELDS,
    TimestampFilterSet,
)
from apps.gcd.models import Universe


class UniverseFilterSet(TimestampFilterSet):
    """Filters for universe list endpoints."""

    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
    )
    designation = django_filters.CharFilter(
        field_name='designation',
        lookup_expr='icontains',
    )
    multiverse = django_filters.NumberFilter(field_name='verse_id')

    class Meta:
        """FilterSet metadata for universe filtering."""

        model = Universe
        fields = (
            'name',
            'designation',
            'year_first_published',
            'multiverse',
        ) + TIMESTAMP_FILTER_FIELDS
