# -*- coding: utf-8 -*-
import pytest

from apps.oi.interchange import (
    LIST_RESERVED, REF_RESERVED, NotationError, Ref, canonical_text, escape,
    keywords_of, parse_item, parse_items, parse_ref, render_ref,
    split_free_text, split_items, tokens_of)


def text_of(tokens):
    return ''.join(token[0] for token in tokens)


def plain(tokens):
    return not any(token[1] for token in tokens)


@pytest.mark.parametrize('text', [
    'Doe; Jane', 'a^b', '(The) [Team] {x}', '@home', '&Ben', '=cameo',
    '!death', '#1 Fan', ' leading', 'trailing ', ';;', '  ',
    'two\r\nlines\ttab'])
def test_escaped_name_and_note(text):
    item, = parse_items('%s (%s)' % (escape(text), escape(text)))
    assert item.name.label == text
    (kind, value, position), = item.qualifiers
    assert (kind, text_of(value)) == ('text', text)


@pytest.mark.parametrize('note, escaped', [
    ('cameo', '^cameo'), ('flashback, death', '^flashback, death'),
    ('napping', 'n^apping'), ('a (b)', 'a ^(b^)')])
def test_note_read_as_keyword_has_an_escape(note, escaped):
    assert escape(note, keyword=True) == escaped
    item, = parse_items('A (%s)' % escaped)
    (kind, value, position), = item.qualifiers
    assert text_of(value) == note
    assert not plain(value)


@pytest.mark.parametrize('text, keywords', [
    ('Cameo', ('cameo', [])), ('Origin,Death', (None, ['origin', 'death'])),
    ('villain, death', ('villain', ['death'])),
    ('cameo flashback', ('cameo', ['flashback'])),
    ('cameo, villain', None), ('death, death', None), ('Corpse, 2', None),
    ('villain, introduction', None), (' ', None)])
def test_role_and_flags_share_a_qualifier(text, keywords):
    assert keywords_of(text, {'cameo': 'cameo', 'villain': 'villain'}) == \
        keywords


@pytest.mark.parametrize('name, disambiguation, written', [
    ('DC [circle and serifs]', '', 'DC [circle and serifs]'),
    ('12 Evergreens (trees)', '', '12 Evergreens (trees)'),
    ('@#*!', '', '@#*!'),
    ('Salleck Publications; édition B.D.', '',
     'Salleck Publications^; édition B.D.'),
    ('Royal', 'U. S. Royal; adventure (co',
     'Royal {U. S. Royal^; adventure (co}'),
    ('a^b {c}', '', 'a^^b ^{c^}')])
def test_lists_of_linked_objects_escape_little(name, disambiguation,
                                                written):
    assert render_ref(name, disambiguation, reserved=LIST_RESERVED) == \
        written
    item, = split_items(tokens_of(written), brackets={'{': '}'})
    ref = parse_ref(item, 0, reserved=LIST_RESERVED)
    assert (ref.label, ref.disambiguation or '') == (name, disambiguation)


def test_single_linked_object_keeps_semicolons():
    written = render_ref('A Seita C.R.L.; Geomais, Lda. (x)',
                         reserved=REF_RESERVED)
    assert written == 'A Seita C.R.L.; Geomais, Lda. (x)'
    assert parse_ref(tokens_of(written), 0, reserved=REF_RESERVED).label == \
        'A Seita C.R.L.; Geomais, Lda. (x)'


def test_anchor_id_and_disambiguation():
    items = parse_items('A {#711}; B {711}; C {^#711}; D {^{x^}}; E {}')
    assert [(item.name.id, item.name.disambiguation) for item in items] == [
        (711, None), (None, '711'), (None, '#711'), (None, '{x}'), (None, '')]


def test_qualifier_sigils():
    item, = parse_items(
      'A (@Marvel: mainstream) (&The ^(Team^) {#5}) (&&Team {^#1}) '
      '(&@Test: Earth-2^; ^[alt^]) (flashback, death) (cameo) '
      '(as ^[guests^])')
    kinds = [kind for kind, value, position in item.qualifiers]
    assert kinds == ['universe', 'group', 'group_name', 'group_universe',
                     'text', 'text', 'text']
    universe, group, group_name, group_universe = [
      value for kind, value, position in item.qualifiers[:4]]
    assert universe == Ref('Marvel: mainstream', position=4)
    assert (group.label, group.id) == ('The (Team)', 5)
    assert (group_name.label, group_name.disambiguation) == ('Team', '#1')
    assert group_universe.label == 'Test: Earth-2; [alt]'
    assert [text_of(value) for kind, value, position
            in item.qualifiers[4:]] == ['flashback, death', 'cameo',
                                        'as [guests]']


def test_empty_sigils():
    item, = parse_items('A (@) (&@)')
    assert [(kind, value) for kind, value, position in item.qualifiers] == [
        ('universe', None), ('group_universe', None)]
    group, = parse_items('&G (&) (&&)')
    assert group.sigil == '&'
    assert [(kind, value) for kind, value, position in group.qualifiers] == [
        ('group', None), ('group_name', None)]


def test_tree():
    universe, spider = parse_items(
      '@Marvel: mainstream [&The ^(Team^) {^#1} (as ^[guests^]) '
      '[Jane (cameo); Ben (@)]; Logan]; Spider-Man [Peter Parker]')
    assert (universe.sigil, universe.name.label) == ('@', 'Marvel: mainstream')
    team, logan = universe.children
    assert (team.sigil, team.name.label, team.name.disambiguation) == (
      '&', 'The (Team)', '#1')
    assert [member.name.label for member in team.children] == ['Jane', 'Ben']
    assert logan.children is None
    assert spider.children[0].name.label == 'Peter Parker'


@pytest.mark.parametrize('text, free_text, count', [
    (';; Ben Parker (Flashback; Cameo)', 'Ben Parker (Flashback; Cameo)', 0),
    ('A ;; Ben Parker (Flashback; Cameo)', 'Ben Parker (Flashback; Cameo)',
     1),
    ('A ;; x ;; y', 'x ;; y', 1),
    ('A;;x', 'x', 1),
    (';;  two spaces', ' two spaces', 0),
    ('A; B', None, 2),
    ('', None, 0)])
def test_free_text(text, free_text, count):
    tokens, found = split_free_text(tokens_of(text))
    assert found == free_text
    assert len(split_items(tokens)) == count


def test_free_text_escapes_only_caret_and_controls():
    tokens, free_text = split_free_text(tokens_of(';; a ( ;; [ ^^ ^n'))
    assert free_text == 'a ( ;; [ ^ \n'


@pytest.mark.parametrize('text, position, token', [
    ('Ben Parker (Flashback; Cameo)', 21, ';'),
    ('A (x', 4, ''),
    ('A (x)) ', 5, ')'),
    ('A^', 1, ''),
    ('A ()', 3, ''),
    ('A {#x}', 3, '#x'),
    ('A; ; B', 3, ''),
    ('A;', 2, ''),
    ('A [B] [C]', 6, '[C]'),
    ('A [B; ]', 6, ''),
    ('A (x) B', 6, 'B'),
    ('A (x) {y}', 6, '{y}'),
    ('A {x} y', 6, 'y'),
    ('A [B (x]', 7, ']'),
    ('@', 1, ''),
    ('A (& {x})', 4, '')])
def test_syntax_errors(text, position, token):
    with pytest.raises(NotationError) as error:
        parse_items(text)
    assert error.value.kind == 'syntax'
    assert (error.value.position, error.value.token) == (position, token)


# the canonical stress test of github.com/ProfNardi/ParserCharacters
STRESS_TEST = (
  'Alpha (a,b) (c); Alpha; Alpha (a); Beta [X]; Beta [Y] (i1,i2); '
  'Beta [X] (i3); Gamma [A;B]; Gamma [A; B]; Gamma [A; B; C]; '
  'Gamma [A [AA]; B]; Gamma [A; B [BB]]; Delta [One Two]; Delta [One; Two]; '
  'Delta [One; Two] (info); Epsilon [Solo]; Epsilon (info) [Solo]; '
  'Epsilon [Solo] (info1, info2); Zeta (a(b)); Zeta (a,b; Eta [Unclosed; '
  'Theta (Unclosed; Iota [A] [B]; Iota [A] (x) [B] (y); Kappa [M [N [O]]]; '
  'Kappa [M; N [O; P]]; Lambda; Lambda (x); Lambda (y); Mu [X; Y] [Z]; '
  'Mu [X] [Y; Z]; Nu [A [B; C]; D]; Xi; Omicron (o1,o2) (o3); '
  'Pi [P1 [P2] (pinfo)]; Rho [R1; R2] (rinfo1, rinfo2); '
  'Sigma [One Two; Three]; Tau [One; Two Three]; Upsilon [A; B] (u1) '
  '(u2,u3); Phi [A; B]; Chi [A [AA] (i1); B]; Psi [A; B] (i); Omega')


def _tolerant(text):
    results = []
    for item in split_items(tokens_of(text, tolerant=True), tolerant=True):
        try:
            results.append(parse_item(item, tolerant=True))
        except NotationError as error:
            results.append(error)
    return results


def test_legacy_stress_test():
    results = _tolerant(STRESS_TEST)
    assert len(results) == 42
    assert sorted(result.message for result in results
                  if isinstance(result, NotationError)) == [
        'second square bracket', 'second square bracket',
        'second square bracket', 'second square bracket',
        'unbalanced bracket', 'unbalanced bracket', 'unbalanced bracket']
    canonical = canonical_text(STRESS_TEST)
    assert 'Gamma [A; B]; Gamma [A; B];' in canonical
    assert 'Zeta (a^(b^))' in canonical
    assert canonical_text(canonical) == canonical


@pytest.mark.parametrize('text', [
    STRESS_TEST, 'A [B', 'A (x; B (y; C', 'A [x; B [y]', ';;; A ;  ; B;',
    'A ] B; C', 'A [B (c]; D)', 'Ben Parker (Flashback; Cameo)',
    'X  [ a ;b ](  c  d )', 'A ^', '&G (&) [M (@)]; @U [N] ;; free ^ text'])
def test_canonical_text_is_idempotent(text):
    canonical = canonical_text(text)
    assert canonical_text(canonical) == canonical


@pytest.mark.parametrize('text, canonical', [
    # nothing is dropped: text after the brackets is kept as written
    ('A (x) B', 'A (x) B'),
    # a note is kept whole, commas included
    ('A (as Tom, Dick)', 'A (as Tom, Dick)'),
    # a character also appearing as a member is kept
    ('Batman; JLA [Batman; Flash]', 'Batman; JLA [Batman; Flash]'),
    ('A(x)', 'A (x)'),
    ('Justice League [Wonder Woman; Batman [Bruce Wayne] (cameo)];'
     'Jimmy Olsen (origin, death)',
     'Justice League [Wonder Woman; Batman [Bruce Wayne] (cameo)]; '
     'Jimmy Olsen (origin, death)')])
def test_canonical_text_loses_nothing(text, canonical):
    assert canonical_text(text) == canonical


def test_second_anchor_names_the_owner():
    item, = parse_items('Warlock {Marvel} {Adam Warlock} (cameo)')
    assert (item.name.label, item.name.disambiguation, item.name.owner) == (
      'Warlock', 'Marvel', 'Adam Warlock')
    item, = parse_items('X {} {A}')
    assert (item.name.disambiguation, item.name.owner) == ('', 'A')
    for text, message in (('A {x} {y} {z}', 'more than two anchors'),
                          ('A {x} {}', 'empty anchor')):
        with pytest.raises(NotationError) as error:
            parse_items(text)
        assert error.value.message == message


def test_empty_disambiguation_before_the_second_anchor():
    from apps.oi.interchange import render_ref
    assert escape('') == ''
    text = render_ref('X', '', owner='@A')
    assert text == 'X {} {^@A}'
    item, = parse_items(text)
    assert (item.name.disambiguation, item.name.owner) == ('', '@A')
