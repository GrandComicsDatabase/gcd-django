"""Conditional request helpers for the v2 API.

Re-exports the DRF-aware conditional decorators from
``rest_framework_condition`` so v2 viewsets have a single import point,
and provides factories that build the per-model callables described in
the PRD: one query against ``modified``, no serialization, no full
queryset evaluation.
"""

import hashlib

from rest_framework_condition import etag, last_modified
from rest_framework_condition.decorators import condition


def _cache_key(model, request, pk):
    """Return a stable request-local cache key for conditional metadata."""
    return f'{model._meta.label_lower}:{request.get_full_path()}:{pk}'


def _request_cache(request):
    """Return a request-local cache dict, or ``None`` for simple sentinels."""
    if not hasattr(request, '__dict__') or not hasattr(
        request, 'get_full_path'
    ):
        return None
    cache = getattr(request, '_gcd_v2_conditional_cache', None)
    if cache is None:
        cache = {}
        request._gcd_v2_conditional_cache = cache
    return cache


def make_last_modified(model, *, soft_delete=True, queryset_getter=None):
    """Return a ``last_modified(request, pk=None, **kwargs)`` callable.

    Detail (``pk`` provided) returns the row's ``modified`` timestamp,
    or ``None`` if the row is missing or soft-deleted. List (``pk`` is
    ``None``) returns ``Max('modified')`` across the model.

    ``soft_delete`` defaults to ``True`` and excludes ``deleted=True``
    rows; set to ``False`` for ``GcdLink``-style join tables that have
    no ``deleted`` column.

    Pass ``queryset_getter`` to scope the list timestamp to a filtered
    result set instead of the entire table. The callable receives the
    same ``request`` / ``pk`` / ``**kwargs`` the conditional decorator
    passes to the generated function and must return a queryset.
    """

    def _last_modified(request, pk=None, **kwargs):
        cache = _request_cache(request)
        key = None if cache is None else _cache_key(model, request, pk)
        if key is not None and key in cache:
            return cache[key]
        if queryset_getter is None:
            qs = model._default_manager.all()
        else:
            qs = queryset_getter(request, pk=pk, **kwargs)
        if soft_delete:
            qs = qs.filter(deleted=False)
        if pk is not None:
            latest = (
                qs.filter(pk=pk).values_list('modified', flat=True).first()
            )
        else:
            # Use the indexed modified column directly instead of an
            # aggregate scan so broad list endpoints stay cheap on the
            # production-sized tables.
            latest = (
                qs.order_by('-modified')
                .values_list('modified', flat=True)
                .first()
            )
        if key is not None:
            cache[key] = latest
        return latest

    return _last_modified


def make_etag(model, *, soft_delete=True, queryset_getter=None):
    """Return an ``etag(request, pk=None, **kwargs)`` callable.

    The ETag is derived from the request path plus the latest modified
    timestamp for the requested resource. Detail requests return
    ``None`` when the row is absent so the wrapped view can still 404.
    Empty list result sets still receive a stable ETag so clients can
    cache the empty response body.
    """
    last_modified_getter = make_last_modified(
        model,
        soft_delete=soft_delete,
        queryset_getter=queryset_getter,
    )

    def _etag(request, pk=None, **kwargs):
        latest = last_modified_getter(request, pk=pk, **kwargs)
        if pk is not None and latest is None:
            return None
        latest_repr = 'empty' if latest is None else latest.isoformat()
        payload = f'{request.get_full_path()}::{latest_repr}'
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    return _etag


__all__ = [
    'condition',
    'etag',
    'last_modified',
    'make_etag',
    'make_last_modified',
]
