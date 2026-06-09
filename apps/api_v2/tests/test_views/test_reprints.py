# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the reprint v2 endpoints."""

from decimal import Decimal

from django.urls import reverse
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.api_v2.views.reprints import ReprintViewSet
from apps.gcd.models import Reprint, Story, StoryType


def _create_story_type(name='Comic Story', sort_code=19):
    """Create or return a story type row for reprint tests."""
    story_type, _ = StoryType.objects.get_or_create(
        name=name,
        defaults={'sort_code': sort_code},
    )
    return story_type


def _create_issue(series, *, number, sort_code):
    """Create a minimal issue row for reprint view tests."""
    return series.issue_set.model.objects.create(
        number=number,
        title='',
        volume='',
        isbn='',
        valid_isbn='',
        variant_name='',
        barcode='',
        publication_date='',
        key_date='2024-01-01',
        on_sale_date='2024-01-08',
        sort_code=sort_code,
        indicia_frequency='',
        price='',
        editing='',
        notes='',
        indicia_printer_sourced_by='',
        series=series,
    )


def _create_story(issue, *, title, sequence_number):
    """Create a story row for view tests."""
    return Story.objects.create(
        title=title,
        feature='Feature Text',
        sequence_number=sequence_number,
        page_count=Decimal('10.000'),
        script='',
        pencils='',
        inks='',
        colors='',
        letters='',
        editing='',
        job_number='',
        genre='',
        characters='',
        synopsis='',
        reprint_notes='',
        notes='',
        issue=issue,
        type=_create_story_type(),
    )


def _create_reprint(origin, target, *, origin_issue=None, target_issue=None):
    """Create a reprint row for view tests."""
    return Reprint.objects.create(
        origin=origin,
        target=target,
        origin_issue=origin_issue or origin.issue,
        target_issue=target_issue or target.issue,
        notes='Translated and recolored.',
    )


def test_reprint_list_returns_paginated_results(api_client, issue):
    """The list endpoint is anon-readable and paginated."""
    target_issue = _create_issue(issue.series, number='2', sort_code=2)
    origin = _create_story(issue, title='Original Story', sequence_number=1)
    target = _create_story(
        target_issue,
        title='Target Story',
        sequence_number=1,
    )
    reprint = _create_reprint(origin, target)

    response = api_client.get(reverse('reprint-list'))

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['next'] is None
    assert response.data['previous'] is None
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['id'] == reprint.pk
    assert response.data['results'][0]['origin_story'] == {
        'id': origin.pk,
        'title': 'Original Story',
    }
    assert response.data['results'][0]['target_issue'] == {
        'id': target_issue.pk,
        'descriptor': target_issue.issue_descriptor,
        'series_name': target_issue.series.name,
    }


def test_reprint_list_queryset_uses_id_based_issue_ordering():
    """The list queryset avoids the costly related-issue default sort."""
    assert ReprintViewSet.queryset.query.order_by == (
        'origin_issue_id',
        'target_issue_id',
        'id',
    )


def test_reprint_list_queryset_uses_modified_ordering_for_delta_filters():
    """Modified delta requests switch to an index-friendly ordering."""
    view = ReprintViewSet()
    request = APIRequestFactory().get(
        '/api/v2/reprints/',
        {'modified__gt': '2025-01-01T00:00:00Z'},
    )
    view.request = Request(request)
    view.action = 'list'

    queryset = view.get_queryset()

    assert queryset.query.order_by == ('modified', 'id')


def test_reprint_list_skips_exact_count_for_modified_delta_filters():
    """Modified delta requests opt into no-count pagination."""
    view = ReprintViewSet()
    request = APIRequestFactory().get(
        '/api/v2/reprints/',
        {'modified__gt': '2025-01-01T00:00:00Z'},
    )

    assert view.should_skip_exact_count(Request(request)) is True


def test_reprint_detail_returns_expected_payload(api_client, issue):
    """The detail endpoint returns the reprint serializer payload."""
    target_issue = _create_issue(issue.series, number='2', sort_code=2)
    origin = _create_story(issue, title='Original Story', sequence_number=1)
    target = _create_story(
        target_issue,
        title='Target Story',
        sequence_number=1,
    )
    reprint = _create_reprint(origin, target)

    response = api_client.get(
        reverse('reprint-detail', kwargs={'pk': reprint.pk}),
    )

    assert response.status_code == 200
    assert response.data['id'] == reprint.pk
    assert response.data['origin_story'] == {
        'id': origin.pk,
        'title': 'Original Story',
    }
    assert response.data['origin_issue'] == {
        'id': issue.pk,
        'descriptor': issue.issue_descriptor,
        'series_name': issue.series.name,
    }
    assert response.data['target_story'] == {
        'id': target.pk,
        'title': 'Target Story',
    }
    assert response.data['target_issue'] == {
        'id': target_issue.pk,
        'descriptor': target_issue.issue_descriptor,
        'series_name': target_issue.series.name,
    }
    assert response.data['notes'] == 'Translated and recolored.'


def test_reprint_detail_handles_issue_level_null_story(api_client, issue):
    """Issue-level reprints with null stories still return 200."""
    target_issue = _create_issue(issue.series, number='2', sort_code=2)
    target = _create_story(
        target_issue,
        title='Target Story',
        sequence_number=1,
    )
    reprint = _create_reprint(
        None,
        target,
        origin_issue=issue,
        target_issue=target.issue,
    )

    response = api_client.get(
        reverse('reprint-detail', kwargs={'pk': reprint.pk}),
    )

    assert response.status_code == 200
    assert response.data['origin_story'] is None
    assert response.data['target_story'] == {
        'id': target.pk,
        'title': 'Target Story',
    }


def test_reprint_list_applies_filter_query_params(api_client, issue):
    """The list endpoint applies django-filter query params."""
    target_issue = _create_issue(issue.series, number='2', sort_code=2)
    origin = _create_story(issue, title='Original Story', sequence_number=1)
    target = _create_story(
        target_issue,
        title='Target Story',
        sequence_number=1,
    )
    other_target = _create_story(
        target_issue,
        title='Other Target Story',
        sequence_number=2,
    )
    matching = _create_reprint(origin, target)
    _create_reprint(origin, other_target)

    response = api_client.get(
        reverse('reprint-list'),
        {
            'origin_issue': str(issue.pk),
            'target_issue': str(target_issue.pk),
            'origin_story': str(origin.pk),
            'target_story': str(target.pk),
            'origin_issue__series': str(issue.series_id),
            'target_issue__series': str(target_issue.series_id),
        },
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == matching.pk


def test_reprint_list_returns_304_for_if_modified_since(
    authenticated_client,
    issue,
):
    """List responses support Last-Modified cache validation."""
    target_issue = _create_issue(issue.series, number='2', sort_code=2)
    origin = _create_story(issue, title='Original Story', sequence_number=1)
    target = _create_story(
        target_issue,
        title='Target Story',
        sequence_number=1,
    )
    _create_reprint(origin, target)

    response = authenticated_client.get(reverse('reprint-list'))

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('reprint-list'),
        HTTP_IF_MODIFIED_SINCE=response['Last-Modified'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''


def test_reprint_detail_returns_304_for_if_none_match(
    authenticated_client,
    issue,
):
    """Detail responses support ETag cache validation."""
    target_issue = _create_issue(issue.series, number='2', sort_code=2)
    origin = _create_story(issue, title='Original Story', sequence_number=1)
    target = _create_story(
        target_issue,
        title='Target Story',
        sequence_number=1,
    )
    reprint = _create_reprint(origin, target)

    response = authenticated_client.get(
        reverse('reprint-detail', kwargs={'pk': reprint.pk}),
    )

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('reprint-detail', kwargs={'pk': reprint.pk}),
        HTTP_IF_NONE_MATCH=response['ETag'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''
