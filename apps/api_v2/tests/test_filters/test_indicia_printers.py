# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the indicia printer filter set."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.api_v2.filters.indicia_printers import IndiciaPrinterFilterSet
from apps.gcd.models import IndiciaPrinter, Printer
from apps.stddata.models import Country


@pytest.fixture
def printer(db, country):
    """Return a saved Printer tied to the shared country."""
    return Printer.objects.create(
        name='Test Printer',
        year_began=1950,
        notes='',
        country=country,
    )


@pytest.fixture
def other_country(db):
    """Return a second country for indicia printer filter tests."""
    obj, _ = Country.objects.get_or_create(
        code='yy',
        defaults={'name': 'Other Country'},
    )
    return obj


def _create_indicia_printer(
    *,
    printer,
    country,
    name,
    year_began=1950,
    year_ended=None,
):
    """Create a minimal indicia printer row for filter tests."""
    return IndiciaPrinter.objects.create(
        name=name,
        year_began=year_began,
        year_ended=year_ended,
        notes='',
        parent=printer,
        country=country,
    )


def _set_timestamps(obj, *, created, modified):
    """Persist explicit created/modified timestamps for filter tests."""
    IndiciaPrinter.objects.filter(pk=obj.pk).update(
        created=created,
        modified=modified,
    )
    obj.refresh_from_db()


def test_indicia_printer_filter_matches_name_icontains(printer, country):
    """The name filter uses case-insensitive containment."""
    matching = _create_indicia_printer(
        printer=printer,
        country=country,
        name='Quebecor Printing',
    )
    _create_indicia_printer(
        printer=printer,
        country=country,
        name='World Color Press',
    )

    queryset = IndiciaPrinterFilterSet(
        {'name': 'quebecor'},
        queryset=IndiciaPrinter.objects.all(),
    ).qs

    assert list(queryset) == [matching]


def test_indicia_printer_filter_matches_exact_fields(
    printer,
    country,
    other_country,
):
    """Parent, country, and year filters narrow results correctly."""
    other_parent = Printer.objects.create(
        name='Other Printer',
        year_began=1940,
        notes='',
        country=country,
    )
    matching = _create_indicia_printer(
        printer=printer,
        country=country,
        name='Matching Plant',
        year_began=1960,
        year_ended=1980,
    )
    _create_indicia_printer(
        printer=other_parent,
        country=country,
        name='Wrong Parent',
        year_began=1960,
        year_ended=1980,
    )
    _create_indicia_printer(
        printer=printer,
        country=other_country,
        name='Wrong Country',
        year_began=1960,
        year_ended=1980,
    )
    _create_indicia_printer(
        printer=printer,
        country=country,
        name='Wrong Year',
        year_began=1961,
        year_ended=1980,
    )

    queryset = IndiciaPrinterFilterSet(
        {
            'parent': str(printer.pk),
            'country': country.code,
            'year_began': '1960',
            'year_ended': '1980',
        },
        queryset=IndiciaPrinter.objects.all(),
    ).qs

    assert list(queryset) == [matching]


def test_indicia_printer_filter_matches_modified_range(printer, country):
    """Modified range filters support delta-style sync queries."""
    older = _create_indicia_printer(
        printer=printer,
        country=country,
        name='Older Plant',
    )
    newer = _create_indicia_printer(
        printer=printer,
        country=country,
        name='Newer Plant',
    )
    now = timezone.now()
    _set_timestamps(
        older,
        created=now - timedelta(days=3),
        modified=now - timedelta(days=2),
    )
    _set_timestamps(
        newer,
        created=now - timedelta(days=1),
        modified=now - timedelta(hours=1),
    )

    queryset = IndiciaPrinterFilterSet(
        {'modified__gt': (now - timedelta(days=1)).isoformat()},
        queryset=IndiciaPrinter.objects.all(),
    ).qs

    assert list(queryset) == [newer]


def test_indicia_printer_filter_matches_created_range(printer, country):
    """Created range filters support bounded indicia printer queries."""
    older = _create_indicia_printer(
        printer=printer,
        country=country,
        name='Older Plant',
    )
    newer = _create_indicia_printer(
        printer=printer,
        country=country,
        name='Newer Plant',
    )
    now = timezone.now()
    older_created = now - timedelta(days=3)
    newer_created = now - timedelta(hours=1)
    _set_timestamps(
        older,
        created=older_created,
        modified=older_created,
    )
    _set_timestamps(
        newer,
        created=newer_created,
        modified=newer_created,
    )

    queryset = IndiciaPrinterFilterSet(
        {'created__lte': (now - timedelta(days=1)).isoformat()},
        queryset=IndiciaPrinter.objects.all(),
    ).qs

    assert list(queryset) == [older]
