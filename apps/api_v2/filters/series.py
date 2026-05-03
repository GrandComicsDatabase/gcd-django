"""django-filter configuration for v2 series endpoints."""

import django_filters

from apps.gcd.models import Series


class SeriesFilterSet(django_filters.FilterSet):
    """Filters for series list endpoints."""

    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
    )
    country = django_filters.CharFilter(field_name='country__code')
    language = django_filters.CharFilter(field_name='language__code')
    publisher = django_filters.NumberFilter(field_name='publisher_id')
    publication_type = django_filters.NumberFilter(
        field_name='publication_type_id',
    )
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
            'modified__gt',
            'modified__gte',
            'modified__lt',
            'modified__lte',
            'created__gt',
            'created__gte',
            'created__lt',
            'created__lte',
        )
