"""Conditional request helpers for the v2 API.

Re-exports ``last_modified`` and ``etag`` from
``rest_framework_condition`` so v2 viewsets have a single import point,
and provides ``make_last_modified``, a factory that builds the
per-model callable described in the PRD: one query against ``modified``,
no serialization, no full queryset evaluation.
"""

from django.db.models import Max
from rest_framework_condition import etag, last_modified


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
        if queryset_getter is None:
            qs = model._default_manager.all()
        else:
            qs = queryset_getter(request, pk=pk, **kwargs)
        if soft_delete:
            qs = qs.filter(deleted=False)
        if pk is not None:
            return qs.filter(pk=pk).values_list('modified', flat=True).first()
        return qs.aggregate(latest=Max('modified'))['latest']

    return _last_modified


__all__ = ['etag', 'last_modified', 'make_last_modified']
