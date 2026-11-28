# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for Award and paginated recipient endpoints."""

import json
import re
from datetime import UTC, datetime

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.api_v2.filters.common import TIMESTAMP_FILTER_FIELDS
from apps.api_v2.serializers.awards import AwardRecipientSerializer
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


def _filter_form(response):
    """Return the body and the field names of the Filters modal form."""
    content = response.content.decode()
    modal = content.split('id="filtersModal"', 1)[1]
    body = modal.split('<form', 1)[1].split('</form>', 1)[0]
    names = [
        name
        for name in re.findall(r'name="([^"]*)"', body)
        if name and name != 'csrfmiddlewaretoken'
    ]
    return body, names


def test_award_list_and_detail_return_expected_contract(api_client):
    """Award routes are anonymous, paginated, and list/detail aware."""
    award = Award.objects.create(
        name='Eisner Awards',
        notes='Award notes',
    )

    list_response = api_client.get(reverse('api-v2-award-list'))
    detail_response = api_client.get(
        reverse('api-v2-award-detail', kwargs={'pk': award.pk}),
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

    response = api_client.get(reverse('api-v2-award-list'), {'name': 'eisner'})

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

    list_response = api_client.get(reverse('api-v2-award-list'))
    detail_response = api_client.get(
        reverse('api-v2-award-detail', kwargs={'pk': deleted.pk}),
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
        reverse('api-v2-award-recipients', kwargs={'pk': award.pk}),
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


def test_award_recipient_serializer_receives_view_context(
    api_client,
    monkeypatch,
):
    """The recipient action uses DRF's context-aware serializer factory."""
    award = Award.objects.create(name='Eisner Awards', notes='')
    _create_received_award(
        award=award,
        recipient=_create_creator('Jane Doe'),
    )
    original = AwardRecipientSerializer.to_representation

    def assert_view_context(serializer, instance):
        assert 'request' in serializer.context
        assert 'view' in serializer.context
        return original(serializer, instance)

    monkeypatch.setattr(
        AwardRecipientSerializer,
        'to_representation',
        assert_view_context,
    )

    response = api_client.get(
        reverse('api-v2-award-recipients', kwargs={'pk': award.pk}),
    )

    assert response.status_code == 200


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
        reverse('api-v2-award-recipients', kwargs={'pk': award.pk}),
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
        reverse('api-v2-award-recipients', kwargs={'pk': award.pk}),
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

    list_response = api_client.get(reverse('api-v2-award-list'))
    recipient_response = api_client.get(
        reverse('api-v2-award-recipients', kwargs={'pk': award.pk}),
    )

    assert list_response.status_code == 200
    assert 'ETag' in list_response
    assert 'Last-Modified' in list_response
    assert recipient_response.status_code == 200
    assert recipient_response.data['results'][0]['id'] == recipient.pk
    assert 'ETag' in recipient_response
    assert 'Last-Modified' in recipient_response

    cached_list = api_client.get(
        reverse('api-v2-award-list'),
        HTTP_IF_NONE_MATCH=list_response['ETag'],
    )
    cached_recipients = api_client.get(
        reverse('api-v2-award-recipients', kwargs={'pk': award.pk}),
        HTTP_IF_NONE_MATCH=recipient_response['ETag'],
    )

    assert cached_list.status_code == 304
    assert cached_recipients.status_code == 304


def test_empty_award_recipient_page_supports_etag(api_client):
    """Awards without recipients still expose a stable page validator."""
    award = Award.objects.create(name='Empty Award', notes='')

    response = api_client.get(
        reverse('api-v2-award-recipients', kwargs={'pk': award.pk}),
    )

    assert response.status_code == 200
    assert response.data['count'] == 0
    assert response.data['results'] == []
    assert 'ETag' in response

    cached_response = api_client.get(
        reverse('api-v2-award-recipients', kwargs={'pk': award.pk}),
        HTTP_IF_NONE_MATCH=response['ETag'],
    )

    assert cached_response.status_code == 304


def test_award_recipient_page_offers_the_recipient_filters(api_client):
    """The Filters form of a recipient page lists the recipient filters."""
    award = Award.objects.create(name='Test Award', notes='')
    url = reverse('api-v2-award-recipients', kwargs={'pk': award.pk})

    response = api_client.get(url, HTTP_ACCEPT='text/html')

    assert response.status_code == 200
    body, names = _filter_form(response)
    assert set(names) == {
        'recipient_type',
        'award_year',
        *TIMESTAMP_FILTER_FIELDS,
    }
    assert '[invalid name]' not in body

    submitted = api_client.get(
        url,
        dict.fromkeys(names, ''),
        HTTP_ACCEPT='text/html',
    )

    assert submitted.status_code == 200


@pytest.mark.parametrize(
    'query',
    [
        {'modified__gt': '2021-01-01T00:00:00Z'},
        {'name': 'Another'},
    ],
)
def test_award_recipients_ignore_the_award_list_filters(api_client, query):
    """Award list filters do not hide the Award of a recipient page."""
    award = Award.objects.create(name='Test Award', notes='')
    Award.objects.filter(pk=award.pk).update(
        modified=datetime(2020, 1, 1, tzinfo=UTC),
    )
    recipient = _create_received_award(
        award=award,
        recipient=_create_creator('Some Creator'),
    )

    response = api_client.get(
        reverse('api-v2-award-recipients', kwargs={'pk': award.pk}),
        query,
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == recipient.pk


@pytest.mark.parametrize('pk_offset', [0, 1])
def test_award_recipients_of_a_hidden_award_are_not_found(
    api_client,
    pk_offset,
):
    """Recipient pages of deleted or missing Awards answer 404."""
    deleted = Award.objects.create(
        name='Deleted Award',
        notes='',
        deleted=True,
    )
    _create_received_award(
        award=deleted,
        recipient=_create_creator('Some Creator'),
    )

    response = api_client.get(
        reverse(
            'api-v2-award-recipients',
            kwargs={'pk': deleted.pk + pk_offset},
        ),
    )

    assert response.status_code == 404
    assert response.data == {'detail': 'No Award matches the given query.'}


def test_award_recipient_schema_lists_the_recipient_filters(api_client):
    """The schema documents the recipient filters and the Award id."""
    response = api_client.get(reverse('api-v2-schema'), {'format': 'json'})

    assert response.status_code == 200
    schema = json.loads(response.content)
    parameters = {
        parameter['name']: parameter
        for parameter in schema['paths']['/api/v2/awards/{id}/recipients/'][
            'get'
        ]['parameters']
    }
    assert set(parameters) - {'id', 'page', 'page_size', 'format'} == {
        'recipient_type',
        'award_year',
        *TIMESTAMP_FILTER_FIELDS,
    }
    assert parameters['id']['description'] == (
        'A unique integer value identifying this award.'
    )
