# -*- coding: utf-8 -*-

import pytest

from django.test import RequestFactory

from apps.gcd.models import (
    Character, CharacterNameDetail, CharacterRelation, CharacterRelationType,
    CreditType, Group, GroupNameDetail, GroupRelation, GroupRelationType,
    Issue, Series, Universe)
from apps.gcd.models.creator import Creator, CreatorNameDetail
from apps.gcd.models.story import CREDIT_TYPES
from apps.oi import states
from apps.oi.models import (
    CTYPES, Changeset, IssueRevision, StoryCharacterRevision,
    StoryCreditRevision, StoryGroupRevision, StoryRevision)
from apps.oi.views import compare_stories_copy
from apps.stddata.models import Language, Script


@pytest.fixture
def other_language():
    return Language.objects.get_or_create(code='XZY',
                                          name='Other Test Language')[0]


@pytest.fixture
def issue_changeset(any_indexer, any_added_issue):
    changeset = Changeset.objects.create(
        state=states.OPEN, indexer=any_indexer, change_type=CTYPES['issue'])
    IssueRevision.clone(any_added_issue, changeset)
    return changeset


@pytest.fixture
def make_story_revision(issue_changeset, story_add_values):
    def make(issue=None):
        values = dict(story_add_values)
        if issue is not None:
            values['issue'] = issue
        return StoryRevision.objects.create(changeset=issue_changeset,
                                            **values)
    return make


@pytest.fixture
def issue_in_other_language(any_added_issue, other_language):
    series = Series.objects.get(pk=any_added_issue.series_id)
    series.pk = None
    series.language = other_language
    series.save()
    issue = Issue.objects.get(pk=any_added_issue.pk)
    issue.pk = None
    issue.series = series
    issue.save()
    return issue


def make_character(name, language):
    character = Character.objects.create(
        name=name, sort_name=name, disambiguation='', language=language,
        description='', notes='')
    return CharacterNameDetail.objects.create(
        name=name, sort_name=name, character=character, is_official_name=True)


def make_group(name, language):
    group = Group.objects.create(
        name=name, sort_name=name, disambiguation='', language=language,
        description='', notes='')
    return GroupNameDetail.objects.create(
        name=name, sort_name=name, group=group, is_official_name=True)


def make_creator(name):
    script = Script.objects.get_or_create(
        id=Script.LATIN_PK,
        defaults={'code': 'Latn', 'number': Script.LATIN_PK,
                  'name': 'Latin'})[0]
    creator = Creator.objects.create(gcd_official_name=name, sort_name=name)
    return CreatorNameDetail.objects.create(
        name=name, creator=creator, is_official_name=True, in_script=script)


def add_credit(story_revision, creator, **kwargs):
    credit_type = CreditType.objects.get_or_create(
        id=CREDIT_TYPES['script'],
        defaults={'name': 'script', 'sort_code': 1})[0]
    return StoryCreditRevision.objects.create(
        changeset=story_revision.changeset, story_revision=story_revision,
        creator=creator, credit_type=credit_type, **kwargs)


def add_character(story_revision, name_detail, groups=(), **kwargs):
    appearance = StoryCharacterRevision.objects.create(
        changeset=story_revision.changeset, story_revision=story_revision,
        character=name_detail, **kwargs)
    appearance.group_name.add(*groups)
    return appearance


def add_group(story_revision, group_name):
    return StoryGroupRevision.objects.create(
        changeset=story_revision.changeset, story_revision=story_revision,
        group_name=group_name)


def translate_character(original, translation):
    relation_type = CharacterRelationType.objects.get_or_create(
        id=1, defaults={'type': 'republished as',
                        'reverse_type': 'originally published as'})[0]
    CharacterRelation.objects.create(
        from_character=original.character,
        to_character=translation.character,
        relation_type=relation_type, notes='')


def translate_group(original, translation):
    relation_type = GroupRelationType.objects.get_or_create(
        id=1, defaults={'type': 'republished as',
                        'reverse_type': 'originally published as'})[0]
    GroupRelation.objects.create(
        from_group=original.group, to_group=translation.group,
        relation_type=relation_type, notes='')


def compare_and_copy(source, target, **post):
    data = {'field_to_copy': ['script', 'characters'],
            'copy_select': 'Copy Selected Values'}
    data.update(post)
    request = RequestFactory().post('/', data)
    request.user = target.changeset.indexer
    response = compare_stories_copy.__wrapped__(
        request, story_revision_id=target.id, other_revision_id=source.id)
    assert response.status_code == 302


def credits(story_revision):
    return sorted(story_revision.story_credit_revisions.filter(deleted=False)
                  .values_list('creator__name', flat=True))


def characters(story_revision):
    return sorted(story_revision.story_character_revisions
                  .filter(deleted=False)
                  .values_list('character__name', flat=True))


def groups(story_revision):
    return sorted(story_revision.story_group_revisions.filter(deleted=False)
                  .values_list('group_name__name', flat=True))


def group_names(appearance):
    return sorted(appearance.group_name.values_list('name', flat=True))


@pytest.mark.django_db
def test_compare_page_offers_choice_with_replace_as_default(
        make_story_revision):
    source = make_story_revision()
    target = make_story_revision()
    request = RequestFactory().get('/')
    request.user = target.changeset.indexer
    request.session = {}

    response = compare_stories_copy.__wrapped__(
        request, story_revision_id=target.id, other_revision_id=source.id)

    content = response.content.decode()
    assert ('<input type="radio" name="existing" value="replace" checked>'
            in content)
    assert '<input type="radio" name="existing" value="keep">' in content


@pytest.mark.django_db
@pytest.mark.parametrize('post', [{}, {'existing': 'replace'}],
                         ids=['default', 'replace'])
def test_copy_replaces_existing_entries(make_story_revision, any_language,
                                        post):
    source = make_story_revision()
    target = make_story_revision()
    team = make_group('Team', any_language)
    add_credit(source, make_creator('Source Writer'))
    add_character(source, make_character('Hero', any_language), [team])
    add_group(source, team)
    add_credit(target, make_creator('Target Writer'))
    add_character(target, make_character('Bystander', any_language))
    add_group(target, make_group('Other Team', any_language))

    compare_and_copy(source, target, **post)

    assert credits(target) == ['Source Writer']
    assert characters(target) == ['Hero']
    assert groups(target) == ['Team']


@pytest.mark.django_db
def test_copy_keeps_existing_entries(make_story_revision, any_language):
    source = make_story_revision()
    target = make_story_revision()
    writer = make_creator('Writer')
    hero = make_character('Hero', any_language)
    team = make_group('Team', any_language)
    add_credit(source, writer)
    add_credit(source, make_creator('Co-Writer'))
    add_character(source, hero, [team], notes='source notes')
    add_character(source, make_character('Sidekick', any_language))
    add_group(source, team)
    existing_credit = add_credit(target, writer, uncertain=True)
    add_credit(target, make_creator('Translator'))
    existing_hero = add_character(target, hero, notes='target notes')
    add_character(target, make_character('Bystander', any_language))
    add_group(target, team)
    add_group(target, make_group('Other Team', any_language))

    compare_and_copy(source, target, existing='keep')

    assert credits(target) == ['Co-Writer', 'Translator', 'Writer']
    assert characters(target) == ['Bystander', 'Hero', 'Sidekick']
    assert groups(target) == ['Other Team', 'Team']
    existing_credit.refresh_from_db()
    assert existing_credit.uncertain and not existing_credit.deleted
    existing_hero.refresh_from_db()
    assert existing_hero.notes == 'target notes'
    assert not existing_hero.deleted


@pytest.mark.django_db
def test_copy_keep_merges_groups_of_character(make_story_revision,
                                              any_language):
    source = make_story_revision()
    target = make_story_revision()
    universe = Universe.objects.create(
        multiverse='', name='Earth-Test', designation='', description='',
        notes='')
    hero = make_character('Hero', any_language)
    team = make_group('Team', any_language)
    team_alias = GroupNameDetail.objects.create(
        name='The Team', sort_name='Team, The', group=team.group)
    league = make_group('League', any_language)
    add_character(source, hero, [team, league], group_universe=universe)
    with_groups = add_character(target, hero, [team_alias])
    villain = make_character('Villain', any_language)
    add_character(source, villain, [league], group_universe=universe)
    without_groups = add_character(target, villain)

    compare_and_copy(source, target, existing='keep')

    assert characters(target) == ['Hero', 'Villain']
    assert group_names(with_groups) == ['League', 'The Team']
    with_groups.refresh_from_db()
    assert with_groups.group_universe is None
    assert group_names(without_groups) == ['League']
    without_groups.refresh_from_db()
    assert without_groups.group_universe == universe


@pytest.mark.django_db
def test_copy_keep_from_other_language(make_story_revision,
                                       issue_in_other_language,
                                       any_language, other_language):
    source = make_story_revision(issue_in_other_language)
    target = make_story_revision()
    hero = make_character('Hero', other_language)
    heros = make_character('Heros', any_language)
    translate_character(hero, heros)
    sidekick = make_character('Sidekick', other_language)
    acolyte = make_character('Acolyte', any_language)
    translate_character(sidekick, acolyte)
    team = make_group('Team', other_language)
    equipe = make_group('Equipe', any_language)
    translate_group(team, equipe)
    add_character(source, hero, [team])
    add_character(source, sidekick)
    add_group(source, team)
    existing_heros = add_character(target, heros, notes='target notes')
    add_character(target, make_character('Passant', any_language))
    add_group(target, equipe)

    compare_and_copy(source, target, existing='keep')

    assert characters(target) == ['Acolyte', 'Heros', 'Passant']
    assert groups(target) == ['Equipe']
    existing_heros.refresh_from_db()
    assert existing_heros.notes == 'target notes'
    assert group_names(existing_heros) == ['Equipe']
