# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 Feature endpoints."""

import django_filters
from django.db.models import Q

from apps.api_v2.filters.common import (
    TIMESTAMP_FILTER_FIELDS,
    LanguageCodeFilter,
    TimestampFilterSet,
)
from apps.gcd.models import Feature


class FeatureFilterSet(TimestampFilterSet):
    """Filters for Feature list endpoints."""

    name = django_filters.CharFilter(
        method='filter_name',
    )
    feature_type = django_filters.NumberFilter(field_name='feature_type_id')
    language = LanguageCodeFilter(field_name='language')
    genre = django_filters.CharFilter(
        field_name='genre',
        lookup_expr='icontains',
    )

    def filter_name(self, queryset, name, value):
        """Match a Feature's canonical or active alternate names."""
        del name
        return queryset.filter(
            Q(name__icontains=value)
            | Q(
                feature_names__deleted=False,
                feature_names__name__icontains=value,
            ),
        ).distinct()

    class Meta:
        """FilterSet metadata for Feature filtering."""

        model = Feature
        fields = (
            'name',
            'feature_type',
            'language',
            'genre',
            'year_first_published',
        ) + TIMESTAMP_FILTER_FIELDS
