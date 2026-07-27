# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for Award and paginated recipient endpoints."""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.gcd.models import Award, Creator, ReceivedAward

pytestmark = pytest.mark.django_db


def _create_creator(name, *, deleted=False):
    """Create a minimal Creator recipient."""
    return Creator.objects.create(
        gcd_official_name=name,
        sort_name=name,
        disambiguation='',
        birth_province='',
        birth_city='',
        death_province='',
        death_city='',
        bio='',
        notes='',
        deleted=deleted,
    )


def _create_received_award(
    *,
    award,
    recipient,
    name='Best Work',
    year=1989,
    deleted=False,
):
    """Create a received Award for a generic recipient."""
    return ReceivedAward.objects.create(
        content_type=ContentType.objects.get_for_model(recipient),
        object_id=recipient.pk,
        award=award,
        award_name=name,
        award_year=year,
        notes='',
        deleted=deleted,
    )


def test_award_list_and_detail_return_expected_contract(api_client):
    """Award routes are anonymous, paginated, and list/detail aware."""
    award = Award.objects.create(
        name='Eisner Awards',
        notes='Award notes',
    )

    list_response = api_client.get(reverse('award-list'))
    detail_response = api_client.get(
        reverse('award-detail', kwargs={'pk': award.pk}),
    )

    assert list_response.status_code == 200
    assert list_response.data['count'] == 1
    assert list_response.data['results'][0]['id'] == award.pk
    assert 'notes' not in list_response.data['results'][0]
    assert detail_response.status_code == 200
    assert detail_response.data['id'] == award.pk
    assert detail_response.data['notes'] == 'Award notes'
    assert 'recipients' not in detail_response.data


def test_award_list_applies_name_filter(api_client):
    """Award list query parameters use the public filter contract."""
    matching = Award.objects.create(name='Eisner Awards', notes='')
    Award.objects.create(name='Harvey Awards', notes='')

    response = api_client.get(reverse('award-list'), {'name': 'eisner'})

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == matching.pk


def test_award_endpoints_hide_soft_deleted_awards(api_client):
    """Soft-deleted Awards disappear from list and detail routes."""
    Award.objects.create(name='Visible Award', notes='')
    deleted = Award.objects.create(
        name='Deleted Award',
        notes='',
        deleted=True,
    )

    list_response = api_client.get(reverse('award-list'))
    detail_response = api_client.get(
        reverse('award-detail', kwargs={'pk': deleted.pk}),
    )

    assert list_response.status_code == 200
    assert list_response.data['count'] == 1
    assert detail_response.status_code == 404


def test_award_recipients_are_paginated_and_hide_deleted_rows(api_client):
    """The recipient action returns a standard page of active rows."""
    award = Award.objects.create(name='Eisner Awards', notes='')
    creator = _create_creator('Jane Doe')
    first = _create_received_award(
        award=award,
        recipient=creator,
        name='Best Creator',
        year=1989,
    )
    _create_received_award(
        award=award,
        recipient=creator,
        name='Best Writer',
        year=1990,
    )
    _create_received_award(
        award=award,
        recipient=creator,
        name='Deleted Award',
        year=1991,
        deleted=True,
    )
    _create_received_award(
        award=award,
        recipient=_create_creator('Deleted Creator', deleted=True),
        name='Deleted Recipient',
        year=1992,
    )

    response = api_client.get(
        reverse('award-recipients', kwargs={'pk': award.pk}),
        {'page_size': 1},
    )

    assert response.status_code == 200
    assert response.data['count'] == 2
    assert response.data['next'] is not None
    assert response.data['previous'] is None
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['id'] == first.pk
    assert response.data['results'][0]['recipient_type'] == 'creator'
    assert response.data['results'][0]['recipient']['id'] == creator.pk


def test_award_recipients_apply_type_and_year_filters(api_client, issue):
    """Recipient filters combine type and exact Award year."""
    award = Award.objects.create(name='Eisner Awards', notes='')
    creator = _create_creator('Jane Doe')
    matching = _create_received_award(
        award=award,
        recipient=creator,
        name='Best Creator',
        year=1989,
    )
    _create_received_award(
        award=award,
        recipient=creator,
        name='Wrong Year',
        year=1990,
    )
    _create_received_award(
        award=award,
        recipient=issue,
        name='Wrong Type',
        year=1989,
    )

    response = api_client.get(
        reverse('award-recipients', kwargs={'pk': award.pk}),
        {
            'recipient_type': 'creator',
            'award_year': '1989',
        },
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == matching.pk


def test_award_recipients_reject_unknown_recipient_type(api_client):
    """Unsupported recipient types return a filter validation error."""
    award = Award.objects.create(name='Eisner Awards', notes='')

    response = api_client.get(
        reverse('award-recipients', kwargs={'pk': award.pk}),
        {'recipient_type': 'publisher'},
    )

    assert response.status_code == 400


def test_award_and_recipient_routes_support_conditional_requests(api_client):
    """Award roots and recipient pages expose independent validators."""
    award = Award.objects.create(name='Eisner Awards', notes='')
    recipient = _create_received_award(
        award=award,
        recipient=_create_creator('Jane Doe'),
    )

    list_response = api_client.get(reverse('award-list'))
    recipient_response = api_client.get(
        reverse('award-recipients', kwargs={'pk': award.pk}),
    )

    assert list_response.status_code == 200
    assert 'ETag' in list_response
    assert 'Last-Modified' in list_response
    assert recipient_response.status_code == 200
    assert recipient_response.data['results'][0]['id'] == recipient.pk
    assert 'ETag' in recipient_response
    assert 'Last-Modified' in recipient_response

    cached_list = api_client.get(
        reverse('award-list'),
        HTTP_IF_NONE_MATCH=list_response['ETag'],
    )
    cached_recipients = api_client.get(
        reverse('award-recipients', kwargs={'pk': award.pk}),
        HTTP_IF_NONE_MATCH=recipient_response['ETag'],
    )

    assert cached_list.status_code == 304
    assert cached_recipients.status_code == 304


def test_empty_award_recipient_page_supports_etag(api_client):
    """Awards without recipients still expose a stable page validator."""
    award = Award.objects.create(name='Empty Award', notes='')

    response = api_client.get(
        reverse('award-recipients', kwargs={'pk': award.pk}),
    )

    assert response.status_code == 200
    assert response.data['count'] == 0
    assert response.data['results'] == []
    assert 'ETag' in response

    cached_response = api_client.get(
        reverse('award-recipients', kwargs={'pk': award.pk}),
        HTTP_IF_NONE_MATCH=response['ETag'],
    )

    assert cached_response.status_code == 304
