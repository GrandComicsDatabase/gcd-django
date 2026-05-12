# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the character v2 endpoints."""

from django.urls import reverse

from apps.gcd.models import (
    Character,
    CharacterNameDetail,
    Group,
    GroupMembership,
    GroupMembershipType,
    Multiverse,
    Universe,
)
from apps.stddata.models import Language


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


def _create_language(code, name):
    """Create or return a language row for character tests."""
    obj, _created = Language.objects.get_or_create(
        code=code,
        defaults={'name': name},
    )
    return obj


def _create_character(
    *,
    name,
    sort_name,
    year_first_published,
    language,
    universe=None,
    deleted=False,
):
    """Create a minimal character row for view tests."""
    return Character.objects.create(
        name=name,
        sort_name=sort_name,
        disambiguation='',
        universe=universe,
        year_first_published=year_first_published,
        language=language,
        description='',
        notes='',
        deleted=deleted,
    )


def test_character_list_returns_paginated_results(api_client, db):
    """The list endpoint is anon-readable and paginated."""
    english = _create_language('en', 'English')
    marvel = _create_multiverse('Marvel')
    universe = Universe.objects.create(
        multiverse='Marvel',
        verse=marvel,
        name='Mainstream',
        designation='Earth-616',
        year_first_published=1961,
        description='',
        notes='',
    )
    character = _create_character(
        name='Spider-Man',
        sort_name='Spider-Man',
        year_first_published=1962,
        language=english,
        universe=universe,
    )
    character.keywords.add('alpha')

    response = api_client.get(reverse('character-list'))

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['next'] is None
    assert response.data['previous'] is None
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['id'] == character.pk
    assert response.data['results'][0]['language'] == 'en'
    assert response.data['results'][0]['universe'] == {
        'id': universe.pk,
        'name': 'Marvel: Mainstream - Earth-616',
    }


def test_character_detail_returns_expected_payload(
    authenticated_client,
    db,
):
    """The detail endpoint returns the character serializer payload."""
    english = _create_language('en', 'English')
    marvel = _create_multiverse('Marvel')
    universe = Universe.objects.create(
        multiverse='Marvel',
        verse=marvel,
        name='Mainstream',
        designation='Earth-616',
        year_first_published=1961,
        description='',
        notes='',
    )
    character = _create_character(
        name='Spider-Man',
        sort_name='Spider-Man',
        year_first_published=1962,
        language=english,
        universe=universe,
    )
    character.disambiguation = 'Peter Parker'
    character.description = 'Character description'
    character.notes = 'Character notes'
    character.save()
    alias = CharacterNameDetail.objects.create(
        name='Friendly Neighborhood Spider-Man',
        sort_name='Friendly Neighborhood Spider-Man',
        character=character,
        is_official_name=False,
    )
    official = CharacterNameDetail.objects.create(
        name='Spider-Man',
        sort_name='Spider-Man',
        character=character,
        is_official_name=True,
    )
    avengers = Group.objects.create(
        name='Avengers',
        sort_name='Avengers',
        disambiguation='',
        universe=universe,
        year_first_published=1963,
        language=english,
        description='',
        notes='',
    )
    member_type = GroupMembershipType.objects.create(
        type='member',
        reverse_type='belongs to',
    )
    GroupMembership.objects.create(
        character=character,
        group=avengers,
        membership_type=member_type,
        notes='',
    )
    character.keywords.add('alpha', 'beta')

    response = authenticated_client.get(
        reverse('character-detail', kwargs={'pk': character.pk}),
    )

    assert response.status_code == 200
    assert response.data['id'] == character.pk
    assert response.data['name'] == character.name
    assert response.data['sort_name'] == character.sort_name
    assert response.data['disambiguation'] == 'Peter Parker'
    assert response.data['language'] == 'en'
    assert response.data['universe'] == {
        'id': universe.pk,
        'name': 'Marvel: Mainstream - Earth-616',
    }
    assert response.data['name_details'] == [
        {
            'id': alias.pk,
            'name': 'Friendly Neighborhood Spider-Man',
            'sort_name': 'Friendly Neighborhood Spider-Man',
            'is_official_name': False,
        },
        {
            'id': official.pk,
            'name': 'Spider-Man',
            'sort_name': 'Spider-Man',
            'is_official_name': True,
        },
    ]
    assert response.data['group_memberships'] == [
        {'id': avengers.pk, 'name': 'Avengers'},
    ]
    assert set(response.data['keywords']) == {'alpha', 'beta'}


def test_character_list_applies_filter_query_params(
    authenticated_client,
    db,
):
    """The list endpoint applies django-filter query params."""
    english = _create_language('en', 'English')
    spanish = _create_language('es', 'Spanish')
    marvel = _create_multiverse('Marvel')
    dc = _create_multiverse('DC')
    marvel_universe = Universe.objects.create(
        multiverse='Marvel',
        verse=marvel,
        name='Mainstream',
        designation='Earth-616',
        year_first_published=1961,
        description='',
        notes='',
    )
    dc_universe = Universe.objects.create(
        multiverse='DC',
        verse=dc,
        name='Mainstream',
        designation='Earth-0',
        year_first_published=1938,
        description='',
        notes='',
    )
    matching = _create_character(
        name='Spider-Man',
        sort_name='Spider-Man',
        year_first_published=1962,
        language=english,
        universe=marvel_universe,
    )
    _create_character(
        name='Spider-Man ES',
        sort_name='Spider-Man ES',
        year_first_published=1962,
        language=spanish,
        universe=marvel_universe,
    )
    _create_character(
        name='Batman',
        sort_name='Batman',
        year_first_published=1939,
        language=english,
        universe=dc_universe,
    )

    response = authenticated_client.get(
        reverse('character-list'),
        {
            'name': 'spider',
            'year_first_published__gte': '1960',
            'year_first_published__lte': '1965',
            'language': 'en',
            'universe': str(marvel_universe.pk),
        },
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == matching.pk


def test_character_endpoints_hide_soft_deleted_records(
    authenticated_client,
    db,
):
    """Soft-deleted characters disappear from list and detail responses."""
    english = _create_language('en', 'English')
    marvel = _create_multiverse('Marvel')
    universe = Universe.objects.create(
        multiverse='Marvel',
        verse=marvel,
        name='Mainstream',
        designation='Earth-616',
        year_first_published=1961,
        description='',
        notes='',
    )
    visible = _create_character(
        name='Visible Character',
        sort_name='Visible Character',
        year_first_published=1962,
        language=english,
        universe=universe,
    )
    deleted = _create_character(
        name='Deleted Character',
        sort_name='Deleted Character',
        year_first_published=1963,
        language=english,
        universe=universe,
        deleted=True,
    )

    list_response = authenticated_client.get(reverse('character-list'))
    detail_response = authenticated_client.get(
        reverse('character-detail', kwargs={'pk': deleted.pk}),
    )

    assert list_response.status_code == 200
    assert list_response.data['count'] == 1
    assert list_response.data['results'][0]['id'] == visible.pk
    assert detail_response.status_code == 404


def test_character_list_returns_304_for_if_modified_since(
    authenticated_client,
    db,
):
    """List responses support Last-Modified cache validation."""
    english = _create_language('en', 'English')
    marvel = _create_multiverse('Marvel')
    universe = Universe.objects.create(
        multiverse='Marvel',
        verse=marvel,
        name='Mainstream',
        designation='Earth-616',
        year_first_published=1961,
        description='',
        notes='',
    )
    _create_character(
        name='Spider-Man',
        sort_name='Spider-Man',
        year_first_published=1962,
        language=english,
        universe=universe,
    )

    response = authenticated_client.get(reverse('character-list'))

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('character-list'),
        HTTP_IF_MODIFIED_SINCE=response['Last-Modified'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''


def test_character_detail_returns_304_for_if_none_match(
    authenticated_client,
    db,
):
    """Detail responses support ETag cache validation."""
    english = _create_language('en', 'English')
    marvel = _create_multiverse('Marvel')
    universe = Universe.objects.create(
        multiverse='Marvel',
        verse=marvel,
        name='Mainstream',
        designation='Earth-616',
        year_first_published=1961,
        description='',
        notes='',
    )
    character = _create_character(
        name='Spider-Man',
        sort_name='Spider-Man',
        year_first_published=1962,
        language=english,
        universe=universe,
    )

    response = authenticated_client.get(
        reverse('character-detail', kwargs={'pk': character.pk}),
    )

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('character-detail', kwargs={'pk': character.pk}),
        HTTP_IF_NONE_MATCH=response['ETag'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''
