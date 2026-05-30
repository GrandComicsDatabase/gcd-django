# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 group endpoints."""

import django_filters

from apps.api_v2.filters.common import LanguageCodeFilter
from apps.gcd.models import Group


class GroupFilterSet(django_filters.FilterSet):
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
    modified__gt = django_filters.IsoDateTimeFilter(
        field_name='modified',
        lookup_expr='gt',
    )
    modified__gte = django_filters.IsoDateTimeFilter(
        field_name='modified',
        lookup_expr='gte',
    )
    modified__lt = django_filters.IsoDateTimeFilter(
        field_name='modified',
        lookup_expr='lt',
    )
    modified__lte = django_filters.IsoDateTimeFilter(
        field_name='modified',
        lookup_expr='lte',
    )
    created__gt = django_filters.IsoDateTimeFilter(
        field_name='created',
        lookup_expr='gt',
    )
    created__gte = django_filters.IsoDateTimeFilter(
        field_name='created',
        lookup_expr='gte',
    )
    created__lt = django_filters.IsoDateTimeFilter(
        field_name='created',
        lookup_expr='lt',
    )
    created__lte = django_filters.IsoDateTimeFilter(
        field_name='created',
        lookup_expr='lte',
    )

    class Meta:
        """FilterSet metadata for group filtering."""

        model = Group
        fields = (
            'name',
            'year_first_published__gte',
            'year_first_published__lte',
            'language',
            'universe',
            'modified__gt',
            'modified__gte',
            'modified__lt',
            'modified__lte',
            'created__gt',
            'created__gte',
            'created__lt',
            'created__lte',
        )
