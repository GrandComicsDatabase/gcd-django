# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Performance tests for character endpoints."""

from django.db import connection
from django.test.utils import CaptureQueriesContext
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
):
    """Create a minimal character row for performance tests."""
    return Character.objects.create(
        name=name,
        sort_name=sort_name,
        disambiguation='',
        universe=universe,
        year_first_published=year_first_published,
        language=language,
        description='',
        notes='',
    )


def _populate_character_relationships(character, *, universe, language):
    """Attach related rows so the serializer exercises all prefetches."""
    CharacterNameDetail.objects.create(
        name=f'{character.name} Official',
        sort_name=f'{character.sort_name} Official',
        character=character,
        is_official_name=True,
    )
    group = Group.objects.create(
        name=f'{character.name} Group',
        sort_name=f'{character.sort_name} Group',
        disambiguation='',
        universe=universe,
        year_first_published=character.year_first_published,
        language=language,
        description='',
        notes='',
    )
    member_type, _created = GroupMembershipType.objects.get_or_create(
        type='member',
        defaults={'reverse_type': 'belongs to'},
    )
    GroupMembership.objects.create(
        character=character,
        group=group,
        membership_type=member_type,
        notes='',
    )
    character.keywords.add(character.name.lower())


def test_character_list_query_count(api_client, db):
    """The character list stays on the expected query budget."""
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
    first = _create_character(
        name='Spider-Man',
        sort_name='Spider-Man',
        year_first_published=1962,
        language=english,
        universe=universe,
    )
    second = _create_character(
        name='Thing',
        sort_name='Thing',
        year_first_published=1961,
        language=english,
        universe=universe,
    )
    _populate_character_relationships(
        first,
        universe=universe,
        language=english,
    )
    _populate_character_relationships(
        second,
        universe=universe,
        language=english,
    )

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(reverse('character-list'))

    assert response.status_code == 200
    assert len(context) == 6


def test_character_detail_query_count(api_client, db):
    """The character detail endpoint avoids lazy-loading regressions."""
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
    _populate_character_relationships(
        character,
        universe=universe,
        language=english,
    )

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(
            reverse('character-detail', kwargs={'pk': character.pk}),
        )

    assert response.status_code == 200
    assert len(context) == 5
