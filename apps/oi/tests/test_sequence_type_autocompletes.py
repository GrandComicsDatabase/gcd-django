import pytest

from apps.gcd.models import (
    Feature, FeatureLogo, FeatureNameDetail, FeatureType, StoryArc)
from apps.gcd.models.story import NO_FEATURE_TYPES, STORY_TYPES
from apps.select.views import (
    FeatureLogoAutocomplete, FeatureNameAutocomplete, StoryArcAutocomplete)

COMIC_STORY = STORY_TYPES['comic story']
IN_HOUSE_COLUMN = STORY_TYPES['in-house column']
STORY_FEATURE_TYPE = 1
IN_HOUSE_FEATURE_TYPE = 4


def _offered(view_class, sequence_type=None):
    """ What the autocomplete offers for a sequence of the given type. """
    view = view_class()
    view.forwarded = {'type': str(sequence_type)} if sequence_type else {}
    view.q = ''
    return list(view.get_queryset())


def _feature_with_logo(name, feature_type_id, language):
    feature_type, _ = FeatureType.objects.get_or_create(
      id=feature_type_id, defaults={'name': name})
    feature = Feature.objects.create(
      name=name, sort_name=name, genre='', language=language,
      feature_type=feature_type, notes='')
    feature_name = FeatureNameDetail.objects.create(
      feature=feature, name=name, sort_name=name, is_official_name=True)
    logo = FeatureLogo.objects.create(name=name, sort_name=name, notes='')
    logo.feature.add(feature)
    logo.feature_name.add(feature_name)
    return feature_name, logo


@pytest.mark.django_db
@pytest.mark.parametrize('sequence_type', NO_FEATURE_TYPES)
def test_no_feature_is_offered_for_a_type_without_features(any_language,
                                                           sequence_type):
    feature_name, logo = _feature_with_logo('Story Feature',
                                            STORY_FEATURE_TYPE, any_language)

    assert _offered(FeatureNameAutocomplete, COMIC_STORY) == [feature_name]
    assert _offered(FeatureLogoAutocomplete, COMIC_STORY) == [logo]
    assert _offered(FeatureNameAutocomplete, sequence_type) == []
    assert _offered(FeatureLogoAutocomplete, sequence_type) == []


@pytest.mark.django_db
def test_in_house_logos_are_offered_only_for_in_house_columns(any_language):
    _, story_logo = _feature_with_logo('Story Feature', STORY_FEATURE_TYPE,
                                       any_language)
    _, in_house_logo = _feature_with_logo('Column', IN_HOUSE_FEATURE_TYPE,
                                          any_language)

    assert _offered(FeatureLogoAutocomplete, IN_HOUSE_COLUMN) == [
      in_house_logo]
    assert _offered(FeatureLogoAutocomplete, COMIC_STORY) == [story_logo]


@pytest.mark.django_db
def test_story_arcs_are_offered_only_for_comic_stories(any_language):
    story_arc = StoryArc.objects.create(
      name='An Arc', sort_name='An Arc', language=any_language,
      description='', notes='')

    assert _offered(StoryArcAutocomplete, COMIC_STORY) == [story_arc]
    assert _offered(StoryArcAutocomplete, STORY_TYPES['ad']) == []
    # The form of the relations between story arcs forwards no type.
    assert _offered(StoryArcAutocomplete) == [story_arc]
