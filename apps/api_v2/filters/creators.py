# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 creator endpoints."""

import calendar

import django_filters
from django.core.exceptions import ValidationError
from django.db.models import (
    Case,
    ExpressionWrapper,
    F,
    IntegerField,
    Q,
    Value,
    When,
)
from django.db.models.functions import Cast

from apps.gcd.models import Creator
from apps.stddata.forms import DateForm

PARTIAL_DATE_ERROR = (
    'Enter a valid partial date in YYYY, YYYY-MM, or YYYY-MM-DD format.'
)
NUMERIC_COMPONENT_RE = r'^\d+$'


def _parse_partial_date(value):
    """Return a parsed ``Date`` instance for a compact partial-date string."""
    form = DateForm(data={'date': value})
    if not form.is_valid() or form.cleaned_data['date'] is None:
        raise ValidationError(PARTIAL_DATE_ERROR)
    return form.instance


def validate_partial_date(value):
    """Validate a creator partial-date filter value."""
    _parse_partial_date(value)


def _date_component_expr(field_name, component):
    """Return an integer expression for one ``Date`` component."""
    return Case(
        When(**{f'{field_name}__{component}': ''}, then=Value(0)),
        default=Cast(F(f'{field_name}__{component}'), IntegerField()),
        output_field=IntegerField(),
    )


def _date_sort_key(field_name):
    """Return a sortable integer key for a related partial date."""
    year_expr = _date_component_expr(field_name, 'year')
    month_expr = _date_component_expr(field_name, 'month')
    day_expr = _date_component_expr(field_name, 'day')
    return ExpressionWrapper(
        year_expr * 10000 + month_expr * 100 + day_expr,
        output_field=IntegerField(),
    )


def _lower_bound(date_obj):
    """Return the inclusive lower-bound sort key for a partial date."""
    year = int(date_obj.year)
    month = int(date_obj.month) if date_obj.month else 0
    day = int(date_obj.day) if date_obj.day else 0
    return year * 10000 + month * 100 + day


def _upper_bound(date_obj):
    """Return the inclusive upper-bound sort key for a partial date."""
    year = int(date_obj.year)
    if not date_obj.month:
        return year * 10000 + 1231
    month = int(date_obj.month)
    if not date_obj.day:
        last_day = calendar.monthrange(year, month)[1]
        return year * 10000 + month * 100 + last_day
    day = int(date_obj.day)
    return year * 10000 + month * 100 + day


def _filter_comparable_partial_dates(queryset, field_name):
    """Restrict filters to partial dates with numeric stored components."""
    return (
        queryset.filter(**{f'{field_name}__isnull': False})
        .filter(**{f'{field_name}__year__regex': NUMERIC_COMPONENT_RE})
        .filter(
            Q(**{f'{field_name}__month': ''})
            | Q(**{f'{field_name}__month__regex': NUMERIC_COMPONENT_RE})
        )
        .filter(
            Q(**{f'{field_name}__day': ''})
            | Q(**{f'{field_name}__day__regex': NUMERIC_COMPONENT_RE})
        )
    )


class CreatorFilterSet(django_filters.FilterSet):
    """Filters for creator list endpoints."""

    name = django_filters.CharFilter(
        field_name='gcd_official_name',
        lookup_expr='icontains',
    )
    birth_country = django_filters.CharFilter(field_name='birth_country__code')
    birth_date__gte = django_filters.CharFilter(
        method='filter_birth_date_gte',
        validators=[validate_partial_date],
    )
    birth_date__lte = django_filters.CharFilter(
        method='filter_birth_date_lte',
        validators=[validate_partial_date],
    )
    death_date__gte = django_filters.CharFilter(
        method='filter_death_date_gte',
        validators=[validate_partial_date],
    )
    death_date__lte = django_filters.CharFilter(
        method='filter_death_date_lte',
        validators=[validate_partial_date],
    )
    death_date__isnull = django_filters.BooleanFilter(
        field_name='death_date',
        lookup_expr='isnull',
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
        """FilterSet metadata for creator filtering."""

        model = Creator
        fields = (
            'name',
            'birth_country',
            'birth_date__gte',
            'birth_date__lte',
            'death_date__gte',
            'death_date__lte',
            'death_date__isnull',
            'modified__gt',
            'modified__gte',
            'modified__lt',
            'modified__lte',
            'created__gt',
            'created__gte',
            'created__lt',
            'created__lte',
        )

    def _filter_partial_date(self, queryset, field_name, value, lookup):
        """Filter a related ``Date`` field against a compact range bound."""
        parsed = _parse_partial_date(value)
        bound = (
            _lower_bound(parsed) if lookup == 'gte' else _upper_bound(parsed)
        )
        sort_key_name = f'_{field_name}_sort_key'
        return (
            _filter_comparable_partial_dates(queryset, field_name)
            .annotate(**{sort_key_name: _date_sort_key(field_name)})
            .filter(**{f'{sort_key_name}__{lookup}': bound})
        )

    def filter_birth_date_gte(self, queryset, name, value):
        """Filter creators whose birth date is on or after the bound."""
        del name
        return self._filter_partial_date(queryset, 'birth_date', value, 'gte')

    def filter_birth_date_lte(self, queryset, name, value):
        """Filter creators whose birth date is on or before the bound."""
        del name
        return self._filter_partial_date(queryset, 'birth_date', value, 'lte')

    def filter_death_date_gte(self, queryset, name, value):
        """Filter creators whose death date is on or after the bound."""
        del name
        return self._filter_partial_date(queryset, 'death_date', value, 'gte')

    def filter_death_date_lte(self, queryset, name, value):
        """Filter creators whose death date is on or before the bound."""
        del name
        return self._filter_partial_date(queryset, 'death_date', value, 'lte')
