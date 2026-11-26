"""The language box of the feature relation form and its To feature list.

To feature of "Adding Relation with Feature" lists the features whose
name holds the typed text, in all languages. The language box above it
narrows the list to one language; left empty, the list stays as it was.
"""
import json

import pytest
from django.urls import reverse

from apps.gcd.models import Feature, FeatureType
from apps.oi.forms.feature import FeatureRelationRevisionForm
from apps.stddata.models import Language

NAME = 'Test Feature'

pytestmark = pytest.mark.django_db


@pytest.fixture
def features(db):
    """Features of the same name: two English, two German, one Italian."""
    languages = {code: Language.objects.get_or_create(
                   code=code, defaults={'name': name})[0]
                 for code, name in [('en', 'English'), ('de', 'German'),
                                    ('it', 'Italian'), ('fi', 'Finnish')]}
    feature_type, _ = FeatureType.objects.get_or_create(
      id=1, defaults={'name': 'feature'})
    return [Feature.objects.create(
              name=NAME, sort_name=NAME, genre='', notes='',
              disambiguation=str(number), language=languages[code],
              feature_type=feature_type)
            for number, code in enumerate(['en', 'de', 'en', 'de', 'it'])]


def _list(client, forwarded):
    """Return the ids that To feature lists for the name, in all pages."""
    found, page, more = [], 1, True
    while more:
        data = client.get(reverse('feature_autocomplete'),
                          {'q': NAME, 'page': page,
                           'forward': json.dumps(forwarded)}).json()
        found += [int(result['id']) for result in data['results']]
        more = data['pagination']['more']
        page += 1
    return found


def test_chosen_language_lists_only_its_features(client, any_indexer,
                                                 features):
    """With German chosen, To feature lists only the German features."""
    client.force_login(any_indexer)
    german = [feature.id for feature in features
              if feature.language.code == 'de']

    assert sorted(_list(client, {'language': 'de'})) == german


def test_no_language_lists_all_languages(client, any_indexer, features):
    """With no language chosen, the features of all languages are listed."""
    client.force_login(any_indexer)

    assert sorted(_list(client, {'language': ''})) == \
        [feature.id for feature in features]


def test_language_box_offers_the_languages_of_features(features):
    """The box offers all languages first, then those that have features.

    It sits above To feature and is passed to its list.
    """
    form = FeatureRelationRevisionForm()
    field = form.fields['to_feature_language']
    forwarded = [(item.src, item.dst)
                 for item in form.fields['to_feature'].widget.forward]

    assert [(str(value), label) for value, label in field.choices] == [
      ('', 'All languages'), ('en', 'English'), ('de', 'German'),
      ('it', 'Italian')]
    assert not field.required
    assert list(form.fields).index('to_feature_language') == \
        list(form.fields).index('to_feature') - 1
    assert forwarded == [('to_feature_language', 'language')]
