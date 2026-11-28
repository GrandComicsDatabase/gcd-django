import pytest

from apps.gcd.models import (
    Feature, FeatureNameDetail, FeatureRelation, FeatureRelationType,
    FeatureType)
from apps.stddata.models import Language

pytestmark = pytest.mark.django_db


def _feature(name, language, disambiguation=''):
    """ A feature of the story type with its official name. """
    feature_type, _ = FeatureType.objects.get_or_create(
      id=1, defaults={'name': 'story'})
    feature = Feature.objects.create(
      name=name, sort_name=name, genre='', language=language,
      feature_type=feature_type, disambiguation=disambiguation, notes='')
    return FeatureNameDetail.objects.create(
      feature=feature, name=name, sort_name=name, is_official_name=True)


def _other_language():
    """ A language that is not the one of the test series. """
    return Language.objects.get_or_create(
      code='XZY', defaults={'name': 'Other Test Language'})[0]


def _translate(source, target):
    """ Record target as the translation of source. """
    relation_type, _ = FeatureRelationType.objects.get_or_create(
      id=1, defaults={'name': 'translation',
                      'description': 'translated as',
                      'reverse_description': 'translated from'})
    FeatureRelation.objects.create(
      from_feature=source.feature, to_feature=target.feature,
      relation_type=relation_type)


def _migrate(story, text):
    """ Press Migrate on the sequence with this text feature. """
    story.feature = text
    story.save()
    story.migrate_feature()
    story.refresh_from_db()
    return list(story.feature_name.all())


@pytest.mark.parametrize('text, name', [
  ('Amor', 'Prins Namor'),
  ('DC Comics', 'Backstage at DC Comics'),
  ('Arrow', 'The Arrow'),
  ('Yikes', 'Yikes!')])
def test_name_that_only_contains_the_text_is_not_linked(
        any_added_story_rev, text, name):
    """ The only name containing the text is not linked for that. """
    story = any_added_story_rev
    _feature(name, story.issue.series.language)

    assert _migrate(story, text) == []
    assert story.feature == text


def test_whole_name_is_linked_and_the_rest_stays(any_added_story_rev):
    """ Of two parts only the whole name is linked, the other stays. """
    story = any_added_story_rev
    namor = _feature('Prins Namor', story.issue.series.language)

    assert _migrate(story, 'Prins Namor; Amor') == [namor]
    assert story.feature == 'Amor'


def test_two_features_with_the_whole_name_are_not_linked(
        any_added_story_rev):
    """ A whole name shared by two features links neither. """
    story = any_added_story_rev
    language = story.issue.series.language
    _feature('Captain Marvel', language, 'Fawcett')
    _feature('Captain Marvel', language, 'Marvel')

    assert _migrate(story, 'Captain Marvel') == []
    assert story.feature == 'Captain Marvel'


def test_translation_is_not_found_by_part_of_a_name(any_added_story_rev):
    """ A name of another language that only contains the text is not
    used to link its translation. """
    story = any_added_story_rev
    _translate(_feature('Prins Namor', _other_language()),
               _feature('Sub-Mariner', story.issue.series.language))

    assert _migrate(story, 'Amor') == []
    assert story.feature == 'Amor'


def test_translation_is_found_among_longer_names(any_added_story_rev):
    """ The whole name of another language links its translation, also
    when longer names there contain the text. """
    story = any_added_story_rev
    other = _other_language()
    legion = _feature('Legion der Super-Helden', story.issue.series.language)
    _translate(_feature('Legion of Super-Heroes', other), legion)
    _feature('Tales of the Legion of Super-Heroes', other)

    assert _migrate(story, 'Legion of Super-Heroes') == [legion]
    assert story.feature == ''


def test_disambiguation_is_found_through_a_translation(any_added_story_rev):
    """ 'Name [disambiguation]' of another language links its
    translation. """
    story = any_added_story_rev
    spider = _feature('Spider-Man', story.issue.series.language)
    _translate(_feature('Spindeln', _other_language(), 'Spider-Man'), spider)

    assert _migrate(story, 'Spindeln [Spider-Man]') == [spider]
    assert story.feature == ''


def test_disambiguation_picks_the_whole_name(any_added_story_rev):
    """ 'Name [disambiguation]' links the whole Name with that
    disambiguation, not a longer name with it. """
    story = any_added_story_rev
    language = story.issue.series.language
    fawcett = _feature('Captain Marvel', language, 'Fawcett')
    _feature('Captain Marvel', language, 'Marvel')
    _feature('Captain Marvel Jr.', language, 'Fawcett')

    assert _migrate(story, 'Captain Marvel [Fawcett]') == [fawcett]
    assert story.feature == ''


def test_disambiguation_must_begin_with_the_bracket(any_added_story_rev):
    """ 'Name [x]' links Name only with a disambiguation beginning with
    x, also when the name itself has brackets. """
    story = any_added_story_rev
    _feature('[Pin-Up]', story.issue.series.language, 'DC')

    assert _migrate(story, '[Pin-Up] [Marvel]') == []
    assert story.feature == '[Pin-Up] [Marvel]'


def test_text_after_the_bracket_is_not_ignored(any_added_story_rev):
    """ A bracket followed by more text is not read as a disambiguation,
    so the rest of the text is not lost. """
    story = any_added_story_rev
    language = story.issue.series.language
    _feature('Captain Marvel', language, 'Fawcett')
    _feature('Captain Marvel', language, 'Marvel')
    text = 'Captain Marvel [Fawcett] and Mary Marvel'

    assert _migrate(story, text) == []
    assert story.feature == text


def test_bracket_that_names_a_disambiguation_is_not_dropped(
        any_added_story_rev):
    """ The second try without the bracket is not made when the text
    with the bracket matched a name. """
    story = any_added_story_rev
    language = story.issue.series.language
    _feature('Toto II', language, 'Soldino')
    _feature('Toto', language, 'Rob-Vel')

    assert _migrate(story, 'Toto [Soldino]') == []
    assert story.feature == 'Toto [Soldino]'


def test_bracket_that_matches_nothing_is_dropped(any_added_story_rev):
    """ A bracketed note at the end that matches no name is dropped for
    a second try. """
    story = any_added_story_rev
    mickey = _feature('Mikke Mus', story.issue.series.language, 'Disney')

    assert _migrate(story, 'Mikke Mus [serieheftet]') == [mickey]
    assert story.feature == ''


def test_bracket_in_the_middle_is_not_dropped(any_added_story_rev):
    """ The second try drops only bracketed notes at the end, never the
    text after them. """
    story = any_added_story_rev
    _feature('Looney Tunes', story.issue.series.language)
    text = 'Looney Tunes [and] Merrie Melodies Comics'

    assert _migrate(story, text) == []
    assert story.feature == text


def test_second_try_stays_in_the_series_language(any_added_story_rev):
    """ The second try does not link through a translation the name that
    the bracket ruled out in the other language. """
    story = any_added_story_rev
    other = _other_language()
    _feature('Toto II', other, 'Soldino')
    _translate(_feature('Toto', other, 'Rob-Vel'),
               _feature('Pierino', story.issue.series.language, 'Rob-Vel'))

    assert _migrate(story, 'Toto [Soldino]') == []
    assert story.feature == 'Toto [Soldino]'
