"""Read the text of the characters field of a sequence.

``parse`` splits the text into items and says, for each one, whether it is
well-formed, has warnings or has an error. It uses no database, so the same
rules hold for every series and language. ``render`` writes an item back in
the standard form: it is shown as "Read as" and never written into the
field.

The syntax comes from the wiki page Character Appearances and from the text
that beta writes for linked characters:

- items are separated by ";"; a line break at the top level also ends an
  item, with a warning;
- an item is a name followed by groups, in any number and order: square
  brackets hold other items (names of the same character, members of a
  group) separated by ";", parentheses hold notes separated by ",";
- a heading such as "VILLAINS:" applies to the items after it, up to the
  next heading or a blank line.

A bracket that is never closed, or closed by the wrong kind, makes the rest
of the text an error: guessing where it was meant to close would be a
silent repair.
"""

import re
from dataclasses import dataclass, field

ERROR = 'error'
WARNING = 'warning'

OPENERS = {'(': ')', '[': ']', '{': '}'}
CLOSERS = {')': '(', ']': '[', '}': '{'}
# limits far above the texts of the catalog (longest 11,438 characters,
# brackets at most 6 deep), so that any input is read in a bounded time
MAX_LENGTH = 20000
MAX_DEPTH = 20
MAX_ENTRIES = 100

ROLES = ('antagonist', 'cameo', 'featured', 'guest', 'supporting',
         'villain')
FLAGS = ('flashback', 'origin', 'death')
# other words in use for a role or a flag, each with what it stands for
SYNONYMS = (
    ('villains', ('villain',)),
    ('guest star', ('guest',)),
    ('guest-star', ('guest',)),
    ('guest stars', ('guest',)),
    ('feature', ('featured',)),
    ('dies', ('death',)),
    ('in flashback', ('flashback',)),
    ('cameo flashback', ('cameo', 'flashback')),
    ('morte', ('death',)),
    ('mort', ('death',)),
    ('muerte', ('death',)),
    ('tod', ('death',)),
    ('r\u00fcckblick', ('flashback',)),
    ('villano', ('villain',)),
    ('vilain', ('villain',)),
)
# old abbreviations: recognised and warned, never read as a role or flag
ABBREVIATIONS = ('I', 'GA', 'GS', 'D', 'O', 'V', '1st', 'C')
# headings read as a role or flag of each item after them
HEADINGS = (
    ('villain', ('villain',)),
    ('villains', ('villain',)),
    ('guest', ('guest',)),
    ('guests', ('guest',)),
    ('guest stars', ('guest',)),
    ('cameo', ('cameo',)),
    ('cameos', ('cameo',)),
    ('cameo flashback', ('cameo', 'flashback')),
    ('feature', ('featured',)),
)
# headings read as the first note of each item after them
LABEL_HEADINGS = ('heros', 'personaggi minori', 'prologo', 'v', 'gs', 'i')
MARKERS = ('also appears as', 'also as', 'as', 'aka', 'come')

GLOSS = re.compile(r'^([^\[\]]+?) ?\[([^\[\]]+)\]$')


def _readings(targets):
    """Readings of keyword targets, as ('role'|'flag', target) pairs."""
    return tuple(('role' if target in ROLES else 'flag', target)
                 for target in targets)


KEYWORDS = {
    **{role: _readings((role,)) for role in ROLES},
    **{flag: _readings((flag,)) for flag in FLAGS},
    **{key: _readings(targets) for key, targets in SYNONYMS},
}
HEADING_READINGS = {key: _readings(targets) for key, targets in HEADINGS}


def _key(text):
    """The lookup form of a text: case folded, white space collapsed."""
    return ' '.join(text.split()).casefold()


def _tidy(text):
    """The text with each run of white space turned into one space."""
    return ' '.join(text.split())


def _space_kind(run):
    """What is wrong with a run of white space that is not one space."""
    if '\n' in run:
        return 'A line break inside the item'
    if len(run) == 1:
        return 'A white space that is not a plain space'
    return 'More than one space'


@dataclass
class Diagnostic:
    """A finding on the text: level, code, span and message."""
    level: str
    code: str
    start: int
    end: int
    message: str


@dataclass
class Segment:
    """A note between separators inside parentheses, and its readings."""
    start: int
    end: int
    readings: tuple


@dataclass
class Group:
    """Square brackets with their items, or parentheses with notes."""
    kind: str
    start: int
    end: int
    elements: list = field(default_factory=list)
    segments: list = field(default_factory=list)


@dataclass
class Node:
    """An item: a name followed by its groups."""
    start: int
    end: int
    name: str
    groups: list = field(default_factory=list)
    uncertain: bool = False


@dataclass
class Heading:
    """A heading such as "VILLAINS:" and how its items are read."""
    start: int
    end: int
    text: str
    readings: tuple
    what: str
    used: bool = False


@dataclass
class Unit:
    """An item at the top level; node is None when an error stops it."""
    number: int
    start: int
    end: int
    node: Node = None
    heading: Heading = None
    diagnostics: list = field(default_factory=list)

    @property
    def level(self):
        """ERROR, WARNING or None for a well-formed item."""
        levels = {diagnostic.level for diagnostic in self.diagnostics}
        if ERROR in levels:
            return ERROR
        return WARNING if levels else None


@dataclass
class Part:
    """A piece of the text at the top level, in text order.

    kind is 'unit', 'heading', 'separator' or 'space'; together the parts
    cover the whole text.
    """
    kind: str
    start: int
    end: int


@dataclass
class Parsed:
    """The result of ``parse``."""
    text: str
    parts: list
    units: list
    headings: list
    general: list


class _ItemError(Exception):
    """An error that stops the reading of the current item."""

    def __init__(self, diagnostic):
        """Keep the diagnostic for the unit."""
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


class _Reader:
    """Reads one text; ``parse`` is the entry point."""

    def __init__(self, text):
        """Start on text with no findings."""
        self.text = text
        self.has_semicolon = ';' in text
        self.found = []
        self.closing = {}

    def _warn(self, code, start, end, message):
        """Add a warning to the item being read."""
        self.found.append(Diagnostic(WARNING, code, start, end, message))

    def _error(self, code, start, end, message):
        """An error that stops the item being read."""
        return _ItemError(Diagnostic(ERROR, code, start, end, message))

    def run(self):
        """Read the whole text."""
        text, length = self.text, len(self.text)
        parts, units, headings, general, pending = [], [], [], [], []
        heading = None
        last_unit = None
        separators = 0
        newline = heading_since = False
        pos = 0
        while pos < length:
            char = text[pos]
            if char.isspace():
                end = pos
                while end < length and text[end].isspace():
                    end += 1
                run = text[pos:end]
                parts.append(Part('space', pos, end))
                if '\n' in run:
                    newline = True
                    if run.count('\n') > 1:
                        heading = None
                elif (pos and text[pos - 1] == ';' and end < length
                      and run != ' '):
                    pending.append(Diagnostic(
                      WARNING, 'spaces', pos, end,
                      '%s before this item.' % _space_kind(run)))
                if end < length and text[end] == ';' and '\n' not in run \
                        and last_unit and last_unit.level != ERROR \
                        and not separators and not heading_since:
                    last_unit.diagnostics.append(Diagnostic(
                      WARNING, 'spaces', pos, end,
                      'Space before the ";" after this item.'))
                pos = end
                continue
            if char == ';':
                parts.append(Part('separator', pos, pos + 1))
                if heading_since and not separators:
                    pending.append(Diagnostic(
                      WARNING, 'heading_separator', pos, pos + 1,
                      'A ";" right after a heading.'))
                elif separators or not last_unit:
                    if not (last_unit or headings or separators):
                        message = 'The text starts with ";".'
                        code = 'leading_separator'
                    else:
                        message = 'Two ";" with no item between them.'
                        code = 'double_separator'
                    pending.append(Diagnostic(WARNING, code, pos, pos + 1,
                                              message))
                elif pos + 1 < length and not text[pos + 1].isspace() \
                        and text[pos + 1] != ';':
                    pending.append(Diagnostic(
                      WARNING, 'spaces', pos, pos + 1,
                      'No space after the ";" before this item.'))
                separators += 1
                pos += 1
                continue
            found = self._heading_at(pos)
            if found:
                parts.append(Part('heading', found.start, found.end))
                headings.append(found)
                heading = found
                heading_since = True
                separators = 0
                newline = False
                pos = found.end
                continue
            unit, end = self._unit(pos, len(units) + 1)
            if heading:
                heading.used = True
            if heading and unit.level != ERROR:
                unit.heading = heading
                unit.diagnostics.insert(0, Diagnostic(
                  WARNING, 'heading', heading.start, heading.end,
                  '"%s:" is a heading: this item is read %s.'
                  % (heading.text, heading.what)))
            if last_unit and newline and not separators \
                    and not heading_since:
                pending.append(Diagnostic(
                  WARNING, 'newline_separator', pos, pos,
                  'A line break, not ";", separates this item from the '
                  'one before.'))
            if unit.level != ERROR:
                unit.diagnostics[:0] = pending
            pending = []
            units.append(unit)
            parts.append(Part('unit', unit.start, unit.end))
            last_unit = unit
            separators = 0
            newline = heading_since = False
            pos = unit.end
        if pending:
            if last_unit and last_unit.level != ERROR:
                last_unit.diagnostics.extend(pending)
            elif not last_unit:
                general.extend(pending)
        for found in headings:
            if not found.used:
                general.append(Diagnostic(
                  WARNING, 'heading', found.start, found.end,
                  '"%s:" is a heading with no item after it.' % found.text))
        return Parsed(text, parts, units, headings, general)

    def _heading_at(self, pos):
        """The heading that starts at pos, or None."""
        text = self.text
        end = pos
        while end < len(text) and text[end] not in ':;[](){}\n':
            end += 1
        if end == len(text) or text[end] != ':':
            return None
        key = _key(text[pos:end])
        label = _tidy(text[pos:end])
        if key in HEADING_READINGS:
            readings = HEADING_READINGS[key]
            what = 'with "%s"' % ', '.join(value for _, value in readings)
        elif key in LABEL_HEADINGS:
            readings = (('note', label),)
            what = 'with the note "%s"' % label
        else:
            return None
        return Heading(pos, end + 1, label, readings, what)

    def _unit(self, pos, number):
        """Read the top-level item at pos; return it and where it ends."""
        text = self.text
        end, fatal, extra = self._extent(pos)
        while end > pos and text[end - 1].isspace():
            end -= 1
        unit = Unit(number, pos, end)
        if fatal or extra:
            unit.diagnostics = [found for found in (extra, fatal) if found]
            return unit, end
        self.found = []
        try:
            unit.node = self._node(pos, end)
        except _ItemError as stop:
            unit.diagnostics = [stop.diagnostic]
            return unit, end
        quotes = text.count('"', pos, end)
        if quotes % 2:
            first = text.index('"', pos, end)
            self._warn('quotes', first, first + 1,
                       'An odd number of double quotes.')
        braces = [i for i in range(pos, end) if text[i] in '{}']
        if braces:
            self._warn('braces', braces[0], braces[0] + 1,
                       'Braces are read as part of the text.')
        unit.diagnostics = sorted(self.found, key=lambda found: found.start)
        return unit, end

    def _extent(self, pos):
        """Where the item at pos ends, and the bracket errors in it.

        Returns (end, fatal, extra): end is the ";" or line break that ends
        the item, or the end of the text; fatal is an error that leaves the
        rest of the text unread; extra is an error of the item alone: a
        closing bracket that closes nothing, or brackets nested too deep.
        Records where each bracket of the item closes.
        """
        text, length = self.text, len(self.text)
        stack, extra = [], None
        for i in range(pos, length):
            char = text[i]
            if char in OPENERS:
                stack.append(i)
                if len(stack) > MAX_DEPTH and extra is None:
                    extra = Diagnostic(
                      ERROR, 'too_deep', i, i + 1, 'Brackets nested more '
                      'than %d levels deep.' % MAX_DEPTH)
            elif char in CLOSERS:
                if not stack:
                    if extra is None:
                        extra = Diagnostic(
                          ERROR, 'brace' if char == '}' else 'extra',
                          i, i + 1, '"%s" has no opening "%s".'
                          % (char, CLOSERS[char]))
                elif text[stack[-1]] == CLOSERS[char]:
                    self.closing[stack.pop()] = i
                else:
                    opener = text[stack[-1]]
                    code = 'brace' if '{' in (opener, CLOSERS[char]) \
                        else 'crossed'
                    return length, Diagnostic(
                      ERROR, code, i, i + 1, '"%s" closes "%s". The text '
                      'from here to the end is not read.' % (char, opener)),\
                        extra
            elif not stack and char in ';\n':
                return i, None, extra
        if stack:
            opener = text[stack[0]]
            return length, Diagnostic(
              ERROR, 'brace' if opener == '{' else 'unclosed', stack[0],
              stack[0] + 1, '"%s" is never closed. The text from here to '
              'the end is not read.' % opener), extra
        return length, None, extra

    def _match(self, pos):
        """Index of the bracket closing the one at pos (text balanced)."""
        return self.closing[pos]

    def _node(self, start, end):
        """Read the item text[start:end], balanced and without outer
        white space."""
        text = self.text
        pos = start
        while pos < end and text[pos] not in '([':
            pos = self._match(pos) + 1 if text[pos] == '{' else pos + 1
        name_end = pos
        while name_end > start and text[name_end - 1].isspace():
            name_end -= 1
        if name_end == start:
            raise self._error('starts_with_group', pos, pos + 1,
                              'The item starts with "%s" instead of a '
                              'name.' % text[pos])
        node = Node(start, end, _tidy(text[start:name_end]))
        self._check_name(start, name_end)
        gap = name_end
        while pos < end:
            if text[pos] in '([':
                self._check_gap(gap, pos)
                close = self._match(pos)
                node.groups.append(self._group(pos, close))
                gap = pos = close + 1
                while pos < end and text[pos].isspace():
                    pos += 1
                continue
            rest = text[pos:end]
            if rest == '?':
                node.uncertain = True
            elif rest == '.':
                self._warn('period', pos, end, 'A "." after the last "%s".'
                           % text[gap - 1])
            else:
                raise self._error('text_after_group', pos, end,
                                  'Text after "%s" in the same item. '
                                  'Characters are separated by ";".'
                                  % text[gap - 1])
            break
        brackets = [group for group in node.groups if group.kind == '[']
        if len(brackets) > 1:
            self._warn('double_brackets', brackets[1].start,
                       brackets[1].start + 1,
                       'Two pairs of square brackets after one name.')
        return node

    def _check_name(self, start, end):
        """Warnings on the name text[start:end]."""
        name = self.text[start:end]
        self._check_runs(start, end)
        commas = name.count(',')
        if commas > 1:
            self._warn('commas', start, end, 'Several commas in one name. '
                       'Characters are separated by ";".')
        elif commas and not self.has_semicolon:
            self._warn('commas', start, end, 'A comma in a text without '
                       '";". Characters are separated by ";".')
        if ':' in name:
            colon = start + name.index(':')
            self._warn('colon', colon, colon + 1, '":" in a name.')

    def _check_runs(self, start, end):
        """A warning for each run of white space that is not one space."""
        for found in re.finditer(r'\s+', self.text[start:end]):
            if found.group() != ' ':
                self._space(start + found.start(), start + found.end())

    def _space(self, start, end):
        """A warning on the white space text[start:end]."""
        self._warn('spaces', start, end,
                   '%s.' % _space_kind(self.text[start:end]))

    def _check_gap(self, start, end):
        """The space before a group must be one space."""
        if start == end:
            self._warn('spaces', end, end + 1,
                       'No space before "%s".' % self.text[end])
        elif self.text[start:end] != ' ':
            self._space(start, end)

    def _group(self, start, close):
        """Read the group from text[start] to text[close]."""
        text = self.text
        kind = text[start]
        group = Group(kind, start, close + 1)
        if text[start + 1].isspace():
            self._warn('spaces', start + 1, start + 2,
                       'Space after "%s".' % kind)
        if text[close - 1].isspace():
            self._warn('spaces', close - 1, close,
                       'Space before "%s".' % OPENERS[kind])
        pieces = self._split(start + 1, close, ';' if kind == '[' else ',;')
        for index, (piece_start, piece_end, sep) in enumerate(pieces):
            first, last = piece_start, piece_end
            while first < last and text[first].isspace():
                first += 1
            while last > first and text[last - 1].isspace():
                last -= 1
            if first == last:
                self._empty_piece(kind, index, len(pieces),
                                  piece_start if sep is None else sep)
                continue
            if sep is not None:
                self._check_separator(sep, last, piece_end,
                                      pieces[index + 1])
            if kind == '[':
                group.elements.append(self._element(first, last))
            else:
                if sep is not None and text[sep] == ';':
                    self._warn('semicolon_in_parentheses', sep, sep + 1,
                               '";" inside parentheses. Notes are '
                               'separated by ",".')
                group.segments.append(self._segment(first, last))
        if not group.elements and not group.segments:
            raise self._error('empty_group', start, close + 1,
                              '"%s" is empty.' % _tidy(text[start:close + 1]))
        return group

    def _split(self, start, end, separators):
        """Pieces of text[start:end] at its own depth, as (start, end,
        index of the separator after it or None)."""
        text = self.text
        pieces = []
        piece = pos = start
        while pos < end:
            if text[pos] in OPENERS:
                pos = self._match(pos) + 1
                continue
            if text[pos] in separators:
                pieces.append((piece, pos, pos))
                piece = pos + 1
            pos += 1
        pieces.append((piece, end, None))
        return pieces

    def _empty_piece(self, kind, index, count, pos):
        """Warnings for an empty piece inside a group."""
        if kind == '(':
            self._warn('empty_note', pos, pos,
                       'An empty note between separators.')
        elif index == 0:
            self._warn('leading_separator', pos, pos + 1,
                       'The square brackets start with ";".')
        elif index < count - 1:
            self._warn('double_separator', pos, pos + 1,
                       'Two ";" with no item between them.')

    def _check_separator(self, sep, last, piece_end, following):
        """Spaces around the separator at sep, after a piece ending at
        last (piece_end with its white space)."""
        text = self.text
        if last < piece_end:
            self._warn('spaces', last, piece_end,
                       'Space before "%s".' % text[sep])
        next_start, next_end, _ = following
        if not text[next_start:next_end].strip():
            return
        run = re.match(r'\s*', text[next_start:next_end]).group()
        if not run:
            self._warn('spaces', sep, sep + 1,
                       'No space after "%s".' % text[sep])
        elif run != ' ':
            self._space(next_start, next_start + len(run))

    def _element(self, start, end):
        """Read an item inside square brackets."""
        node = self._node(start, end)
        key = _key(node.name)
        if not node.groups and key in KEYWORDS:
            self._warn('keyword_in_brackets', start, end,
                       '"%s" is in square brackets. Roles and notes go in '
                       'parentheses.' % node.name)
        for marker in MARKERS:
            if key.startswith(marker + ' '):
                self._warn('marker', start, start + len(marker),
                           'A name in square brackets starts with "%s". '
                           'Notes go in parentheses.' % marker)
                break
        return node

    def _segment(self, start, end):
        """Read a note inside parentheses."""
        raw = self.text[start:end]
        self._check_runs(start, end)
        for pos in range(start, end):
            if self.text[pos] in '([' and \
                    not self.text[pos + 1:self.closing[pos]].strip():
                raise self._error('empty_group', pos, self.closing[pos] + 1,
                                  '"%s" is empty.' % _tidy(
                                    self.text[pos:self.closing[pos] + 1]))
        key = _key(raw)
        if key in KEYWORDS:
            return Segment(start, end, KEYWORDS[key])
        if raw in ABBREVIATIONS:
            self._warn('abbreviation', start, end, '"%s" is an '
                       'abbreviation. Write the word in full.' % raw)
        else:
            gloss = GLOSS.match(_tidy(raw))
            if gloss:
                first, second = (_key(word) for word in gloss.groups())
                if first in KEYWORDS and KEYWORDS[first] == \
                        KEYWORDS.get(second):
                    return Segment(start, end, KEYWORDS[first])
        return Segment(start, end, (('note', _tidy(raw)),))


def parse(text):
    """Read the text of a characters field; see the module docstring."""
    return _Reader(text).run()


def _reading_text(reading):
    """How a reading is written inside parentheses."""
    return reading[1]


def render(node):
    """The item in the standard form, as "Read as" shows it."""
    text = node.name
    for group in node.groups:
        if group.kind == '[':
            text += ' [%s]' % '; '.join(render(element)
                                        for element in group.elements)
        else:
            text += ' (%s)' % ', '.join(
              _reading_text(reading) for segment in group.segments
              for reading in segment.readings)
    if node.uncertain:
        text += '?'
    return text


def read_as(unit):
    """The unit in the standard form, with the readings of its heading
    right after the name."""
    text = render(unit.node)
    if not unit.heading:
        return text
    name = unit.node.name
    return '%s (%s)%s' % (name, ', '.join(
      _reading_text(reading) for reading in unit.heading.readings),
      text[len(name):])


def structure(node):
    """What an item means, without positions or spelling, for comparing
    two readings."""
    groups = []
    for group in node.groups:
        if group.kind == '[':
            groups.append(('[', tuple(structure(element)
                                      for element in group.elements)))
        else:
            groups.append(('(', tuple(reading for segment in group.segments
                                      for reading in segment.readings)))
    return (node.name, tuple(groups), node.uncertain)


def _short(text, limit=80):
    """The text cut to limit characters."""
    return text if len(text) <= limit else text[:limit - 3] + '...'


def _lines(diagnostics, start, end):
    """Diagnostics with their column inside text[start:end], if any."""
    lines = []
    for diagnostic in diagnostics:
        label = 'Error' if diagnostic.level == ERROR else 'Warning'
        column = None
        if start <= diagnostic.start < end:
            column = diagnostic.start - start + 1
            label += ', column %d' % column
        lines.append({'level': diagnostic.level, 'column': column,
                      'label': label, 'message': diagnostic.message})
    return lines


def report(parsed):
    """What the check shows: counts and the entries with findings."""
    entries = []
    for found in parsed.general:
        entries.append({'number': None, 'level': WARNING, 'read_as': None,
                        'text': _short(parsed.text[found.start:found.end]),
                        'lines': _lines([found], 0, 0)})
    for item in parsed.units:
        if not item.diagnostics:
            continue
        entries.append({
          'number': item.number, 'level': item.level,
          'text': _short(parsed.text[item.start:item.end]),
          'lines': _lines(item.diagnostics, item.start, item.end),
          'read_as': read_as(item) if item.node else None})
    levels = [unit.level for unit in parsed.units]
    return {'items': len(levels), 'well_formed': levels.count(None),
            'warnings': levels.count(WARNING), 'errors': levels.count(ERROR),
            'entries': entries[:MAX_ENTRIES],
            'more': max(0, len(entries) - MAX_ENTRIES)}
