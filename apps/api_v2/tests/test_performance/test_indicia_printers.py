# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Performance tests for indicia printer endpoints."""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import IndiciaPrinter, Printer


def _create_printer(country):
    """Create a parent Printer for performance tests."""
    return Printer.objects.create(
        name='Test Printer',
        year_began=1950,
        notes='',
        country=country,
    )


def _create_indicia_printer(*, printer, country, name):
    """Create a minimal indicia printer row for performance tests."""
    return IndiciaPrinter.objects.create(
        name=name,
        year_began=1950,
        notes='',
        parent=printer,
        country=country,
    )


def test_indicia_printer_list_query_count(api_client, country):
    """The indicia printer list stays on its query budget."""
    printer = _create_printer(country)
    _create_indicia_printer(
        printer=printer,
        country=country,
        name='Alpha Plant',
    )
    _create_indicia_printer(
        printer=printer,
        country=country,
        name='Beta Plant',
    )

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(reverse('indicia-printer-list'))

    assert response.status_code == 200
    assert len(context) == 3


def test_indicia_printer_detail_query_count(api_client, country):
    """The detail endpoint avoids lazy-loading regressions."""
    printer = _create_printer(country)
    indicia_printer = _create_indicia_printer(
        printer=printer,
        country=country,
        name='Detail Plant',
    )
    indicia_printer.keywords.add('detail')

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(
            reverse(
                'indicia-printer-detail',
                kwargs={'pk': indicia_printer.pk},
            ),
        )

    assert response.status_code == 200
    assert len(context) == 3
