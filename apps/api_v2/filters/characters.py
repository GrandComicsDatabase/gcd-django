# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 character endpoints."""

import django_filters

from apps.gcd.models import Character
from apps.stddata.models import Language


def _request_filter_cache(request):
    """Return a request-local cache for repeated filter lookups."""
    if request is None or not hasattr(request, '__dict__'):
        return None
    cache = getattr(request, '_gcd_v2_character_filter_cache', None)
    if cache is None:
        cache = {}
        request._gcd_v2_character_filter_cache = cache
    return cache


class CharacterFilterSet(django_filters.FilterSet):
    """Filters for character list endpoints."""

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
    language = django_filters.CharFilter(method='filter_language')
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
        """FilterSet metadata for character filtering."""

        model = Character
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

    def filter_language(self, queryset, name, value):
        """Resolve language codes to language_id without a join."""
        del name
        request_cache = _request_filter_cache(getattr(self, 'request', None))
        cache_key = f'language_id:{value}'
        if request_cache is not None and cache_key in request_cache:
            language_id = request_cache[cache_key]
        else:
            language_id = (
                Language.objects.filter(code=value)
                .values_list('id', flat=True)
                .first()
            )
            if request_cache is not None:
                request_cache[cache_key] = language_id
        if language_id is None:
            return queryset.none()
        return queryset.filter(language_id=language_id)
