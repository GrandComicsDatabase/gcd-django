# -*- coding: utf-8 -*-
"""Tests of the reader of the characters text, without a database."""

import itertools
import random

import pytest

from apps.oi.characters_text import (
    ABBREVIATIONS, ERROR, FLAGS, HEADINGS, KEYWORDS, LABEL_HEADINGS,
    MARKERS, ROLES, SYNONYMS, WARNING, parse, read_as, render, report,
    structure)


def findings(text):
    """(item number, code, column in the item) of each finding."""
    parsed = parse(text)
    return [(unit.number, found.code, found.start - unit.start + 1)
            for unit in parsed.units for found in unit.diagnostics]


def levels(text):
    """The level of each item: None for a well-formed one."""
    return [unit.level for unit in parse(text).units]


def names(text):
    """The names of the items read at the top level."""
    return [unit.node.name if unit.node else None
            for unit in parse(text).units]


# The examples of the wiki page Character Appearances, and the forms that
# beta writes for linked characters.
WELL_FORMED = [
    'Sam Zabel; Mr. Lupicinus; Cynthia; Moxie; Toxie; Tisco',
    'Jimmy Olsen',
    'Jimmy Olsen (origin, death)',
    'Red Tornado [Ma Hunkel] (cameo)',
    'Green Lantern [Hal Jordan]; Green Lantern [Alan Scott] (cameo)',
    'Batman (photo of Adam West)',
    'Batman [Bruce Wayne] (of Earth-2)',
    'Justice League of America [Green Lantern [Hal Jordan] (origin); '
    'Superman [Clark Kent] (Earth-1)];',
    'Justice Society of America [Superman [Clark Kent] (Earth-2); '
    'Flash [Jay Garrick] (cameo)]',
    'Tarzan',
    '? (photo of Joy Lansing)',
    'Roy Rogers (photo)',
    'Superboy [Clark Kent] (in flashback); Superman [Clark Kent]',
    'Batman [Bruce Wayne (also disguised as Commissioner Gordon)]',
    'Batman [Bruce Wayne] (also disguised as Commissioner Gordon)',
    'Firestorm [Ronnie Raymond; Martin Stein]',
    'Robin [Dick Grayson]; Robin [Richard Grayson] '
    '(Earth-Two (Pre-Crisis))',
    'President John Wilkes Booth (Earth-Three, cameo); Christopher '
    'Columbus (Earth-Three, cameo)',
    'Mrs. Jones (Mr. Jones\' wife); Mr. Smith (owner of drug store)',
    'Superman (introduction, origin)',
    # what beta writes: group, its notes, members, flags, role, notes
    'Justice League (Earth-2) (first appearance) [Superman [Clark Kent] '
    '(flashback, death, origin) (cameo) (note); Batman]; Alfred',
    'Batman [Earth-2]',
    'Flash [Jay Garrick] (cameo)?',
    'Superman Jr.; Dr. Mid-Nite & Hourman; Black Canary / Dinah',
]


@pytest.mark.parametrize('text', WELL_FORMED)
def test_well_formed_texts_have_no_finding(text):
    """The examples of the wiki and the forms beta writes are well-formed."""
    parsed = parse(text)

    assert parsed.units
    assert all(unit.level is None for unit in parsed.units)
    assert not parsed.general


def test_items_names_and_groups():
    """Names, members, secret identities and notes are read into the tree."""
    parsed = parse('Justice League [Superman [Clark Kent] (cameo); '
                   'Batman]; Alfred (death, dies, in flashback)')

    league, alfred = (unit.node for unit in parsed.units)
    assert league.name == 'Justice League'
    members = league.groups[0].elements
    assert [member.name for member in members] == ['Superman', 'Batman']
    assert members[0].groups[0].elements[0].name == 'Clark Kent'
    assert structure(members[0])[1][1] == ('(', (('role', 'cameo'),))
    assert structure(alfred)[1] == (('(', (
      ('flag', 'death'), ('flag', 'death'), ('flag', 'flashback'))),)


def test_spans_are_exact():
    """Parts, items, groups and notes cover the exact characters."""
    text = 'Ann; Bob [Carl] (cameo, x)'
    parsed = parse(text)

    assert [(part.kind, part.start, part.end) for part in parsed.parts] == [
      ('unit', 0, 3), ('separator', 3, 4), ('space', 4, 5),
      ('unit', 5, 26)]
    bob = parsed.units[1].node
    assert (bob.start, bob.end) == (5, 26)
    brackets, notes = bob.groups
    assert (brackets.start, brackets.end) == (9, 15)
    carl = brackets.elements[0]
    assert (carl.start, carl.end) == (10, 14)
    assert [(segment.start, segment.end) for segment in notes.segments] \
        == [(17, 22), (24, 25)]


def test_a_comma_never_separates_items():
    """A comma belongs to the name, at the top level and in brackets."""
    assert names('Batman, Robin; Alfred') == ['Batman, Robin', 'Alfred']
    assert [element.name for element in
            parse('JLA [Hawkman, Hawkgirl; Atom]').units[0].node
            .groups[0].elements] == ['Hawkman, Hawkgirl', 'Atom']


def test_words_joining_names_stay_in_the_name():
    """"and", "e", "&" and "/" do not split a name and are not warned."""
    for text in ('Batman and Robin', 'Tizio e Caio', 'Batman & Robin',
                 'Batman / Robin'):
        assert names(text) == [text]
        assert levels(text) == [None]


def test_parentheses_nest():
    """A "(" closes at its own ")", not at the first one."""
    node = parse('Joker (also (as) Red Hood, x) (cameo)').units[0].node

    assert structure(node)[1] == (
      ('(', (('note', 'also (as) Red Hood'), ('note', 'x'))),
      ('(', (('role', 'cameo'),)))


@pytest.mark.parametrize('text, expected', [
  # an unclosed parenthesis takes the rest of the text, past any ";"
  ('Ann; Ronny Edge (death (criminale, foo; Batman; Robin',
   [(2, 'unclosed', 12)]),
  ('Ann [Bob; Carl', [(1, 'unclosed', 5)]),
  ('Ann (b]; Carl', [(1, 'crossed', 7)]),
  ('Ann (b}; Carl', [(1, 'brace', 7)]),
  ('Ann {b); Carl', [(1, 'brace', 7)]),
  ('Ann {b; Carl', [(1, 'brace', 5)]),
  ('Ann (b)); Carl', [(1, 'extra', 8)]),
  ('Ann } b; Carl', [(1, 'brace', 5)]),
  ('Ann (); Carl', [(1, 'empty_group', 5)]),
  ('Ann [ ]; Carl', [(1, 'empty_group', 5)]),
  ('Ann [;]; Carl', [(1, 'empty_group', 5)]),
  ('Ann (,); Carl', [(1, 'empty_group', 5)]),
  ('(cameo) Ann; Carl', [(1, 'starts_with_group', 1)]),
  ('JLA [[Bob]]; Carl', [(1, 'starts_with_group', 6)]),
  ('X (fan art), Y; Carl', [(1, 'text_after_group', 12)]),
  ('Ann [Bob] Carl', [(1, 'text_after_group', 11)]),
  ('Ann (b) ?x', [(1, 'text_after_group', 9)]),
  ('JLA [Ann (b) c]; Carl', [(1, 'text_after_group', 14)]),
  ('Ann (b ()); Carl', [(1, 'empty_group', 8)]),
  ('Ann (b [ ]); Carl', [(1, 'empty_group', 8)]),
  ('Ann (b {c ()}); Carl', [(1, 'empty_group', 11)]),
  ('Ann' + ' [a' * 21 + ']' * 21 + '; Carl', [(1, 'too_deep', 65)]),
])
def test_errors(text, expected):
    """Each error, its column, and the items it leaves unread."""
    found = findings(text)

    assert [item for item in found if item[0] == 1 or 'unclosed' in
            item[1]] == expected
    for unit in parse(text).units:
        if unit.level == ERROR:
            assert unit.node is None


def test_an_unclosed_parenthesis_leaves_the_rest_unread():
    """An unclosed "(" takes the rest of the text, past any ";"."""
    parsed = parse('Ann; Ronny Edge (death; Batman; Robin')

    assert len(parsed.units) == 2
    assert parsed.units[1].level == ERROR
    assert (parsed.units[1].start, parsed.units[1].end) == (5, 37)


def test_an_extra_closing_bracket_stops_only_its_item():
    """A ")" that closes nothing makes an error of its item only."""
    assert levels('Ann (b)); Carl') == [ERROR, None]


@pytest.mark.parametrize('text, expected', [
  ('Batman[Bruce Wayne] (cameo)', [(1, 'spaces', 7)]),
  ('Batman  [Bruce Wayne]', [(1, 'spaces', 7)]),
  ('Batman [ Bruce Wayne]', [(1, 'spaces', 9)]),
  ('Batman [Bruce Wayne ]', [(1, 'spaces', 20)]),
  ('Batman  Bruce', [(1, 'spaces', 7)]),
  ('Ann (cameo,death)', [(1, 'spaces', 11)]),
  ('Ann (cameo ,death)', [(1, 'spaces', 11), (1, 'spaces', 12)]),
  ('JLA [Ann;Bob]', [(1, 'spaces', 9)]),
  ('JLA [Ann;\nBob]', [(1, 'spaces', 10)]),
  ('Ann ; Bob', [(1, 'spaces', 4)]),
  ('Ann;Bob', [(2, 'spaces', 0)]),
  ('Ann;  Bob', [(2, 'spaces', -1)]),
  ('Ann (b; c)', [(1, 'semicolon_in_parentheses', 7)]),
  ('Ann [Bob] [Carl]', [(1, 'double_brackets', 11)]),
  ('Ann\nBob', [(2, 'newline_separator', 1)]),
  ('Ann [as Bob]', [(1, 'marker', 6)]),
  ('Ann [also appears as Bob]', [(1, 'marker', 6)]),
  ('Ann [aka Bob]', [(1, 'marker', 6)]),
  ('Ann [come Bob]', [(1, 'marker', 6)]),
  ('Ann [cameo]', [(1, 'keyword_in_brackets', 6)]),
  ('Ann [Villains]', [(1, 'keyword_in_brackets', 6)]),
  ('Ann (O, GA)', [(1, 'abbreviation', 6), (1, 'abbreviation', 9)]),
  ('Ann; ; Bob', [(2, 'double_separator', -1)]),
  ('; Ann', [(1, 'leading_separator', -1)]),
  (';; Ann', [(1, 'leading_separator', -2), (1, 'double_separator', -1)]),
  ('Ann\nVILLAINS:\nBob', [(2, 'heading', -9)]),
  ('Ann\nVILLAINS: Bob ; Carl', [(2, 'heading', -9),
                                 (2, 'spaces', 4), (3, 'heading', -15)]),
  ('Ann; VILLAINS: ; Bob', [(2, 'heading_separator', -1),
                            (2, 'heading', -11)]),
  ('VILLAINS: ; Bob', [(1, 'heading_separator', -1), (1, 'heading', -11)]),
  ('JLA [; Ann]', [(1, 'leading_separator', 6)]),
  ('JLA [Ann; ; Bob]', [(1, 'double_separator', 11)]),
  ('Ann (b, , c)', [(1, 'empty_note', 9)]),
  ('Ann (cameo).', [(1, 'period', 12)]),
  ('Ann, Bob, Carl; Dan', [(1, 'commas', 1)]),
  ('Ann, Bob', [(1, 'commas', 1)]),
  ('Heroes: Ann', [(1, 'colon', 7)]),
  ('JLA [Villains: Ann]', [(1, 'colon', 14)]),
  ('Ann "the Bat; Bob', [(1, 'quotes', 5)]),
  ('Ann {the Bat}; Bob', [(1, 'braces', 5)]),
])
def test_warnings(text, expected):
    """Each warning and its column; no error comes with them."""
    assert findings(text) == expected
    assert WARNING in levels(text)
    assert ERROR not in levels(text)


@pytest.mark.parametrize('text, message', [
  ('Ann [Bob].', 'A "." after the last "]".'),
  ('Ann (b).', 'A "." after the last ")".'),
  ('Ann  [Bob]', 'More than one space.'),
  ('Ann' + chr(160) + '[Bob]', 'A white space that is not a plain space.'),
  ('Ann;' + chr(9) + 'Bob', 'A white space that is not a plain space before '
   'this item.'),
  ('Ann;   Bob', 'More than one space before this item.'),
  ('JLA [Ann;' + chr(10) + 'Bob]', 'A line break inside the item.'),
  ('VILLAINS: ; Bob', 'A ";" right after a heading.'),
])
def test_messages(text, message):
    """The message tells what is wrong in plain words."""
    messages = [found.message for unit in parse(text).units
                for found in unit.diagnostics]

    assert message in messages


def test_nesting_up_to_the_limit_is_read():
    """Brackets 20 levels deep are read, and quickly."""
    text = '; '.join(['Ann' + ' [a' * 20 + ']' * 20] * 400)

    parsed = parse(text)

    assert len(parsed.units) == 400
    assert {unit.level for unit in parsed.units} == {None}


def test_one_comma_in_a_text_with_semicolons_is_well_formed():
    """One comma in a name is fine when ";" separates the items."""
    assert levels('Smith, John; Ann') == [None, None]
    assert levels('Justice League [Superman, Batman]; Alfred') == [None, None]
    assert levels('Justice League [Superman, Batman, Flash]; Alfred') \
        == [WARNING, None]
    assert levels('Justice League (Superman, Batman)') == [None]


@pytest.mark.parametrize('text', [
  'Ann (cameo)?', 'Ann (cameo) ?', 'Ann;', 'Ann; Bob;', 'JLA [Ann; Bob;]',
  'Ann;\nBob', 'Ann (Earth-2) [Bob]', 'Ann [Bob] (b) (c)',
  'Ann (vilain [villain])', 'Ann [Earth-2]', 'Superman Jr.',
  'Ann\r\n; Bob', '? (photo)', 'Ann [Bob (also as Carl)]'])
def test_accepted_forms(text):
    """Forms in use that are read without findings."""
    assert levels(text) == [None] * len(parse(text).units)


def test_trailing_period_after_a_name_is_part_of_the_name():
    """A "." ends a name such as "Jr."; after a group it is warned."""
    assert names('Superman Jr.') == ['Superman Jr.']
    assert findings('Ann (cameo).') == [(1, 'period', 12)]


def test_uncertain_mark_after_the_last_group():
    """A "?" after the last group marks the item as uncertain."""
    node = parse('Ann (cameo)?').units[0].node

    assert node.uncertain
    assert not parse('Ann? (cameo)').units[0].node.uncertain


@pytest.mark.parametrize('text, scoped', [
  ('VILLAINS: Ann; Bob\nCarl', [True, True, True]),
  ('villains: Ann; Bob\n\nCarl', [True, True, False]),
  ('Villains: Ann\n \nCarl', [True, False]),
  ('GUESTS: Ann\nVILLAINS: Bob', [True, True]),
])
def test_headings_hold_up_to_a_blank_line(text, scoped):
    """A heading applies up to the next heading or a blank line."""
    units = parse(text).units

    assert [unit.heading is not None for unit in units] == scoped
    assert [unit.level for unit in units if unit.heading] == \
        [WARNING] * scoped.count(True)


@pytest.mark.parametrize('heading, read', [
  ('VILLAINS', 'Ann (villain)'),
  ('Villains', 'Ann (villain)'),
  ('GuEsT StArS', 'Ann (guest)'),
  ('cameo flashback', 'Ann (cameo, flashback)'),
  ('FEATURE', 'Ann (featured)'),
  ('Personaggi minori', 'Ann (Personaggi minori)'),
  ('HEROS', 'Ann (HEROS)'),
  ('GS', 'Ann (GS)'),
])
def test_headings_ignore_case(heading, read):
    """Headings are found whatever their case, and read as listed."""
    unit = parse('%s: Ann' % heading).units[0]

    assert unit.heading.text == heading
    assert read_as(unit) == read
    assert findings('%s: Ann' % heading)[0][1] == 'heading'


def test_a_heading_with_no_item_is_reported():
    """A heading with no item after it is a finding of its own."""
    parsed = parse('Ann; VILLAINS:')

    assert [found.code for found in parsed.general] == ['heading']
    entry = report(parsed)['entries'][0]
    assert entry['text'] == 'VILLAINS:'
    assert entry['lines'][0]['column'] is None
    assert entry['lines'][0]['label'] == 'Warning'


def test_a_heading_before_an_error_is_not_reported_alone():
    """A heading before an item with an error is not called empty."""
    parsed = parse('VILLAINS: Ann (b')

    assert not parsed.general
    assert parsed.units[0].heading is None
    assert [found.code for found in parsed.units[0].diagnostics] == \
        ['unclosed']


def test_new_lines_after_a_heading_are_no_separator():
    """A line break after a heading is not taken for a separator."""
    assert findings('VILLAINS:\nAnn; Bob') == [
      (1, 'heading', -9), (2, 'heading', -14)]


@pytest.mark.parametrize('segment, readings', [
  ('cameo', (('role', 'cameo'),)),
  ('CAMEO', (('role', 'cameo'),)),
  ('guest  star', (('role', 'guest'),)),
  ('Guest-Star', (('role', 'guest'),)),
  ('cameo flashback', (('role', 'cameo'), ('flag', 'flashback'))),
  ('Morte', (('flag', 'death'),)),
  ('tod', (('flag', 'death'),)),
  ('R\u00fcckblick', (('flag', 'flashback'),)),
  ('mort', (('flag', 'death'),)),
  ('vilain', (('role', 'villain'),)),
  ('vilain [villain]', (('role', 'villain'),)),
  ('villano [villain]', (('role', 'villain'),)),
  ('vilain [cameo]', (('note', 'vilain [cameo]'),)),
  ('also in flashback', (('note', 'also in flashback'),)),
  ('cameos', (('note', 'cameos'),)),
  ('o', (('note', 'o'),)),
  ('O', (('note', 'O'),)),
  ('introduction', (('note', 'introduction'),)),
])
def test_segments(segment, readings):
    """How each note is read: role, flag or plain note."""
    node = parse('Ann (%s)' % segment).units[0].node

    assert node.groups[0].segments[0].readings == readings


def test_abbreviations_are_case_sensitive():
    """Abbreviations are recognised only with their exact case."""
    assert findings('Ann (O)') == [(1, 'abbreviation', 6)]
    assert findings('Ann (o)') == []
    assert findings('Ann (1ST)') == []


def test_no_keyword_has_two_targets():
    """The closed tables hold each key once, in lower case."""
    keys = list(ROLES) + list(FLAGS) + [key for key, _ in SYNONYMS]
    headings = [key for key, _ in HEADINGS] + list(LABEL_HEADINGS)

    assert len(keys) == len(set(keys)) == len(KEYWORDS)
    assert len(headings) == len(set(headings))
    assert all(key == key.casefold() for key in keys + headings)
    assert all(marker == marker.casefold() for marker in MARKERS)
    assert len(ABBREVIATIONS) == len(set(ABBREVIATIONS))


def test_report_of_the_page():
    """The report gives the counts and the entries the page shows."""
    text = ('Ann; Bob; Batman[Bruce Wayne] (cameo); Carl; Dan; Eve; Fay; '
            'Gus; Ronny Edge (death (criminale, morte; Hal')
    result = report(parse(text))

    assert (result['items'], result['well_formed'], result['warnings'],
            result['errors']) == (9, 7, 1, 1)
    batman, ronny = result['entries']
    assert batman == {
      'number': 3, 'level': WARNING, 'text': 'Batman[Bruce Wayne] (cameo)',
      'lines': [{'level': WARNING, 'column': 7,
                 'label': 'Warning, column 7',
                 'message': 'No space before "[".'}],
      'read_as': 'Batman [Bruce Wayne] (cameo)'}
    assert ronny['number'] == 9
    assert ronny['text'] == 'Ronny Edge (death (criminale, morte; Hal'
    assert ronny['lines'] == [{
      'level': ERROR, 'column': 12, 'label': 'Error, column 12',
      'message': '"(" is never closed. The text from here to the end is '
                 'not read.'}]
    assert ronny['read_as'] is None


def test_report_shows_at_most_100_entries():
    """Past 100 entries the report gives only how many more there are."""
    text = '; '.join('Ann[%d]' % number for number in range(150))

    result = report(parse(text))

    assert len(result['entries']) == 100
    assert result['entries'][-1]['number'] == 100
    assert result['more'] == 50
    assert report(parse('Ann[Bob]'))['more'] == 0


def test_report_cuts_long_items():
    """Long items are cut in the report."""
    text = 'Ann (%s' % ('x' * 100)

    assert report(parse(text))['entries'][0]['text'] == text[:77] + '...'


def test_render_writes_the_standard_form():
    """render writes spaces, separators and keywords in standard form."""
    unit = parse('Ann[Bob ;Carl  (Dies,in  flashback;O)]  (vilain [villain])'
                 ' ?').units[0]
    uncertain = parse('VILLAINS: Ann (cameo)?').units[0]

    assert render(unit.node) == \
        'Ann [Bob; Carl (death, flashback, O)] (villain)?'
    assert read_as(uncertain) == 'Ann (villain) (cameo)?'


def test_parse_does_not_change_the_text():
    """The report shows an item with an error exactly as it was written."""
    text = 'Ann (b; Carl'
    parsed = parse(text)

    assert parsed.text == text
    assert report(parsed)['entries'][0]['text'] == text


# Real texts of the dump of 2026-10-28, by story id: Dylan Dog
# (3339295, 4364128, 4318624, 3302951), Nathan Never (3606333) and
# headings (184217).
REAL = {
  3339295: (
    'Fantasma scrittore (innamorato di Olivia, nessun nome); Jenna (ex-fidanza'
    'ta di Dexter, barista); Olivia Dickenson (cliente di Dylan, book scout de'
    'lla Uderground Press); agente Melissa Turner (poliziotta, scrittrice dile'
    'ttante, strega); Janet e Nick (coppia racconto sugli gnomi); Wang (dirett'
    'ore del Chelsea restaurant, morte); Amenophi III (faraone dimenticato, mu'
    'mmia); Jim [as James Trenton] (amico di Jack, sbranato, morte); Jack Grah'
    'am (amico di Jim, sbranato, morte; dottor McMohan (medico pronto soccorso'
    ', malato di porfiria cronica); agente Caruso (licantropo)'),
  4364128: (
    'Florence Carson (cliente di Bloch, crede che il suo capoufficio si un vam'
    'piro); Poly (supportin) (informatore dei bassifondi); Ronny Edge (death ('
    "criminale, si trova all'inferno); Molly Edge (sorella di Ronny, infermier"
    'a); agente Jones; Virgil Bloch (guest) (come capostazione di Nowhere, fig'
    'lio di Bloch, aiuta Dylan)'),
  4318624: (
    'Linda Straub [as Linda Belmont] (antagonist) (esperta di tecniche di mani'
    'polazione mentale, ex agente Stasi, figlia di Heinrich Straub); Allison C'
    'olber (cliente di Dylan, figlia di Joseph Colber); Joseph Colber (padre d'
    'i Allison Colber, suicidato con la pistola); Layton (segretario di Joseph'
    ' Colber, ucciso); Sir Robert Albright (suicida, si \xe8 lanciato da un pa'
    'lazzo); Alan Levin (suicida, bevendo vino avvelenato); Calvin Radek (espe'
    'rto informatico di Scotland Yard); fratello di Robert Albright); Raymond '
    '(autista di Robert Albright); Nick (amico di Allison); Isaia Liddle [as J'
    'anus] (giocatore di golf, presunto responsabile della morte di Johnny Boy'
    '); Johnny Boy Connolly (solo nominato, fratello di Lillie)'),
  3302951: (
    'Clive; Emily (fidanzata di Clive); Tobey; Serena; Derek (capo famiglia); '
    'Myridh (moglie di Derek); figlie di Derek e Myridh [April, May, June, Sea'
    'nna (imprigionata, licantropo)] Rory (fratello di Myridh, cognato di Dere'
    'k).'),
  3606333: (
    'Presidente Burton; Generale Joseph Davis (morte); Colonnello Grant; Signo'
    'ra Thompson (servizi segreti); Masami Hashimoto (entit\xe0 nel cyberspazi'
    'o, contrasta Arkad); Reiko Sanada (entit\xe0 nel cyberspazio, contrasta A'
    "rkad); McCoy (soldatessa, cattura Arkad, perde l'uso delle gambe, feature"
    'd);\r\nPersonaggi minori: Famiglia del prologo [Mark (padre); Beatrix (ma'
    'dre); Billy (figlio); Louise (figlia sopravvissuta)] (uccisi da Arkad); L'
    'upe Vasquez (flashback, morte); Milton (pilota satellite "Born Again"); A'
    'ssistenti di Michael Thomas [Scott; Ash; Greg (pilota trasportatore)] (mo'
    'rti); Soldati semplici (Franklin (morte); Ferguson (morte); Brooks (morte'
    '); Smith]; Yoshihiro Fujiwara; Minako Satoru; Ezra Connery (flashback, pa'
    'dre di Susan Connery); Lockhart (flashback, cameo, uccise Susan Connery);'
    ' Jimmy (pilota flyer); Margareth Grabble [Susan Connery] (falsa identit'
    "\xe0 all'aeroporto Skyfinger); Eveline Dubois (giornalista inviata); Bill"
    'y (pilota flyer).'),
  184217: (
    'X-Men [Cyclops [Scott Summers]; Marvel Girl [Jean Grey]; Angel [Warren Wo'
    'rthington III]; Iceman [Bobby Drake]; Beast [Hank McCoy]]; Professor X; G'
    'UESTS: Quicksliver [Pietro Maximoff]; Scarlet Witch [Wanda Maximoff]; VIL'
    'LAINS: Magneto; Toad [Mortimer Toynbee]; CAMEO FLASHBACK: Avengers [Capta'
    'in America [Steve Rogers]; Hawkeye [Clint Barton]; Hercules; Goliath [Han'
    'k Pym]; Wasp [Janet Van Dyne]]'),
}


@pytest.mark.parametrize('story_id, counts, codes', [
  (3339295, (9, 7, 1, 1), ['marker', 'unclosed']),
  (4364128, (3, 2, 0, 1), ['unclosed']),
  (4318624, (12, 9, 2, 1), ['extra', 'marker']),
  (3302951, (7, 6, 0, 1), ['text_after_group']),
  (3606333, (12, 7, 4, 1), ['crossed', 'heading']),
  (184217, (7, 2, 5, 0), ['heading']),
])
def test_real_texts(story_id, counts, codes):
    """Real texts of the dump give the measured counts and findings."""
    result = report(parse(REAL[story_id]))

    assert (result['items'], result['well_formed'], result['warnings'],
            result['errors']) == counts
    parsed = parse(REAL[story_id])
    assert sorted({found.code for unit in parsed.units
                   for found in unit.diagnostics}) == codes


def test_real_headings_apply_to_the_items_after_them():
    """In a real text each heading applies to the items after it."""
    units = parse(REAL[184217]).units

    assert [read_as(unit) for unit in units[2:5]] == [
      'Quicksliver (guest) [Pietro Maximoff]',
      'Scarlet Witch (guest) [Wanda Maximoff]', 'Magneto (villain)']
    assert read_as(units[6]).startswith('Avengers (cameo, flashback) '
                                        '[Captain America')
    assert [unit.heading for unit in units[:2]] == [None, None]


def _check_invariants(text):
    """The properties that hold for any text."""
    parsed = parse(text)
    report(parsed)
    position = 0
    for part in parsed.parts:
        assert part.start == position
        position = part.end
    assert position == len(text)
    assert ''.join(text[part.start:part.end] for part in parsed.parts) \
        == text
    for unit in parsed.units:
        for found in unit.diagnostics:
            assert 0 <= found.start <= found.end <= len(text)
        if unit.node is None:
            assert unit.level == ERROR
            continue
        _check_spans(unit.node, unit.start, unit.end)
        written = render(unit.node)
        again = parse(written)
        assert len(again.units) == 1
        node = again.units[0].node
        assert node is not None
        assert structure(node) == structure(unit.node)
        assert render(node) == written
        assert not [found for found in again.units[0].diagnostics
                    if found.code == 'spaces']
        if unit.heading:
            _check_read_as(unit)


def _check_read_as(unit):
    """read_as gives a text read as the item plus its heading group."""
    again = parse(read_as(unit))
    assert len(again.units) == 1
    node = again.units[0].node
    assert node is not None
    name, groups, uncertain = structure(unit.node)
    assert structure(node) == (
      name, (('(', unit.heading.readings),) + groups, uncertain)
    assert not [found for found in again.units[0].diagnostics
                if found.code == 'spaces']


def _check_spans(node, start, end):
    """Every span lies inside the span of its parent."""
    assert start <= node.start < node.end <= end
    for group in node.groups:
        assert node.start < group.start < group.end <= node.end
        for element in group.elements:
            _check_spans(element, group.start + 1, group.end - 1)
        for segment in group.segments:
            assert group.start < segment.start < segment.end < group.end


def test_all_short_texts():
    """The invariants hold for every text of up to five characters."""
    alphabet = 'a ;[](),:\n'
    for length in range(6):
        for letters in itertools.product(alphabet, repeat=length):
            _check_invariants(''.join(letters))


def test_random_texts():
    """The invariants hold for 5,000 random texts."""
    generator = random.Random(784)
    letters = 'ab ;[](){},:\n"?.-'
    words = ['cameo', 'O', 'GA', 'villains', 'Villains:', 'as ', 'dies',
             'vilain [villain]', 'cameo flashback', '\r\n', '  ']
    for _ in range(5000):
        text = ''.join(
          generator.choice(letters) if generator.random() < 0.8
          else generator.choice(words)
          for _ in range(generator.randint(1, 40)))
        _check_invariants(text)
