"""makemessages keeps the messages that the site looks up at run time.

The pages translate these messages through a variable: the names of the
statistics with {% trans stat.name %}, the credit labels with
_(field.title()), and Rosetta the names of settings.LANGUAGES.
makemessages reads only literal texts, so a message that the code does
not mark goes obsolete ("#~") in every message file at its next run.
"""
import os
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.utils import translation

from apps.gcd.templatetags.credits import show_credit
from apps.stats.models import CountStats

ROOT = Path(__file__).resolve().parents[3]

RUNTIME_MESSAGES = [
    # The values of CountStats.name.
    'publishers', 'brands', 'indicia publishers', 'series', 'issues',
    'variant issues', 'issue indexes', 'covers', 'stories', 'creators',
    # The labels of the credits template tags.
    'Script', 'Pencils', 'Inks', 'Colors', 'Letters', 'Characters',
    'Feature', 'Genre', 'Pages', 'Keywords', 'Synopsis', 'Title', 'Isbn',
    'Barcode',
    # The names of settings.LANGUAGES.
    'German', 'English', 'Dutch', 'Portuguese', 'Italian', 'Swedish',
]

# The editor credit has its own context: the front page uses "Editing"
# for the link to the editing of the database.
EDITOR_ENTRY = 'msgctxt "credit"\nmsgid "Editing"\nmsgstr ""'


@pytest.fixture(scope='module')
def catalog(tmp_path_factory):
    """The Italian message file that makemessages makes from the Python code.

    makemessages runs in a folder of links to the code, so it writes the
    file there and leaves the locale folder of the site alone.
    """
    work = tmp_path_factory.mktemp('makemessages')
    (work / 'apps').symlink_to(ROOT / 'apps', target_is_directory=True)
    (work / 'settings.py').symlink_to(ROOT / 'settings.py')
    cwd = os.getcwd()
    os.chdir(work)
    try:
        with override_settings(LOCALE_PATHS=[str(work / 'locale')]):
            call_command('makemessages', locale=['it'], extensions=['py'],
                         symlinks=True, verbosity=0)
    finally:
        os.chdir(cwd)
    return (work / 'locale' / 'it' / 'LC_MESSAGES' /
            'django.po').read_text(encoding='utf-8')


def compile_catalog(text, settings, folder):
    """Compile TEXT as the Italian message file of the site, in FOLDER."""
    messages = folder / 'it' / 'LC_MESSAGES'
    messages.mkdir(parents=True)
    (messages / 'django.po').write_text(text, encoding='utf-8')
    subprocess.run(['msgfmt', '-o', str(messages / 'django.mo'),
                    str(messages / 'django.po')],
                   check=True, capture_output=True)
    settings.LOCALE_PATHS = [str(folder)]


def test_makemessages_finds_the_runtime_messages(catalog):
    """Each message that the site looks up at run time has an entry."""
    found = set(re.findall(r'^msgid "(.*)"$', catalog, re.MULTILINE))

    assert [msgid for msgid in RUNTIME_MESSAGES if msgid not in found] == []
    assert EDITOR_ENTRY in catalog


@pytest.mark.django_db
def test_front_page_statistics_from_the_message_file(catalog, client,
                                                     settings, tmp_path):
    """The front page shows a statistic with the text of its entry."""
    settings.USE_TEMPLATESADMIN = False
    CountStats.objects.create(name='covers', count=2)
    compile_catalog(
        catalog.replace('msgid "covers"\nmsgstr ""',
                        'msgid "covers"\nmsgstr "copertine"'),
        settings, tmp_path)

    response = client.get('/?lang=it')

    assert response.status_code == 200
    assert '2 copertine' in response.content.decode()


def test_editor_credit_label_from_the_credit_context(catalog, settings,
                                                     tmp_path):
    """The editor credit shows the entry of the credit context."""
    compile_catalog(
        catalog.replace(EDITOR_ENTRY, EDITOR_ENTRY[:-2] + '"Cura"') +
        '\nmsgid "Editing"\nmsgstr "Inserisci / modifica"\n',
        settings, tmp_path)
    story = SimpleNamespace(editing='Some Editor',
                            credits=SimpleNamespace(all=list))

    with translation.override('it'):
        label = show_credit(story, 'editing', tailwind=True)

    assert label == ('<span class="field-name-label">Cura:</span>'
                     'Some Editor')
