# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the issue filter set."""

from datetime import timedelta

from django.utils import timezone

from apps.api_v2.filters.issues import IssueFilterSet
from apps.gcd.models import Issue


def _set_timestamps(obj, *, created, modified):
    """Persist explicit created/modified timestamps for filter tests."""
    Issue.objects.filter(pk=obj.pk).update(
        created=created,
        modified=modified,
    )
    obj.refresh_from_db()


def _create_issue(
    series,
    *,
    number,
    key_date,
    on_sale_date,
    isbn='',
    barcode='',
    variant_of=None,
):
    """Create a minimal issue row for filter tests."""
    return Issue.objects.create(
        number=number,
        title='',
        volume='',
        isbn=isbn,
        valid_isbn='',
        variant_name='',
        barcode=barcode,
        publication_date='',
        key_date=key_date,
        on_sale_date=on_sale_date,
        sort_code=int(number),
        indicia_frequency='',
        price='',
        editing='',
        notes='',
        indicia_printer_sourced_by='',
        series=series,
        variant_of=variant_of,
    )


def test_issue_filter_matches_series_number_isbn_and_barcode(
    series, publisher
):
    """Exact issue filters narrow list results correctly."""
    other_series = series.__class__.objects.create(
        name='Other Series',
        sort_name='Other Series',
        year_began=1991,
        publication_dates='1991 - present',
        notes='',
        tracking_notes='',
        country=series.country,
        language=series.language,
        publisher=publisher,
    )
    matching = _create_issue(
        series,
        number='1',
        key_date='2024-01-01',
        on_sale_date='2024-01-08',
        isbn='1111111111111',
        barcode='12345',
    )
    _create_issue(
        other_series,
        number='1',
        key_date='2024-01-01',
        on_sale_date='2024-01-08',
        isbn='1111111111111',
        barcode='12345',
    )
    _create_issue(
        series,
        number='2',
        key_date='2024-01-01',
        on_sale_date='2024-01-08',
        isbn='2222222222222',
        barcode='67890',
    )

    qs = IssueFilterSet(
        {
            'series': str(series.pk),
            'number': '1',
            'isbn': '1111111111111',
            'barcode': '12345',
        },
        queryset=Issue.objects.all(),
    ).qs

    assert list(qs) == [matching]


def test_issue_filter_matches_key_date_and_on_sale_date_ranges(series):
    """Date-like char filters support range-style issue queries."""
    earlier = _create_issue(
        series,
        number='1',
        key_date='2024-01-01',
        on_sale_date='2024-01-08',
    )
    later = _create_issue(
        series,
        number='2',
        key_date='2024-03-01',
        on_sale_date='2024-03-08',
    )

    qs = IssueFilterSet(
        {
            'key_date__gte': '2024-02-01',
            'on_sale_date__lte': '2024-03-31',
        },
        queryset=Issue.objects.all(),
    ).qs

    assert list(qs) == [later]
    assert earlier not in qs


def test_issue_filter_matches_variant_presence(series):
    """Variant filtering supports base-only and variant-only queries."""
    base = _create_issue(
        series,
        number='1',
        key_date='2024-01-01',
        on_sale_date='2024-01-08',
    )
    variant = _create_issue(
        series,
        number='2',
        key_date='2024-01-02',
        on_sale_date='2024-01-09',
        variant_of=base,
    )

    variant_qs = IssueFilterSet(
        {'variant_of': 'true'},
        queryset=Issue.objects.all(),
    ).qs
    base_qs = IssueFilterSet(
        {'variant_of': 'false'},
        queryset=Issue.objects.all(),
    ).qs

    assert list(variant_qs) == [variant]
    assert list(base_qs) == [base]


def test_issue_filter_matches_modified_and_created_ranges(series):
    """Created/modified range filters support sync-style issue queries."""
    older = _create_issue(
        series,
        number='1',
        key_date='2024-01-01',
        on_sale_date='2024-01-08',
    )
    newer = _create_issue(
        series,
        number='2',
        key_date='2024-02-01',
        on_sale_date='2024-02-08',
    )
    now = timezone.now()
    _set_timestamps(
        older,
        created=now - timedelta(days=3),
        modified=now - timedelta(days=2),
    )
    _set_timestamps(
        newer,
        created=now - timedelta(hours=2),
        modified=now - timedelta(hours=1),
    )

    modified_qs = IssueFilterSet(
        {'modified__gt': (now - timedelta(days=1)).isoformat()},
        queryset=Issue.objects.all(),
    ).qs
    created_qs = IssueFilterSet(
        {'created__lte': (now - timedelta(days=1)).isoformat()},
        queryset=Issue.objects.all(),
    ).qs

    assert list(modified_qs) == [newer]
    assert list(created_qs) == [older]
