# -*- coding: utf-8 -*-
"""
Interchange representation of an issue with its sequences.

CSV, TSV, JSON and YAML carry the same record: the fields of the issue and
of its sequences, each value in the same text form in all four formats.
JSON and YAML only add their own booleans, CSV and TSV escape ^ and the
control characters of the text fields, so that every cell fits on a line.
Linked objects are written by name and disambiguation, as a person writes
them; an id is accepted, but never needed nor written.

The characters, the credits and the lists of linked objects use one
notation:

  items     := item ('; ' item)*
  item      := [sigil] name [anchor [anchor]] qualifier* [' [' items ']']
  anchor    := ' {' disambiguation '}'           ' {#id}' for an id
  qualifier := ' (' text ')'

A second anchor holds the official name of the character, group, creator
or feature whose name it is.

A reference is resolved in the context of the series: by its id, its
second anchor, its disambiguation (without one preferably an object
without disambiguation), then by preferences, in order: those of the
field, such as the brands of the publisher of the series, the language
of the series, the name which is the official name of its owner, the
names used in the series. A reference is written as the shortest one
which resolves back to the object: name and disambiguation, else with
the second anchor too, so that writing what was read gives the same text.

Escapes: '^' before ^ ; ( ) [ ] { }, before a leading @ or &, before
spaces at the start or the end, and ^n ^t ^r for newline, tab and carriage
return. A qualifier is recognized by its sigil or as a keyword, a
qualifier with an escape is never a keyword. The fields which are lists of
linked objects, such as brands or features, have no qualifiers and
members: there only ^ ; { } are escaped, in a single linked object only
^ { }.

The characters of a sequence are a tree written as text, universe -> group
-> character, followed by the free text of the field:

  characters := items [' ;; ' free_text] | ';; ' free_text
  universe   := '@' multiverse ': ' universe ' [' groups, characters ']'
  group      := '&' name [anchor] qualifier* [' [' members ']']
  character  := name [anchor] qualifier* [' [' characters ']']

Qualifiers of a character: '@' universe, '&' group, '&&' group name, '&@'
universe of the group, the flags 'flashback, origin, death', a role such
as 'cameo', and a note. Flags and at most one role may share a qualifier,
separated by commas or spaces, as in '(villain, death)'; any other text
is a note. Of a group: '@' universe, a note, and '&' or '&&'
if its members are linked to the group or to both group and group name,
instead of the group name alone.

Values are inherited down the tree: an item has the universe of its
universe, a member the universe of its group and is a member in the
universe of the group, characters inside a character share its universe.
'(@)' is no universe, '(&@)' a group universe equal to the universe. The
free text escapes only ^ and the control characters.
"""
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from functools import reduce

from django.db.models import Q

from apps.gcd.models import (Brand, CharacterNameDetail, CharacterRelation,
                             CharacterRole, CreatorNameDetail,
                             CreatorSignature, Feature,
                             FeatureLogo, FeatureNameDetail, Group,
                             GroupNameDetail, IndiciaPrinter,
                             IndiciaPublisher, StoryArc, Universe)
from apps.gcd.models.story import STORY_TYPES

RESERVED = '^;()[]{}'
# a list of linked objects has no qualifiers and members, only the escape,
# the anchors and the separator are reserved, a single linked object has no
# separator either
LIST_RESERVED = '^;{}'
REF_RESERVED = '^{}'
SIGILS = '@&'
FLAGS = ('flashback', 'origin', 'death')
FREE_TEXT_SEPARATOR = ';;'
# escaped as ^n, ^t, ^r
CONTROLS = {'\n': 'n', '\t': 't', '\r': 'r'}
UNCONTROLS = {code: char for char, code in CONTROLS.items()}
BRACKETS = {'(': ')', '[': ']', '{': '}'}
# how members are linked to their group, by default to the group name
LINKS = ('group', 'group_name')
DEFAULT_LINKS = ('group_name',)
LINK_PATTERNS = [DEFAULT_LINKS, ('group',), LINKS]
# '(&@)': the universe of the group is the universe of the character
SAME = 'same'
# 'alias of' and 'secret identity of', shown by GCD in square brackets
IDENTITY_RELATION = 2


class NotationError(Exception):
    def __init__(self, kind, message, position=None, token='',
                 candidates=()):
        self.kind = kind
        self.message = message
        self.position = position
        self.token = token
        self.candidates = list(candidates)
        super().__init__(str(self))

    def __str__(self):
        text = self.message
        if self.token:
            text += ' "%s"' % self.token
        if self.position is not None:
            if isinstance(self.position, int):
                text = 'at position %d: %s' % (self.position + 1, text)
            else:
                text = 'at %s: %s' % (self.position, text)
        if self.candidates:
            text += ', candidates: %s' % ' | '.join(self.candidates)
        return text


def _syntax_error(message, position, token=''):
    return NotationError('syntax', message, position, token)


@dataclass
class Ref:
    label: str
    id: int = None
    # None means that no disambiguation was given
    disambiguation: str = None
    position: object = None
    # the official name of the owner of the name
    owner: str = None


@dataclass
class GroupEntry:
    name: Ref
    universe: Ref = None
    notes: str = ''
    position: object = None


@dataclass
class AppearanceEntry:
    name: Ref
    universe: Ref = None
    groups: list = field(default_factory=list)
    group_names: list = field(default_factory=list)
    # a Ref, None or SAME
    group_universe: object = None
    role: str = None
    flags: list = field(default_factory=list)
    notes: str = ''
    position: object = None
    # the group name of the enclosing group and how the member is linked
    member_of: Ref = None
    member_links: tuple = ()
    # the names of the characters inside or around, such as the civilian
    # identity, preferably related characters
    related: list = field(default_factory=list)


@dataclass
class Characters:
    groups: list = field(default_factory=list)
    appearances: list = field(default_factory=list)
    free_text: str = ''


def universe_label(universe):
    return '%s: %s' % (universe.multiverse, universe.universe_name())


def _sorted(objects):
    return sorted(objects, key=lambda related: related.id)


def _flags(appearance):
    return [flag for flag in FLAGS if getattr(appearance, 'is_' + flag)]


# notation

def _escaped(char):
    return '^' + CONTROLS.get(char, char)


def escape(text, keyword=False, reserved=RESERVED):
    """
    Escapes a name or a note. A keyword is a note which would read as a
    keyword, such as a role, it gets an escape.
    """
    chars = [_escaped(char) if char in reserved or char in CONTROLS
             else char for char in text]
    # the parser trims spaces and reads a leading @ or & as sigil
    start = len(text) - len(text.lstrip())
    end = len(text.rstrip())
    for index in list(range(start)) + list(range(max(end, start),
                                                 len(text))):
        chars[index] = _escaped(text[index])
    if text and text[0] in SIGILS and reserved == RESERVED:
        chars[0] = _escaped(text[0])
    if keyword and all(len(char) == 1 for char in chars):
        for index, char in enumerate(text):
            if char not in UNCONTROLS:
                chars[index] = _escaped(char)
                break
    return ''.join(chars)


def escape_text(text):
    """
    Escapes a text cell of a flat file or the free text: ^ and the control
    characters.
    """
    return ''.join(_escaped(char) if char == '^' or char in CONTROLS
                   else char for char in text)


def unescape_text(raw, position=None):
    text = ''
    index = 0
    while index < len(raw):
        if raw[index] == '^':
            if index + 1 == len(raw):
                raise _syntax_error('dangling escape', position)
            text += UNCONTROLS.get(raw[index + 1], raw[index + 1])
            index += 2
            continue
        text += raw[index]
        index += 1
    return text


def render_ref(label, disambiguation='', object_id=None, owner=None,
               reserved=RESERVED):
    text = escape(label, reserved=reserved)
    if object_id is not None:
        text += ' {#%d}' % object_id
    elif disambiguation or owner:
        disambiguation = escape(disambiguation or '', reserved=reserved)
        if disambiguation.startswith('#'):
            disambiguation = '^' + disambiguation
        text += ' {%s}' % disambiguation
    if owner:
        text += ' {%s}' % escape(owner, reserved=reserved)
    return text


# A notation is read as tokens (char, escaped, position), so that only
# unescaped characters have a meaning.

def tokens_of(text, offset=0, tolerant=False):
    tokens = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == '^':
            if index + 1 < len(text):
                code = text[index + 1]
                tokens.append((UNCONTROLS.get(code, code), True,
                               offset + index))
                index += 2
                continue
            if not tolerant:
                raise _syntax_error('dangling escape', offset + index)
        tokens.append((char, False, offset + index))
        index += 1
    return tokens


def _text(tokens):
    return ''.join(token[0] for token in tokens)


def _raw(text, tokens):
    """
    The text of the tokens as written.
    """
    if not tokens:
        return ''
    end = tokens[-1][2] + (2 if tokens[-1][1] else 1)
    return text[tokens[0][2]:end]


def _is(token, chars):
    return not token[1] and token[0] in chars


def _plain(tokens):
    """
    Written without escapes, which a keyword must be.
    """
    return not any(token[1] for token in tokens)


def _strip(tokens):
    start, end = 0, len(tokens)
    while start < end and not tokens[start][1] and \
            tokens[start][0].isspace():
        start += 1
    while end > start and not tokens[end - 1][1] and \
            tokens[end - 1][0].isspace():
        end -= 1
    return tokens[start:end]


def _end(tokens):
    if not tokens:
        return 0
    return tokens[-1][2] + (2 if tokens[-1][1] else 1)


def _brackets(reserved):
    """
    The brackets with a meaning, the others are text.
    """
    return {opening: closing for opening, closing in BRACKETS.items()
            if opening in reserved}


def _closing(tokens, start, brackets=BRACKETS):
    """
    The index of the bracket closing the one at start, -1 if none.
    """
    stack = []
    for index in range(start, len(tokens)):
        token = tokens[index]
        if _is(token, brackets):
            stack.append(brackets[token[0]])
        elif _is(token, brackets.values()):
            if stack.pop() != token[0]:
                return -1
            if not stack:
                return index
    return -1


def _can_close(tokens, start, stack):
    stack = list(stack)
    for token in tokens[start:]:
        if _is(token, BRACKETS):
            stack.append(BRACKETS[token[0]])
        elif _is(token, ')]}') and stack and stack[-1] == token[0]:
            stack.pop()
            if not stack:
                return True
    return False


def split_items(tokens, tolerant=False, brackets=BRACKETS):
    """
    Splits at the semicolons outside brackets, returns the stripped items.
    In tolerant mode, as in ParserCharacters, a semicolon in a bracket
    which is not closed any more ends the item, so that an unbalanced
    bracket does not swallow the following items, and empty items are
    dropped.
    """
    items = []
    stack = []
    start = 0
    for index, token in enumerate(tokens):
        if _is(token, brackets):
            stack.append(brackets[token[0]])
        elif _is(token, brackets.values()):
            if stack and stack[-1] == token[0]:
                stack.pop()
            elif not tolerant:
                raise _syntax_error('unbalanced bracket', token[2], token[0])
        elif _is(token, ';') and (not stack or tolerant and not _can_close(
                tokens, index + 1, stack)):
            items.append((tokens[start:index], token[2]))
            start = index + 1
            stack = []
    if stack and not tolerant:
        raise _syntax_error('unbalanced bracket', _end(tokens))
    items.append((tokens[start:], _end(tokens)))
    result = []
    for item, end in items:
        item = _strip(item)
        if item:
            result.append(item)
        elif not tolerant and len(items) > 1:
            raise _syntax_error('empty item', end)
    return result


def _free_text_index(tokens):
    """
    The index of the ';;' starting the free text, -1 if there is none.
    """
    depth = 0
    for index, token in enumerate(tokens):
        if _is(token, BRACKETS):
            depth += 1
        elif _is(token, ')]}'):
            depth = max(depth - 1, 0)
        elif depth == 0 and _is(token, ';') and index + 1 < len(tokens) \
                and _is(tokens[index + 1], ';'):
            return index
    return -1


def split_free_text(tokens):
    """
    Returns the tokens of the items and the free text, None without.
    """
    index = _free_text_index(tokens)
    if index < 0:
        return tokens, None
    rest = tokens[index + 2:]
    if rest and _is(rest[0], ' '):
        rest = rest[1:]
    return tokens[:index], _text(rest)


@dataclass
class Item:
    sigil: str
    name: Ref
    # (kind, value, position): kind is a sigil kind with a Ref or None, or
    # 'text' with the tokens of the text
    qualifiers: list = field(default_factory=list)
    # the items in square brackets, None without brackets, and the number
    # of qualifiers before them
    children: list = None
    position: int = 0
    children_at: int = 0


QUALIFIER_SIGILS = (('&@', 'group_universe'), ('&&', 'group_name'),
                    ('&', 'group'), ('@', 'universe'))


def _check_escaped(tokens, reserved=RESERVED):
    for token in tokens:
        if _is(token, reserved):
            raise _syntax_error('unescaped reserved character', token[2],
                                token[0])


def _anchors_end(tokens, start, brackets=BRACKETS):
    """
    The index after the anchors starting at start.
    """
    end = start
    while end < len(tokens) and _is(tokens[end], '{'):
        close = _closing(tokens, end, brackets)
        if close < 0:
            raise _syntax_error('unbalanced bracket', tokens[end][2], '{')
        end = following = close + 1
        while following < len(tokens) and not tokens[following][1] and \
                tokens[following][0].isspace():
            following += 1
        if following < len(tokens) and _is(tokens[following], '{'):
            end = following
    return end


def parse_ref(tokens, position, empty=False, reserved=RESERVED):
    """
    A name with its anchors, None for no name if empty is allowed. Only
    the reserved characters need an escape.
    """
    tokens = _strip(tokens)
    brackets = _brackets(reserved)
    brace = next((index for index, token in enumerate(tokens)
                  if _is(token, '{')), -1)
    anchors = []
    if brace >= 0:
        if _anchors_end(tokens, brace, brackets) != len(tokens):
            raise _syntax_error('the anchor {...} must end the name',
                                tokens[brace][2], _text(tokens[brace:]))
        index = brace
        while index < len(tokens):
            if _is(tokens[index], '{'):
                close = _closing(tokens, index, brackets)
                anchors.append(tokens[index + 1:close])
                _check_escaped(anchors[-1], reserved)
                index = close
            index += 1
        if len(anchors) > 2:
            raise _syntax_error('more than two anchors', tokens[brace][2],
                                _text(tokens[brace:]))
        tokens = _strip(tokens[:brace])
    _check_escaped(tokens, reserved)
    label = _text(tokens)
    if not label:
        if empty and not anchors:
            return None
        raise _syntax_error('missing name', position)
    ref = Ref(label, position=tokens[0][2])
    if anchors:
        anchor = anchors[0]
        if anchor and _is(anchor[0], '#'):
            digits = _text(anchor[1:])
            if not digits.isdigit():
                raise _syntax_error('invalid id', anchor[0][2],
                                    _text(anchor))
            ref.id = int(digits)
        else:
            ref.disambiguation = _text(anchor)
    if len(anchors) == 2:
        ref.owner = _text(anchors[1])
        if not ref.owner:
            raise _syntax_error('empty anchor', position)
    return ref


def _qualifier(tokens, position, tolerant, sigils):
    tokens = _strip(tokens)
    if not tokens:
        raise _syntax_error('empty qualifier', position)
    for sigil, kind in QUALIFIER_SIGILS if sigils else ():
        if len(tokens) >= len(sigil) and all(
                _is(token, char) for token, char in zip(tokens, sigil)):
            return kind, parse_ref(tokens[len(sigil):],
                                   tokens[0][2] + len(sigil), empty=True)
    if not tolerant:
        _check_escaped(tokens)
    return 'text', tokens


def parse_item(tokens, tolerant=False, sigils=True):
    """
    Parses an item, the tokens are stripped and not empty.
    """
    position = tokens[0][2]
    sigil = ''
    if sigils and _is(tokens[0], SIGILS):
        sigil = tokens[0][0]
        tokens = tokens[1:]
    end = _anchors_end(tokens, next(
      (index for index, token in enumerate(tokens)
       if _is(token, '()[]{}')), len(tokens)))
    item = Item(sigil, parse_ref(tokens[:end], position + len(sigil)),
                position=position)
    index = end
    while index < len(tokens):
        token = tokens[index]
        if not token[1] and token[0].isspace():
            index += 1
            continue
        if _is(token, '(['):
            close = _closing(tokens, index)
            if close < 0:
                raise _syntax_error('unbalanced bracket', token[2], token[0])
            inner = tokens[index + 1:close]
            if token[0] == '(':
                kind, value = _qualifier(inner, token[2] + 1, tolerant,
                                         sigils)
                item.qualifiers.append((kind, value, token[2] + 1))
            else:
                if item.children is not None:
                    raise _syntax_error('second square bracket', token[2],
                                        _text(tokens[index:close + 1]))
                item.children = [parse_item(child, tolerant, sigils)
                                 for child in split_items(inner, tolerant)]
                item.children_at = len(item.qualifiers)
                if not item.children:
                    raise _syntax_error('empty square bracket', token[2])
            index = close + 1
            continue
        if _is(token, ')]}'):
            raise _syntax_error('unbalanced bracket', token[2], token[0])
        if _is(token, '{'):
            raise _syntax_error('the anchor {...} must follow the name',
                                token[2], _text(tokens[index:]))
        raise _syntax_error('text after the brackets', token[2],
                            _text(tokens[index:]))
    return item


def parse_items(text, tolerant=False, sigils=True):
    return [parse_item(item, tolerant, sigils)
            for item in split_items(tokens_of(text, tolerant=tolerant),
                                    tolerant)]


def _render_qualifier(kind, value):
    if kind == 'text':
        return escape(_text(value), keyword=not _plain(value))
    sigil = dict((kind, sigil) for sigil, kind in QUALIFIER_SIGILS)[kind]
    if value is None:
        return sigil
    return sigil + render_ref(value.label, value.disambiguation, value.id,
                              value.owner)


def render_item(item):
    """
    The canonical text of a parsed item.
    """
    parts = [' (%s)' % _render_qualifier(kind, value)
             for kind, value, position in item.qualifiers]
    if item.children is not None:
        parts.insert(item.children_at, ' [%s]' % '; '.join(
          render_item(child) for child in item.children))
    return item.sigil + render_ref(item.name.label, item.name.disambiguation,
                                   item.name.id, item.name.owner) + \
        ''.join(parts)


def canonical_text(text):
    """
    The canonical form of a characters text, as far as it can be read
    without the database: items which cannot be read are kept as written.
    """
    tokens = tokens_of(text, tolerant=True)
    tokens, free_text = split_free_text(tokens)
    parts = []
    for item in split_items(tokens, tolerant=True):
        try:
            parts.append(render_item(parse_item(item, tolerant=True)))
        except NotationError:
            parts.append(_raw(text, item))
    result = '; '.join(parts)
    if free_text is not None:
        result += (' ' if result else '') + FREE_TEXT_SEPARATOR + ' ' + \
                  escape_text(free_text)
    return result


# resolution

# models whose name belongs to another object with disambiguation and
# language
OWNERS = {CharacterNameDetail: 'character', GroupNameDetail: 'group',
          CreatorNameDetail: 'creator', FeatureNameDetail: 'feature'}


def _field_names(model):
    return {field.name for field in model._meta.get_fields()}


def _owner_model(model):
    if model in OWNERS:
        return model._meta.get_field(OWNERS[model]).related_model
    return model


def _owner_object(model, related):
    return getattr(related, OWNERS[model]) if model in OWNERS else related


def label_of(model, related):
    if model is Universe:
        return universe_label(related)
    return related.name


def disambiguation_of(model, related):
    return getattr(_owner_object(model, related), 'disambiguation', '')


# the official name of the owner of a name
OFFICIAL_NAMES = {CharacterNameDetail: 'name', GroupNameDetail: 'name',
                  CreatorNameDetail: 'gcd_official_name',
                  FeatureNameDetail: 'name'}


def official_name(model, related):
    return getattr(_owner_object(model, related), OFFICIAL_NAMES[model])


def _describe(model, candidate):
    owner = _owner_object(model, candidate)
    text = label_of(model, candidate)
    if getattr(owner, 'disambiguation', ''):
        text += ' {%s}' % owner.disambiguation
    details = ['#%d' % candidate.id]
    if 'language' in _field_names(type(owner)):
        details.insert(0, owner.language.code)
    return '%s (%s)' % (text, ', '.join(details))


def _raise_all(errors):
    unique = []
    for error in errors:
        if str(error) not in [str(known) for known in unique]:
            unique.append(error)
    if len(unique) == 1:
        raise unique[0]
    raise NotationError(unique[0].kind, '; '.join(
      str(error) for error in unique))


# objects used in the issues or sequences of a series
SERIES_SCOPES = {
  CharacterNameDetail: 'storycharacter__story__issue',
  GroupNameDetail: 'storygroup__story__issue',
  CreatorNameDetail: ('storycredit__story__issue', 'issuecredit__issue'),
  CreatorSignature: 'credits__story__issue',
  Brand: 'issue', IndiciaPublisher: 'issue', IndiciaPrinter: 'issue',
  Feature: 'story__issue', FeatureNameDetail: 'story__issue',
  FeatureLogo: 'story__issue', StoryArc: 'story__issue'}


def _series_links(model, series):
    """
    The links of the objects to the series, a credit, an appearance, a
    sequence or an issue, each as its model, the name of its field of the
    object and the filters of an active link of the series.
    """
    paths = SERIES_SCOPES[model]
    links = []
    for path in (paths,) if isinstance(paths, str) else paths:
        link, *rest = path.split('__')
        relation = model._meta.get_field(link)
        links.append((relation.related_model, relation.field.name,
                      {'__'.join(rest + ['series']): series,
                       'deleted': False}))
    return links


def feature_types(story_type):
    """
    The types of the features GCD allows for a type of sequence.
    """
    if story_type.id == STORY_TYPES['letters_page']:
        return [2]
    if story_type.id == STORY_TYPES['in-house column']:
        return [4]
    if story_type.id in (STORY_TYPES['ad'], STORY_TYPES['comics-form ad']):
        return [1, 3]
    return [1]


# The preferences of the fields, the same for reading and writing.

def issue_scopes(series):
    """
    The indicia publishers and brands of the publisher of the series.
    """
    publisher = series.publisher
    return {'indicia_publisher': {'parent': publisher},
            'brand_emblem': {'in_use__publisher': publisher}}


def story_scopes(story_type, feature_names=()):
    """
    The features of the types GCD allows for the type of the sequence, the
    logos of its features.
    """
    scopes = {}
    if story_type:
        types = feature_types(story_type)
        scopes = {'feature_object': {'feature_type__in': types},
                  'feature_name': {'feature__feature_type__in': types},
                  'feature_logo': [
                    {'feature_name__feature__feature_type__in': types}]}
    if feature_names:
        scopes.setdefault('feature_logo', []).insert(
          0, {'feature_name__in': list(feature_names)})
    return scopes


def signature_scope(creator, generic):
    """
    The signatures of the creator of the credit, generic or not.
    """
    scope = [{'generic': generic}]
    if creator:
        scope.insert(0, {'creator': creator.creator})
    return scope


def membership_scope(group_name):
    """
    The characters which are members of the group.
    """
    return {'character__memberships__group': group_name.group}


class Resolver:
    """
    Resolves references, given by name and disambiguation, to database
    objects. Without disambiguation the object without one is taken, or
    the only object of that name. Preferences narrow ambiguous candidates
    down, in order: scopes, filters such as the brands of the publisher,
    the language of the series, the name which is the official name of its
    owner, the names used in the series. Lookups are cached.
    """
    def __init__(self, language=None, series=None):
        self.language_id = getattr(language, 'id', language)
        self.series_id = getattr(series, 'id', series)
        self._by_id = defaultdict(dict)
        self._by_label = defaultdict(dict)
        self._roles = None
        self._universes = None
        self._universe_names = None
        self._scopes = {}

    def _queryset(self, model):
        queryset = model.objects.all()
        if 'deleted' in _field_names(model):
            queryset = queryset.filter(deleted=False)
        prefix = ''
        if model in OWNERS:
            prefix = OWNERS[model] + '__'
            queryset = queryset.filter(**{prefix + 'deleted': False})
            queryset = queryset.select_related(OWNERS[model])
        if 'language' in _field_names(_owner_model(model)):
            queryset = queryset.select_related(prefix + 'language')
        return queryset

    def _universe_index(self):
        if self._universes is None:
            self._universes = defaultdict(list)
            for universe in Universe.objects.filter(deleted=False):
                self._universes[universe_label(universe)].append(universe)
                self._by_id[Universe][universe.id] = universe
        return self._universes

    def universes_named(self, name, reference=None):
        """
        The universes with the name GCD shows, with or without multiverse,
        in any case, preferably of the multiverse of the reference universe.
        """
        if self._universe_names is None:
            # by lower case name
            self._universe_names = defaultdict(dict)
            for label, universes in self._universe_index().items():
                for universe in universes:
                    for text in (label, universe.universe_name(),
                                 universe.name, universe.designation):
                        if text:
                            self._universe_names[text.lower()][
                              universe.id] = universe
        candidates = list(self._universe_names.get(name.lower(), {}).values())
        if len(candidates) > 1 and reference:
            candidates = [universe for universe in candidates
                          if universe.verse_id == reference.verse_id] or \
                         candidates
        return candidates

    def universe_named(self, name, reference=None):
        candidates = self.universes_named(name, reference)
        return candidates[0] if len(candidates) == 1 else None

    def multiverse_universes(self, name, reference=None):
        """
        The universes of the multiverse of the name, the reference universe
        first.
        """
        universes = [universe for universes in self._universe_index().values()
                     for universe in universes
                     if universe.multiverse.lower() == name.lower()]
        return sorted(universes, key=lambda universe: (
          universe != reference, universe_label(universe)))

    def _by_object_id(self, model, object_id):
        if model is Universe:
            self._universe_index()
        if object_id not in self._by_id[model]:
            self._by_id[model][object_id] = self._queryset(model).filter(
              id=object_id).first()
        return self._by_id[model][object_id]

    def _candidates(self, model, label, ignore_case=False):
        """
        The objects of the name, with ignore_case, for text written by hand,
        those of the name in another case if none has it as written.
        """
        if model is Universe:
            return self._universe_index().get(label, [])
        if label not in self._by_label[model]:
            # the database comparison ignores case and trailing spaces
            self._by_label[model][label] = list(
              self._queryset(model).filter(name=label))
        found = self._by_label[model][label]
        exact = [related for related in found if related.name == label]
        if exact or not ignore_case:
            return exact
        return [related for related in found
                if related.name.lower() == label.lower()]

    def _in_scope(self, model, found, scope):
        key = (model, tuple(related.id for related in found),
               tuple(sorted((name, tuple(value) if isinstance(value, list)
                             else value) for name, value in scope.items())))
        if key not in self._scopes:
            self._scopes[key] = set(self._queryset(model).filter(
              id__in=[related.id for related in found], **scope)
              .values_list('id', flat=True))
        return [related for related in found if related.id in
                self._scopes[key]]

    def _linked(self, model, found, link, name, filters):
        """
        The objects with an active link to the series, queried from the
        links, which is much faster than from the objects.
        """
        key = (model, tuple(related.id for related in found), link, name)
        if key not in self._scopes:
            self._scopes[key] = set(link.objects.filter(
              **{name + '__in': [related.id for related in found]},
              **filters).order_by().values_list(name, flat=True))
        return [related for related in found if related.id in
                self._scopes[key]]

    def kind_of(self, ref, with_members=False, reference=None):
        """
        Whether a name without sigil, written by hand, is a group or a
        character, as GCD shows groups without members, or, with members,
        also a universe. Returns the kind and the universe. A name of more
        than one kind is ambiguous, the candidates are its readings; for the
        name of a multiverse the candidates are its universes.
        """
        universes, multiverse = [], False
        if with_members and ref.disambiguation is None and ref.id is None:
            universes = self.universes_named(ref.label, reference)
            if not universes:
                universes = self.multiverse_universes(ref.label,
                                                      reference)[:10]
                multiverse = bool(universes)
        kinds = ['universe'] if universes else []
        readings = ['@' + escape(universe_label(universe))
                    for universe in universes]
        for kind, model, sigil in (('group', GroupNameDetail, '&'),
                                   ('character', CharacterNameDetail, '')):
            if self._candidates(model, ref.label, ignore_case=True):
                kinds.append(kind)
                readings.append(sigil + render_ref(ref.label,
                                                   ref.disambiguation))
        if kinds == ['universe'] and multiverse:
            raise NotationError('not_found', 'a multiverse, not a universe',
                                ref.position, ref.label, readings)
        if len(readings) > 1:
            raise NotationError('ambiguous', 'ambiguous ' + ' or '.join(kinds),
                                ref.position, ref.label, readings)
        if kinds == ['universe']:
            return 'universe', universes[0]
        return (kinds or ['character'])[0], None

    def roles(self):
        # the roles by lower case name, keywords of the notation
        if self._roles is None:
            self._roles = {role.name.lower(): role
                           for role in CharacterRole.objects.all()}
        return self._roles

    def role_named(self, text):
        return self.roles().get(text.strip().lower())

    def role(self, name, position):
        role = self.role_named(name)
        if role is None:
            raise NotationError('invalid', 'unknown role', position, name,
                                sorted(self.roles()))
        return role

    def resolve_ref(self, model, ref, any_disambiguation=False, scope=()):
        """
        any_disambiguation is set for text written by hand as GCD shows it,
        which may also differ in case.
        """
        if ref is None:
            return None
        ignore_case = any_disambiguation
        has_disambiguation = 'disambiguation' in _field_names(
          _owner_model(model))
        if not has_disambiguation and ref.disambiguation:
            raise _syntax_error('no disambiguation for a %s' %
                                model._meta.verbose_name, ref.position,
                                ref.disambiguation)
        if ref.id is not None:
            related = self._by_object_id(model, ref.id)
            if related:
                return related
            # no valid id, use the name without disambiguation
            any_disambiguation = ref.disambiguation is None
        candidates = self._candidates(model, ref.label, ignore_case)
        found = candidates
        if ref.owner is not None:
            if model not in OWNERS:
                raise _syntax_error('no second anchor for a %s' %
                                    model._meta.verbose_name, ref.position,
                                    ref.owner)
            found = [related for related in found
                     if official_name(model, related) == ref.owner]
        if has_disambiguation and not any_disambiguation:
            if ref.disambiguation is None:
                found = [related for related in found
                         if not disambiguation_of(model, related)] or found
            else:
                found = [related for related in found
                         if disambiguation_of(model, related) ==
                         ref.disambiguation]
        for filters in [scope] if isinstance(scope, dict) else scope:
            if len(found) > 1:
                found = self._in_scope(model, found, filters) or found
        if len(found) > 1 and self.language_id:
            found = [related for related in found
                     if getattr(_owner_object(model, related), 'language_id',
                                None) == self.language_id] or found
        if ref.owner is None and model in OWNERS and len(found) > 1:
            # preferably the name which is the official name of its owner
            found = [related for related in found
                     if official_name(model, related) == ref.label] or found
        if self.series_id and model in SERIES_SCOPES:
            for link, name, filters in _series_links(model, self.series_id):
                if len(found) > 1:
                    found = self._linked(model, found, link, name,
                                         filters) or found
        if len(found) == 1:
            return found[0]
        if found:
            raise NotationError(
              'ambiguous', 'ambiguous %s' % model._meta.verbose_name,
              ref.position, ref.label,
              [_describe(model, related) for related in found])
        raise NotationError(
          'not_found', 'unknown %s' % model._meta.verbose_name, ref.position,
          ref.label, [_describe(model, related) for related in candidates])

    def reference(self, model, related, scope=(), reserved=RESERVED):
        """
        The shortest reference which resolves back to the object: its name
        with its disambiguation, else also with the official name of its
        owner. A duplicate which no name tells apart gets the first.
        """
        label = label_of(model, related)
        disambiguation = disambiguation_of(model, related)
        texts = [render_ref(label, disambiguation, reserved=reserved)]
        if model in OWNERS:
            texts.append(render_ref(label, disambiguation,
                                    owner=official_name(model, related),
                                    reserved=reserved))
        for text in texts:
            try:
                if self.resolve_ref(model, parse_ref(tokens_of(text), 0,
                                                     reserved=reserved),
                                    scope=scope) == related:
                    return text
            except NotationError:
                pass
        return texts[0]

    def resolve_group(self, entry, any_disambiguation=False):
        # universe -> group
        universe = self.resolve_ref(Universe, entry.universe)
        return {
          'group_name': self.resolve_ref(GroupNameDetail, entry.name,
                                         any_disambiguation),
          'universe': universe,
          'notes': entry.notes}

    def related_scope(self, labels):
        """
        The names of the characters which are an identity of a character of
        one of the names, as GCD shows them in square brackets, such as
        Two-Face [Harvey Dent].
        """
        key = ('related', tuple(sorted(labels)))
        if key not in self._scopes:
            named = set(self._queryset(CharacterNameDetail).filter(
              name__in=labels).values_list('character_id', flat=True))
            related = set()
            for first, second in CharacterRelation.objects.filter(
                  Q(from_character__in=named) | Q(to_character__in=named),
                  relation_type_id=IDENTITY_RELATION) \
                    .values_list('from_character_id', 'to_character_id'):
                related.add(second if first in named else first)
            self._scopes[key] = {'character__in': sorted(related)}
        return self._scopes[key]

    def resolve_appearance(self, entry, any_disambiguation=False):
        # universe -> group -> character
        universe = self.resolve_ref(Universe, entry.universe)
        if entry.group_universe is SAME:
            group_universe = universe
        else:
            group_universe = self.resolve_ref(Universe, entry.group_universe)
        groups = [self.resolve_ref(Group, ref, any_disambiguation)
                  for ref in entry.groups]
        group_names = [self.resolve_ref(GroupNameDetail, ref,
                                        any_disambiguation)
                       for ref in entry.group_names]
        scope = []
        if entry.member_of:
            group_name = self.resolve_ref(GroupNameDetail, entry.member_of,
                                          any_disambiguation)
            if 'group' in entry.member_links:
                groups.insert(0, group_name.group)
            if 'group_name' in entry.member_links:
                group_names.insert(0, group_name)
            scope.append(membership_scope(group_name))
        if entry.related:
            scope.append(self.related_scope(entry.related))
        return {
          'character': self.resolve_ref(CharacterNameDetail, entry.name,
                                        any_disambiguation, scope),
          'universe': universe,
          'group': groups,
          'group_name': group_names,
          'group_universe': group_universe,
          'role': self.role(entry.role, entry.position)
          if entry.role else None,
          'is_flashback': 'flashback' in entry.flags,
          'is_origin': 'origin' in entry.flags,
          'is_death': 'death' in entry.flags,
          'notes': entry.notes}

    def resolve(self, characters, any_disambiguation=False):
        """
        Returns the resolved groups and appearances, raises a NotationError
        with all failed references.
        """
        groups, appearances, errors = [], [], []
        for entry in characters.groups:
            try:
                groups.append(self.resolve_group(entry, any_disambiguation))
            except NotationError as error:
                errors.append(error)
        for entry in characters.appearances:
            try:
                appearances.append(self.resolve_appearance(
                  entry, any_disambiguation))
            except NotationError as error:
                errors.append(error)
        if errors:
            _raise_all(errors)
        return groups, appearances


# characters

class CharactersReader:
    """
    Reads parsed characters into the entries of the groups and appearances,
    inheriting the values down the tree.

    Strict for files: groups are marked with '&', universes with '@', and
    a missing universe is no universe. Tolerant for the free text of the
    editing form, which also reads characters as GCD shows them: an item
    without '&' is a group if its name is only the name of a group, an
    item with members at the top a universe if its name is only the name
    of a universe, a universe can be given by its name, and a missing
    universe is the reference universe of the sequence.
    """
    def __init__(self, resolver, tolerant=False, reference_universe=None):
        self.resolver = resolver
        self.tolerant = tolerant
        self.reference_universe = reference_universe
        self.reference = None
        if reference_universe:
            self.reference = Ref(universe_label(reference_universe),
                                 id=reference_universe.id)

    def read(self, items, characters=None):
        characters = characters or Characters()
        for item in items:
            self._item(item, self.reference, characters, top=True)
        return characters

    def _item(self, item, universe, characters, top=False):
        if item.sigil == '@':
            if not top or item.children is None or item.qualifiers or \
               item.name.disambiguation is not None or item.name.id:
                raise _syntax_error('a universe is written as '
                                    '"@multiverse: universe [...]" at the '
                                    'top', item.position, item.name.label)
            self._universe(item, Ref(item.name.label,
                                     position=item.name.position), characters)
            return
        kind = 'group' if item.sigil == '&' else 'character'
        if not item.sigil and self.tolerant:
            kind, found = self.resolver.kind_of(
              item.name, top and item.children is not None and
              not item.qualifiers, self.reference_universe)
            if kind == 'universe':
                self._universe(item, Ref(universe_label(found), id=found.id,
                                         position=item.name.position),
                               characters)
                return
        if kind == 'group':
            self._group(item, universe, characters)
        else:
            self._appearance(item, universe, characters)

    def _universe(self, item, ref, characters):
        for child in item.children:
            if child.sigil == '@':
                raise _syntax_error('a universe in a universe',
                                    child.position, child.name.label)
            self._item(child, ref, characters)

    def _classify(self, kind, value, position, is_group):
        """
        The kinds and values of a qualifier, a role and flags may share one.
        """
        if kind != 'text':
            if kind == 'group_universe' and value is None:
                value = SAME
            return [(kind, value)]
        text, plain = _text(value), _plain(value)
        if plain and not is_group:
            keywords = keywords_of(text, self.resolver.roles())
            if keywords:
                role, flags = keywords
                return ([('role', role.name)] if role else []) + \
                    ([('flags', flags)] if flags else [])
        if plain and self.tolerant:
            universe = self.resolver.universe_named(text,
                                                    self.reference_universe)
            if universe:
                return [('universe', Ref(universe_label(universe),
                                         id=universe.id, position=position))]
        return [('notes', text)]

    def _qualifiers(self, item, is_group):
        values = {}
        kinds = ('universe', 'group', 'group_name', 'notes') if is_group \
            else ('universe', 'group', 'group_name', 'group_universe',
                  'flags', 'role', 'notes')
        for qualifier_kind, qualifier, position in item.qualifiers:
            raw = _render_qualifier(qualifier_kind, qualifier)
            for kind, value in self._classify(qualifier_kind, qualifier,
                                              position, is_group):
                if kind not in kinds:
                    raise _syntax_error('qualifier not for a %s' % (
                                        'group' if is_group else 'character'),
                                        position, raw)
                if kind in ('group', 'group_name'):
                    if is_group != (value is None):
                        raise _syntax_error(
                          'a group links its members with "&" or "&&", a '
                          'character names its groups', position, raw)
                    if not is_group:
                        values.setdefault(kind + 's', []).append(value)
                        continue
                if kind in values:
                    raise _syntax_error('repeated qualifier', position, raw)
                values[kind] = value
        return values

    def _group(self, item, universe, characters):
        values = self._qualifiers(item, is_group=True)
        group_universe = values.get('universe', universe)
        links = tuple(link for link in LINKS if link in values)
        if links == ('group_name',):
            links = DEFAULT_LINKS
        characters.groups.append(GroupEntry(
          item.name, group_universe, values.get('notes', ''), item.position))
        for child in item.children or []:
            if child.sigil:
                raise _syntax_error('a group has only characters as '
                                    'members', child.position,
                                    child.sigil + child.name.label)
            member = self._appearance(child, group_universe, characters,
                                      group_universe)
            member.member_of = item.name
            member.member_links = links or DEFAULT_LINKS

    def _appearance(self, item, universe, characters, group_universe=None):
        values = self._qualifiers(item, is_group=False)
        entry = AppearanceEntry(
          item.name, universe=values.get('universe', universe),
          groups=values.get('groups', []),
          group_names=values.get('group_names', []),
          group_universe=values.get('group_universe', group_universe),
          role=values.get('role'), flags=values.get('flags', []),
          notes=values.get('notes', ''), position=item.position)
        characters.appearances.append(entry)
        # characters inside a character, e.g. its civilian identity
        for child in item.children or []:
            if child.sigil:
                raise _syntax_error('only characters inside a character',
                                    child.position,
                                    child.sigil + child.name.label)
            inside = self._appearance(child, entry.universe, characters)
            entry.related.append(child.name.label)
            inside.related.append(item.name.label)
        return entry


def read_characters(text, resolver):
    """
    Reads the characters of a file, raises NotationError.
    """
    tokens, free_text = split_free_text(tokens_of(text))
    items = [parse_item(item) for item in split_items(tokens)]
    characters = CharactersReader(resolver).read(items)
    characters.free_text = free_text or ''
    return characters


def _same(first, second):
    return (first.id if first else None) == (second.id if second else None)


@dataclass
class GroupRow:
    group_name: object
    universe: object
    notes: str


@dataclass
class AppearanceRow:
    character: object
    universe: object
    groups: list
    group_names: list
    group_universe: object
    role: object
    flags: list
    notes: str


def story_rows(story):
    """
    The groups and appearances of a sequence or of its revision, in the
    order of their creation.
    """
    groups = [GroupRow(group.group_name, group.universe, group.notes)
              for group in _sorted(story.active_groups.select_related(
                'group_name__group', 'universe'))]
    appearances = [
      AppearanceRow(appearance.character, appearance.universe,
                    _sorted(appearance.group.all()),
                    _sorted(appearance.group_name.all()),
                    appearance.group_universe, appearance.role,
                    _flags(appearance), appearance.notes)
      for appearance in _sorted(
        story.active_characters.select_related(
          'character__character', 'universe', 'group_universe', 'role')
        .prefetch_related('group', 'group_name__group'))]
    return groups, appearances


def resolved_rows(groups, appearances):
    return (
      [GroupRow(values['group_name'], values['universe'], values['notes'])
       for values in groups],
      [AppearanceRow(values['character'], values['universe'],
                     _sorted(values['group']), _sorted(values['group_name']),
                     values['group_universe'], values['role'],
                     [flag for flag in FLAGS if values['is_' + flag]],
                     values['notes'])
       for values in appearances])


def _links(group, row):
    links = []
    if any(related.id == group.group_name.group_id for related in row.groups):
        links.append('group')
    if any(related.id == group.group_name.id for related in row.group_names):
        links.append('group_name')
    return tuple(links)


def _members(group_rows, appearance_rows):
    """
    The members of each group of the sequence, the appearances linked to
    the group in the universe of the group, and how they are linked: as
    most of them are, with the others linked in more ways.
    """
    assigned = set()
    members = []
    for group in group_rows:
        candidates = [(number, _links(group, row))
                      for number, row in enumerate(appearance_rows)
                      if number not in assigned and
                      _same(row.group_universe, group.universe)]
        candidates = [(number, links) for number, links in candidates
                      if links]
        counts = Counter(links for number, links in candidates)
        links = max(LINK_PATTERNS, key=lambda pattern: (
          counts[pattern], -LINK_PATTERNS.index(pattern)))
        numbers = [number for number, found in candidates
                   if set(links) <= set(found)]
        assigned.update(numbers)
        members.append((links, numbers))
    return members


def keywords_of(text, roles):
    """
    The role and the flags of a qualifier written with keywords only, such
    as 'cameo', 'origin, death' or 'villain death', None for a note.
    """
    text = text.strip().lower()
    if text in roles:
        return roles[text], []
    words = [word for word in re.split(r'[\s,]+', text) if word]
    found = [roles[word] for word in words if word in roles]
    flags = [word for word in words if word in FLAGS]
    if not words or len(found) + len(flags) != len(words) or \
       len(found) > 1 or len(set(flags)) != len(flags):
        return None
    return (found[0] if found else None), flags


def _reads_as_keyword(text, roles):
    return keywords_of(text, roles) is not None


def _render_universe(universe):
    return escape(universe_label(universe)) if universe else ''


def _render_appearance(row, universe, resolver, membership=None):
    qualifiers = []
    if not _same(row.universe, universe):
        qualifiers.append('@' + _render_universe(row.universe))
    groups, group_names = row.groups, row.group_names
    if membership:
        group, links = membership
        if 'group' in links:
            groups = [related for related in groups
                      if related.id != group.group_name.group_id]
        if 'group_name' in links:
            group_names = [related for related in group_names
                           if related.id != group.group_name.id]
    qualifiers += ['&' + resolver.reference(Group, related)
                   for related in groups]
    qualifiers += ['&&' + resolver.reference(GroupNameDetail, related)
                   for related in group_names]
    if membership is None and row.group_universe:
        qualifiers.append('&@' + ('' if _same(row.group_universe,
                                              row.universe)
                                  else _render_universe(row.group_universe)))
    if row.flags:
        qualifiers.append(', '.join(row.flags))
    if row.role:
        qualifiers.append(row.role.name)
    if row.notes:
        qualifiers.append(escape(row.notes, keyword=_reads_as_keyword(
          row.notes, resolver.roles())))
    scope = membership_scope(membership[0].group_name) if membership else ()
    return resolver.reference(CharacterNameDetail, row.character, scope) + \
        ''.join(' (%s)' % qualifier for qualifier in qualifiers)


def _render_group(group, links, members, resolver):
    text = '&' + resolver.reference(GroupNameDetail, group.group_name)
    if 'group' in links:
        text += ' (&)'
    if links == LINKS:
        text += ' (&&)'
    if group.notes:
        text += ' (%s)' % escape(group.notes)
    if members:
        text += ' [%s]' % '; '.join(
          _render_appearance(row, group.universe, resolver, (group, links))
          for row in members)
    return text


def _universe_key(universe):
    return universe_label(universe) if universe else ''


def _group_key(row):
    name = row.group_name
    return (name.sort_name, name.name, name.group.disambiguation,
            name.group.name, _universe_key(row.universe), row.notes)


def _appearance_key(row):
    name = row.character
    return (name.sort_name, name.name, name.character.disambiguation,
            name.character.name, _universe_key(row.universe),
            _universe_key(row.group_universe),
            [(related.name, related.disambiguation) for related in row.groups],
            [(related.name, related.group.disambiguation)
             for related in row.group_names],
            row.role.name if row.role else '', row.flags, row.notes)


def render_characters(resolver, group_rows, appearance_rows, free_text=''):
    """
    The characters as text: the items of each universe, groups with their
    members and then the other characters, each by sort name as GCD shows
    them. The order depends only on the data, not on the order of creation,
    so that the same data gives the same text. The names are the shortest
    ones which the resolver, of the series, reads back.
    """
    group_rows = sorted(group_rows, key=_group_key)
    appearance_rows = sorted(appearance_rows, key=_appearance_key)
    members = _members(group_rows, appearance_rows)
    assigned = {number for links, numbers in members for number in numbers}
    blocks = defaultdict(list)
    universes = {}
    for group, (links, numbers) in zip(group_rows, members):
        key = group.universe.id if group.universe else None
        universes[key] = group.universe
        blocks[key].append(_render_group(
          group, links, [appearance_rows[number] for number in numbers],
          resolver))
    for number, row in enumerate(appearance_rows):
        if number not in assigned:
            key = row.universe.id if row.universe else None
            universes[key] = row.universe
            blocks[key].append(_render_appearance(row, row.universe,
                                                  resolver))
    items = []
    for key in sorted(blocks, key=lambda key: (
          key is not None, universe_label(universes[key]) if key else '',
          key or 0)):
        if key is None:
            items += blocks[key]
        else:
            items.append('@%s [%s]' % (_render_universe(universes[key]),
                                       '; '.join(blocks[key])))
    text = '; '.join(items)
    if free_text:
        text += (' ' if text else '') + FREE_TEXT_SEPARATOR + ' ' + \
                escape_text(free_text)
    return text


def characters_text(story, resolver=None):
    """
    The characters of a sequence as text, with what the migration converts
    of its free text, so that an import migrates it; what the migration
    cannot convert stays free text.
    """
    if resolver is None:
        series = story.issue.series
        resolver = Resolver(series.language, series)
    group_rows, appearance_rows = story_rows(story)
    free_text = story.characters
    if free_text:
        universes = list(story.universe.all())
        groups, appearances, free_text, errors, unresolved = migrate_text(
          free_text, resolver, plain_names=True,
          reference_universe=universes[0] if len(universes) == 1 else None)
        migrated_groups, migrated_appearances = resolved_rows(groups,
                                                              appearances)
        group_rows += migrated_groups
        appearance_rows += migrated_appearances
    return render_characters(resolver, group_rows, appearance_rows,
                             free_text)


def create_revisions(story_revision, groups, appearances):
    from apps.oi.models import StoryCharacterRevision, StoryGroupRevision
    for values in groups:
        StoryGroupRevision.objects.create(
          changeset=story_revision.changeset, story_revision=story_revision,
          **values)
    for values in appearances:
        values = dict(values)
        group = values.pop('group')
        group_name = values.pop('group_name')
        revision = StoryCharacterRevision.objects.create(
          changeset=story_revision.changeset, story_revision=story_revision,
          **values)
        revision.group.set(group)
        revision.group_name.set(group_name)


# the text field of the editing form

def _is_notation(tokens):
    """
    Whether an item uses what only the notation has: a sigil, an anchor
    or an escape.
    """
    if _is(tokens[0], SIGILS) or any(token[1] or _is(token, '{')
                                     for token in tokens):
        return True
    for index, token in enumerate(tokens):
        if _is(token, '('):
            rest = _strip(tokens[index + 1:])
            if rest and _is(rest[0], SIGILS):
                return True
    return False


def migrate_text(text, resolver, plain_names=False, reference_universe=None):
    """
    Converts the resolvable items of the free text of the characters field.
    Items written in the notation are always converted and must resolve,
    other items, read as GCD shows characters, if plain_names is set. An
    item is converted completely or stays text, so that converting the
    remaining text again changes nothing.

    Returns the resolved groups and appearances, the remaining free text,
    the errors of the items written in the notation, and why the other
    items stayed text, such as an unknown or ambiguous name.
    """
    groups, appearances, errors, remaining, unresolved = [], [], [], [], []
    tokens = tokens_of(text, tolerant=True)
    if _free_text_index(tokens) >= 0:
        # the field is written in the notation
        try:
            characters = read_characters(text, resolver)
            groups, appearances = resolver.resolve(characters)
            return groups, appearances, characters.free_text, [], []
        except NotationError as error:
            return [], [], text, [error], []
    strict = CharactersReader(resolver)
    tolerant = CharactersReader(resolver, tolerant=True,
                                reference_universe=reference_universe)
    for item in split_items(tokens, tolerant=True):
        raw = _raw(text, item)
        notation = _is_notation(item)
        if not notation and not plain_names:
            remaining.append(raw)
            continue
        try:
            if notation:
                characters = strict.read([parse_item(
                  tokens_of(raw, item[0][2]))])
                item_groups, item_appearances = resolver.resolve(characters)
            else:
                characters = tolerant.read([parse_item(item, tolerant=True)])
                item_groups, item_appearances = resolver.resolve(
                  characters, any_disambiguation=True)
            groups += item_groups
            appearances += item_appearances
        except NotationError as error:
            (errors if notation else unresolved).append(error)
            remaining.append(raw)
    return groups, appearances, '; '.join(remaining), errors, unresolved


def check_text(text, resolver, reference_universe=None):
    """
    Checks the characters field while it is typed: the brackets, the
    separators and the escapes, then the items as the migration reads them.
    Returns the problems and the text which the migration would save.
    """
    problems = []
    try:
        tokens, free_text = split_free_text(tokens_of(text))
        split_items(tokens)
    except NotationError as error:
        problems.append(error)
    groups, appearances, remaining, errors, unresolved = migrate_text(
      text, resolver, plain_names=True, reference_universe=reference_universe)
    for error in errors + unresolved:
        if str(error) not in [str(problem) for problem in problems]:
            problems.append(error)
    return problems, render_characters(
      resolver, *resolved_rows(groups, appearances), remaining)


# issue records
#
# An issue with its sequences is a record with the same fields in all four
# formats: CSV and TSV write it as rows below a header row, one row for the
# issue and one for each sequence, JSON and YAML as a mapping with the
# sequences in story_set. Empty values are left out.
#
# A credit is written as
#
#   creator [anchor] (credit type) (credited, signed, uncertain, sourced)
#     (as: name) (signed as: name) (signature: name) (source: text)
#     (credit name)
#
# the credit type and the flags as keywords, the others by their key, a
# generic signature as (generic signature: name).

ISSUE_FIELDS = [
  'number', 'title', 'no_title', 'volume', 'no_volume', 'volume_not_printed',
  'display_volume_with_number', 'variant_of', 'variant_name',
  'variant_cover_status', 'isbn', 'no_isbn', 'barcode', 'no_barcode',
  'rating', 'no_rating', 'publication_date', 'key_date', 'on_sale_date',
  'on_sale_date_uncertain', 'indicia_frequency', 'no_indicia_frequency',
  'price', 'page_count', 'page_count_uncertain', 'editing', 'no_editing',
  'indicia_publisher', 'indicia_pub_not_printed', 'brand_emblem', 'no_brand',
  'indicia_printer', 'indicia_printer_not_printed',
  'indicia_printer_sourced_by', 'notes', 'keywords', 'credits']
STORY_FIELDS = [
  'title', 'title_inferred', 'first_line', 'type', 'feature',
  'feature_object', 'feature_name', 'feature_logo', 'page_count',
  'page_count_uncertain', 'script', 'pencils', 'inks', 'colors', 'letters',
  'editing', 'no_script', 'no_pencils', 'no_inks', 'no_colors',
  'no_letters', 'no_editing', 'job_number', 'genre', 'story_arc',
  'universe', 'characters', 'synopsis', 'reprint_notes', 'notes',
  'keywords', 'credits']
RECORD = 'record'
COLUMNS = [RECORD] + ISSUE_FIELDS + [name for name in STORY_FIELDS
                                     if name not in ISSUE_FIELDS]
CREDIT_FIELDS = ['creator', 'credit_type', 'is_credited', 'is_signed',
                 'signature', 'uncertain', 'credited_as', 'signed_as',
                 'is_sourced', 'sourced_by', 'credit_name']
ISSUE_CREDIT_FIELDS = [name for name in CREDIT_FIELDS
                       if name not in ('is_signed', 'signature', 'signed_as')]
CREDIT_FLAGS = {'credited': 'is_credited', 'signed': 'is_signed',
                'uncertain': 'uncertain', 'sourced': 'is_sourced'}
CREDIT_KEYS = {'as: ': 'credited_as', 'signed as: ': 'signed_as',
               'signature: ': 'signature', 'generic signature: ': 'signature',
               'source: ': 'sourced_by'}
GENERIC_SIGNATURE = 'generic signature: '
YES = 'yes'
DEFAULT_VARIANT_COVER_STATUS = 'ARTWORK_DIFFERENCE'


def _ref_models():
    from apps.gcd.models import (Brand, CreatorSignature, CreditType, Feature,
                                 FeatureLogo, IndiciaPrinter,
                                 IndiciaPublisher, StoryArc, StoryType)
    return {'indicia_publisher': IndiciaPublisher, 'brand_emblem': Brand,
            'indicia_printer': IndiciaPrinter, 'type': StoryType,
            'feature_object': Feature, 'feature_name': FeatureNameDetail,
            'feature_logo': FeatureLogo, 'story_arc': StoryArc,
            'universe': Universe, 'creator': CreatorNameDetail,
            'credit_type': CreditType, 'signature': CreatorSignature}


SINGLE_REFS = {'indicia_publisher', 'type'}
MULTI_REFS = {'brand_emblem', 'indicia_printer', 'feature_object',
              'feature_name', 'feature_logo', 'story_arc', 'universe'}
# values in the notation, the same text in all formats
NOTATION_FIELDS = SINGLE_REFS | MULTI_REFS | {'credits', 'characters'}


def _reserved(name):
    """
    The reserved characters of the references of a field.
    """
    if name in MULTI_REFS:
        return LIST_RESERVED
    if name in SINGLE_REFS:
        return REF_RESERVED
    return RESERVED


def _boolean_fields():
    from apps.oi.models import IssueRevision, StoryRevision
    from django.db.models import BooleanField
    return {name for revision_class in (IssueRevision, StoryRevision)
            for name, field in
            revision_class._get_single_value_fields().items()
            if isinstance(field, BooleanField)} | set(CREDIT_FLAGS.values())


def _decimal_text(value):
    return None if value is None else '{:f}'.format(value.normalize())


def _credit_types():
    from apps.gcd.models import CreditType
    return {name.lower(): name
            for name in CreditType.objects.values_list('name', flat=True)}


def _reads_as_credit_keyword(text, credit_types):
    flags = [flag.strip().lower() for flag in text.split(',')]
    return text.strip().lower() in credit_types or \
        (all(flag in CREDIT_FLAGS for flag in flags) and
         len(set(flags)) == len(flags)) or text.startswith(tuple(CREDIT_KEYS))


def unused_fields(series):
    """
    The issue fields which the series does not use, GCD neither shows nor
    saves them.
    """
    from apps.oi.models import IssueRevision
    return {name for name, path in
            IssueRevision._get_conditional_field_tuple_mapping().items()
            if not reduce(getattr, path[1:], series)}


def _sparse(data):
    """
    Leaves out empty values, a missing key stands for the empty value.
    """
    for key in [key for key, value in data.items()
                if value is None or value is False or value in ('', [], {})]:
        del data[key]
    return data


class RecordWriter:
    """
    Writes the records of the issues of a series, values as in a JSON or
    YAML file. Each reference is the shortest one which the RecordImporter
    of the series resolves back to the object.
    """
    def __init__(self, series):
        self.series = series
        self.resolver = Resolver(series.language, series)
        self.models = _ref_models()
        self._credit_types = None

    def credit_types(self):
        if self._credit_types is None:
            self._credit_types = _credit_types()
        return self._credit_types

    def _ref(self, name, related, scope=()):
        return self.resolver.reference(self.models[name], related, scope,
                                       _reserved(name))

    def _credit(self, credit, fields):
        qualifiers = [credit.credit_type.name]
        flags = [flag for flag, name in CREDIT_FLAGS.items()
                 if name in fields and getattr(credit, name)]
        if flags:
            qualifiers.append(', '.join(flags))
        for key, name in CREDIT_KEYS.items():
            value = getattr(credit, name, None) if name in fields else None
            if name == 'signature' and value:
                if value.generic != (key == GENERIC_SIGNATURE):
                    continue
                value = value.name
            if value:
                qualifiers.append(key + escape(value))
        if credit.credit_name:
            qualifiers.append(escape(credit.credit_name,
                                     keyword=_reads_as_credit_keyword(
                                       credit.credit_name,
                                       self.credit_types())))
        return self._ref('creator', credit.creator) + \
            ''.join(' (%s)' % qualifier for qualifier in qualifiers)

    def _record(self, data_object, fields, credits, credit_fields, revision,
                scopes, unused=()):
        from apps.oi.models import get_keywords, on_sale_date_as_string
        record = {}
        for name in fields:
            if name in unused:
                continue
            if name == 'credits':
                # as GCD shows them, by credit type, and in an order which
                # depends only on the data
                value = '; '.join(text for sort_code, text in sorted(
                  (credit.credit_type.sort_code,
                   self._credit(credit, credit_fields))
                  for credit in credits))
            elif name == 'characters':
                value = characters_text(data_object, self.resolver)
            elif name == 'keywords':
                value = data_object.keywords if revision \
                        else get_keywords(data_object)
            elif name == 'on_sale_date':
                value = on_sale_date_as_string(data_object) if revision \
                        else data_object.on_sale_date
            elif name == 'variant_of':
                value = data_object.variant_of.number \
                        if data_object.variant_of else None
            elif name == 'variant_cover_status':
                from apps.gcd.models import VCS_Codes
                value = VCS_Codes(data_object.variant_cover_status).name
                if value == DEFAULT_VARIANT_COVER_STATUS:
                    value = None
            elif name in MULTI_REFS:
                value = '; '.join(
                  self._ref(name, related, scopes.get(name, ()))
                  for related in _sorted(getattr(data_object, name).all()))
            elif name in SINGLE_REFS:
                related = getattr(data_object, name)
                value = self._ref(name, related, scopes.get(name, ())) \
                    if related else None
            elif name == 'page_count':
                value = _decimal_text(data_object.page_count)
            else:
                value = getattr(data_object, name)
            record[name] = value
        return _sparse(record)

    def issue(self, issue, revision=False):
        """
        The record of the issue with its sequences.
        """
        if revision:
            credits = issue.issue_credit_revisions.filter(deleted=False)
            stories = [(story, story.story_credit_revisions.filter(
                         deleted=False)) for story in issue.active_stories()]
        else:
            credits = issue.active_credits
            stories = [(story, story.active_credits.select_related(
                         'credit_type')) for story in
                       issue.active_stories().select_related('type')
                       .prefetch_related('feature_object', 'feature_name',
                                         'feature_logo', 'story_arc',
                                         'universe')
                       .order_by('sequence_number')]
        # the record tells this format from format 1.0 in JSON and YAML
        record = {RECORD: 'issue', **self._record(
          issue, ISSUE_FIELDS, credits, ISSUE_CREDIT_FIELDS, revision,
          issue_scopes(self.series), unused_fields(self.series))}
        record['story_set'] = [
          self._record(story, STORY_FIELDS, story_credits, CREDIT_FIELDS,
                       revision, story_scopes(story.type,
                                              story.feature_name.all()))
          for story, story_credits in stories]
        return record


def issue_record(issue, revision=False):
    """
    The issue with its sequences, values as in a JSON or YAML file.
    """
    return RecordWriter(issue.series).issue(issue, revision)


def _cell(name, value):
    if value is True:
        return YES
    if name in NOTATION_FIELDS or name == 'page_count':
        return value
    return escape_text(str(value))


def flat_rows(record):
    """
    Header row and rows of an issue for CSV and TSV, only with the columns
    in use.
    """
    records = [('issue', record)] + [('sequence', story)
                                     for story in record['story_set']]
    columns = [column for column in COLUMNS[1:]
               if any(column in values for kind, values in records)]
    return [[RECORD] + columns] + [
      [kind] + [_cell(column, values[column]) if column in values else ''
                for column in columns]
      for kind, values in records]


# decoding of records, values are checked and references parsed, the
# resolution happens when the revisions are created

@dataclass
class CreditEntry:
    creator: Ref
    credit_type: Ref
    values: dict
    signature: Ref = None
    position: object = None
    generic_signature: bool = False


def _expect(value, kinds, path):
    if not isinstance(value, kinds):
        raise _syntax_error('unexpected value', path, repr(value))
    return value


def _located(ref, path):
    if ref is not None and not isinstance(ref.position, str):
        ref.position = '%s, position %d' % (path, (ref.position or 0) + 1)
    return ref


def _relocate(characters, path):
    for entry in characters.groups + characters.appearances:
        refs = [entry, entry.name, entry.universe]
        if isinstance(entry, AppearanceEntry):
            refs += entry.groups + entry.group_names + [entry.member_of]
            if entry.group_universe is not SAME:
                refs.append(entry.group_universe)
        for ref in refs:
            _located(ref, path)


class RecordDecoder:
    """
    Turns the raw values of a record into checked values and references.
    CSV and TSV cells are text, JSON and YAML values text or booleans.
    """
    def __init__(self, flat):
        self.flat = flat
        self.booleans = _boolean_fields()
        self.models = _ref_models()
        # roles and credit types are keywords of the notation
        self.resolver = Resolver()
        self.credit_types = _credit_types()

    def _boolean(self, value, path):
        if value in (None, '', 'no', False):
            return False
        if value in (YES, True):
            return True
        raise NotationError('invalid', 'expected "yes", "no" or empty',
                            path, str(value))

    def _string(self, value, path):
        if value is None:
            return ''
        if not self.flat and isinstance(value, (int, float)) and \
           not isinstance(value, bool):
            return str(value)
        value = _expect(value, str, path)
        return unescape_text(value, path) if self.flat else value

    def _refs(self, value):
        return [parse_ref(item, item[0][2], reserved=LIST_RESERVED)
                for item in split_items(tokens_of(value),
                                        brackets=_brackets(LIST_RESERVED))]

    def _credit(self, tokens):
        item = parse_item(tokens, sigils=False)
        if item.children is not None:
            raise _syntax_error('a credit has no square brackets',
                                item.position)
        entry = CreditEntry(item.name, None, {}, position=item.position)
        for kind, value, position in item.qualifiers:
            text, plain = _text(value), _plain(value)
            flags = [flag.strip().lower() for flag in text.split(',')]
            name = None
            if plain and text.strip().lower() in self.credit_types:
                if entry.credit_type:
                    raise _syntax_error('repeated credit type', position,
                                        text)
                entry.credit_type = Ref(
                  self.credit_types[text.strip().lower()], position=position)
                continue
            if plain and all(flag in CREDIT_FLAGS for flag in flags):
                for flag in flags:
                    if CREDIT_FLAGS[flag] in entry.values:
                        raise _syntax_error('repeated flag', position, flag)
                    entry.values[CREDIT_FLAGS[flag]] = True
                continue
            for key, key_name in CREDIT_KEYS.items():
                if len(value) > len(key) and all(
                     _is(token, char) for token, char in zip(value, key)):
                    name, text = key_name, _text(value[len(key):])
                    break
            else:
                name = 'credit_name'
            if name in entry.values or (name == 'signature' and
                                        entry.signature):
                raise _syntax_error('repeated qualifier', position, text)
            if name == 'signature':
                entry.signature = Ref(text, position=position + len(key))
                entry.generic_signature = key == GENERIC_SIGNATURE
            else:
                entry.values[name] = text
        if not entry.credit_type:
            raise NotationError('invalid', 'missing credit type',
                                entry.position, item.name.label,
                                sorted(self.credit_types.values()))
        return entry

    def _credits(self, value, fields, path):
        entries = []
        for item in split_items(tokens_of(value)):
            entry = self._credit(item)
            for ref in (entry.creator, entry.credit_type, entry.signature):
                _located(ref, path)
            for name in entry.values:
                if name not in fields:
                    raise NotationError('invalid', 'not for this credit',
                                        path, name)
            if entry.signature and 'signature' not in fields:
                raise NotationError('invalid', 'not for this credit', path,
                                    'signature')
            entry.position = '%s, position %d' % (path, item[0][2] + 1)
            entries.append(entry)
        return entries

    def decode(self, raw, fields, credit_fields, path):
        """
        Raw values of a record, keyed by field name.
        """
        if not self.flat:
            _expect(raw, dict, path)
            unknown = set(raw) - set(fields + ['story_set'])
            if unknown:
                raise _syntax_error('unknown key', path,
                                    ', '.join(sorted(unknown)))
        values = {}
        for name in fields:
            value = raw.get(name)
            field_path = '%s, column %s' % (path, name) if self.flat \
                else '%s.%s' % (path, name)
            try:
                values[name] = self._value(name, value, credit_fields,
                                           field_path)
            except NotationError as error:
                # positions inside a value are offsets
                if not isinstance(error.position, str):
                    error.position = '%s, position %d' % (
                      field_path, (error.position or 0) + 1)
                raise
        return values

    def _value(self, name, value, credit_fields, path):
        if name in self.booleans:
            return self._boolean(value, path)
        if name in NOTATION_FIELDS:
            value = _expect('' if value is None else value, str, path)
        if name == 'credits':
            return self._credits(value, credit_fields, path)
        if name == 'characters':
            tokens, free_text = split_free_text(tokens_of(value))
            characters = CharactersReader(self.resolver).read(
              [parse_item(item) for item in split_items(tokens)])
            characters.free_text = free_text or ''
            _relocate(characters, path)
            return characters
        if name in MULTI_REFS:
            return [_located(ref, path) for ref in self._refs(value)]
        if name in SINGLE_REFS:
            if not value:
                return None
            return _located(parse_ref(tokens_of(value), 0,
                                      reserved=REF_RESERVED), path)
        if name == 'page_count':
            return _decimal(value, path)
        return self._string(value, path)


def _decimal(value, path):
    if value in (None, ''):
        return None
    try:
        return Decimal(str(_expect(value, (str, int, float), path)))
    except InvalidOperation:
        raise NotationError('invalid', 'not a number', path, str(value))


# Format 1.0, the files of GCD before this record, read as GCD read them.
# Flat files have no header row and their columns in this order, JSON and
# YAML the same names, an issue without the key 'record'. Credits, feature
# and characters are text, 'None' marks a missing value, a title in square
# brackets is inferred, a '?' marks an uncertain page count or on-sale date.

LEGACY_ISSUE_FIELDS = [
  'number', 'volume', 'indicia_publisher', 'brand_emblem',
  'publication_date', 'key_date', 'indicia_frequency', 'price', 'page_count',
  'editing', 'isbn', 'notes', 'barcode', 'on_sale_date', 'title',
  'indicia_printer', 'rating', 'reprint_notes', 'keywords', 'variant_name',
  'variant_cover_status']
LEGACY_STORY_FIELDS = [
  'title', 'type', 'feature', 'page_count', 'script', 'pencils', 'inks',
  'colors', 'letters', 'editing', 'genre', 'characters', 'job_number',
  'reprint_notes', 'synopsis', 'notes', 'keywords', 'first_line']
LEGACY_CREDITS = ['script', 'pencils', 'inks', 'colors', 'letters',
                  'editing']
# the number of cells of a row, a variant in a series has two more
LEGACY_CELLS = {'issue': tuple(range(10, 20)),
                'sequence': tuple(range(10, 19))}
LEGACY_VARIANT_CELLS = (21,)
# the values of an issue which a file of format 1.0 sets
LEGACY_ISSUE_VALUES = {
  'number', 'volume', 'no_volume', 'indicia_publisher',
  'indicia_pub_not_printed', 'no_brand', 'publication_date', 'key_date',
  'indicia_frequency', 'no_indicia_frequency', 'price', 'page_count',
  'page_count_uncertain', 'editing', 'no_editing', 'isbn', 'no_isbn',
  'notes', 'barcode', 'no_barcode', 'year_on_sale', 'month_on_sale',
  'day_on_sale', 'on_sale_date_uncertain', 'title', 'no_title',
  'indicia_printer_not_printed', 'rating', 'no_rating', 'keywords'}


def _legacy_page_count(text):
    """
    The page count and whether it is uncertain.
    """
    uncertain = '?' in text
    text = text.split('?')[0].strip()
    try:
        Decimal(text)
    except InvalidOperation:
        return '', True
    return text, uncertain


def is_legacy(issue, stories):
    """
    Whether an issue of a JSON or YAML file is of format 1.0.
    """
    return RECORD not in issue and \
        set(issue) <= set(LEGACY_ISSUE_FIELDS + ['story_set']) and \
        all(isinstance(story, dict) and set(story) <= set(LEGACY_STORY_FIELDS)
            for story in stories)


def legacy_values(raw, kind, flat):
    """
    The values of an issue or a sequence of format 1.0 as raw values of
    this record, those of a flat file as its cells.
    """
    raw = {name: '' if value is None else str(value).strip()
           for name, value in raw.items()}
    yes = YES if flat else True
    text = escape_text if flat else str
    values = {}

    def missing(name, value):
        if value.lower() == 'none':
            values['no_' + name] = yes
            return True
        return False

    page_count, uncertain = _legacy_page_count(raw.get('page_count', ''))
    values['page_count'] = page_count
    if kind == 'issue':
        for name in ('number', 'publication_date', 'price', 'notes',
                     'keywords', 'volume'):
            values[name] = text(raw.get(name, ''))
        if not raw.get('volume'):
            values['no_volume'] = yes
        for name in ('indicia_frequency', 'editing', 'isbn', 'barcode',
                     'rating', 'title'):
            if not missing(name, raw.get(name, '')):
                values[name] = text(raw.get(name, ''))
        publisher = raw.get('indicia_publisher', '')
        if publisher.lower() == 'none':
            values['indicia_pub_not_printed'] = yes
        else:
            values['indicia_publisher'] = escape(publisher,
                                                 reserved=REF_RESERVED)
        for name, flag in (('brand_emblem', 'no_brand'),
                           ('indicia_printer', 'indicia_printer_not_printed')):
            names = raw.get(name, '')
            if names.lower() == 'none':
                values[flag] = yes
            else:
                values[name] = '; '.join(
                  escape(item.strip(), reserved=LIST_RESERVED)
                  for item in names.split(';') if item.strip())
        values['key_date'] = text(raw.get('key_date', '').replace('.', '-'))
        on_sale_date = raw.get('on_sale_date', '')
        if on_sale_date.endswith('?'):
            values['on_sale_date_uncertain'] = yes
            on_sale_date = on_sale_date[:-1].strip()
        values['on_sale_date'] = text(on_sale_date)
        if uncertain and page_count:
            values['page_count_uncertain'] = yes
        if raw.get('variant_name'):
            values['variant_of'] = text(raw.get('number', ''))
            values['variant_name'] = text(raw['variant_name'])
            values['variant_cover_status'] = raw.get(
              'variant_cover_status', '').upper().replace(' ', '_')
    else:
        title = raw.get('title', '')
        if title.startswith('[') and title.endswith(']'):
            title = title[1:-1]
            values['title_inferred'] = yes
        values['title'] = text(title)
        values['type'] = escape(raw.get('type', ''), reserved=REF_RESERVED)
        for name in ('feature', 'genre', 'job_number', 'reprint_notes',
                     'synopsis', 'notes', 'keywords', 'first_line'):
            values[name] = text(raw.get(name, ''))
        if uncertain:
            values['page_count_uncertain'] = yes
        for name in LEGACY_CREDITS:
            if not missing(name, raw.get(name, '')):
                values[name] = text(raw.get(name, ''))
        empty = [name for name in LEGACY_CREDITS if not values.get(name)]
        cover = raw.get('type', '').lower() == 'cover'
        for name in ('script', 'letters') if cover else ():
            if name in empty:
                values['no_' + name] = yes
        if 'editing' in empty:
            values['no_editing'] = yes
        if raw.get('characters'):
            values['characters'] = ';; ' + escape_text(raw['characters'])
    return {name: value for name, value in values.items() if value}


def legacy_rows(rows, sequences_only=False, series=False):
    """
    The rows of a flat file of format 1.0 as rows of this record, a header
    row and a row for each row, empty rows stay empty. The first row is the
    issue, the others its sequences; in a series each row is an issue, a
    variant may be followed by its cover sequence.
    """
    records = []
    variant = False
    for number, row in enumerate(rows, 1):
        if not any(row):
            records.append(None)
            continue
        if sequences_only:
            kind = 'sequence'
        elif series:
            kind = 'sequence' if variant and len(row) > 1 and \
                row[1].strip().lower() == 'cover' else 'issue'
        else:
            kind = 'sequence' if any(records) else 'issue'
        cells = LEGACY_CELLS[kind] + (LEGACY_VARIANT_CELLS if series and
                                      kind == 'issue' else ())
        if len(row) not in cells:
            raise _syntax_error(
              'a row of %s of format 1.0, a file without header row, has %d '
              'to %d cells%s, not %d' % (
                kind, cells[0], LEGACY_CELLS[kind][-1],
                ' or %d for a variant' % LEGACY_VARIANT_CELLS[0]
                if len(cells) > len(LEGACY_CELLS[kind]) else '', len(row)),
              'line %d' % number)
        raw = dict(zip(LEGACY_ISSUE_FIELDS if kind == 'issue'
                       else LEGACY_STORY_FIELDS, row))
        records.append((kind, legacy_values(raw, kind, flat=True)))
        variant = kind == 'issue' and bool(raw.get('variant_name'))
    columns = [column for column in COLUMNS[1:]
               if any(column in record[1] for record in records if record)]
    return [[RECORD] + columns] + [
      [record[0]] + [record[1].get(column, '') for column in columns]
      if record else [] for record in records]


def read_flat_records(rows, sequences_only=False, series=False):
    """
    Rows of a flat file with a header row, returns the raw records with
    their sequences, as dicts of text cells. Columns can be left out.
    With sequences_only the issue rows are ignored and not needed. A file
    without header row is of format 1.0, as are its line numbers.
    """
    first = 2
    if rows and rows[0] and rows[0][0] != RECORD:
        rows, first = legacy_rows(rows, sequences_only, series), 1
    if not rows or not rows[0] or rows[0][0] != RECORD:
        raise _syntax_error('the first row must be the header row, starting '
                            'with "%s"' % RECORD, 'line 1')
    header = rows[0]
    unknown = [column for column in header if column not in COLUMNS]
    if unknown or len(set(header)) != len(header):
        raise _syntax_error('unknown or repeated column', 'line 1',
                            ', '.join(unknown))
    records = []
    for number, row in enumerate(rows[1:], first):
        if not any(row):
            continue
        if len(row) != len(header):
            raise _syntax_error('the row has %d cells, the header %d' % (
                                len(row), len(header)), 'line %d' % number)
        cells = dict(zip(header, row))
        kind = cells.pop(RECORD)
        allowed = ISSUE_FIELDS if kind == 'issue' else STORY_FIELDS
        if kind not in ('issue', 'sequence'):
            raise _syntax_error('the record must be "issue" or "sequence"',
                                'line %d' % number, kind)
        for column, value in cells.items():
            if value and column not in allowed:
                raise _syntax_error('column not used for a %s' % kind,
                                    'line %d' % number, column)
        if kind == 'issue':
            records.append((None if sequences_only else cells, number, []))
        elif not records and sequences_only:
            records.append((None, number, [(cells, number)]))
        elif not records:
            raise _syntax_error('a sequence needs an issue before it',
                                'line %d' % number)
        else:
            records[-1][2].append((cells, number))
    return records


class RecordImporter:
    """
    Resolves the decoded records of a series and creates the revisions,
    all references are resolved by name and disambiguation.
    """
    def __init__(self, series):
        self.series = series
        self.resolver = Resolver(series.language, series)
        self.models = _ref_models()
        self.errors = []

    def _resolve(self, name, ref, scope=()):
        try:
            return self.resolver.resolve_ref(self.models[name], ref,
                                             scope=scope)
        except NotationError as error:
            self.errors.append(error)

    def _credits(self, entries):
        credits = []
        for entry in entries:
            values = dict(entry.values)
            values['creator'] = self._resolve('creator', entry.creator)
            values['credit_type'] = self._resolve('credit_type',
                                                  entry.credit_type)
            if entry.signature:
                values['signature'] = self._resolve(
                  'signature', entry.signature, signature_scope(
                    values['creator'], entry.generic_signature))
            credits.append(values)
        return credits

    def _multi(self, values, names, scopes={}):
        return {name: [self._resolve(name, ref, scopes.get(name, ()))
                       for ref in values.pop(name)]
                for name in names}

    def check(self):
        if self.errors:
            errors, self.errors = self.errors, []
            _raise_all(errors)

    def issue(self, values):
        """
        Returns field values, many-to-many values and credits of an issue.
        """
        from apps.gcd.models import VCS_Codes
        from apps.oi.models import on_sale_date_fields
        values = dict(values)
        for name in unused_fields(self.series):
            if values.get(name):
                self.errors.append(NotationError(
                  'invalid', 'the series does not use this field', name))
        scopes = issue_scopes(self.series)
        values.pop('variant_of')
        credits = self._credits(values.pop('credits'))
        values['indicia_publisher'] = self._resolve(
          'indicia_publisher', values['indicia_publisher'],
          scopes['indicia_publisher'])
        multi = self._multi(values, ['brand_emblem', 'indicia_printer'],
                            scopes)
        status = values.pop('variant_cover_status') or \
            DEFAULT_VARIANT_COVER_STATUS
        if status not in VCS_Codes.__members__:
            self.errors.append(NotationError(
              'invalid', 'unknown variant cover status',
              'variant_cover_status', status, VCS_Codes.__members__))
        else:
            values['variant_cover_status'] = VCS_Codes[status]
        on_sale_date = values.pop('on_sale_date')
        try:
            values['year_on_sale'], values['month_on_sale'], \
              values['day_on_sale'] = on_sale_date_fields(on_sale_date)
        except ValueError:
            self.errors.append(NotationError(
              'invalid', 'invalid on-sale date', 'on_sale_date',
              on_sale_date))
        return values, multi, credits

    def story(self, values):
        """
        Returns field values, many-to-many values, credits and characters
        of a sequence.
        """
        values = dict(values)
        credits = self._credits(values.pop('credits'))
        if values['type'] is None:
            self.errors.append(NotationError('invalid', 'missing type',
                                             'type'))
        else:
            values['type'] = self._resolve('type', values['type'])
        multi = self._multi(values, ['feature_object', 'feature_name',
                                     'story_arc', 'universe'],
                            story_scopes(values['type']))
        multi.update(self._multi(values, ['feature_logo'], story_scopes(
          values['type'], [name for name in multi['feature_name'] if name])))
        characters = values.pop('characters')
        groups, appearances = [], []
        try:
            groups, appearances = self.resolver.resolve(characters)
        except NotationError as error:
            self.errors.append(error)
        values['characters'] = characters.free_text
        return values, multi, credits, (groups, appearances)


def create_credits(revision_class, credits, **kwargs):
    for values in credits:
        revision_class.objects.create(**kwargs, **values)


def set_multi(revision, multi):
    for name, objects in multi.items():
        getattr(revision, name).set(objects)
