"""makemessages keeps the messages that the site looks up at run time.

The pages translate these messages through a variable: the names of the
statistics with CountStats.name_for_count(), the credit labels with
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

# Languages with different plural rules: one form (ja), the singular
# also for 0 (fr), three forms (sr).
LANGUAGES = ['it', 'de', 'fr', 'es', 'sr', 'ja']

RUNTIME_MESSAGES = [
    # The labels of the credits template tags.
    'Script', 'Pencils', 'Inks', 'Colors', 'Letters', 'Characters',
    'Feature', 'Genre', 'Pages', 'Keywords', 'Synopsis', 'Title', 'Isbn',
    'Barcode',
    # The names of settings.LANGUAGES.
    'German', 'English', 'Dutch', 'Portuguese', 'Italian', 'Swedish',
]

# The names of the statistics, singular and plural, with their context.
STAT_CONTEXT = 'msgctxt "statistics"\n'
STAT_NAMES = [
    ('publisher', 'publishers'), ('brand', 'brands'),
    ('indicia publisher', 'indicia publishers'), ('series', 'series'),
    ('issue', 'issues'), ('variant issue', 'variant issues'),
    ('issue index', 'issue indexes'), ('cover', 'covers'),
    ('story', 'stories'), ('creator', 'creators'),
]

# Test texts for "issue" and "issues" by language, one for each plural
# form, and the text that the front page must show for each count.
PLURAL_CASES = {
    'it': (['numero', 'numeri'],
           {0: 'numeri', 1: 'numero', 2: 'numeri', 5: 'numeri'}),
    'de': (['Heft', 'Hefte'], {0: 'Hefte', 1: 'Heft', 2: 'Hefte'}),
    'fr': (['numéro', 'numéros'],
           {0: 'numéro', 1: 'numéro', 2: 'numéros'}),
    'es': (['número', 'números'],
           {0: 'números', 1: 'número', 2: 'números'}),
    'sr': (['sveska', 'sveske', 'svezaka'],
           {1: 'sveska', 2: 'sveske', 4: 'sveske', 5: 'svezaka',
            11: 'svezaka', 21: 'sveska', 22: 'sveske'}),
    'ja': (['号'], {0: '号', 1: '号', 2: '号'}),
}

# The editor credit has its own context: the front page uses "Editing"
# for the link to the editing of the database.
EDITOR_ENTRY = 'msgctxt "credit"\nmsgid "Editing"\nmsgstr ""'


@pytest.fixture(scope='module')
def catalogs(tmp_path_factory):
    """The message files that makemessages makes from the Python code.

    makemessages runs in a folder of links to the code, so it writes the
    files there and leaves the locale folder of the site alone. Returns
    the text of each file by language.
    """
    work = tmp_path_factory.mktemp('makemessages')
    (work / 'apps').symlink_to(ROOT / 'apps', target_is_directory=True)
    (work / 'settings.py').symlink_to(ROOT / 'settings.py')
    cwd = os.getcwd()
    os.chdir(work)
    try:
        with override_settings(LOCALE_PATHS=[str(work / 'locale')]):
            call_command('makemessages', locale=LANGUAGES,
                         extensions=['py'], symlinks=True, verbosity=0)
    finally:
        os.chdir(cwd)
    return {language: (work / 'locale' / language / 'LC_MESSAGES' /
                       'django.po').read_text(encoding='utf-8')
            for language in LANGUAGES}


def compile_catalog(language, text, settings, folder):
    """Compile TEXT as the message file of LANGUAGE in FOLDER."""
    messages = folder / language / 'LC_MESSAGES'
    messages.mkdir(parents=True)
    (messages / 'django.po').write_text(text, encoding='utf-8')
    subprocess.run(['msgfmt', '-o', str(messages / 'django.mo'),
                    str(messages / 'django.po')],
                   check=True, capture_output=True)
    settings.LOCALE_PATHS = [str(folder)]


def fill_plural(text, singular, forms):
    """TEXT with the statistics entry of SINGULAR filled with FORMS.

    The entry gets one msgstr for each plural form that the header of
    TEXT names (makemessages writes two in a new file, whatever the
    language); the last of FORMS fills the forms beyond them. TEXT
    without that entry comes back as it is.
    """
    head = '%smsgid "%s"\nmsgid_plural ' % (STAT_CONTEXT, singular)
    start = text.find(head)
    if start < 0:
        return text
    end = text.find('\n\n', start)
    end = len(text) if end < 0 else end
    lines = text[start:end].split('\n')
    nplurals = int(re.search(r'nplurals=(\d+)', text).group(1))
    lines[3:] = ['msgstr[%d] "%s"' % (n, forms[min(n, len(forms) - 1)])
                 for n in range(nplurals)]
    return text[:start] + '\n'.join(lines) + text[end:]


def test_makemessages_finds_the_runtime_messages(catalogs):
    """Each message that the site looks up at run time has an entry."""
    catalog = catalogs['it']
    found = set(re.findall(r'^msgid "(.*)"$', catalog, re.MULTILINE))

    assert [msgid for msgid in RUNTIME_MESSAGES if msgid not in found] == []
    assert [singular for singular, plural in STAT_NAMES
            if '%smsgid "%s"\nmsgid_plural "%s"\n'
            % (STAT_CONTEXT, singular, plural) not in catalog] == []
    assert EDITOR_ENTRY in catalog


@pytest.mark.django_db
def test_front_page_statistics_in_english_by_count(client, settings):
    """In English a statistic of 1 has the singular, others the plural."""
    settings.USE_TEMPLATESADMIN = False
    CountStats.objects.create(name='covers', count=1)
    CountStats.objects.create(name='issues', count=2)

    response = client.get('/')

    assert response.status_code == 200
    assert '1 cover<br>' in response.content.decode()
    assert '2 issues<br>' in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize('language', LANGUAGES)
def test_front_page_statistics_by_count(catalogs, client, settings,
                                        tmp_path, language):
    """The front page shows the form of its entry that the count needs."""
    forms, expected = PLURAL_CASES[language]
    settings.USE_TEMPLATESADMIN = False
    compile_catalog(language,
                    fill_plural(catalogs[language], 'issue', forms),
                    settings, tmp_path)
    stat = CountStats.objects.create(name='issues', count=0)

    shown = {}
    for count in expected:
        stat.count = count
        stat.save()
        page = client.get('/?lang=%s' % language).content.decode()
        shown[count] = re.search(r'^\s*%d ([^<\n]*)<br>$' % count, page,
                                 re.MULTILINE).group(1)

    assert shown == expected


@pytest.mark.django_db
def test_statistics_name_apart_from_a_plain_entry(catalogs, client,
                                                  settings, tmp_path):
    """A plain entry of the same word keeps its own text.

    The story type "cover" is such an entry once the code marks it.
    Without the context the two entries are one, and msgfmt refuses the
    file or one of the two texts is lost.
    """
    settings.USE_TEMPLATESADMIN = False
    text = fill_plural(catalogs['it'], 'cover', ['copertina', 'copertine'])
    plain = '\nmsgid "cover"\nmsgstr ""\n'
    if plain in text:
        text = text.replace(plain, plain[:-3] + '"Copertina (tipo)"\n')
    else:
        text += '\nmsgid "cover"\nmsgstr "Copertina (tipo)"\n'
    compile_catalog('it', text, settings, tmp_path)
    CountStats.objects.create(name='covers', count=2)

    page = client.get('/?lang=it').content.decode()
    with translation.override('it'):
        story_type = translation.gettext('cover')

    assert '2 copertine<br>' in page
    assert story_type == 'Copertina (tipo)'


def test_editor_credit_label_from_the_credit_context(catalogs, settings,
                                                     tmp_path):
    """The editor credit shows the entry of the credit context."""
    compile_catalog(
        'it',
        catalogs['it'].replace(EDITOR_ENTRY, EDITOR_ENTRY[:-2] + '"Cura"') +
        '\nmsgid "Editing"\nmsgstr "Inserisci / modifica"\n',
        settings, tmp_path)
    story = SimpleNamespace(editing='Some Editor',
                            credits=SimpleNamespace(all=list))

    with translation.override('it'):
        label = show_credit(story, 'editing', tailwind=True)

    assert label == ('<span class="field-name-label">Cura:</span>'
                     'Some Editor')
