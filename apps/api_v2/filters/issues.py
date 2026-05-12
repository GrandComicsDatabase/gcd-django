# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 issue endpoints."""

from datetime import date

import django_filters
from django.core.exceptions import ValidationError

from apps.gcd.models import Issue
from apps.gcd.models.issue import issues_for_iso_week


def validate_iso_week(value):
    """Validate an ISO week string in ``YYYY-Www`` form."""
    try:
        year_text, week_text = value.split('-W')
    except ValueError as exc:
        raise ValidationError(
            'Enter a valid ISO week in YYYY-Www format.',
        ) from exc
    if (
        len(year_text) != 4
        or len(week_text) != 2
        or not year_text.isdigit()
        or not week_text.isdigit()
    ):
        raise ValidationError('Enter a valid ISO week in YYYY-Www format.')
    try:
        date.fromisocalendar(int(year_text), int(week_text), 1)
    except ValueError as exc:
        raise ValidationError(
            'Enter a valid ISO week in YYYY-Www format.',
        ) from exc


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
    on_sale_iso_week = django_filters.CharFilter(
        method='filter_on_sale_iso_week',
        validators=[validate_iso_week],
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
            'on_sale_iso_week',
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

    def filter_on_sale_iso_week(self, queryset, name, value):
        """Filter issues to the Monday-Sunday window for an ISO week."""
        del name
        year_text, week_text = value.split('-W')
        week_qs, _monday, _sunday = issues_for_iso_week(
            int(year_text),
            int(week_text),
        )
        return queryset.filter(pk__in=week_qs.values('pk'))
