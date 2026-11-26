"""
The pages show the names of the sequence types and of the character roles
in the language of the page when a message file translates them; the text
built for search, export and the API keeps the names of the database.
"""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import polib
import pytest
import yaml
from django.core.management import call_command
from django.urls import reverse
from django.utils import translation

from apps.gcd.models import Story
from apps.gcd.models.story import DEPRECATED_TYPES, character_notes

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures'
# Test translations of the seeded sequence type and character role.
ITALIAN = {'cartoon': 'vignetta', 'featured': 'protagonista'}


def _fixture_names(file_name):
    """The names of a fixture of a type table, by primary key."""
    with open(FIXTURES / file_name, encoding='utf-8') as fixture:
        if file_name.endswith('.yaml'):
            rows = yaml.safe_load(fixture)
        else:
            rows = json.load(fixture)
    return {row['pk']: row['fields']['name'] for row in rows}


def test_each_type_and_role_has_a_msgid():
    """
    Every sequence type in use and every character role of the fixtures is
    listed for makemessages, once.
    """
    vocabulary = importlib.import_module('apps.gcd.models.vocabulary')
    types = [name for pk, name in _fixture_names('storytype.yaml').items()
             if pk not in DEPRECATED_TYPES]
    roles = list(_fixture_names('characterrole.json').values())

    assert sorted(vocabulary.STORY_TYPE_NAMES) == sorted(types)
    assert sorted(vocabulary.CHARACTER_ROLE_NAMES) == sorted(roles)


@pytest.fixture
def italian(settings, tmp_path):
    """
    The Italian message file holds the test translations; a page asked with
    ?lang=it uses it.
    """
    catalog = polib.POFile()
    catalog.metadata = {'Content-Type': 'text/plain; charset=UTF-8'}
    for msgid, msgstr in ITALIAN.items():
        catalog.append(polib.POEntry(msgid=msgid, msgstr=msgstr))
    folder = tmp_path / 'it' / 'LC_MESSAGES'
    folder.mkdir(parents=True)
    catalog.save_as_mofile(str(folder / 'django.mo'))
    settings.LOCALE_PATHS = [str(tmp_path)]


@pytest.fixture
def story(db):
    """The seeded cartoon sequence, with a featured character."""
    call_command('seed_development_data')
    return Story.objects.get(type__name='cartoon')


def _page(client, url, lang):
    """The page in the language, as text."""
    response = client.get(url, {'lang': lang})
    assert response.status_code == 200
    return response.content.decode()


def test_issue_page_shows_the_type_and_the_role_translated(client, italian,
                                                           story):
    """The heading of the sequence and its list of characters."""
    page = _page(client, story.issue.get_absolute_url(), 'it')

    assert 'vignetta / ' in page
    assert ' (protagonista)' in page
    assert 'cartoon' not in page
    assert 'featured' not in page


def test_issue_page_in_english_keeps_the_names(client, italian, story):
    """English has no message file: the names of the database show."""
    page = _page(client, story.issue.get_absolute_url(), 'en')

    assert 'cartoon / ' in page
    assert ' (featured)' in page


def test_sequence_list_shows_the_type_translated(client, italian, story):
    """The list of the sequences of a character, as other lists."""
    character = story.appearing_characters.get().character.character
    url = reverse('character_sequences',
                  kwargs={'character_id': character.id})

    assert 'vignetta /' in _page(client, url, 'it')
    assert 'cartoon /' in _page(client, url, 'en')


def test_role_in_the_text_keeps_the_name(italian):
    """The text form feeds the search index, the export and the API."""
    character = SimpleNamespace(is_flashback=False, is_death=False,
                                is_origin=False, role='featured', notes='')
    with translation.override('it'):
        assert character_notes(character, html=True) == ' (protagonista)'
        assert character_notes(character) == ' (featured)'
