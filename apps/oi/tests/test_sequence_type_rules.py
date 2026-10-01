"""Exhaustive type matrix using the catalog's complete StoryType fixture."""
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from django.core.exceptions import ValidationError

from apps.oi.sequence_validation import validate_sequence_type_fields

TYPES = yaml.safe_load((Path(__file__).parents[2] / 'gcd/fixtures/storytype.yaml').read_text())
TYPE_IDS = [entry['pk'] for entry in TYPES]
TYPE_NAMES = [entry['fields']['name'] for entry in TYPES]
NO_FEATURE = {8, 22, 24, 25}


def values(type_id, **changes):
    data = dict(type=SimpleNamespace(id=type_id), feature='', feature_name=[],
                feature_logo=[], genre='', story_arc=[])
    data.update(changes)
    return data


def assert_validity(data, allowed):
    if allowed:
        validate_sequence_type_fields(data)
    else:
        with pytest.raises(ValidationError):
            validate_sequence_type_fields(data)


@pytest.mark.parametrize('type_id', TYPE_IDS, ids=TYPE_NAMES)
def test_each_type_feature_genre_and_arc_rules(type_id):
    validate_sequence_type_fields(values(type_id))
    assert_validity(values(type_id, feature='Avengers'), type_id not in NO_FEATURE)
    assert_validity(values(type_id, genre='adventure'), type_id not in NO_FEATURE)
    assert_validity(values(type_id, story_arc=[object()]), type_id == 19)


@pytest.mark.parametrize('type_id', TYPE_IDS, ids=TYPE_NAMES)
@pytest.mark.parametrize('feature_type', [1, 2, 3, 4], ids=['regular', 'letters', 'ad', 'column'])
def test_each_type_linked_feature_categories(type_id, feature_type):
    name = SimpleNamespace(feature=SimpleNamespace(feature_type=SimpleNamespace(id=feature_type)))
    allowed = type_id not in NO_FEATURE
    if type_id == 12:
        allowed = feature_type == 2
    elif type_id == 29:
        allowed = feature_type == 4
    elif feature_type == 3:
        allowed = allowed and type_id in {2, 28}
    elif feature_type in {2, 4}:
        allowed = False
    assert_validity(values(type_id, feature_name=[name]), allowed)
    assert_validity(values(type_id, feature='legacy text', feature_name=[name]), False)


@pytest.mark.django_db
@pytest.mark.parametrize('feature_type', [1, 2, 3, 4])
def test_each_type_logo_categories(feature_type, any_language):
    from apps.gcd.models import Feature, FeatureNameDetail, FeatureLogo, FeatureType
    category, _ = FeatureType.objects.get_or_create(pk=feature_type, defaults={'name': 'test'})
    feature = Feature.objects.create(name='Feature', sort_name='Feature',
                                     language=any_language, feature_type=category)
    name = FeatureNameDetail.objects.create(feature=feature, name='Feature', sort_name='Feature')
    logo = FeatureLogo.objects.create(name='Logo')
    logo.feature_name.add(name)
    for type_id in TYPE_IDS:
        allowed = type_id not in NO_FEATURE | {6}
        if type_id == 12:
            allowed = feature_type == 2
        elif type_id == 29:
            allowed = feature_type == 4
        elif feature_type == 3:
            allowed = allowed and type_id in {2, 28}
        elif feature_type in {2, 4}:
            allowed = False
        assert_validity(values(type_id, feature_logo=[logo]), allowed)


@pytest.mark.parametrize('type_id', TYPE_IDS, ids=TYPE_NAMES)
def test_each_type_missing_page_count_rule(type_id):
    from apps.oi.sequence_validation import validate_sequence_page_count
    data = dict(type=SimpleNamespace(id=type_id), page_count=None, page_count_uncertain=False)
    if type_id == 11:
        validate_sequence_page_count(data)
    else:
        with pytest.raises(ValidationError):
            validate_sequence_page_count(data)
    data['page_count_uncertain'] = True
    validate_sequence_page_count(data)
    data.update(page_count=1, page_count_uncertain=False)
    validate_sequence_page_count(data)
