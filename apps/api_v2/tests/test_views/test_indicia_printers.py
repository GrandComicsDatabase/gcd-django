# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the indicia printer v2 endpoints."""

import pytest
from django.urls import reverse

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
    """Return a second country for indicia printer view tests."""
    obj, _ = Country.objects.get_or_create(
        code='yy',
        defaults={'name': 'Other Country'},
    )
    return obj


def _create_indicia_printer(
    *,
    printer,
    country,
    name='Test Indicia Printer',
    year_began=1960,
    year_ended=None,
    deleted=False,
):
    """Create a minimal indicia printer row for view tests."""
    return IndiciaPrinter.objects.create(
        name=name,
        year_began=year_began,
        year_ended=year_ended,
        notes='',
        parent=printer,
        country=country,
        deleted=deleted,
    )


def test_indicia_printer_list_returns_paginated_results(
    api_client,
    printer,
    country,
):
    """The list endpoint is anonymous, paginated, and trimmed."""
    indicia_printer = _create_indicia_printer(
        printer=printer,
        country=country,
    )

    response = api_client.get(reverse('indicia-printer-list'))

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['next'] is None
    assert response.data['previous'] is None
    assert len(response.data['results']) == 1
    result = response.data['results'][0]
    assert result['id'] == indicia_printer.pk
    assert result['parent'] == {
        'id': printer.pk,
        'name': printer.name,
    }
    assert result['country'] == country.code
    assert 'notes' not in result
    assert 'keywords' not in result


def test_indicia_printer_detail_returns_expected_payload(
    authenticated_client,
    printer,
    country,
):
    """The detail endpoint returns descriptive and uncertainty fields."""
    indicia_printer = _create_indicia_printer(
        printer=printer,
        country=country,
    )
    indicia_printer.year_began_uncertain = True
    indicia_printer.year_overall_began = 1955
    indicia_printer.year_overall_ended = 1985
    indicia_printer.year_overall_ended_uncertain = True
    indicia_printer.url = 'https://example.com/plant/'
    indicia_printer.notes = 'Detail notes'
    indicia_printer.issue_count = 21
    indicia_printer.save()
    indicia_printer.keywords.add('alpha', 'beta')

    response = authenticated_client.get(
        reverse(
            'indicia-printer-detail',
            kwargs={'pk': indicia_printer.pk},
        ),
    )

    assert response.status_code == 200
    assert response.data['id'] == indicia_printer.pk
    assert response.data['parent'] == {
        'id': printer.pk,
        'name': printer.name,
    }
    assert response.data['country'] == country.code
    assert response.data['year_began_uncertain'] is True
    assert response.data['year_overall_began'] == 1955
    assert response.data['year_overall_ended'] == 1985
    assert response.data['year_overall_ended_uncertain'] is True
    assert response.data['url'] == 'https://example.com/plant/'
    assert response.data['notes'] == 'Detail notes'
    assert response.data['issue_count'] == 21
    assert set(response.data['keywords']) == {'alpha', 'beta'}


def test_indicia_printer_list_applies_filter_query_params(
    authenticated_client,
    printer,
    country,
    other_country,
):
    """The list endpoint applies the complete filter contract."""
    other_parent = Printer.objects.create(
        name='Other Printer',
        year_began=1940,
        notes='',
        country=country,
    )
    matching = _create_indicia_printer(
        printer=printer,
        country=country,
        name='Quebecor Printing',
        year_began=1960,
        year_ended=1980,
    )
    _create_indicia_printer(
        printer=other_parent,
        country=other_country,
        name='Different Plant',
        year_began=1940,
    )

    response = authenticated_client.get(
        reverse('indicia-printer-list'),
        {
            'name': 'quebecor',
            'parent': str(printer.pk),
            'country': country.code,
            'year_began': '1960',
            'year_ended': '1980',
        },
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == matching.pk


def test_indicia_printer_endpoints_hide_soft_deleted_records(
    api_client,
    printer,
    country,
):
    """Soft-deleted rows disappear from list and detail responses."""
    visible = _create_indicia_printer(
        printer=printer,
        country=country,
        name='Visible Plant',
    )
    deleted = _create_indicia_printer(
        printer=printer,
        country=country,
        name='Deleted Plant',
        deleted=True,
    )

    list_response = api_client.get(reverse('indicia-printer-list'))
    detail_response = api_client.get(
        reverse(
            'indicia-printer-detail',
            kwargs={'pk': deleted.pk},
        ),
    )

    assert list_response.status_code == 200
    assert list_response.data['count'] == 1
    assert list_response.data['results'][0]['id'] == visible.pk
    assert detail_response.status_code == 404


def test_indicia_printer_list_returns_304_for_if_modified_since(
    authenticated_client,
    printer,
    country,
):
    """List responses support Last-Modified cache validation."""
    _create_indicia_printer(
        printer=printer,
        country=country,
    )

    response = authenticated_client.get(reverse('indicia-printer-list'))

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('indicia-printer-list'),
        HTTP_IF_MODIFIED_SINCE=response['Last-Modified'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''


def test_indicia_printer_detail_returns_304_for_if_none_match(
    authenticated_client,
    printer,
    country,
):
    """Detail responses support ETag cache validation."""
    indicia_printer = _create_indicia_printer(
        printer=printer,
        country=country,
    )

    response = authenticated_client.get(
        reverse(
            'indicia-printer-detail',
            kwargs={'pk': indicia_printer.pk},
        ),
    )

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse(
            'indicia-printer-detail',
            kwargs={'pk': indicia_printer.pk},
        ),
        HTTP_IF_NONE_MATCH=response['ETag'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''
