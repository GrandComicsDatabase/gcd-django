# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 indicia printer endpoints."""

import django_filters

from apps.api_v2.filters.common import (
    TIMESTAMP_FILTER_FIELDS,
    TimestampFilterSet,
)
from apps.gcd.models import IndiciaPrinter


class IndiciaPrinterFilterSet(TimestampFilterSet):
    """Filters for indicia printer list endpoints."""

    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
    )
    parent = django_filters.NumberFilter(field_name='parent_id')
    country = django_filters.CharFilter(field_name='country__code')

    class Meta:
        """FilterSet metadata for indicia printer filtering."""

        model = IndiciaPrinter
        fields = (
            'name',
            'parent',
            'country',
            'year_began',
            'year_ended',
        ) + TIMESTAMP_FILTER_FIELDS
