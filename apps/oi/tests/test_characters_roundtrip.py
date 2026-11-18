# -*- coding: utf-8 -*-
"""The text beta writes for linked characters reads back without findings.

Rows -> show_characters -> the reader of the characters text: groups,
members, secret identities, flags, role and notes come back as the rows
hold them. Names hold none of ";[]()" and notes hold no role or flag word.
The case of a last group without members is left out: beta writes it
without a separator before the next name.
"""

import pytest

from apps.gcd.models import (
    Character, CharacterNameDetail, CharacterRelation, CharacterRelationType,
    CharacterRole, Group, GroupNameDetail, Story, StoryCharacter, StoryGroup)
from apps.gcd.models.story import show_characters
from apps.oi.characters_text import ROLES, parse

ALIAS_OF = 2


def _name(model, detail_model, language, name):
    """An object with one official name; return the name."""
    record = model.objects.create(name=name, sort_name=name,
                                  disambiguation='', language=language,
                                  description='', notes='')
    owner = 'character' if model is Character else 'group'
    return detail_model.objects.create(name=name, sort_name=name,
                                       is_official_name=True,
                                       **{owner: record})


@pytest.fixture
def make(any_language):
    """Build characters, groups and secret identities of a story."""
    relation_type = CharacterRelationType.objects.get_or_create(
      id=ALIAS_OF, defaults={'type': 'alias of',
                             'reverse_type': 'secret identity of'})[0]
    roles = {role: CharacterRole.objects.get_or_create(
               name=role, defaults={'sort_code': index})[0]
             for index, role in enumerate(ROLES)}

    class Maker:
        """Helpers bound to the story under test."""

        def __init__(self):
            """Start with no rows."""
            self.story = None

        def character(self, name, identities=(), role=None, flags=(),
                      notes='', group=None):
            """A row of the story, with the rows of its identities."""
            detail = _name(Character, CharacterNameDetail, any_language,
                           name)
            row = StoryCharacter.objects.create(
              character=detail, story=self.story,
              role=roles[role] if role else None,
              is_flashback='flashback' in flags, is_death='death' in flags,
              is_origin='origin' in flags, notes=notes)
            if group:
                row.group_name.add(group.group_name)
            for identity in identities:
                civilian = _name(Character, CharacterNameDetail,
                                 any_language, identity)
                CharacterRelation.objects.create(
                  from_character=detail.character,
                  to_character=civilian.character,
                  relation_type=relation_type, notes='')
                StoryCharacter.objects.create(character=civilian,
                                              story=self.story, notes='')
            return row

        def group(self, name, notes=''):
            """A group of the story."""
            detail = _name(Group, GroupNameDetail, any_language, name)
            return StoryGroup.objects.create(group_name=detail,
                                             story=self.story, notes=notes)

    return Maker()


def _appearance(node):
    """What the reader got for one character: name, identities, flags,
    role and notes."""
    identities, flags, roles, notes = [], set(), [], []
    for group in node.groups:
        if group.kind == '[':
            identities += [element.name for element in group.elements]
            continue
        for segment in group.segments:
            for kind, value in segment.readings:
                {'flag': flags.add, 'role': roles.append,
                 'note': notes.append}[kind](value)
    return (node.name, identities, flags, roles, ', '.join(notes))


def _expected(row, identities=()):
    """The same values, from a row of the story."""
    flags = {flag for flag, value in (('flashback', row.is_flashback),
                                      ('death', row.is_death),
                                      ('origin', row.is_origin)) if value}
    return (row.character.name, list(identities), flags,
            [row.role.name] if row.role else [], row.notes)


@pytest.mark.django_db
def test_rows_read_back_from_the_text(make, any_added_story):
    """Rows written by beta read back with all their values."""
    story = make.story = any_added_story
    story.characters = 'Lois Lane (cameo)'
    story.save()
    league = make.group('Justice League', notes='first appearance')
    rows = [
      (make.character('Batman', flags=('death', 'origin'), group=league),
       ()),
      (make.character('Superman', identities=['Clark Kent'], role='cameo',
                      flags=('flashback',), notes='with cape',
                      group=league), ['Clark Kent']),
      (make.character('Alfred', role='supporting', notes='butler'), ()),
      (make.character('Firestorm', role='guest',
                      identities=['Martin Stein', 'Ronnie Raymond']),
       ['Martin Stein', 'Ronnie Raymond']),
    ]
    for index, role in enumerate(ROLES):
        rows.append((make.character('Extra %d' % index, role=role,
                                    notes='note %d' % index), ()))
    story = Story.objects.get(id=story.id)

    text = show_characters(story, url=False)
    parsed = parse(text)

    assert [unit.diagnostics for unit in parsed.units] == \
        [[]] * len(parsed.units), text
    nodes = {unit.node.name: unit.node for unit in parsed.units}
    group = nodes.pop('Justice League')
    assert [(item.kind, item.segments and item.segments[0].readings)
            for item in group.groups] == [
      ('(', (('note', 'first appearance'),)), ('[', [])]
    members = {element.name: element for element in group.groups[1].elements}
    assert list(members) == ['Batman', 'Superman']
    lois = nodes.pop('Lois Lane')
    assert _appearance(lois) == ('Lois Lane', [], set(), ['cameo'], '')
    for row, identities in rows:
        name = row.character.name
        node = members.pop(name) if name in members else nodes.pop(name)
        assert _appearance(node) == _expected(row, identities)
    assert not members and not nodes


@pytest.mark.django_db
def test_groups_only(make, any_added_story):
    """A text of groups only, ending with "; ", is well-formed."""
    story = make.story = any_added_story
    story.characters = ''
    story.save()
    titans = make.group('Teen Titans')
    make.character('Robin', identities=['Dick Grayson'], group=titans)
    make.character('Wally West', group=titans, flags=('flashback',))
    story = Story.objects.get(id=story.id)

    text = show_characters(story, url=False)
    parsed = parse(text)

    assert text == 'Teen Titans [Robin [Dick Grayson]; Wally West ' \
                   '(flashback)]; '
    assert [unit.level for unit in parsed.units] == [None]
