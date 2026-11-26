"""The language box of the feature logo form and its Feature name list.

Feature name of "Adding Feature Logo" lists the feature names that hold
the typed text, in all languages. The language box above it narrows the
list to the names of the features of one language; left empty, the list
stays as it was.
"""
import json

import pytest
from django.urls import reverse

from apps.gcd.models import Feature, FeatureNameDetail, FeatureType
from apps.oi.forms.feature import FeatureLogoRevisionForm
from apps.stddata.models import Language

NAME = 'Test Feature'

pytestmark = pytest.mark.django_db


@pytest.fixture
def names(db):
    """Feature names of the same text: two English, two German, one Italian.

    Each belongs to a feature of its language.
    """
    languages = {code: Language.objects.get_or_create(
                   code=code, defaults={'name': name})[0]
                 for code, name in [('en', 'English'), ('de', 'German'),
                                    ('it', 'Italian'), ('fi', 'Finnish')]}
    feature_type, _ = FeatureType.objects.get_or_create(
      id=1, defaults={'name': 'feature'})
    found = []
    for number, code in enumerate(['en', 'de', 'en', 'de', 'it']):
        feature = Feature.objects.create(
          name=NAME, sort_name=NAME, genre='', notes='',
          disambiguation=str(number), language=languages[code],
          feature_type=feature_type)
        found.append(FeatureNameDetail.objects.create(
          feature=feature, name=NAME, sort_name=NAME, is_official_name=True))
    return found


def _list(client, forwarded):
    """Return the ids that Feature name lists for the text, in all pages."""
    found, page, more = [], 1, True
    while more:
        data = client.get(reverse('feature_name_autocomplete'),
                          {'q': NAME, 'page': page,
                           'forward': json.dumps(forwarded)}).json()
        found += [int(result['id']) for result in data['results']]
        more = data['pagination']['more']
        page += 1
    return found


def test_chosen_language_lists_only_its_names(client, any_indexer, names):
    """With German chosen, the names of the German features are listed."""
    client.force_login(any_indexer)
    german = [name.id for name in names
              if name.feature.language.code == 'de']

    assert sorted(_list(client, {'language': 'de'})) == german


def test_no_language_lists_all_languages(client, any_indexer, names):
    """With no language chosen, the names of all languages are listed."""
    client.force_login(any_indexer)

    assert sorted(_list(client, {'language': ''})) == \
        [name.id for name in names]


def test_language_box_offers_the_languages_of_features(names):
    """The box offers all languages first, then those that have features.

    It sits right above Feature name and is passed to its list; the image
    box stays below Feature name.
    """
    form = FeatureLogoRevisionForm()
    field = form.fields['feature_name_language']
    forwarded = [(item.src, item.dst)
                 for item in form.fields['feature_name'].widget.forward]
    order = list(form.fields)

    assert [(str(value), label) for value, label in field.choices] == [
      ('', 'All languages'), ('en', 'English'), ('de', 'German'),
      ('it', 'Italian')]
    assert not field.required
    assert order[2:5] == ['feature_name_language', 'feature_name',
                          'feature_logo_image']
    assert forwarded == [('feature_name_language', 'language')]
