# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the group v2 endpoints."""

from django.urls import reverse

from apps.gcd.models import (
    Character,
    Group,
    GroupMembership,
    GroupMembershipType,
    GroupNameDetail,
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
    """Create or return a language row for group tests."""
    obj, _created = Language.objects.get_or_create(
        code=code,
        defaults={'name': name},
    )
    return obj


def _create_group(
    *,
    name,
    sort_name,
    year_first_published,
    language,
    universe=None,
    deleted=False,
):
    """Create a minimal group row for view tests."""
    return Group.objects.create(
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


def test_group_list_returns_paginated_results(api_client, db):
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
    group = _create_group(
        name='Justice League',
        sort_name='Justice League',
        year_first_published=1960,
        language=english,
        universe=universe,
    )
    group.keywords.add('alpha')

    response = api_client.get(reverse('group-list'))

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['next'] is None
    assert response.data['previous'] is None
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['id'] == group.pk
    assert response.data['results'][0]['language'] == 'en'
    assert response.data['results'][0]['universe'] == {
        'id': universe.pk,
        'name': 'Marvel: Mainstream - Earth-616',
    }


def test_group_detail_returns_expected_payload(authenticated_client, db):
    """The detail endpoint returns the group serializer payload."""
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
    group = _create_group(
        name='Justice League',
        sort_name='Justice League',
        year_first_published=1960,
        language=english,
        universe=universe,
    )
    group.disambiguation = 'Silver Age'
    group.description = 'Group description'
    group.notes = 'Group notes'
    group.save()
    alias = GroupNameDetail.objects.create(
        name='JLA',
        sort_name='JLA',
        group=group,
        is_official_name=False,
    )
    official = GroupNameDetail.objects.create(
        name='Justice League',
        sort_name='Justice League',
        group=group,
        is_official_name=True,
    )
    batman = Character.objects.create(
        name='Batman',
        sort_name='Batman',
        disambiguation='',
        universe=universe,
        year_first_published=1939,
        language=english,
        description='',
        notes='',
    )
    member_type = GroupMembershipType.objects.create(
        type='member',
        reverse_type='belongs to',
    )
    GroupMembership.objects.create(
        character=batman,
        group=group,
        membership_type=member_type,
        notes='',
    )
    group.keywords.add('alpha', 'beta')

    response = authenticated_client.get(
        reverse('group-detail', kwargs={'pk': group.pk}),
    )

    assert response.status_code == 200
    assert response.data['id'] == group.pk
    assert response.data['name'] == group.name
    assert response.data['sort_name'] == group.sort_name
    assert response.data['disambiguation'] == 'Silver Age'
    assert response.data['language'] == 'en'
    assert response.data['universe'] == {
        'id': universe.pk,
        'name': 'Marvel: Mainstream - Earth-616',
    }
    assert response.data['name_details'] == [
        {
            'id': alias.pk,
            'name': 'JLA',
            'sort_name': 'JLA',
            'is_official_name': False,
        },
        {
            'id': official.pk,
            'name': 'Justice League',
            'sort_name': 'Justice League',
            'is_official_name': True,
        },
    ]
    assert response.data['members'] == [
        {'id': batman.pk, 'name': 'Batman'},
    ]
    assert set(response.data['keywords']) == {'alpha', 'beta'}


def test_group_list_applies_filter_query_params(authenticated_client, db):
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
    matching = _create_group(
        name='X-Men',
        sort_name='X-Men',
        year_first_published=1963,
        language=english,
        universe=marvel_universe,
    )
    _create_group(
        name='X-Men ES',
        sort_name='X-Men ES',
        year_first_published=1963,
        language=spanish,
        universe=marvel_universe,
    )
    _create_group(
        name='Justice League',
        sort_name='Justice League',
        year_first_published=1960,
        language=english,
        universe=dc_universe,
    )

    response = authenticated_client.get(
        reverse('group-list'),
        {
            'name': 'x-men',
            'year_first_published__gte': '1960',
            'year_first_published__lte': '1965',
            'language': 'en',
            'universe': str(marvel_universe.pk),
        },
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == matching.pk


def test_group_endpoints_hide_soft_deleted_records(
    authenticated_client,
    db,
):
    """Soft-deleted groups disappear from list and detail responses."""
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
    visible = _create_group(
        name='Visible Group',
        sort_name='Visible Group',
        year_first_published=1960,
        language=english,
        universe=universe,
    )
    deleted = _create_group(
        name='Deleted Group',
        sort_name='Deleted Group',
        year_first_published=1965,
        language=english,
        universe=universe,
        deleted=True,
    )

    list_response = authenticated_client.get(reverse('group-list'))
    detail_response = authenticated_client.get(
        reverse('group-detail', kwargs={'pk': deleted.pk}),
    )

    assert list_response.status_code == 200
    assert list_response.data['count'] == 1
    assert list_response.data['results'][0]['id'] == visible.pk
    assert detail_response.status_code == 404


def test_group_list_returns_304_for_if_modified_since(
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
    _create_group(
        name='Justice League',
        sort_name='Justice League',
        year_first_published=1960,
        language=english,
        universe=universe,
    )

    response = authenticated_client.get(reverse('group-list'))

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('group-list'),
        HTTP_IF_MODIFIED_SINCE=response['Last-Modified'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''


def test_group_detail_returns_304_for_if_none_match(
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
    group = _create_group(
        name='Justice League',
        sort_name='Justice League',
        year_first_published=1960,
        language=english,
        universe=universe,
    )

    response = authenticated_client.get(
        reverse('group-detail', kwargs={'pk': group.pk}),
    )

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('group-detail', kwargs={'pk': group.pk}),
        HTTP_IF_NONE_MATCH=response['ETag'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''
