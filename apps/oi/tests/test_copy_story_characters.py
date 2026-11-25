"""Copy of the characters and groups of a sequence to another one."""
import pytest

from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.gcd.models import Issue, Series
from apps.gcd.models.character import (
    Character, CharacterNameDetail, CharacterRelation, CharacterRelationType,
    Group, GroupNameDetail, GroupRelation, GroupRelationType, Universe)
from apps.oi.models import (
    StoryCharacterRevision, StoryGroupRevision, StoryRevision)
from apps.stddata.models import Language

COPY = {'field_to_copy': ['characters'], 'copy_select': 'Copy'}
KEEP = dict(COPY, keep_characters='on')


def story_revision(changeset, values, **others):
    """Return a new revision of a sequence."""
    revision = StoryRevision(changeset=changeset, **dict(values, **others))
    revision.save()
    return revision


@pytest.fixture
def indexer_client(client, any_indexer):
    """Return a client of the indexer who holds the revisions."""
    any_indexer.user_permissions.add(
      Permission.objects.get(codename='can_reserve'))
    client.force_login(any_indexer)
    return client


@pytest.fixture
def source(any_adding_changeset, story_add_values):
    """Return the revision that is copied from."""
    return story_revision(any_adding_changeset, story_add_values)


@pytest.fixture
def target(any_adding_changeset, story_add_values):
    """Return a revision in the language of the source."""
    return story_revision(any_adding_changeset, story_add_values)


@pytest.fixture
def french():
    """Return the language of the reprint."""
    return Language.objects.create(code='XZF', name='Test French')


@pytest.fixture
def reprint(any_adding_changeset, story_add_values, any_added_issue, french):
    """Return a revision of a sequence in another language."""
    series = Series.objects.get(id=any_added_issue.series_id)
    series.pk = None
    series.language = french
    series.save()
    issue = Issue.objects.get(id=any_added_issue.id)
    issue.pk = None
    issue.series = series
    issue.number = '2'
    issue.save()
    return story_revision(any_adding_changeset, story_add_values, issue=issue)


def character(name, language):
    """Return the official name of a new character."""
    new = Character.objects.create(name=name, disambiguation='',
                                   language=language, description='',
                                   notes='')
    return CharacterNameDetail.objects.create(name=name, character=new,
                                              is_official_name=True)


def group(name, language):
    """Return the official name of a new group."""
    new = Group.objects.create(name=name, disambiguation='',
                               language=language, description='', notes='')
    return GroupNameDetail.objects.create(name=name, group=new,
                                          is_official_name=True)


def appears(name, revision, notes='', universe=None):
    """Add a character to a revision."""
    StoryCharacterRevision.objects.create(
      changeset=revision.changeset, story_revision=revision, character=name,
      notes=notes, universe=universe)


def group_appears(name, revision, notes=''):
    """Add a group to a revision."""
    StoryGroupRevision.objects.create(
      changeset=revision.changeset, story_revision=revision, group_name=name,
      notes=notes)


def translated(name, translation):
    """Make a character the translation of another one."""
    kind = CharacterRelationType.objects.get_or_create(
      id=1, defaults={'type': 'translation', 'reverse_type': 'translation'})
    CharacterRelation.objects.create(
      from_character=name.character, to_character=translation.character,
      relation_type=kind[0])


def group_translated(name, translation):
    """Make a group the translation of another one."""
    kind = GroupRelationType.objects.get_or_create(
      id=1, defaults={'type': 'translation', 'reverse_type': 'translation'})
    GroupRelation.objects.create(
      from_group=name.group, to_group=translation.group,
      relation_type=kind[0])


def characters(revision):
    """Return the name and notes of the characters of a revision."""
    return sorted(revision.story_character_revisions.exclude(deleted=True)
                  .values_list('character__name', 'notes'))


def groups(revision):
    """Return the name and notes of the groups of a revision."""
    return sorted(revision.story_group_revisions.exclude(deleted=True)
                  .values_list('group_name__name', 'notes'))


def copy(client, source, target, data):
    """Send the copy form, and return the target as it is stored."""
    response = client.post(reverse(
      'compare_revisions_copy', kwargs={'story_revision_id': target.id,
                                        'other_revision_id': source.id}), data)
    assert response.status_code == 302
    target.refresh_from_db()
    return target


@pytest.mark.django_db
def test_page_offers_keeping(indexer_client, source, target):
    """The page of a sequence has the choice."""
    response = indexer_client.get(reverse(
      'compare_revisions_copy', kwargs={'story_revision_id': target.id,
                                        'other_revision_id': source.id}))
    assert 'name="keep_characters"' in response.content.decode()


@pytest.mark.django_db
def test_copy_replaces_without_keeping(indexer_client, source, target,
                                       any_language):
    """Not asked to keep, the target ends up with what the source has."""
    both = character('Both', any_language)
    appears(character('Only target', any_language), target, 'mine')
    appears(both, target, 'same')
    appears(both, source, 'same')
    appears(character('Only source', any_language), source, 'theirs')

    copy(indexer_client, source, target, COPY)

    assert characters(target) == [('Both', 'same'),
                                  ('Only source', 'theirs')]


@pytest.mark.django_db
def test_keeping_adds_only_the_others(indexer_client, source, target,
                                      any_language):
    """What the target has stays as it is; the rest is added."""
    both = character('Both', any_language)
    appears(character('Only target', any_language), target, 'mine')
    appears(both, target, 'mine')
    appears(both, source, 'theirs')
    appears(character('Only source', any_language), source, 'theirs')

    copy(indexer_client, source, target, KEEP)

    assert characters(target) == [('Both', 'mine'),
                                  ('Only source', 'theirs'),
                                  ('Only target', 'mine')]


@pytest.mark.django_db
def test_keeping_tells_universes_apart(indexer_client, source, target,
                                       any_language):
    """A character of another universe is another appearance."""
    name = character('Twice', any_language)
    universe = Universe.objects.create(
      multiverse='Test', name='Other', designation='1', description='',
      notes='')
    appears(name, target, 'mine')
    appears(name, source, 'theirs', universe)

    copy(indexer_client, source, target, KEEP)

    assert characters(target) == [('Twice', 'mine'), ('Twice', 'theirs')]


def reprint_characters(source, reprint, english, french):
    """Fill a source and its reprint in another language."""
    spider = character('Spider', english)
    hulk = character('Hulk', english)
    araignee = character('Araignee', french)
    translated(spider, araignee)
    translated(hulk, character('Hulk FR', french))
    appears(spider, source, 'theirs')
    appears(hulk, source, 'theirs')
    appears(character('Untranslated', english), source, 'theirs')
    appears(araignee, reprint, 'mine')
    appears(character('Only FR', french), reprint, 'mine')


@pytest.mark.django_db
def test_copy_to_a_reprint_replaces_without_keeping(
      indexer_client, source, reprint, any_language, french):
    """Not asked to keep, what has no counterpart in the source goes."""
    reprint_characters(source, reprint, any_language, french)

    copy(indexer_client, source, reprint, COPY)

    assert characters(reprint) == [('Araignee', 'theirs'),
                                   ('Hulk FR', 'theirs')]


@pytest.mark.django_db
def test_keeping_on_a_reprint_adds_only_missing_translations(
      indexer_client, source, reprint, any_language, french):
    """A translation already there is not added twice."""
    reprint_characters(source, reprint, any_language, french)

    copy(indexer_client, source, reprint, KEEP)

    assert characters(reprint) == [('Araignee', 'mine'),
                                   ('Hulk FR', 'theirs'),
                                   ('Only FR', 'mine')]


@pytest.mark.django_db
def test_keeping_covers_the_groups(indexer_client, source, target,
                                   any_language):
    """Groups follow the characters."""
    both = group('Both', any_language)
    group_appears(group('Only target', any_language), target, 'mine')
    group_appears(both, target, 'mine')
    group_appears(both, source, 'theirs')
    group_appears(group('Only source', any_language), source, 'theirs')

    copy(indexer_client, source, target, KEEP)

    assert groups(target) == [('Both', 'mine'), ('Only source', 'theirs'),
                              ('Only target', 'mine')]


@pytest.mark.django_db
def test_keeping_translates_the_groups(indexer_client, source, reprint,
                                       any_language, french):
    """A group already there in translation is not added twice."""
    team = group('Team', any_language)
    other = group('Other', any_language)
    equipe = group('Equipe', french)
    group_translated(team, equipe)
    group_translated(other, group('Other FR', french))
    group_appears(team, source, 'theirs')
    group_appears(other, source, 'theirs')
    group_appears(equipe, reprint, 'mine')
    group_appears(group('Only FR', french), reprint, 'mine')

    copy(indexer_client, source, reprint, KEEP)

    assert groups(reprint) == [('Equipe', 'mine'), ('Only FR', 'mine'),
                               ('Other FR', 'theirs')]


@pytest.mark.django_db
@pytest.mark.parametrize('data, had, stored', [
    (KEEP, 'Mine', 'Mine'),
    (KEEP, '', 'Theirs'),
    (COPY, 'Mine', 'Theirs'),
])
def test_text_of_the_characters(indexer_client, source, target, data, had,
                                stored):
    """Keeping also keeps the text, unless there is none."""
    source.characters = 'Theirs'
    source.save()
    target.characters = had
    target.save()

    assert copy(indexer_client, source, target, data).characters == stored


@pytest.mark.django_db
def test_keeping_does_not_touch_the_other_fields(indexer_client, source,
                                                 target):
    """The choice is about the characters only."""
    source.title = 'Theirs'
    source.save()

    copied = copy(indexer_client, source, target,
                  dict(KEEP, field_to_copy=['title', 'characters']))

    assert copied.title == 'Theirs'
