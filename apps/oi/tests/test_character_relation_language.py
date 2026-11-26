"""The language box of the character relation form and its Character B list.

Character B of "Adding Relation with Character" lists the characters whose
name holds the typed text, in all languages. The language box above it
narrows the list to one language; left empty, the list stays as it was.
"""
import json

import pytest
from django.urls import reverse

from apps.gcd.models import Character
from apps.oi.forms.character import CharacterRelationRevisionForm
from apps.stddata.models import Language

NAME = 'Test Hero'
PAGE = 10  # results on each page of the picker

pytestmark = pytest.mark.django_db


@pytest.fixture
def heroes(db):
    """Characters of the same name in three languages; the Italian is last.

    The English and German ones come first in the list, so the Italian one
    is not on the first page.
    """
    languages = {code: Language.objects.get_or_create(
                   code=code, defaults={'name': name})[0]
                 for code, name in [('en', 'English'), ('de', 'German'),
                                    ('it', 'Italian'), ('fi', 'Finnish')]}
    found = []
    for year in range(1950, 1950 + PAGE + 1):
        code = 'en' if year % 2 else 'de'
        found.append(Character.objects.create(
          name=NAME, sort_name=NAME, disambiguation='', description='',
          notes='', year_first_published=year, language=languages[code]))
    found.append(Character.objects.create(
      name=NAME, sort_name=NAME, disambiguation='', description='',
      notes='', year_first_published=2000, language=languages['it']))
    return found


def _list(client, forwarded, page=1):
    """Return the ids on a page of Character B, and if more pages follow."""
    answer = client.get(reverse('character_autocomplete'),
                        {'q': NAME, 'page': page,
                         'forward': json.dumps(forwarded)})
    data = answer.json()
    return ([int(result['id']) for result in data['results']],
            data['pagination']['more'])


def test_chosen_language_lists_only_its_characters(client, any_indexer,
                                                   heroes):
    """With Italian chosen, Character B lists only the Italian character."""
    client.force_login(any_indexer)
    italian = heroes[-1]

    ids, more = _list(client, {'language': 'it'})

    assert ids == [italian.id]
    assert not more


def test_chosen_language_with_the_relation_filter(client, any_indexer,
                                                  heroes):
    """The choice narrows the list that the relation type already narrows.

    For "republished as" from an English character, the list holds the
    other languages; with German chosen it holds the German ones only.
    """
    client.force_login(any_indexer)
    german = [hero.id for hero in heroes if hero.language.code == 'de']

    ids, more = _list(client, {'language_code': 'en', 'relation_type': '1',
                               'language': 'de'})

    assert ids == german
    assert not more


def test_no_language_lists_all_languages_page_by_page(client, any_indexer,
                                                      heroes):
    """With no language chosen, all languages are listed, as before.

    The Italian character is past the first page; scrolling the list loads
    the next page, which holds it.
    """
    client.force_login(any_indexer)

    first, more = _list(client, {'language': ''})
    second, more_after = _list(client, {'language': ''}, page=2)

    assert first == [hero.id for hero in heroes[:PAGE]]
    assert more
    assert second == [hero.id for hero in heroes[PAGE:]]
    assert not more_after


def test_language_box_offers_the_languages_of_characters(heroes):
    """The box offers all languages first, then those that have characters.

    It sits above Character B and is passed to its list.
    """
    form = CharacterRelationRevisionForm()
    field = form.fields['to_character_language']
    forwarded = [(item.src, item.dst)
                 for item in form.fields['to_character'].widget.forward
                 if not isinstance(item, str)]

    assert [(str(value), label) for value, label in field.choices] == [
      ('', 'All languages'), ('en', 'English'), ('de', 'German'),
      ('it', 'Italian')]
    assert not field.required
    assert list(form.fields).index('to_character_language') == \
        list(form.fields).index('to_character') - 1
    assert forwarded == [('to_character_language', 'language')]
