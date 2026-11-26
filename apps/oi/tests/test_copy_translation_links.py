"""A character or a group goes to another language by its translation."""
import pytest

from apps.gcd.models import Issue, Series
from apps.gcd.models.character import (
    Character, CharacterNameDetail, CharacterRelation, CharacterRelationType,
    Group, GroupNameDetail, GroupRelation, GroupRelationType)
from apps.oi.models import StoryCharacterRevision, StoryRevision
from apps.stddata.models import Language

MODELS = {
    Character: (CharacterNameDetail, CharacterRelation, CharacterRelationType,
                'character'),
    Group: (GroupNameDetail, GroupRelation, GroupRelationType, 'group'),
}
TRANSLATION, OTHER = 1, 2


@pytest.fixture
def german():
    """Return the language of the translations."""
    return Language.objects.create(code='XZG', name='Test German')


@pytest.fixture
def reprint(any_adding_changeset, story_add_values, any_added_issue, german):
    """Return a revision of a sequence in a series in German."""
    series = Series.objects.get(id=any_added_issue.series_id)
    series.pk = None
    series.language = german
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


def new(model, name, language):
    """Return a new character or group with its official name."""
    item = model.objects.create(name=name, disambiguation='',
                                language=language, description='', notes='')
    names, _, _, field = MODELS[model]
    names.objects.create(name=name, is_official_name=True, **{field: item})
    return item


def relate(source, target, type_id):
    """Link two characters or two groups with a relation of a type."""
    _, links, kinds, field = MODELS[type(source)]
    kind = kinds.objects.get_or_create(
      id=type_id, defaults={'type': 'Test', 'reverse_type': 'Test'})[0]
    links.objects.create(relation_type=kind, **{'from_' + field: source,
                                                 'to_' + field: target})


@pytest.mark.django_db
@pytest.mark.parametrize('is_source', [True, False])
def test_other_relations_are_no_translations(
      is_source, any_adding_changeset, story_add_values, any_language,
      german, reprint):
    """Another relation with a German object leaves the translation."""
    found = {}
    for model in MODELS:
        found[model] = new(model, 'Spider', any_language)
        pairs = [(found[model], new(model, 'Spinne', german)),
                 (found[model], new(model, 'Other', german))]
        if not is_source:
            pairs = [(target, source) for source, target in pairs]
        relate(*pairs[0], TRANSLATION)
        relate(*pairs[1], OTHER)
    source = StoryRevision(changeset=any_adding_changeset, **story_add_values)
    source.save()
    appearance = StoryCharacterRevision.objects.create(
      changeset=any_adding_changeset, story_revision=source,
      character=found[Character].official_name())
    appearance.group_name.add(found[Group].official_name())

    copied = StoryCharacterRevision.copied_translation(appearance, reprint)

    assert copied is not None
    assert copied.character.name == 'Spinne'
    assert [name.name for name in copied.group_name.all()] == ['Spinne']
