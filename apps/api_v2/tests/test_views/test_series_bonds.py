# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the Series Bond v2 endpoints."""

from django.urls import reverse

from apps.gcd.models import Issue, Series, SeriesBond, SeriesBondType


def _create_series(series, *, name, year_began):
    """Create a Series sharing the fixture Series' reference data."""
    return Series.objects.create(
        name=name,
        sort_name=name,
        year_began=year_began,
        publication_dates=f'{year_began} - present',
        notes='',
        tracking_notes='',
        country=series.country,
        language=series.language,
        publisher=series.publisher,
    )


def _create_issue(series, *, number, sort_code):
    """Create a minimal Issue for Series Bond view tests."""
    return Issue.objects.create(
        number=number,
        title='',
        volume='',
        isbn='',
        valid_isbn='',
        variant_name='',
        barcode='',
        publication_date='',
        key_date='',
        on_sale_date='',
        sort_code=sort_code,
        indicia_frequency='',
        price='',
        editing='',
        notes='',
        indicia_printer_sourced_by='',
        series=series,
    )


def _create_bond(series, issue, *, reserved=False):
    """Create a complete Series Bond view fixture."""
    target = _create_series(series, name='Target Series', year_began=2000)
    target_issue = _create_issue(target, number='1', sort_code=1)
    bond_type = SeriesBondType.objects.create(
        name='continues',
        description='Continues at',
        notes='',
    )
    bond = SeriesBond.objects.create(
        origin=series,
        origin_issue=issue,
        target=target,
        target_issue=target_issue,
        bond_type=bond_type,
        notes='The numbering continues in the target Series.',
        reserved=reserved,
    )
    return bond, target, target_issue, bond_type


def test_series_bond_list_returns_paginated_results(api_client, series, issue):
    """The list endpoint is anonymous, paginated, and trimmed."""
    bond, target, _target_issue, _bond_type = _create_bond(series, issue)

    response = api_client.get(reverse('series-bond-list'))

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['next'] is None
    assert response.data['previous'] is None
    assert len(response.data['results']) == 1
    result = response.data['results'][0]
    assert result['id'] == bond.pk
    assert result['origin']['id'] == series.pk
    assert result['target']['id'] == target.pk
    assert 'notes' not in result
    assert 'reserved' not in result


def test_series_bond_detail_returns_expected_payload(
    authenticated_client,
    series,
    issue,
):
    """The detail endpoint returns complete Series Bond data."""
    bond, target, target_issue, bond_type = _create_bond(series, issue)

    response = authenticated_client.get(
        reverse('series-bond-detail', kwargs={'pk': bond.pk}),
    )

    assert response.status_code == 200
    assert response.data['id'] == bond.pk
    assert response.data['origin'] == {
        'id': series.pk,
        'name': 'Test Series',
        'year_began': 1990,
    }
    assert response.data['target'] == {
        'id': target.pk,
        'name': 'Target Series',
        'year_began': 2000,
    }
    assert response.data['target_issue'] == {
        'id': target_issue.pk,
        'descriptor': target_issue.issue_descriptor,
    }
    assert response.data['bond_type'] == {
        'id': bond_type.pk,
        'name': 'continues',
        'description': 'Continues at',
    }
    assert response.data['notes'] == (
        'The numbering continues in the target Series.'
    )
    assert 'reserved' not in response.data


def test_series_bond_list_applies_filter_query_params(
    api_client,
    series,
    issue,
):
    """The list endpoint applies the complete relationship contract."""
    bond, target, target_issue, bond_type = _create_bond(series, issue)

    response = api_client.get(
        reverse('series-bond-list'),
        {
            'origin': str(series.pk),
            'origin_issue': str(issue.pk),
            'target': str(target.pk),
            'target_issue': str(target_issue.pk),
            'bond_type': str(bond_type.pk),
        },
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == bond.pk


def test_series_bond_list_returns_304_for_if_modified_since(
    authenticated_client,
    series,
    issue,
):
    """List responses support Last-Modified cache validation."""
    _create_bond(series, issue)

    response = authenticated_client.get(reverse('series-bond-list'))

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('series-bond-list'),
        HTTP_IF_MODIFIED_SINCE=response['Last-Modified'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''


def test_series_bond_detail_returns_304_for_if_none_match(
    authenticated_client,
    series,
    issue,
):
    """Detail responses support ETag cache validation."""
    bond, _target, _target_issue, _bond_type = _create_bond(series, issue)

    response = authenticated_client.get(
        reverse('series-bond-detail', kwargs={'pk': bond.pk}),
    )

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('series-bond-detail', kwargs={'pk': bond.pk}),
        HTTP_IF_NONE_MATCH=response['ETag'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''


def test_series_bond_reserved_state_is_never_exposed(
    api_client,
    series,
    issue,
):
    """Internal reservation state remains absent from all API payloads."""
    bond, _target, _target_issue, _bond_type = _create_bond(
        series,
        issue,
        reserved=True,
    )

    list_response = api_client.get(reverse('series-bond-list'))
    detail_response = api_client.get(
        reverse('series-bond-detail', kwargs={'pk': bond.pk}),
    )

    assert list_response.status_code == 200
    assert 'reserved' not in list_response.data['results'][0]
    assert detail_response.status_code == 200
    assert 'reserved' not in detail_response.data
