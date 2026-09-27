import pytest

from apps.gcd.models import (
    Creator, CreatorNameDetail, Feature, FeatureNameDetail, FeatureType,
    FeatureRelation, FeatureRelationType, CreditType, CREDIT_TYPES)
from apps.stddata.models import Language, Script


pytestmark = pytest.mark.django_db


def make_feature(name, language):
    feature_type, _ = FeatureType.objects.get_or_create(
        pk=1, defaults={'name': 'Feature'})
    feature = Feature.objects.create(
        name=name, sort_name=name, language=language,
        feature_type=feature_type)
    return FeatureNameDetail.objects.create(
        feature=feature, name=name, is_official_name=True)


@pytest.mark.parametrize('other_language', [False, True])
@pytest.mark.parametrize('text, candidate', [
    ('man', 'manage'), ('Batman', 'Batman & Robin')])
def test_partial_feature_is_preserved(
        any_added_story_rev, other_language, text, candidate):
    story = any_added_story_rev
    language = story.issue.series.language
    if other_language:
        language = Language.objects.exclude(pk=language.pk).exclude(
            code__in=['zxx', 'und']).first()
    make_feature(candidate, language)
    story.feature = text

    story.migrate_feature()

    story.refresh_from_db()
    assert story.feature == text
    assert not story.feature_name.exists()


@pytest.mark.parametrize('matches', [1, 2])
@pytest.mark.parametrize('text, candidate', [
    ('man', 'manage'), ('Batman', 'Batman & Robin')])
def test_only_unique_full_feature_name_migrates(
        any_added_story_rev, matches, text, candidate):
    story = any_added_story_rev
    language = story.issue.series.language
    make_feature(candidate, language)
    exact = [make_feature(text, language) for _ in range(matches)]
    story.feature = text + '; unknown'

    story.migrate_feature()
    story.migrate_feature()

    story.refresh_from_db()
    assert story.feature == ('unknown' if matches == 1 else text + '; unknown')
    assert list(story.feature_name.all()) == (exact if matches == 1 else [])


@pytest.mark.parametrize('source_name', ['man', 'manage'])
def test_translation_requires_full_source_name(any_added_story_rev, source_name):
    story = any_added_story_rev
    language = story.issue.series.language
    other_language = Language.objects.exclude(pk=language.pk).exclude(
        code__in=['zxx', 'und']).first()
    source = make_feature(source_name, other_language)
    target = make_feature('Translated feature', language)
    relation_type, _ = FeatureRelationType.objects.get_or_create(
        pk=1, defaults={'name': 'translation'})
    FeatureRelation.objects.create(
        from_feature=source.feature, to_feature=target.feature,
        relation_type=relation_type)
    story.feature = 'man'

    story.migrate_feature()

    story.refresh_from_db()
    assert story.feature == ('' if source_name == 'man' else 'man')
    assert list(story.feature_name.all()) == (
        [target] if source_name == 'man' else [])


def make_creator(name):
    creator = Creator.objects.create(gcd_official_name=name)
    script, _ = Script.objects.get_or_create(
        code='Latn', defaults={'number': 215, 'name': 'Latin'})
    return CreatorNameDetail.objects.create(
        creator=creator, name=name, is_official_name=True,
        in_script=script)


@pytest.mark.parametrize('level', ['story', 'issue'])
@pytest.mark.parametrize('suffix', ['', ' (credited)', '(credited)', ' ?'])
def test_creator_name_is_not_truncated(
        any_added_story_rev, any_added_issue_rev, level, suffix):
    story = any_added_story_rev
    revision = story if level == 'story' else any_added_issue_rev
    field = 'script' if level == 'story' else 'editing'
    CreditType.objects.get_or_create(
        pk=CREDIT_TYPES[field], defaults={'name': field, 'sort_code': 1})
    relation = ('story_credit_revisions' if level == 'story'
                else 'issue_credit_revisions')
    expected = make_creator('Alan')
    make_creator('Ala')
    make_creator('Alan Moore')
    setattr(revision, field, ' ; Alan' + suffix + '; ; unknown; ')

    revision.migrate_credits()
    revision.migrate_credits()

    revision.refresh_from_db()
    assert getattr(revision, field) == 'unknown'
    credits = getattr(revision, relation).all()
    assert credits.count() == 1
    assert credits.get().creator == expected
    assert credits.get().is_credited == ('credited' in suffix)
    assert credits.get().uncertain == ('?' in suffix)


@pytest.mark.parametrize('matches', [0, 2])
@pytest.mark.parametrize('text', ['Alan', 'Alan (credited)?'])
def test_partial_or_ambiguous_creator_is_preserved(
        any_added_story_rev, matches, text):
    story = any_added_story_rev
    make_creator('Alan Moore')
    for _ in range(matches):
        make_creator('Alan')
    story.script = text

    story.migrate_credits()

    story.refresh_from_db()
    assert story.script == text
    assert not story.story_credit_revisions.exists()
