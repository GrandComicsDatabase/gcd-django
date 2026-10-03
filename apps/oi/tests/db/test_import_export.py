# -*- coding: utf-8 -*-
import csv
import io
import json
from collections import Counter
from decimal import Decimal

import pytest
import yaml

from django.contrib.auth.models import Permission
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from django.urls import reverse

from apps.gcd.models import (
    Character, CharacterNameDetail, CreditType, Creator, CreatorNameDetail,
    CreatorSignature, Issue, Series, Story, StoryCharacter, StoryCredit)
from apps.indexer.models import Error
from apps.stddata.models import Language, Script
from apps.oi import import_export, states
from apps.oi.interchange import (
    Ref, Resolver, characters_text, check_text, issue_record, migrate_text,
    read_characters, render_characters, resolved_rows)
from apps.oi.models import Changeset, IssueRevision, CTYPES

FORMATS = ['csv', 'tsv', 'json', 'yaml']


def _request(user, method='get', data=None):
    request = getattr(RequestFactory(), method)('/', data=data or {})
    request.user = user
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


@pytest.fixture
def importer(any_indexer):
    any_indexer.user_permissions.add(
      Permission.objects.get(codename='can_reserve'))
    return type(any_indexer).objects.get(id=any_indexer.id)


@pytest.fixture
def credited_story(story_with_characters):
    story = story_with_characters
    script = Script.objects.get_or_create(
      id=Script.LATIN_PK,
      defaults={'code': 'Latn', 'number': Script.LATIN_PK, 'name': 'Latin'})[0]
    creator = Creator.objects.create(gcd_official_name='Jane Doe',
                                     sort_name='Doe, Jane', bio='',
                                     disambiguation='(writer)')
    creator_name = CreatorNameDetail.objects.create(
      name='Jane Doe', creator=creator, in_script=script)
    # a generic and a specific signature of the same name
    signatures = [CreatorSignature.objects.create(
                    name='J. D. (1)', creator=creator, notes='',
                    generic=generic) for generic in (True, False)]
    for name, signature in zip(('script', 'pencils'), signatures):
        credit_type = CreditType.objects.get_or_create(
          name=name, defaults={'sort_code': len(name)})[0]
        StoryCredit.objects.create(
          story=story, creator=creator_name, credit_type=credit_type,
          is_signed=True, signature=signature, signed_as='J.D., Jr. "kid"',
          is_credited=True, credited_as='as: me',
          credit_name='plot; dialogue')
    # control characters and escapes in text fields
    story.notes = 'line one\r\nline\ttwo ^n'
    story.save()
    return Story.objects.get(id=story.id)


def _export(user, issue_id, file_format, revision=False):
    if file_format in ('csv', 'tsv'):
        return import_export.export_issue_to_file(
          _request(user), issue_id, use_csv=file_format == 'csv',
          revision=revision).content
    return import_export.export_issue_to_structured_file(
      _request(user), issue_id, use_yaml=file_format == 'yaml',
      revision=revision).content


def _load(content, file_format):
    text = content.decode('utf-8')
    if file_format == 'csv':
        return list(csv.reader(io.StringIO(text, newline='')))
    if file_format == 'tsv':
        return [line.split('\t') for line in text.split('\r\n')]
    if file_format == 'yaml':
        return yaml.safe_load(text)
    return json.loads(text)


def _import_into_new_changeset(user, issue, content, file_format):
    changeset = Changeset.objects.create(indexer=user, state=states.OPEN,
                                         change_type=CTYPES['issue'])
    issue_revision = IssueRevision.clone(issue, changeset)
    response = import_export.import_issue_from_file(
      _request(user, 'post', {
        'flatfile': SimpleUploadedFile('issue.' + file_format, content),
        file_format: '1'}),
      issue.id, changeset.id)
    return response, issue_revision


def _error_text(response):
    return Error.objects.get(
      error_key=response['Location'].split('=')[-1]).error_text


@pytest.mark.django_db
@pytest.mark.parametrize('file_format', FORMATS)
def test_issue_round_trip(importer, credited_story, file_format):
    issue = credited_story.issue
    exported = _export(importer, issue.id, file_format)
    assert b'{#' not in exported

    response, issue_revision = _import_into_new_changeset(
      importer, issue, exported, file_format)

    assert 'error' not in response['Location']
    story_revision = issue_revision.changeset.storyrevisions.get()
    assert story_revision.notes == credited_story.notes
    assert story_revision.story_credit_revisions.count() == 2
    assert story_revision.story_character_revisions.count() == 5
    assert story_revision.story_group_revisions.count() == 2
    reexported = _export(importer, issue_revision.id, file_format,
                         revision=True)
    assert _load(reexported, file_format) == _load(exported, file_format)


@pytest.mark.django_db
@pytest.mark.parametrize('file_format', FORMATS)
def test_series_import_adds_issue_with_sequences(importer, credited_story,
                                                 file_format):
    issue = credited_story.issue
    response = import_export.import_issues_to_series(
      _request(importer, 'post', {
        'file': SimpleUploadedFile('issue.' + file_format,
                                   _export(importer, issue.id, file_format)),
        file_format: '1'}),
      issue.series.id)

    assert 'error' not in response['Location']
    changeset = Changeset.objects.filter(
      change_type=CTYPES['issue_add'], indexer=importer).get()
    issue_revision = changeset.issuerevisions.get()
    assert issue_revision.number == issue.number
    assert list(issue_revision.brand_emblem.all()) == \
        list(issue.brand_emblem.all())
    story_revision = changeset.storyrevisions.get()
    assert story_revision.issue is None
    assert story_revision.story_credit_revisions.count() == 2
    # the sequences are part of the changeset
    assert story_revision in list(changeset.revisions)


def _flat_with(user, story, column, value):
    rows = _load(_export(user, story.issue.id, 'tsv'), 'tsv')
    rows[2][rows[0].index(column)] = value
    rows[1][rows[0].index('notes')] = 'changed by the import'
    return '\r\n'.join('\t'.join(row) for row in rows).encode('utf-8')


@pytest.mark.django_db
@pytest.mark.parametrize('column, value, message', [
    ('characters', 'Nobody', 'line 3, column characters, position 1: '
                             'unknown character name detail'),
    ('characters', 'Ben Parker (Flashback; Cameo)',
     'line 3, column characters, position 22: unescaped reserved character'),
    ('characters', '#1 Fan {other}', 'candidates: #1 Fan {#hash} (XZZ, #'),
    ('characters', '#1 Fan (cameo) (x) (y)', 'repeated qualifier'),
    ('characters', 'Jane [&Team]', 'only characters inside a character'),
    ('credits', 'Jane Doe (inks)', 'missing credit type'),
    ('credits', 'Jane Doe {(writer)} (script)',
     'line 3, column credits, position 11: unescaped reserved character'),
    ('credits', 'John Doe (script)', 'unknown creator name detail'),
    ('type', 'comic', 'unknown story type'),
    ('notes', 'dangling ^', 'line 3, column notes'),
    ('title_inferred', 'maybe', 'expected &quot;yes&quot;')])
def test_import_is_all_or_nothing(importer, credited_story, column, value,
                                  message):
    issue = credited_story.issue
    response, issue_revision = _import_into_new_changeset(
      importer, issue, _flat_with(importer, credited_story, column, value),
      'tsv')

    assert message in _error_text(response)
    assert not issue_revision.changeset.storyrevisions.exists()
    issue_revision.refresh_from_db()
    assert issue_revision.notes != 'changed by the import'


@pytest.mark.django_db
def test_credits_text(credited_story):
    story, = [story for story in issue_record(credited_story.issue)[
               'story_set'] if 'credits' in story]
    assert story['credits'] == (
      'Jane Doe {^(writer^)} (script) (credited, signed) (as: as: me) '
      '(signed as: J.D., Jr. "kid") (generic signature: J. D. ^(1^)) '
      '(plot^; dialogue); '
      'Jane Doe {^(writer^)} (pencils) (credited, signed) (as: as: me) '
      '(signed as: J.D., Jr. "kid") (signature: J. D. ^(1^)) '
      '(plot^; dialogue)')


@pytest.mark.django_db
def test_fields_not_used_by_the_series(importer, credited_story):
    issue = credited_story.issue
    Series.objects.filter(id=issue.series_id).update(has_isbn=False)
    Issue.objects.filter(id=issue.id).update(isbn='123', no_isbn=True)
    issue = Issue.objects.get(id=issue.id)
    # GCD neither shows nor saves them
    record = issue_record(issue)
    assert 'isbn' not in record and 'no_isbn' not in record

    response, issue_revision = _import_into_new_changeset(
      importer, issue, b'record\tnumber\tisbn\r\nissue\t1\t123\r\n', 'tsv')

    assert 'isbn: the series does not use this field' in \
        _error_text(response)


@pytest.mark.django_db
def test_import_needs_header(importer, credited_story):
    rows = _load(_export(importer, credited_story.issue.id, 'tsv'), 'tsv')
    content = '\r\n'.join('\t'.join(row) for row in rows[1:])

    response, issue_revision = _import_into_new_changeset(
      importer, credited_story.issue, content.encode('utf-8'), 'tsv')

    assert 'the first row must be the header row' in _error_text(response)


@pytest.mark.django_db
def test_import_by_names_with_some_columns(importer, credited_story):
    # names without disambiguation, which are unique
    content = 'record\tnumber\ttitle\ttype\tcharacters\tcredits\r\n' \
              'issue\t1\t\t\t\t\r\n' \
              'sequence\t\tMy Title\tcomic story\t' \
              '#1 Fan (cameo) ;; Ben Parker\t' \
              'Jane Doe (script) (credited)\r\n'

    response, issue_revision = _import_into_new_changeset(
      importer, credited_story.issue, content.encode('utf-8'), 'tsv')

    assert 'error' not in response['Location']
    story_revision = issue_revision.changeset.storyrevisions.get()
    appearance = story_revision.active_characters.get()
    assert appearance.character.name == '#1 Fan'
    assert appearance.role.name == 'cameo'
    assert story_revision.characters == 'Ben Parker'
    credit = story_revision.story_credit_revisions.get()
    assert (credit.creator.name, credit.is_credited) == ('Jane Doe', True)


@pytest.fixture
def duplicate_jane(story_with_characters, any_language):
    """
    A second character with the same name and disambiguation.
    """
    jane = CharacterNameDetail.objects.get(name='Doe; Jane')
    duplicate = Character.objects.create(
      name=jane.name, sort_name=jane.name, disambiguation='711',
      language=any_language, description='', notes='')
    CharacterNameDetail.objects.create(name=jane.name, sort_name=jane.name,
                                       character=duplicate)
    return jane


@pytest.mark.django_db
def test_ambiguous_names_list_the_candidates(importer, credited_story,
                                             duplicate_jane):
    # the duplicate is used in the series as well
    StoryCharacter.objects.create(
      story=credited_story, character=CharacterNameDetail.objects.exclude(
        id=duplicate_jane.id).get(name=duplicate_jane.name), notes='')

    response, issue_revision = _import_into_new_changeset(
      importer, credited_story.issue,
      _export(importer, credited_story.issue.id, 'json'), 'json')

    error = _error_text(response)
    assert 'ambiguous character name detail &quot;Doe; Jane&quot;' in error
    assert error.count('Doe; Jane {711}') >= 2


@pytest.mark.django_db
def test_names_used_in_the_series_are_preferred(importer, credited_story,
                                                duplicate_jane):
    response, issue_revision = _import_into_new_changeset(
      importer, credited_story.issue,
      _export(importer, credited_story.issue.id, 'json'), 'json')

    assert 'error' not in response['Location']
    story_revision = issue_revision.changeset.storyrevisions.get()
    assert duplicate_jane.id in story_revision.active_characters.values_list(
      'character', flat=True)


GROUP_FIELDS = ('group_name', 'universe', 'notes')
APPEARANCE_FIELDS = ('character', 'universe', 'group_universe', 'role',
                     'is_flashback', 'is_origin', 'is_death', 'notes',
                     'group', 'group_name')


def _state(groups, appearances, free_text):
    """
    The characters as multisets, the database stores no order.
    """
    def ids(objects):
        if hasattr(objects, 'all'):
            objects = objects.all()
        return tuple(sorted(related.id for related in objects))

    def value(values, name):
        return values[name].id if values[name] else None

    return (
      Counter((value(g, 'group_name'), value(g, 'universe'), g['notes'])
              for g in groups),
      Counter((value(a, 'character'), value(a, 'universe'),
               value(a, 'group_universe'), value(a, 'role'),
               a['is_flashback'], a['is_origin'], a['is_death'], a['notes'],
               ids(a['group']), ids(a['group_name']))
              for a in appearances),
      free_text)


def _story_state(story):
    return _state(
      [{name: getattr(group, name) for name in GROUP_FIELDS}
       for group in story.active_groups],
      [{name: getattr(appearance, name) for name in APPEARANCE_FIELDS}
       for appearance in story.active_characters],
      story.characters)


def _series_resolver(story):
    # as the import into the series of the story reads
    return Resolver(story.issue.series.language, story.issue.series)


def _resolved_state(story, characters):
    groups, appearances = _series_resolver(story).resolve(characters)
    return _state(groups, appearances, characters.free_text)


# the characters of story_with_characters as text
CHARACTERS = (
  '^&Ben ^{x^} ^^ {Parker ^(Earth^)} (&The ^(Team^) {^#1}) '
  '(&&Team^; ^[B^] {^#1}) (&@Test: Earth-2^; ^[alt^] - ^(b^)) (!x^; ^(y^)); '
  'Doe^; Jane {711} (death) (^flashback); '
  '@DC: mainstream [&Team^; ^[B^] {^#1} (^@home)]; '
  '@Marvel: mainstream [&The ^(Team^) {^#1} (&) (as ^[guests^]) '
  '[^&Ben ^{x^} ^^ {Parker ^(Earth^)} (@DC: mainstream) (origin); '
  'Doe^; Jane {711} (flashback) (cameo) (^cameo)]]; '
  '@Test: Earth-2^; ^[alt^] - ^(b^) '
  '[#1 Fan {^#hash} (&@DC: mainstream) (=no role)] '
  ';; Ben Parker (Flashback; Cameo)')


@pytest.mark.django_db
def test_characters_round_trip(story_with_characters):
    story = Story.objects.get(id=story_with_characters.id)
    text = characters_text(story)
    assert text == CHARACTERS

    resolver = _series_resolver(story)
    characters = read_characters(text, resolver)
    groups, appearances = resolver.resolve(characters)
    assert _state(groups, appearances, characters.free_text) == \
        _story_state(story)
    assert render_characters(resolver, *resolved_rows(groups, appearances),
                             characters.free_text) == text


@pytest.mark.django_db
def test_characters_by_name_and_in_order(story_with_characters):
    """
    The tree written by a person: members inherit universe and group,
    names without disambiguation are unique, flags and roles in any case.
    """
    story = Story.objects.get(id=story_with_characters.id)
    resolver = Resolver(story.issue.series.language)
    characters = read_characters(
      '@Marvel: mainstream [&The ^(Team^) [#1 Fan (Cameo) (Origin,Death)]]',
      resolver)
    (group,), (fan,) = resolver.resolve(characters)
    assert (group['group_name'].name, group['universe'].designation) == (
      'The (Team)', 'mainstream')
    assert fan['universe'] == fan['group_universe'] == group['universe']
    assert fan['group_name'] == [group['group_name']]
    assert fan['group'] == []
    assert (fan['role'].name, fan['is_origin'], fan['is_death']) == (
      'cameo', True, True)


@pytest.mark.django_db
def test_migrate_free_text(story_with_characters, any_language):
    resolver = Resolver(any_language)
    text = 'Spider-Man [Peter Parker]; #1 Fan (cameo); #1 Fan (Corpse, 2)'
    assert migrate_text(text, resolver) == ([], [], text, [], [])

    groups, appearances, remaining, errors, unresolved = migrate_text(
      text, resolver, plain_names=True)
    cameo, corpse = appearances
    assert cameo['character'].name == '#1 Fan'
    assert cameo['role'].name == 'cameo'
    assert corpse['notes'] == 'Corpse, 2'
    assert remaining == 'Spider-Man [Peter Parker]'
    assert errors == []
    # why it stayed text
    assert 'Spider-Man' in str(unresolved[0])


@pytest.fixture
def legacy_story(any_added_story, any_language):
    """
    A story with structured characters as GCD shows them as text: a group
    with members, civilian identities, a universe other than the one of
    the story, and names which are ambiguous without the context.
    """
    from apps.gcd.models import (
        CharacterRelation, CharacterRelationType, CharacterRole, Group,
        GroupMembership, GroupMembershipType, GroupNameDetail,
        StoryCharacter, StoryGroup, Universe)

    def universe(name):
        return Universe.objects.create(multiverse='DC', name=name,
                                       designation='', description='',
                                       notes='')

    def name(model, text):
        related = model.objects.create(
          name=text, sort_name=text, language=any_language,
          description='', notes='')
        detail = GroupNameDetail if model is Group else CharacterNameDetail
        return detail.objects.create(name=text, sort_name=text,
                                     is_official_name=True,
                                     **{model.__name__.lower(): related})

    earth_1, earth_2 = universe('Earth-1'), universe('Earth-2')
    alias_of = CharacterRelationType.objects.get_or_create(
      id=2, defaults={'type': 'alias of',
                      'reverse_type': 'secret identity of'})[0]
    member = GroupMembershipType.objects.create(type='member',
                                                reverse_type='has member')
    guest = CharacterRole.objects.get_or_create(
      name='guest', defaults={'sort_code': 9998})[0]
    league = name(Group, 'Justice League')
    batman, bruce = name(Character, 'Batman'), name(Character, 'Bruce Wayne')
    flash = name(Character, 'Flash')
    name(Character, 'Flash')
    superman, clark = name(Character, 'Superman'), name(Character, 'Clark')
    name(Character, 'Robin')
    name(Group, 'Robin')
    for hero, civilian in ((batman, bruce), (superman, clark)):
        CharacterRelation.objects.create(
          from_character=hero.character, to_character=civilian.character,
          relation_type=alias_of, notes='')
    for hero in (batman, flash):
        GroupMembership.objects.create(
          character=hero.character, group=league.group,
          membership_type=member, notes='')

    story = any_added_story
    story.universe.set([earth_1])
    StoryGroup.objects.create(story=story, group_name=league,
                              universe=earth_1, notes='first team')

    def appearance(character, universe, group=None, **values):
        story_character = StoryCharacter.objects.create(
          story=story, character=character, universe=universe,
          group_universe=universe if group else None,
          **{'notes': '', **values})
        if group:
            story_character.group_name.set([group])

    appearance(batman, earth_1, league, role=guest)
    appearance(bruce, earth_1)
    appearance(flash, earth_1, league, is_flashback=True, is_death=True)
    appearance(superman, earth_2, is_origin=True, notes='as Kal-El, once')
    appearance(clark, earth_2)
    story.characters = ''
    story.save()
    return story


@pytest.mark.django_db
def test_migrate_gcd_text(legacy_story):
    """
    The text GCD shows for structured characters converts back to them.
    """
    story = Story.objects.get(id=legacy_story.id)
    text = story.show_characters_as_text()
    assert text == (
      'Justice League (first team) [Batman [Bruce Wayne] (guest); '
      'Flash (flashback, death)]; Superman [Clark] (Earth-2) (origin) '
      '(as Kal-El, once)')

    groups, appearances, remaining, errors, unresolved = migrate_text(
      text, Resolver(story.issue.series.language), plain_names=True,
      reference_universe=story.universe.get())

    assert (remaining, errors, unresolved) == ('', [], [])
    assert _state(groups, appearances, '') == _story_state(story)


@pytest.mark.django_db
def test_migrate_legacy_keeps_unresolved_entries(legacy_story):
    resolver = Resolver(legacy_story.issue.series.language)
    text = ('Robin; Flash; Superman [Bruce Wayne]; Batman [Bruce Wayne] '
            '(Earth-3); Zeta (a(b)); Justice League [Flash; Nobody]; '
            'Batman (cameo) (villain)')

    groups, appearances, remaining, errors, unresolved = migrate_text(
      text, resolver, plain_names=True)

    assert (groups, errors) == ([], [])
    # unknown notes are notes, a second role is not
    assert [(appearance['character'].name, appearance['notes'])
            for appearance in appearances] == [
        ('Superman', ''), ('Bruce Wayne', ''), ('Batman', 'Earth-3'),
        ('Bruce Wayne', '')]
    # a group or a character, ambiguous and unknown names stay text
    assert remaining == (
      'Robin; Flash; Zeta (a(b)); Justice League [Flash; Nobody]; '
      'Batman (cameo) (villain)')
    # and say why
    assert [(error.kind, error.message) for error in unresolved] == [
      ('ambiguous', 'ambiguous group or character'),
      ('ambiguous', 'ambiguous character name detail'),
      ('not_found', 'unknown character name detail'),
      ('not_found', 'unknown character name detail'),
      ('syntax', 'repeated qualifier')]
    assert unresolved[0].candidates == ['&Robin', 'Robin']
    # migrating again changes nothing
    assert migrate_text(remaining, resolver, plain_names=True)[:4] == (
      [], [], remaining, [])


@pytest.mark.django_db
def test_migrate_reads_text_written_by_hand(legacy_story):
    """
    Names in any case, a role and flags in one qualifier, a universe by
    its name; the notation writes them back as GCD has them.
    """
    story = Story.objects.get(id=legacy_story.id)
    resolver = Resolver(story.issue.series.language)
    text = ('earth-2 [superman (guest, origin)]; justice league [batman '
            '(flashback death)]; Clark (guest villain)')

    groups, appearances, remaining, errors, unresolved = migrate_text(
      text, resolver, plain_names=True)

    assert (remaining, errors, unresolved) == ('', [], [])
    (league,), (superman, batman, clark) = groups, appearances
    assert (superman['character'].name, superman['universe'].name,
            superman['role'].name, superman['is_origin']) == (
      'Superman', 'Earth-2', 'guest', True)
    assert league['group_name'].name == 'Justice League'
    assert (batman['group_name'], batman['is_flashback'],
            batman['is_death']) == ([league['group_name']], True, True)
    # two roles are a note
    assert (clark['role'], clark['notes']) == (None, 'guest villain')
    assert '@DC: Earth-2 [Superman (origin) (guest)' in render_characters(
      resolver, *resolved_rows(groups, appearances))


@pytest.mark.django_db
def test_migrate_tells_universe_group_and_character_apart(legacy_story):
    resolver = Resolver(legacy_story.issue.series.language)
    text = 'DC [Justice League [Batman]]; Robin [Superman]'

    groups, appearances, remaining, errors, unresolved = migrate_text(
      text, resolver, plain_names=True)

    assert remaining == text
    multiverse, robin = unresolved
    assert (multiverse.message, multiverse.candidates) == (
      'a multiverse, not a universe', ['@DC: Earth-1', '@DC: Earth-2'])
    assert (robin.message, robin.candidates) == (
      'ambiguous group or character', ['&Robin', 'Robin'])


@pytest.mark.django_db
def test_characters_are_checked_while_typed(legacy_story, importer, client):
    series = legacy_story.issue.series
    problems, text = check_text('justice league [batman (guest); Nobody',
                                Resolver(series.language, series))
    assert 'unbalanced bracket' in str(problems[0])
    assert 'unknown character name detail "Nobody"' in str(problems[-1])

    client.force_login(importer)
    response = client.post(
      reverse('check_characters', kwargs={'series_id': series.id}),
      {'characters': 'superman (guest, origin); DC [Batman]'})

    content = response.content.decode()
    assert 'a multiverse, not a universe' in content
    assert 'Migrate saves: <code>Superman (origin) (guest) ;; DC [Batman]' \
        '</code>' in content


@pytest.mark.django_db
def test_note_of_keywords_stays_a_note(legacy_story):
    story = Story.objects.get(id=legacy_story.id)
    StoryCharacter.objects.filter(story=story, character__name='Clark') \
        .update(notes='guest, death')
    resolver = Resolver(story.issue.series.language)

    text = characters_text(story, resolver)

    assert 'Clark (^guest, death)' in text
    clark, = [appearance for appearance in
              resolver.resolve(read_characters(text, resolver))[1]
              if appearance['character'].name == 'Clark']
    assert (clark['notes'], clark['role'], clark['is_death']) == (
      'guest, death', None, False)


@pytest.mark.django_db
def test_migrate_reports_unresolved_notation(story_with_characters,
                                             any_language):
    jane = CharacterNameDetail.objects.get(name='Doe; Jane')
    duplicate = Character.objects.create(
      name=jane.name, sort_name=jane.name, disambiguation='711',
      language=any_language, description='', notes='')
    CharacterNameDetail.objects.create(name=jane.name, sort_name=jane.name,
                                       character=duplicate)
    text = 'Doe^; Jane {711}; Nobody (@DC: mainstream); Ben Parker'

    groups, appearances, remaining, errors, unresolved = migrate_text(
      text, Resolver(any_language))

    assert (groups, appearances, remaining, unresolved) == ([], [], text, [])
    ambiguous, unknown = errors
    assert ambiguous.kind == 'ambiguous'
    assert len(ambiguous.candidates) == 2
    assert unknown.kind == 'not_found'


@pytest.mark.django_db
def test_story_form_checks_and_migrates_characters(story_with_characters,
                                                   any_editing_changeset):
    from django import forms
    from apps.oi.forms.story import get_story_revision_form
    from apps.oi.models import StoryRevision

    revision = StoryRevision.clone(data_object=story_with_characters,
                                   changeset=any_editing_changeset)
    form_class = get_story_revision_form(revision=revision,
                                         user=any_editing_changeset.indexer)
    text = '#1 Fan (cameo); Nobody; Ben Parker (Flashback; Cameo)'

    # saving checks only what is written in the notation
    form = form_class(data={}, instance=revision)
    form.cleaned_data = {'characters': text, 'universe': []}
    assert form.clean_characters() == text
    form.cleaned_data = {'characters': 'Nobody (@DC: mainstream)',
                         'universe': []}
    with pytest.raises(forms.ValidationError) as error:
        form.clean_characters()
    assert 'unknown character name detail' in str(error.value)

    # the migrate button converts what resolves
    form = form_class(data={'save_migrate_characters': '1'},
                      instance=revision)
    form.cleaned_data = {'characters': text, 'universe': []}
    assert form.clean_characters() == 'Nobody; Ben Parker (Flashback; Cameo)'
    groups, (fan,) = form.migrated_characters
    assert (fan['character'].name, fan['role'].name) == ('#1 Fan', 'cameo')


@pytest.mark.django_db
def test_api_record_is_the_export(client, credited_story):
    issue = credited_story.issue
    response = client.get('/api/issue/%d/record/?format=json' % issue.id)

    assert response.status_code == 200
    assert response.json() == json.loads(json.dumps(issue_record(issue)))


@pytest.mark.django_db
def test_names_alike_get_the_official_name(story_with_characters,
                                           any_language):
    # another character with a name of the same name and disambiguation
    jane = CharacterNameDetail.objects.get(name='Doe; Jane')
    other = Character.objects.create(
      name='Jane Roe', sort_name='Roe, Jane', disambiguation='711',
      language=any_language, description='', notes='')
    alias = CharacterNameDetail.objects.create(
      name=jane.name, sort_name=jane.name, character=other)
    StoryCharacter.objects.create(story=story_with_characters,
                                  character=alias, notes='alias')
    story = Story.objects.get(id=story_with_characters.id)

    text = characters_text(story)

    # the name of Jane Doe herself needs no second anchor
    assert 'Doe^; Jane {711} (death)' in text
    assert 'Doe^; Jane {711} {Jane Roe} (alias)' in text
    resolver = _series_resolver(story)
    characters = read_characters(text, resolver)
    groups, appearances = resolver.resolve(characters)
    assert _state(groups, appearances, characters.free_text) == \
        _story_state(story)


@pytest.mark.django_db
def test_the_language_of_the_series_before_the_official_name(
      story_with_characters, any_language):
    other_language = Language.objects.get_or_create(
      code='XZY', name='Other Language')[0]
    # Twitch, also named Twitch Williams, and a character of another
    # language named Twitch Williams
    twitch = Character.objects.create(
      name='Twitch', sort_name='Twitch', disambiguation='Spawn',
      language=any_language, description='', notes='')
    alias = CharacterNameDetail.objects.create(
      name='Twitch Williams', sort_name='Williams, Twitch', character=twitch)
    other = Character.objects.create(
      name='Twitch Williams', sort_name='Williams, Twitch',
      disambiguation='Spawn', language=other_language, description='',
      notes='')
    CharacterNameDetail.objects.create(
      name='Twitch Williams', sort_name='Williams, Twitch', character=other,
      is_official_name=True)
    StoryCharacter.objects.create(story=story_with_characters,
                                  character=alias)
    story = Story.objects.get(id=story_with_characters.id)

    text = characters_text(story)

    assert 'Twitch Williams {Spawn};' in text
    characters = read_characters(text, _series_resolver(story))
    assert _resolved_state(story, characters) == _story_state(story)


@pytest.mark.django_db
def test_ghost_names_of_creators(credited_story):
    # Tony Isabella wrote as Len Wein
    script = Script.objects.get(id=Script.LATIN_PK)
    wein = Creator.objects.create(gcd_official_name='Len Wein',
                                  sort_name='Wein, Len', bio='')
    isabella = Creator.objects.create(gcd_official_name='Tony Isabella',
                                      sort_name='Isabella, Tony', bio='')
    names = [CreatorNameDetail.objects.create(
               name='Len Wein', creator=creator, in_script=script)
             for creator in (wein, isabella)]
    editing = CreditType.objects.get_or_create(
      name='editing', defaults={'sort_code': 100})[0]
    for name in names:
        StoryCredit.objects.create(story=credited_story, creator=name,
                                   credit_type=editing)
    story, = [story for story in issue_record(credited_story.issue)[
               'story_set'] if 'credits' in story]
    assert story['credits'].endswith(
      'Len Wein (editing); Len Wein {} {Tony Isabella} (editing)')
    # the name of Len Wein himself is preferred without second anchor
    resolver = Resolver()
    assert resolver.resolve_ref(CreatorNameDetail,
                                Ref('Len Wein')) == names[0]
    assert resolver.resolve_ref(CreatorNameDetail, Ref(
      'Len Wein', disambiguation='', owner='Tony Isabella')) == names[1]


HAND_WRITTEN = '''
number: 99
page_count: 36
page_count_uncertain: true
story_set:
- type: comic story
  title: Written by hand
  page_count: 8.5
  credits: Jane Doe (script) (credited)
  characters: '@Marvel: mainstream [&The ^(Team^) {^#1} [#1 Fan (Cameo)]]
    ;; Ben Parker'
'''


@pytest.mark.django_db
def test_hand_written_yaml_adds_an_issue(importer, credited_story):
    response = import_export.import_issues_to_series(
      _request(importer, 'post', {
        'file': SimpleUploadedFile('issue.yaml', HAND_WRITTEN.encode()),
        'yaml': '1'}),
      credited_story.issue.series.id)

    assert 'error' not in response['Location']
    changeset = Changeset.objects.filter(
      change_type=CTYPES['issue_add'], indexer=importer).get()
    issue_revision = changeset.issuerevisions.get()
    assert (issue_revision.number, issue_revision.page_count,
            issue_revision.page_count_uncertain) == ('99', 36, True)
    story_revision = changeset.storyrevisions.get()
    assert (story_revision.title, story_revision.page_count) == (
      'Written by hand', Decimal('8.5'))
    assert story_revision.characters == 'Ben Parker'
    group, = story_revision.active_groups
    fan, = story_revision.active_characters
    assert (group.group_name.name, group.universe.designation) == (
      'The (Team)', 'mainstream')
    assert (fan.character.name, fan.role.name, fan.universe) == (
      '#1 Fan', 'cameo', group.universe)
    assert list(fan.group_name.all()) == [group.group_name]
    credit, = story_revision.story_credit_revisions.all()
    assert (credit.creator.name, credit.credit_type.name,
            credit.is_credited) == ('Jane Doe', 'script', True)
