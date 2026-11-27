# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the character serializer."""

from apps.api_v2.serializers.characters import CharacterSerializer
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


def test_character_serializer_exposes_contract(db):
    """The character serializer emits the Sprint 2 character contract."""
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
    character = Character.objects.create(
        name='Spider-Man',
        sort_name='Spider-Man',
        disambiguation='Peter Parker',
        universe=universe,
        year_first_published=1962,
        language=english,
        description='Character description',
        notes='Character notes',
    )
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
    CharacterNameDetail.objects.create(
        name='Deleted Alias',
        sort_name='ZZ Deleted Alias',
        character=character,
        is_official_name=False,
        deleted=True,
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
    daily_bugle = Group.objects.create(
        name='Daily Bugle',
        sort_name='Daily Bugle',
        disambiguation='',
        universe=universe,
        year_first_published=1898,
        language=english,
        description='',
        notes='',
    )
    deleted_group = Group.objects.create(
        name='Deleted Group',
        sort_name='Deleted Group',
        disambiguation='',
        universe=universe,
        year_first_published=1950,
        language=english,
        description='',
        notes='',
        deleted=True,
    )
    member_type = GroupMembershipType.objects.create(
        type='member',
        reverse_type='belongs to',
    )
    GroupMembership.objects.create(
        character=character,
        group=daily_bugle,
        membership_type=member_type,
        notes='',
    )
    GroupMembership.objects.create(
        character=character,
        group=avengers,
        membership_type=member_type,
        notes='',
    )
    GroupMembership.objects.create(
        character=character,
        group=avengers,
        membership_type=member_type,
        notes='duplicate role',
    )
    GroupMembership.objects.create(
        character=character,
        group=deleted_group,
        membership_type=member_type,
        notes='',
    )
    character.keywords.add('alpha', 'beta')

    data = CharacterSerializer(character).data

    assert set(data) == {
        'id',
        'name',
        'sort_name',
        'disambiguation',
        'year_first_published',
        'language',
        'description',
        'notes',
        'universe',
        'name_details',
        'group_memberships',
        'keywords',
        'created',
        'modified',
    }
    assert data['id'] == character.pk
    assert data['name'] == 'Spider-Man'
    assert data['sort_name'] == 'Spider-Man'
    assert data['disambiguation'] == 'Peter Parker'
    assert data['year_first_published'] == 1962
    assert data['language'] == 'en'
    assert data['description'] == 'Character description'
    assert data['notes'] == 'Character notes'
    assert data['universe'] == {
        'id': universe.pk,
        'name': 'Marvel: Mainstream - Earth-616',
    }
    assert data['name_details'] == [
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
    assert data['group_memberships'] == [
        {'id': avengers.pk, 'name': 'Avengers'},
        {'id': daily_bugle.pk, 'name': 'Daily Bugle'},
    ]
    assert set(data['keywords']) == {'alpha', 'beta'}
    assert data['created']
    assert data['modified']
