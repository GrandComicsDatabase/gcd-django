# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 series endpoints."""

import re

import django_filters
from django.db.models import Case, IntegerField, Value, When
from django.db.models.functions import Collate

from apps.api_v2.filters.common import (
    TIMESTAMP_FILTER_FIELDS,
    IntegerFilter,
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
    search = django_filters.CharFilter(
        method='filter_search',
        help_text=(
            'Case-insensitive, accent-sensitive title search ranked by exact '
            'title, title prefix, token prefix, then substring. Equal-ranked '
            'results use sort_name, year_began, and id as stable '
            'tie-breakers. Leading and trailing whitespace is ignored and '
            'internal whitespace is collapsed.'
        ),
    )
    country = django_filters.CharFilter(field_name='country__code')
    language = LanguageCodeFilter(field_name='language')
    publisher = IntegerFilter(field_name='publisher_id')
    publication_type = IntegerFilter(
        field_name='publication_type_id',
    )

    class Meta:
        """FilterSet metadata for series filtering."""

        model = Series
        fields = (
            'name',
            'search',
            'year_began',
            'year_ended',
            'country',
            'language',
            'publisher',
            'publication_type',
        ) + TIMESTAMP_FILTER_FIELDS

    def filter_search(self, queryset, name, value):
        """Return title matches in deterministic relevance order."""
        del name
        query = ' '.join(value.split())
        if not query:
            return queryset

        token_prefix_pattern = rf'(^|[[:space:][:punct:]]){re.escape(query)}'
        return (
            queryset.annotate(
                _search_title=Collate(
                    'name',
                    'utf8mb4_0900_as_ci',
                ),
                _search_rank=Case(
                    When(_search_title__exact=query, then=Value(0)),
                    When(_search_title__startswith=query, then=Value(1)),
                    When(
                        name__iregex=token_prefix_pattern,
                        then=Value(2),
                    ),
                    default=Value(3),
                    output_field=IntegerField(),
                ),
            )
            .filter(_search_title__contains=query)
            .order_by(
                '_search_rank',
                'sort_name',
                'year_began',
                'id',
            )
        )
