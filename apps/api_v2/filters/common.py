# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Shared django-filter helpers for v2 endpoints."""

import django_filters
from django_filters.constants import EMPTY_VALUES

from apps.stddata.models import Language


def _request_filter_cache(request):
    """Return a request-local cache for repeated filter lookups."""
    if request is None or not hasattr(request, '__dict__'):
        return None
    cache = getattr(request, '_gcd_v2_filter_cache', None)
    if cache is None:
        cache = {}
        request._gcd_v2_filter_cache = cache
    return cache


def _lookup_language_id(value):
    """Return the language id for a public language code."""
    try:
        return Language.objects.values_list('id', flat=True).get(code=value)
    except Language.DoesNotExist:
        return None


def _resolve_language_id(request, value):
    """Return a cached language id for a public language code."""
    request_cache = _request_filter_cache(request)
    cache_key = f'language_id:{value}'
    if request_cache is not None and cache_key in request_cache:
        return request_cache[cache_key]

    language_id = _lookup_language_id(value)
    if request_cache is not None:
        request_cache[cache_key] = language_id
    return language_id


class LanguageCodeFilter(django_filters.CharFilter):
    """Filter a language FK by public code using an id predicate.

    API consumers pass the language code, e.g. ``?language=en``. The
    queryset uses ``language_id`` internally so list endpoints avoid a
    join to ``stddata_language`` and can use language-aware indexes.
    """

    def filter(self, qs, value):
        """Filter ``qs`` by the language id for ``value``."""
        if value in EMPTY_VALUES:
            return qs

        request = getattr(getattr(self, 'parent', None), 'request', None)
        language_id = _resolve_language_id(request, value)
        if language_id is None:
            return qs.none()
        return qs.filter(**{f'{self.field_name}_id': language_id})
