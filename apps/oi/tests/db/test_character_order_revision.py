# -*- coding: utf-8 -*-


import pytest

from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.gcd.models import (
    Character, CharacterNameDetail, CharacterOrder, CharacterOrderType,
    CharacterRelation, CharacterRelationType, StoryCharacter)
from apps.gcd.models.story import CharacterThroughOrder
from apps.oi.models import (
    CharacterOrderRevision, CharacterThroughOrderRevision, Changeset,
    StoryCharacterRevision, StoryRevision, CTYPES)
from apps.oi import states


def make_character_order_world(any_added_story_rev, any_added_story,
                               any_language, any_indexer, extra_count=0):
    order_type = CharacterOrderType.objects.create(name='Test order')
    character_order = CharacterOrder.objects.create(
        story=any_added_story, type=order_type)

    appearances = {}
    approved_character_revisions = {}
    character_names = ('Alpha', 'Beta', 'Gamma') + tuple(
        'Extra %s' % number for number in range(extra_count))
    for name in character_names:
        character = Character.objects.create(
            name=name,
            sort_name=name,
            disambiguation='',
            language=any_language,
            description='',
            notes='')
        name_detail = CharacterNameDetail.objects.create(
            name=name,
            sort_name=name,
            character=character,
            is_official_name=True)
        appearance = StoryCharacter.objects.create(
            character=name_detail,
            story=any_added_story,
            notes='')
        appearances[name] = appearance
        approved_character_revisions[name] = \
            StoryCharacterRevision.objects.create(
                changeset=any_added_story_rev.changeset,
                committed=True,
                story_character=appearance,
                character=name_detail,
                story_revision=any_added_story_rev,
                notes='')

    current_order = [('Alpha', 10), ('Beta', 20)] + [
        ('Extra %s' % number, 30 + number * 10)
        for number in range(extra_count)
    ]
    for name, order_code in current_order:
        CharacterThroughOrder.objects.create(
            order=character_order,
            story_character=appearances[name],
            order_code=order_code)

    approved_order_revision = CharacterOrderRevision.objects.create(
        changeset=any_added_story_rev.changeset,
        committed=True,
        character_order=character_order,
        story_revision=any_added_story_rev,
        type=order_type)
    for name, order_code in current_order:
        CharacterThroughOrderRevision.objects.create(
            order=approved_order_revision,
            story_character=approved_character_revisions[name],
            order_code=order_code)

    def revision_with_order(*ordered_names):
        changeset = Changeset.objects.create(
            state=states.OPEN,
            indexer=any_indexer,
            change_type=CTYPES['issue'])
        story_revision = StoryRevision.clone(
            any_added_story, changeset=changeset)
        character_revisions = {
            name: StoryCharacterRevision.clone(
                appearance,
                changeset=changeset,
                story_revision=story_revision)
            for name, appearance in appearances.items()
        }
        order_revision = CharacterOrderRevision.clone(
            character_order,
            changeset=changeset,
            story_revision=story_revision)
        for name, order_code in ordered_names:
            CharacterThroughOrderRevision.objects.create(
                order=order_revision,
                story_character=character_revisions[name],
                order_code=order_code)
        return order_revision

    return character_order, appearances, revision_with_order


@pytest.fixture
def character_order_world(any_added_story_rev, any_added_story, any_language,
                          any_indexer):
    return make_character_order_world(
        any_added_story_rev, any_added_story, any_language, any_indexer)


@pytest.fixture
def large_character_order_world(any_added_story_rev, any_added_story,
                                any_language, any_indexer):
    return make_character_order_world(
        any_added_story_rev, any_added_story, any_language, any_indexer,
        extra_count=10)


def order_codes(character_order):
    return dict(CharacterThroughOrder.objects.filter(
        order=character_order).values_list(
            'story_character__character__name', 'order_code'))


@pytest.mark.django_db
def test_commit_adds_character_to_order(character_order_world):
    character_order, _, revision_with_order = character_order_world
    revision = revision_with_order(
        ('Alpha', 10), ('Beta', 20), ('Gamma', 30))

    revision.commit_to_display()

    assert order_codes(character_order) == {
        'Alpha': 10,
        'Beta': 20,
        'Gamma': 30,
    }


@pytest.mark.django_db
def test_commit_removes_character_from_order(character_order_world):
    character_order, _, revision_with_order = character_order_world
    revision = revision_with_order(('Beta', 20),)

    revision.commit_to_display()

    assert order_codes(character_order) == {'Beta': 20}


@pytest.mark.django_db
def test_commit_updates_character_order_codes(character_order_world):
    character_order, _, revision_with_order = character_order_world
    revision = revision_with_order(('Beta', 10), ('Alpha', 20))

    revision.commit_to_display()

    assert order_codes(character_order) == {'Alpha': 20, 'Beta': 10}


@pytest.mark.django_db
def test_reconciliation_uses_bounded_queries(large_character_order_world):
    _, _, revision_with_order = large_character_order_world
    desired_order = [('Beta', 5), ('Gamma', 10)] + [
        ('Extra %s' % number, 15 + number * 5)
        for number in range(10)
    ]
    revision = revision_with_order(*desired_order)
    # Exercise reconciliation without a cached CharacterOrder relation.
    revision = CharacterOrderRevision.objects.get(pk=revision.pk)

    with CaptureQueriesContext(connection) as queries:
        revision._post_save_object({})

    # Two reads plus at most one batched delete, update, and insert.
    assert len(queries) <= 5


@pytest.mark.django_db
def test_display_order_uses_bounded_queries(large_character_order_world):
    """Character-order display does not query once per ordered character."""
    character_order, _, _ = large_character_order_world

    with CaptureQueriesContext(connection) as queries:
        result = character_order.process_ordered_appearing_characters()

    assert [item[0].character.name for item in result[1]] == [
        'Alpha', 'Beta',
        *['Extra %s' % number for number in range(10)],
        'Gamma',
    ]
    # The count stays bounded as the order grows; this fixture currently uses
    # thirteen appearing characters.
    assert len(queries) <= 20


@pytest.mark.django_db
def test_revision_display_uses_revision_through_ids(large_character_order_world):
    """Revision ordering matches StoryCharacterRevision IDs correctly."""
    _, _, revision_with_order = large_character_order_world
    revision = revision_with_order(
        ('Gamma', 5), ('Alpha', 10), ('Beta', 15))

    _, characters = revision.process_ordered_appearing_characters()

    assert [item[0].character.name for item in characters[:3]] == [
        'Gamma', 'Alpha', 'Beta']


@pytest.mark.django_db
def test_edit_order_list_uses_bounded_queries(large_character_order_world):
    """Preparing the edit list does not query once per appearing character."""
    _, _, revision_with_order = large_character_order_world
    revision = revision_with_order(
        ('Alpha', 10), ('Beta', 20), ('Gamma', 30),
        *[('Extra %s' % number, 40 + number * 10)
          for number in range(10)])

    with CaptureQueriesContext(connection) as queries:
        result = revision.story_characters()

    assert result
    assert len(queries) <= 10


@pytest.mark.django_db
def test_display_keeps_alias_and_civilian_order(character_order_world):
    """Bulk identity loading preserves alias/civilian display behavior."""
    character_order, appearances, _ = character_order_world
    relation_type, _ = CharacterRelationType.objects.get_or_create(
        id=2, defaults={'type': 'civilian identity',
                        'reverse_type': 'alias'})
    CharacterRelation.objects.create(
        from_character=appearances['Alpha'].character.character,
        to_character=appearances['Gamma'].character.character,
        relation_type=relation_type,
        notes='')

    _, characters = character_order.process_ordered_appearing_characters()

    assert [item[0].character.name for item in characters] == [
        'Alpha', 'Beta']
    assert [item.character.name for item in characters[0][1]] == ['Gamma']
