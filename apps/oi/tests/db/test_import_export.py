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

from apps.gcd.models import (
    Brand, Character, CharacterNameDetail, CreditType, Creator,
    CreatorNameDetail, CreatorSignature, Group, GroupNameDetail, Issue,
    Series, Story, StoryCharacter, StoryCredit)
from apps.indexer.models import Error
from apps.stddata.models import Language, Script
from apps.oi import import_export, states
from apps.oi.interchange import (
    FLAGS, AppearanceRow, GroupRow, Ref, Resolver, characters_text,
    issue_record, read_characters, render_characters)
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


@pytest.fixture
def namesakes(story_with_characters, any_language):
    """
    A namesake of the same language for the characters, groups and creator
    of the story, so that their disambiguations are needed.
    """
    for name in CharacterNameDetail.objects.filter(
          storycharacter__story=story_with_characters).distinct():
        CharacterNameDetail.objects.create(
          name=name.name, sort_name=name.name, is_official_name=True,
          character=Character.objects.create(
            name=name.name, sort_name=name.name, disambiguation='namesake',
            language=any_language, description='', notes=''))
    group = Group.objects.create(
      name='The (Team)', sort_name='Team', disambiguation='namesake',
      language=any_language, description='', notes='')
    for name in ('The (Team)', 'Team; [B]'):
        GroupNameDetail.objects.create(name=name, group=group,
                                       is_official_name=name == group.name)
    script = Script.objects.get_or_create(
      id=Script.LATIN_PK,
      defaults={'code': 'Latn', 'number': Script.LATIN_PK, 'name': 'Latin'})[0]
    CreatorNameDetail.objects.create(
      name='Jane Doe', in_script=script, creator=Creator.objects.create(
        gcd_official_name='Jane Doe', sort_name='Doe, Jane', bio='',
        disambiguation='namesake'))


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
def test_issue_round_trip(importer, credited_story, namesakes, file_format):
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


# a file of format 1.0: the issue, a sequence and a cover, in the columns
# of GCD before this record
LEGACY_ISSUE = ['7', '', '', 'None', 'May 2020', '2020-05.00', '',
                '3.99 USD', '36?', 'None', '', 'legacy notes', '',
                '2020-03-11?', '', '', '', '', '']
LEGACY_STORIES = [
  ['[Opening]', 'Comic Story', 'Legacy Feature', '12?', 'Jane Doe', 'None',
   '', '', '', '', '', 'Ben Parker; Somebody', '', '', '', 'first sequence',
   '', ''],
  ['', 'cover', '', '1', '', 'John Doe', '', '', '', '']]


def _legacy_file(file_format):
    from apps.oi.interchange import LEGACY_ISSUE_FIELDS, LEGACY_STORY_FIELDS
    if file_format in ('json', 'yaml'):
        data = dict(zip(LEGACY_ISSUE_FIELDS, LEGACY_ISSUE))
        data['story_set'] = [dict(zip(LEGACY_STORY_FIELDS, story))
                             for story in LEGACY_STORIES]
        if file_format == 'yaml':
            return yaml.safe_dump(data).encode()
        return json.dumps(data).encode()
    rows = [LEGACY_ISSUE] + LEGACY_STORIES
    if file_format == 'csv':
        text = io.StringIO()
        csv.writer(text).writerows(rows)
        return text.getvalue().encode()
    return ''.join('\t'.join(row) + '\r\n' for row in rows).encode()


@pytest.mark.django_db
@pytest.mark.parametrize('file_format', FORMATS)
def test_import_reads_format_1_0_as_before(importer, credited_story,
                                           file_format):
    issue = credited_story.issue
    response, issue_revision = _import_into_new_changeset(
      importer, issue, _legacy_file(file_format), file_format)

    assert 'error' not in response['Location']
    issue_revision.refresh_from_db()
    assert (issue_revision.number, issue_revision.no_volume,
            issue_revision.no_brand, issue_revision.key_date,
            issue_revision.page_count, issue_revision.page_count_uncertain,
            issue_revision.no_editing, issue_revision.notes) == (
      '7', True, True, '2020-05-00', Decimal(36), True, True, 'legacy notes')
    assert (issue_revision.year_on_sale, issue_revision.month_on_sale,
            issue_revision.day_on_sale,
            issue_revision.on_sale_date_uncertain) == (2020, 3, 11, True)
    first, cover = issue_revision.changeset.storyrevisions.order_by(
      'sequence_number')
    # credits, feature and characters are text, as before
    assert (first.title, first.title_inferred, first.feature,
            first.page_count, first.page_count_uncertain, first.script,
            first.no_pencils, first.no_editing, first.characters,
            first.notes) == (
      'Opening', True, 'Legacy Feature', Decimal(12), True, 'Jane Doe', True,
      True, 'Ben Parker; Somebody', 'first sequence')
    assert not first.story_credit_revisions.exists()
    assert not first.story_character_revisions.exists()
    assert (cover.pencils, cover.no_script, cover.no_letters,
            cover.no_editing) == ('John Doe', True, True, True)


@pytest.mark.django_db
@pytest.mark.parametrize('file_format', FORMATS)
def test_format_1_0_skips_fields_not_used_by_the_series(
      importer, credited_story, file_format):
    # GCD read them unseen, the empty volume of the file set no_volume
    issue = credited_story.issue
    Series.objects.filter(id=issue.series_id).update(has_volume=False)
    Issue.objects.filter(id=issue.id).update(volume='3', no_volume=False)
    issue = Issue.objects.get(id=issue.id)

    response, issue_revision = _import_into_new_changeset(
      importer, issue, _legacy_file(file_format), file_format)

    assert 'error' not in response['Location']
    issue_revision.refresh_from_db()
    assert (issue_revision.number, issue_revision.volume,
            issue_revision.no_volume) == ('7', '3', False)


@pytest.mark.django_db
def test_import_reads_the_json_of_the_issue_page(importer,
                                                 story_with_characters,
                                                 client):
    # the issue page offers the JSON of the API for download; GCD did not
    # find names with a trailing space, as the brand of the fixture, either
    issue = story_with_characters.issue
    for brand in issue.brand_emblem.all():
        Brand.objects.filter(id=brand.id).update(name=brand.name.strip())
    content = client.get('/api/issue/%d/?format=json' % issue.id).content
    assert b'"api_url"' in content

    response, issue_revision = _import_into_new_changeset(
      importer, issue, content, 'json')

    location = response['Location']
    assert 'error' not in location, _error_text(response)
    story_revision = issue_revision.changeset.storyrevisions.get()
    # the characters are text, as before
    assert story_revision.characters
    assert not story_revision.story_character_revisions.exists()


@pytest.mark.django_db
def test_series_import_reads_format_1_0_variants(importer, credited_story):
    issue = credited_story.issue
    variant = [issue.number] + LEGACY_ISSUE[1:] + ['Sketch Cover',
                                                   'artwork difference']
    text = io.StringIO()
    csv.writer(text).writerows([LEGACY_ISSUE, variant, LEGACY_STORIES[1]])

    response = import_export.import_issues_to_series(
      _request(importer, 'post', {
        'file': SimpleUploadedFile('issues.csv', text.getvalue().encode()),
        'csv': '1'}),
      issue.series.id)

    assert 'error' not in response['Location']
    added, sketch = [changeset.issuerevisions.get() for changeset in
                     Changeset.objects.filter(
                       change_type=CTYPES['issue_add'], indexer=importer)
                     .order_by('id')]
    assert (added.number, added.variant_of) == ('7', None)
    assert (sketch.variant_of, sketch.variant_name,
            sketch.variant_cover_status) == (issue, 'Sketch Cover', 3)
    # the cover after a variant is its sequence
    assert sketch.changeset.storyrevisions.get().type.name == 'cover'


@pytest.mark.django_db
@pytest.mark.parametrize('file_format', ['json', 'tsv'])
def test_export_is_not_read_as_format_1_0(importer, credited_story,
                                          file_format):
    exported = _export(importer, credited_story.issue.id, file_format)
    if file_format == 'json':
        assert json.loads(exported)['record'] == 'issue'
    response, issue_revision = _import_into_new_changeset(
      importer, credited_story.issue, exported, file_format)
    assert 'error' not in response['Location']
    assert issue_revision.changeset.storyrevisions.get() \
        .story_character_revisions.count() == 5


@pytest.mark.django_db
@pytest.mark.parametrize('file_format', FORMATS)
def test_series_import_adds_issues_without_sequences(importer, credited_story,
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
    # the sequences are added in a second step, from the issue
    assert not changeset.storyrevisions.exists()


@pytest.mark.django_db
@pytest.mark.parametrize('status, message', [
    ('NO_DIFFERENCE', 'but a sequence exists for variant'),
    ('ARTWORK_DIFFERENCE', 'is not of type cover')])
def test_series_import_checks_the_cover_of_a_variant(importer, credited_story,
                                                     status, message):
    issue = credited_story.issue
    data = json.loads(_export(importer, issue.id, 'json'))
    data.update({'variant_of': issue.number, 'variant_name': 'Sketch Cover',
                 'variant_cover_status': status})

    response = import_export.import_issues_to_series(
      _request(importer, 'post', {
        'file': SimpleUploadedFile('issue.json', json.dumps(data).encode()),
        'json': '1'}),
      issue.series.id)

    assert message in _error_text(response)
    assert not Changeset.objects.filter(
      change_type=CTYPES['issue_add'], indexer=importer).exists()


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
def test_credits_text(credited_story, namesakes):
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
def test_disambiguation_only_for_namesakes(any_language):
    other_language = Language.objects.get_or_create(
      code='XZY', name='Other Language')[0]

    def character(name, disambiguation, language=any_language):
        return CharacterNameDetail.objects.create(
          name=name, sort_name=name, is_official_name=True,
          character=Character.objects.create(
            name=name, sort_name=name, disambiguation=disambiguation,
            language=language, description='', notes=''))

    bloch = character('Bloch', 'Dylan Dog')
    groucho = character('Groucho', 'Dylan Dog')
    character('Groucho', 'uit Dylan Dog', other_language)
    xabaras = character('Xabaras', 'Dylan Dog')
    character('Xabaras', 'Martin Mystère')
    resolver = Resolver(language=any_language)

    assert [resolver.reference(CharacterNameDetail, name)
            for name in (bloch, groucho, xabaras)] == [
      'Bloch', 'Groucho', 'Xabaras {Dylan Dog}']


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
def test_rows_without_header_are_format_1_0(importer, credited_story):
    rows = _load(_export(importer, credited_story.issue.id, 'tsv'), 'tsv')
    content = '\r\n'.join('\t'.join(row) for row in rows[1:])

    response, issue_revision = _import_into_new_changeset(
      importer, credited_story.issue, content.encode('utf-8'), 'tsv')

    assert 'at line 1: a row of issue of format 1.0, a file without header ' \
        'row, has 10 to 19 cells' in _error_text(response)


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


def _rows(groups, appearances):
    def by_id(objects):
        return sorted(objects, key=lambda related: related.id)

    return (
      [GroupRow(values['group_name'], values['universe'], values['notes'])
       for values in groups],
      [AppearanceRow(values['character'], values['universe'],
                     by_id(values['group']), by_id(values['group_name']),
                     values['group_universe'], values['role'],
                     [flag for flag in FLAGS if values['is_' + flag]],
                     values['notes'])
       for values in appearances])


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
def test_characters_round_trip(story_with_characters, namesakes):
    story = Story.objects.get(id=story_with_characters.id)
    text = characters_text(story)
    assert text == CHARACTERS

    resolver = _series_resolver(story)
    characters = read_characters(text, resolver)
    groups, appearances = resolver.resolve(characters)
    assert _state(groups, appearances, characters.free_text) == \
        _story_state(story)
    assert render_characters(resolver, *_rows(groups, appearances),
                             characters.free_text) == text


@pytest.mark.django_db
@pytest.mark.parametrize('file_format', FORMATS)
def test_characters_typed_as_text_stay_text(importer, story_with_characters,
                                            file_format):
    """
    A name typed as text is not linked by a download and upload, even if it
    is the name of a character.
    """
    story = story_with_characters
    story.characters = '#1 Fan (cameo)'
    story.save()
    story = Story.objects.get(id=story.id)
    assert characters_text(story).endswith(' ;; #1 Fan (cameo)')

    response, issue_revision = _import_into_new_changeset(
      importer, story.issue, _export(importer, story.issue.id, file_format),
      file_format)

    assert 'error' not in response['Location'], _error_text(response)
    story_revision = issue_revision.changeset.storyrevisions.get()
    assert story_revision.characters == '#1 Fan (cameo)'
    assert story_revision.story_character_revisions.count() == \
        story.active_characters.count()


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
def test_export_writes_civilian_identities_as_gcd(legacy_story):
    story = Story.objects.get(id=legacy_story.id)

    text = characters_text(story)

    # inside a group and outside, as GCD shows them
    assert 'Batman [Bruce Wayne] (guest)' in text
    assert 'Superman [Clark] (origin)' in text
    characters = read_characters(text, _series_resolver(story))
    assert _resolved_state(story, characters) == _story_state(story)


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

    # the namesake is of another language
    assert 'Twitch Williams;' in text
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
def test_hand_written_yaml_is_imported(importer, credited_story):
    response, issue_revision = _import_into_new_changeset(
      importer, credited_story.issue, HAND_WRITTEN.encode(), 'yaml')

    assert 'error' not in response['Location'], _error_text(response)
    issue_revision.refresh_from_db()
    assert (issue_revision.number, issue_revision.page_count,
            issue_revision.page_count_uncertain) == ('99', 36, True)
    story_revision = issue_revision.changeset.storyrevisions.get()
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
