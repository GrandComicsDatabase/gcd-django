# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the universe serializer."""

from apps.api_v2.serializers.universes import UniverseSerializer
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


def test_universe_serializer_exposes_contract_for_linked_multiverse(db):
    """The universe serializer emits the Sprint 2 universe contract."""
    marvel = _create_multiverse('Marvel')
    universe = Universe.objects.create(
        multiverse='Marvel',
        verse=marvel,
        name='Ultimate',
        designation='Earth-1610',
        year_first_published=2000,
        year_first_published_uncertain=True,
        description='Universe description',
        notes='Universe notes',
    )

    data = UniverseSerializer(universe).data

    assert set(data) == {
        'id',
        'multiverse',
        'name',
        'designation',
        'display_name',
        'year_first_published',
        'year_first_published_uncertain',
        'description',
        'notes',
        'created',
        'modified',
    }
    assert data['id'] == universe.pk
    assert data['multiverse'] == {
        'id': marvel.pk,
        'name': 'Marvel',
    }
    assert data['name'] == 'Ultimate'
    assert data['designation'] == 'Earth-1610'
    assert data['display_name'] == 'Marvel: Ultimate - Earth-1610'
    assert data['year_first_published'] == 2000
    assert data['year_first_published_uncertain'] is True
    assert data['description'] == 'Universe description'
    assert data['notes'] == 'Universe notes'
    assert data['created']
    assert data['modified']


def test_universe_serializer_falls_back_to_raw_multiverse_string(db):
    """Raw multiverse strings become public multiverse objects when needed."""
    universe = Universe.objects.create(
        multiverse='Legacy Verse',
        name='Pocket Universe',
        designation='Earth-9',
        year_first_published=1984,
        description='Fallback description',
        notes='Fallback notes',
    )

    data = UniverseSerializer(universe).data

    assert data['multiverse'] == {
        'id': None,
        'name': 'Legacy Verse',
    }
    assert data['display_name'] == 'Pocket Universe - Earth-9'
