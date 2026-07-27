# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the indicia printer serializers."""

from apps.api_v2.serializers.indicia_printers import (
    IndiciaPrinterListSerializer,
    IndiciaPrinterSerializer,
)
from apps.gcd.models import IndiciaPrinter, Printer


def _create_printer(country):
    """Create a parent Printer for serializer tests."""
    return Printer.objects.create(
        name='Test Printer',
        year_began=1950,
        notes='',
        country=country,
    )


def _create_indicia_printer(printer, country):
    """Create an indicia printer with complete contract data."""
    indicia_printer = IndiciaPrinter.objects.create(
        name='Test Indicia Printer',
        year_began=1960,
        year_ended=1980,
        year_began_uncertain=True,
        year_ended_uncertain=False,
        year_overall_began=1955,
        year_overall_ended=1985,
        year_overall_began_uncertain=False,
        year_overall_ended_uncertain=True,
        notes='Indicia printer notes',
        url='https://example.com/indicia-printer/',
        parent=printer,
        country=country,
        issue_count=42,
    )
    indicia_printer.keywords.add('alpha', 'beta')
    return indicia_printer


def test_indicia_printer_list_serializer_exposes_trimmed_contract(
    country,
):
    """List rows include identity, browse, count, and timestamp fields."""
    printer = _create_printer(country)
    indicia_printer = _create_indicia_printer(printer, country)

    data = IndiciaPrinterListSerializer(indicia_printer).data

    assert set(data) == {
        'id',
        'name',
        'parent',
        'country',
        'year_began',
        'year_ended',
        'issue_count',
        'created',
        'modified',
    }
    assert data['id'] == indicia_printer.pk
    assert data['name'] == indicia_printer.name
    assert data['parent'] == {
        'id': printer.pk,
        'name': printer.name,
    }
    assert data['country'] == country.code
    assert data['year_began'] == 1960
    assert data['year_ended'] == 1980
    assert data['issue_count'] == 42
    assert data['created']
    assert data['modified']


def test_indicia_printer_detail_serializer_exposes_full_contract(country):
    """Detail rows add uncertainty, overall-year, and descriptive fields."""
    printer = _create_printer(country)
    indicia_printer = _create_indicia_printer(printer, country)

    data = IndiciaPrinterSerializer(indicia_printer).data

    assert set(data) == {
        'id',
        'name',
        'parent',
        'country',
        'year_began',
        'year_ended',
        'issue_count',
        'created',
        'modified',
        'year_began_uncertain',
        'year_ended_uncertain',
        'year_overall_began',
        'year_overall_ended',
        'year_overall_began_uncertain',
        'year_overall_ended_uncertain',
        'url',
        'notes',
        'keywords',
    }
    assert data['parent'] == {
        'id': printer.pk,
        'name': printer.name,
    }
    assert data['country'] == country.code
    assert data['year_began_uncertain'] is True
    assert data['year_ended_uncertain'] is False
    assert data['year_overall_began'] == 1955
    assert data['year_overall_ended'] == 1985
    assert data['year_overall_began_uncertain'] is False
    assert data['year_overall_ended_uncertain'] is True
    assert data['url'] == 'https://example.com/indicia-printer/'
    assert data['notes'] == 'Indicia printer notes'
    assert set(data['keywords']) == {'alpha', 'beta'}
