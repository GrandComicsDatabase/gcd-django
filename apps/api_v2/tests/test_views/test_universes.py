# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the universe v2 endpoints."""

from django.urls import reverse

from apps.gcd.models import Multiverse, Universe


def _create_multiverse(name):
    """Create a multiverse plus a hidden seed universe."""
    seed = Universe.objects.create(
        multiverse=name,
        name='Seed Universe',
        designation='Earth-0',
        year_first_published=1938,
        description='',
        notes='',
        deleted=True,
    )
    multiverse = Multiverse.objects.create(name=name, mainstream=seed)
    seed.verse = multiverse
    seed.save(update_fields=['verse'])
    return multiverse


def _create_universe(
    *,
    multiverse_name,
    verse=None,
    name,
    designation,
    year_first_published,
    deleted=False,
):
    """Create a minimal universe row for view tests."""
    return Universe.objects.create(
        multiverse=multiverse_name,
        verse=verse,
        name=name,
        designation=designation,
        year_first_published=year_first_published,
        description='',
        notes='',
        deleted=deleted,
    )


def test_universe_list_returns_paginated_results(api_client, db):
    """The list endpoint is anon-readable and paginated."""
    marvel = _create_multiverse('Marvel')
    universe = _create_universe(
        multiverse_name='Marvel',
        verse=marvel,
        name='Ultimate',
        designation='Earth-1610',
        year_first_published=2000,
    )

    response = api_client.get(reverse('universe-list'))

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['next'] is None
    assert response.data['previous'] is None
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['id'] == universe.pk
    assert response.data['results'][0]['multiverse'] == {
        'id': marvel.pk,
        'name': marvel.name,
    }
    assert response.data['results'][0]['display_name'] == (
        'Marvel: Ultimate - Earth-1610'
    )


def test_universe_detail_returns_expected_payload(authenticated_client, db):
    """The detail endpoint returns the universe serializer payload."""
    marvel = _create_multiverse('Marvel')
    universe = _create_universe(
        multiverse_name='Marvel',
        verse=marvel,
        name='Ultimate',
        designation='Earth-1610',
        year_first_published=2000,
    )
    universe.year_first_published_uncertain = True
    universe.description = 'Universe description'
    universe.notes = 'Universe notes'
    universe.save()

    response = authenticated_client.get(
        reverse('universe-detail', kwargs={'pk': universe.pk}),
    )

    assert response.status_code == 200
    assert response.data['id'] == universe.pk
    assert response.data['multiverse'] == {
        'id': marvel.pk,
        'name': marvel.name,
    }
    assert response.data['name'] == universe.name
    assert response.data['designation'] == universe.designation
    assert response.data['display_name'] == 'Marvel: Ultimate - Earth-1610'
    assert response.data['year_first_published'] == 2000
    assert response.data['year_first_published_uncertain'] is True
    assert response.data['description'] == 'Universe description'
    assert response.data['notes'] == 'Universe notes'


def test_universe_detail_falls_back_to_raw_multiverse_string(
    authenticated_client,
    db,
):
    """Universe detail uses the raw multiverse string when no verse exists."""
    universe = _create_universe(
        multiverse_name='Legacy Verse',
        name='Pocket Universe',
        designation='Earth-9',
        year_first_published=1984,
    )

    response = authenticated_client.get(
        reverse('universe-detail', kwargs={'pk': universe.pk}),
    )

    assert response.status_code == 200
    assert response.data['multiverse'] == {
        'id': None,
        'name': 'Legacy Verse',
    }


def test_universe_list_applies_filter_query_params(authenticated_client, db):
    """The list endpoint applies django-filter query params."""
    marvel = _create_multiverse('Marvel')
    dc = _create_multiverse('DC')
    matching = _create_universe(
        multiverse_name='Marvel',
        verse=marvel,
        name='Ultimate',
        designation='Earth-1610',
        year_first_published=2000,
    )
    _create_universe(
        multiverse_name='Marvel',
        verse=marvel,
        name='Noir',
        designation='Earth-90214',
        year_first_published=2009,
    )
    _create_universe(
        multiverse_name='DC',
        verse=dc,
        name='Mainstream',
        designation='Earth-0',
        year_first_published=1938,
    )

    response = authenticated_client.get(
        reverse('universe-list'),
        {
            'name': 'ulti',
            'designation': '1610',
            'year_first_published': '2000',
            'multiverse': str(marvel.pk),
        },
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == matching.pk


def test_universe_endpoints_hide_soft_deleted_records(
    authenticated_client,
    db,
):
    """Soft-deleted universes disappear from list and detail responses."""
    marvel = _create_multiverse('Marvel')
    visible = _create_universe(
        multiverse_name='Marvel',
        verse=marvel,
        name='Visible',
        designation='Earth-1',
        year_first_published=1961,
    )
    deleted = _create_universe(
        multiverse_name='Marvel',
        verse=marvel,
        name='Deleted',
        designation='Earth-2',
        year_first_published=1962,
        deleted=True,
    )

    list_response = authenticated_client.get(reverse('universe-list'))
    detail_response = authenticated_client.get(
        reverse('universe-detail', kwargs={'pk': deleted.pk}),
    )

    assert list_response.status_code == 200
    assert list_response.data['count'] == 1
    assert list_response.data['results'][0]['id'] == visible.pk
    assert detail_response.status_code == 404


def test_universe_list_returns_304_for_if_modified_since(
    authenticated_client,
    db,
):
    """List responses support Last-Modified cache validation."""
    marvel = _create_multiverse('Marvel')
    _create_universe(
        multiverse_name='Marvel',
        verse=marvel,
        name='Mainstream',
        designation='Earth-616',
        year_first_published=1961,
    )

    response = authenticated_client.get(reverse('universe-list'))

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('universe-list'),
        HTTP_IF_MODIFIED_SINCE=response['Last-Modified'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''


def test_universe_detail_returns_304_for_if_none_match(
    authenticated_client,
    db,
):
    """Detail responses support ETag cache validation."""
    marvel = _create_multiverse('Marvel')
    universe = _create_universe(
        multiverse_name='Marvel',
        verse=marvel,
        name='Mainstream',
        designation='Earth-616',
        year_first_published=1961,
    )

    response = authenticated_client.get(
        reverse('universe-detail', kwargs={'pk': universe.pk}),
    )

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('universe-detail', kwargs={'pk': universe.pk}),
        HTTP_IF_NONE_MATCH=response['ETag'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''
