# -*- coding: utf-8 -*-
import json

import pytest
import yaml

from django.contrib.auth.models import Permission
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory

from apps.gcd.models.support import GENRES
from apps.gcd.models import (
    Character, CharacterNameDetail, CharacterRole, CreditType, Creator,
    CreatorNameDetail, Group, GroupNameDetail, StoryCharacter,
    StoryCredit, StoryGroup, Universe)
from apps.indexer.models import Error
from apps.stddata.models import Script
from apps.oi import import_export, states
from apps.oi.models import Changeset, IssueRevision, CTYPES


def _request(user, method='get', data=None):
    request = getattr(RequestFactory(), method)('/', data=data or {})
    request.user = user
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


def _load(response, use_yaml):
    if use_yaml:
        return yaml.safe_load(response.content)
    return json.loads(response.content)


@pytest.fixture
def importer(any_indexer):
    any_indexer.user_permissions.add(
      Permission.objects.get(codename='can_reserve'))
    return type(any_indexer).objects.get(id=any_indexer.id)


@pytest.fixture
def linked_story(any_added_story, any_language, second_brand_same_group):
    story = any_added_story
    # invalid genres are dropped on import
    story.genre = '%s; %s' % (GENRES['en'][0], GENRES['en'][1])
    story.save()
    script = Script.objects.get_or_create(
      id=Script.LATIN_PK,
      defaults={'code': 'Latn', 'number': Script.LATIN_PK, 'name': 'Latin'})[0]
    creator = Creator.objects.create(gcd_official_name='Jane Doe',
                                     sort_name='Doe, Jane', bio='')
    creator_name = CreatorNameDetail.objects.create(
      name='Jane Doe', creator=creator, in_script=script)
    credit_type = CreditType.objects.get_or_create(
      name='script', defaults={'sort_code': 1})[0]
    StoryCredit.objects.create(story=story, creator=creator_name,
                               credit_type=credit_type, is_signed=True,
                               signed_as='J.D., Jr. "the kid"',
                               credit_name='plot; dialogue')
    universe = Universe.objects.create(
      multiverse='Test', name='Earth-2; [alt]', designation='',
      description='', notes='')
    role = CharacterRole.objects.get_or_create(
      name='cameo', defaults={'sort_code': 9999})[0]
    group = Group.objects.create(name='The (Team)', sort_name='Team',
                                 disambiguation='', language=any_language,
                                 description='', notes='')
    group_name = GroupNameDetail.objects.create(name='The (Team)',
                                                group=group)
    StoryGroup.objects.create(story=story, group_name=group_name,
                              universe=universe, notes='as [guests]')
    for name in ('Doe; Jane', 'Doe; Jane'):
        character = Character.objects.create(
          name=name, sort_name=name, disambiguation='', language=any_language,
          description='', notes='')
        appearance = StoryCharacter.objects.create(
          character=CharacterNameDetail.objects.create(
            name=name, sort_name=name, character=character,
            is_official_name=True),
          story=story, universe=universe, group_universe=universe,
          role=role, is_flashback=True, notes='(older), "really"')
        appearance.group.add(group)
        appearance.group_name.add(group_name)
    # a second brand of the same name makes the name lookup ambiguous
    second_brand_same_group.name = story.issue.brand_emblem.get().name
    second_brand_same_group.save()
    return story


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


@pytest.mark.django_db
@pytest.mark.parametrize('use_yaml', [False, True])
def test_structured_export_import_round_trip(importer, linked_story,
                                             use_yaml):
    issue = linked_story.issue
    exported = import_export.export_issue_to_structured_file(
      _request(importer), issue.id, use_yaml=use_yaml)
    original = _load(exported, use_yaml)
    story_data = original['story_set'][0]
    assert story_data['title'] == 'Test Story Title'
    assert story_data['title_inferred'] is True
    assert len(story_data['appearing_characters']) == 2
    assert story_data['appearing_groups'][0]['universe_id']

    response, issue_revision = _import_into_new_changeset(
      importer, issue, exported.content, 'yaml' if use_yaml else 'json')

    assert 'error' not in response['Location']
    story_revision = issue_revision.changeset.storyrevisions.get()
    assert story_revision.story_character_revisions.count() == 2
    assert story_revision.story_group_revisions.count() == 1
    assert story_revision.story_credit_revisions.count() == 1
    reexported = import_export.export_issue_to_structured_file(
      _request(importer), issue_revision.id, use_yaml=use_yaml,
      revision=True)
    assert _load(reexported, use_yaml) == original


@pytest.mark.django_db
def test_structured_import_rejects_unknown_ids(importer, linked_story):
    issue = linked_story.issue
    data = json.loads(import_export.export_issue_to_structured_file(
      _request(importer), issue.id).content)
    data['story_set'][0]['appearing_characters'][1]['character_id'] = 0

    response, issue_revision = _import_into_new_changeset(
      importer, issue, json.dumps(data).encode('utf-8'), 'json')

    error = Error.objects.get(error_key=response['Location'].split('=')[-1])
    assert 'does not exist' in error.error_text
    assert not issue_revision.changeset.storyrevisions.exists()
