"""View base classes for the v2 API."""

from rest_framework.viewsets import ReadOnlyModelViewSet


class GCDBaseViewSet(ReadOnlyModelViewSet):
    """Read-only viewset that hides soft-deleted records.

    All v2 list/detail viewsets inherit from this class. Every GCD model
    derived from ``GcdData`` has a ``deleted`` boolean; ``get_queryset``
    applies ``deleted=False`` automatically so subclasses do not have to
    repeat it.

    Subclasses are expected to set:

    * ``queryset`` — with explicit ``select_related`` and
      ``prefetch_related`` declarations covering every related field the
      serializer touches (no lazy loading).
    * ``serializer_class``.

    Subclasses that override ``get_queryset`` must call ``super().
    get_queryset()`` to keep the soft-delete filter applied. This base
    class is intended for ``GcdData``-derived models only; do not use it
    for tables without a ``deleted`` column.
    """

    def get_queryset(self):
        """Return the configured queryset filtered to non-deleted rows."""
        return super().get_queryset().filter(deleted=False)
