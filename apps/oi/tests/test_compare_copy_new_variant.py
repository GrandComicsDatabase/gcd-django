"""Compare & Copy with a sequence of an issue that is not approved yet."""
import pytest
from django.urls import reverse

from apps.gcd.models import Issue, Series, StoryType
from apps.gcd.models.character import (
    Character, CharacterNameDetail, CharacterRelation, CharacterRelationType,
    Group, GroupNameDetail, GroupRelation, GroupRelationType)
from apps.oi.models import (IssueRevision, StoryCharacterRevision,
                            StoryGroupRevision, StoryRevision)
from apps.stddata.models import Language

COPY = {'field_to_copy': ['characters'], 'copy_select': 'Copy'}


def _character(name, language):
    """Return the official name of a new character."""
    new = Character.objects.create(name=name, disambiguation='',
                                   language=language, description='',
                                   notes='')
    return CharacterNameDetail.objects.create(name=name, character=new,
                                              is_official_name=True)


def _group(name, language):
    """Return the official name of a new group."""
    new = Group.objects.create(name=name, disambiguation='',
                               language=language, description='', notes='')
    return GroupNameDetail.objects.create(name=name, group=new,
                                          is_official_name=True)


def _appear(revision, character, group):
    """Put a character and a group on a revision."""
    StoryCharacterRevision.objects.create(
      changeset=revision.changeset, story_revision=revision,
      character=character, notes='')
    StoryGroupRevision.objects.create(
      changeset=revision.changeset, story_revision=revision, group_name=group,
      notes='')


def _copied_names(revision):
    """Return the names of the character and the group of a revision."""
    return (revision.story_character_revisions.get().character.name,
            revision.story_group_revisions.get().group_name.name)


def _revisions_url(target, source):
    """Return the address of Compare & Copy between two revisions."""
    return reverse('compare_revisions_copy',
                   kwargs={'story_revision_id': target.id,
                           'other_revision_id': source.id})


@pytest.fixture
def indexer_client(client, any_indexer):
    """Return a client logged in as the holder of the changeset."""
    any_indexer.is_superuser = True
    any_indexer.save()
    client.force_login(any_indexer)
    return client


@pytest.fixture
def base_issue_revision(any_added_issue, any_variant_adding_changeset):
    """Return the revision of the base issue, older than the variant's."""
    return IssueRevision.clone(data_object=any_added_issue,
                               changeset=any_variant_adding_changeset)


@pytest.fixture
def new_variant_story(base_issue_revision, any_added_variant_rev,
                      story_add_values):
    """Return the cover sequence of a variant that is not approved yet."""
    values = dict(story_add_values, issue=None, sequence_number=0,
                  type=StoryType.objects.get(name='cover'))
    revision = StoryRevision(changeset=any_added_variant_rev.changeset,
                             **values)
    revision.save()
    return revision


@pytest.fixture
def base_story(any_added_variant_rev, story_add_values):
    """Return a sequence of the base issue in the same changeset."""
    revision = StoryRevision(changeset=any_added_variant_rev.changeset,
                             **story_add_values)
    revision.save()
    return revision


@pytest.fixture
def french_story(any_adding_changeset, story_add_values, any_added_issue):
    """Return a revision of a sequence in another language."""
    series = Series.objects.get(id=any_added_issue.series_id)
    series.pk = None
    series.language = Language.objects.create(code='XZF', name='Test French')
    series.save()
    issue = Issue.objects.get(id=any_added_issue.id)
    issue.pk = None
    issue.series = series
    issue.number = '2'
    issue.save()
    revision = StoryRevision(changeset=any_adding_changeset,
                             **dict(story_add_values, issue=issue))
    revision.save()
    return revision


@pytest.mark.django_db
def test_copy_to_a_sequence_of_a_new_variant(
  indexer_client, new_variant_story, any_added_story, any_added_story_rev,
  any_language):
    """An approved sequence can be copied into one with no issue yet."""
    _appear(any_added_story_rev, _character('Hero', any_language),
            _group('Team', any_language))
    url = reverse('compare_stories_copy',
                  kwargs={'story_revision_id': new_variant_story.id,
                          'story_id': any_added_story.id})

    assert indexer_client.get(url).status_code == 200
    response = indexer_client.post(url, COPY)

    assert response.status_code == 302
    assert _copied_names(new_variant_story) == ('Hero', 'Team')


@pytest.mark.django_db
def test_copy_from_a_sequence_of_a_new_variant(
  indexer_client, new_variant_story, base_story, any_language):
    """A sequence with no issue yet can be the source of the copy."""
    _appear(new_variant_story, _character('Hero', any_language),
            _group('Team', any_language))
    url = _revisions_url(base_story, new_variant_story)

    assert indexer_client.get(url).status_code == 200
    response = indexer_client.post(url, COPY)

    assert response.status_code == 302
    assert _copied_names(base_story) == ('Hero', 'Team')


@pytest.mark.django_db
@pytest.mark.parametrize('target_name', ['new_variant_story', 'base_story'])
def test_copy_from_another_language_uses_the_translations(
  request, indexer_client, target_name, french_story, any_language):
    """A copy from another language takes the translated names."""
    target = request.getfixturevalue(target_name)
    french = french_story.issue.series.language
    hero, team = _character('Heros', french), _group('Equipe', french)
    character_kind = CharacterRelationType.objects.get_or_create(
      id=1, defaults={'type': 'translation', 'reverse_type': 'translation'})
    CharacterRelation.objects.create(
      from_character=hero.character,
      to_character=_character('Hero', any_language).character,
      relation_type=character_kind[0])
    group_kind = GroupRelationType.objects.get_or_create(
      id=1, defaults={'type': 'translation', 'reverse_type': 'translation'})
    GroupRelation.objects.create(
      from_group=team.group, to_group=_group('Team', any_language).group,
      relation_type=group_kind[0])
    _appear(french_story, hero, team)

    response = indexer_client.post(_revisions_url(target, french_story), COPY)

    assert response.status_code == 302
    assert _copied_names(target) == ('Hero', 'Team')
