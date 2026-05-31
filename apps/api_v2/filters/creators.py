# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 creator endpoints."""

import calendar

import django_filters
from django.core.exceptions import ValidationError
from django.db.models import (
    Case,
    CharField,
    F,
    Q,
    Value,
    When,
)
from django.db.models.functions import Concat, Replace, Right

from apps.api_v2.filters.common import (
    TIMESTAMP_FILTER_FIELDS,
    TimestampFilterSet,
)
from apps.gcd.models import Creator
from apps.stddata.forms import DateForm

PARTIAL_DATE_ERROR = (
    'Enter a valid partial date in YYYY, YYYY-MM, or YYYY-MM-DD format.'
)
NUMERIC_COMPONENT_RE = r'^\d+$'
PARTIAL_YEAR_RE = r'^[0-9?]+$'
PARTIAL_YEAR_HAS_DIGIT_RE = r'.*\d.*'


def _parse_partial_date(value):
    """Return a parsed ``Date`` instance for a compact partial-date string."""
    form = DateForm(data={'date': value})
    if not form.is_valid() or form.cleaned_data['date'] is None:
        raise ValidationError(PARTIAL_DATE_ERROR)
    return form.instance


def validate_partial_date(value):
    """Validate a creator partial-date filter value."""
    _parse_partial_date(value)


def _date_component_expr(field_name, component, *, empty_value, replacement):
    """Return a zero-padded string expression for one ``Date`` component."""
    width = 4 if component == 'year' else 2
    raw_value = Right(
        Concat(
            Value('0' * width),
            Replace(
                F(f'{field_name}__{component}'),
                Value('?'),
                Value(replacement),
            ),
        ),
        width,
    )
    return Case(
        When(**{f'{field_name}__{component}': ''}, then=Value(empty_value)),
        default=raw_value,
        output_field=CharField(),
    )


def _date_bound_expr(field_name, *, replacement, month_empty, day_empty):
    """Return an ISO-style date bound for comparing stored partial dates."""
    year_expr = _date_component_expr(
        field_name,
        'year',
        empty_value='0000',
        replacement=replacement,
    )
    month_expr = _date_component_expr(
        field_name,
        'month',
        empty_value=month_empty,
        replacement=replacement,
    )
    day_expr = _date_component_expr(
        field_name,
        'day',
        empty_value=day_empty,
        replacement=replacement,
    )
    return Concat(
        year_expr,
        Value('-'),
        month_expr,
        Value('-'),
        day_expr,
        output_field=CharField(),
    )


def _stored_lower_bound_expr(field_name):
    """Return the earliest possible date for a stored partial date."""
    return _date_bound_expr(
        field_name,
        replacement='0',
        month_empty='01',
        day_empty='01',
    )


def _stored_upper_bound_expr(field_name):
    """Return the latest possible date for a stored partial date."""
    return _date_bound_expr(
        field_name,
        replacement='9',
        month_empty='12',
        day_empty='31',
    )


def _normalize_year_bound(value, replacement):
    """Return a four-digit year bound for a parsed partial-date component."""
    if not value:
        return '0000'
    return value.replace('?', replacement).zfill(4)


def _normalize_component_bound(value, *, empty_value):
    """Return a two-digit month/day bound for a parsed component."""
    if not value:
        return empty_value
    return value.zfill(2)


def _lower_bound(date_obj):
    """Return the inclusive lower-bound ISO date for a partial date."""
    return (
        f'{_normalize_year_bound(date_obj.year, "0")}-'
        f'{_normalize_component_bound(date_obj.month, empty_value="01")}-'
        f'{_normalize_component_bound(date_obj.day, empty_value="01")}'
    )


def _upper_bound(date_obj):
    """Return the inclusive upper-bound ISO date for a partial date."""
    year = _normalize_year_bound(date_obj.year, '9')
    if not date_obj.month:
        return f'{year}-12-31'
    month = _normalize_component_bound(date_obj.month, empty_value='12')
    if not date_obj.day:
        if '?' in date_obj.year:
            last_day = 31
        else:
            last_day = calendar.monthrange(int(year), int(month))[1]
        return f'{year}-{month}-{last_day:02d}'
    day = _normalize_component_bound(date_obj.day, empty_value='31')
    return f'{year}-{month}-{day}'


def _filter_comparable_partial_dates(queryset, field_name):
    """Restrict filters to partial dates that can satisfy range queries."""
    return (
        queryset.filter(**{f'{field_name}__isnull': False})
        .filter(**{f'{field_name}__year__regex': PARTIAL_YEAR_RE})
        .filter(**{f'{field_name}__year__regex': PARTIAL_YEAR_HAS_DIGIT_RE})
        .filter(
            Q(**{f'{field_name}__month': ''})
            | Q(**{f'{field_name}__month__regex': NUMERIC_COMPONENT_RE})
        )
        .filter(
            Q(**{f'{field_name}__day': ''})
            | Q(**{f'{field_name}__day__regex': NUMERIC_COMPONENT_RE})
        )
    )


class CreatorFilterSet(TimestampFilterSet):
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
        ) + TIMESTAMP_FILTER_FIELDS

    def _filter_partial_date(self, queryset, field_name, value, lookup):
        """Filter a related ``Date`` field against a compact range bound."""
        parsed = _parse_partial_date(value)
        bound = (
            _lower_bound(parsed) if lookup == 'gte' else _upper_bound(parsed)
        )
        bound_expr = (
            _stored_lower_bound_expr(field_name)
            if lookup == 'gte'
            else _stored_upper_bound_expr(field_name)
        )
        bound_name = f'_{field_name}_{lookup}_bound'
        return (
            _filter_comparable_partial_dates(queryset, field_name)
            .annotate(**{bound_name: bound_expr})
            .filter(**{f'{bound_name}__{lookup}': bound})
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
