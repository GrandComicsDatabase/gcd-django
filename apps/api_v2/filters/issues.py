"""django-filter configuration for v2 issue endpoints."""

import django_filters

from apps.gcd.models import Issue


class IssueFilterSet(django_filters.FilterSet):
    """Filters for issue list endpoints."""

    series = django_filters.NumberFilter(field_name='series_id')
    variant_of = django_filters.BooleanFilter(method='filter_variant_of')
    key_date__gt = django_filters.CharFilter(
        field_name='key_date',
        lookup_expr='gt',
    )
    key_date__gte = django_filters.CharFilter(
        field_name='key_date',
        lookup_expr='gte',
    )
    key_date__lt = django_filters.CharFilter(
        field_name='key_date',
        lookup_expr='lt',
    )
    key_date__lte = django_filters.CharFilter(
        field_name='key_date',
        lookup_expr='lte',
    )
    on_sale_date__gt = django_filters.CharFilter(
        field_name='on_sale_date',
        lookup_expr='gt',
    )
    on_sale_date__gte = django_filters.CharFilter(
        field_name='on_sale_date',
        lookup_expr='gte',
    )
    on_sale_date__lt = django_filters.CharFilter(
        field_name='on_sale_date',
        lookup_expr='lt',
    )
    on_sale_date__lte = django_filters.CharFilter(
        field_name='on_sale_date',
        lookup_expr='lte',
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
        """FilterSet metadata for issue filtering."""

        model = Issue
        fields = (
            'series',
            'number',
            'key_date__gt',
            'key_date__gte',
            'key_date__lt',
            'key_date__lte',
            'on_sale_date__gt',
            'on_sale_date__gte',
            'on_sale_date__lt',
            'on_sale_date__lte',
            'isbn',
            'barcode',
            'variant_of',
            'modified__gt',
            'modified__gte',
            'modified__lt',
            'modified__lte',
            'created__gt',
            'created__gte',
            'created__lt',
            'created__lte',
        )

    def filter_variant_of(self, queryset, name, value):
        """Filter by whether an issue is a variant."""
        del name
        return queryset.filter(variant_of__isnull=not value)
