# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 series endpoints."""

import django_filters

from apps.api_v2.filters.common import (
    TIMESTAMP_FILTER_FIELDS,
    LanguageCodeFilter,
    TimestampFilterSet,
)
from apps.gcd.models import Series


class SeriesFilterSet(TimestampFilterSet):
    """Filters for series list endpoints."""

    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
    )
    country = django_filters.CharFilter(field_name='country__code')
    language = LanguageCodeFilter(field_name='language')
    publisher = django_filters.NumberFilter(field_name='publisher_id')
    publication_type = django_filters.NumberFilter(
        field_name='publication_type_id',
    )

    class Meta:
        """FilterSet metadata for series filtering."""

        model = Series
        fields = (
            'name',
            'year_began',
            'year_ended',
            'country',
            'language',
            'publisher',
            'publication_type',
        ) + TIMESTAMP_FILTER_FIELDS
