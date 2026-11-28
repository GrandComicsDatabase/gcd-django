"""
The page count of a story is followed by "page" or "pages" in the language
of the page, as its message file gives the singular and the plural.
"""
import re
from decimal import Decimal

import polib
import pytest
from django.template.loader import render_to_string
from django.utils import translation

from apps.gcd.models import Issue, Publisher, Series, Story, StoryType
from apps.stddata.models import Country, Language

TEMPLATES = ('gcd/bits/single_story_credits.html',
             'gcd/details/tw_single_story.html')


@pytest.fixture
def german(settings, tmp_path):
    """The German message file holds test translations of page and pages."""
    catalog = polib.POFile()
    catalog.metadata = {'Content-Type': 'text/plain; charset=UTF-8',
                        'Plural-Forms': 'nplurals=2; plural=(n != 1);'}
    catalog.append(polib.POEntry(msgid='page', msgid_plural='pages',
                                 msgstr_plural={0: 'Seite', 1: 'Seiten'}))
    folder = tmp_path / 'de' / 'LC_MESSAGES'
    folder.mkdir(parents=True)
    catalog.save_as_mofile(str(folder / 'django.mo'))
    settings.LOCALE_PATHS = [str(tmp_path)]


@pytest.fixture
def story(db):
    """A story with a script credit, in an issue of a test series."""
    country = Country.objects.get_or_create(
      id=942, defaults={'code': 'n8', 'name': 'Testland P'})[0]
    language = Language.objects.get_or_create(
      id=942, defaults={'code': 'n8', 'name': 'Testish P'})[0]
    series = Series.objects.create(
      name='Some Series', sort_name='Some Series', year_began=1990,
      country=country, language=language, is_comics_publication=True,
      publication_dates='1990',
      publisher=Publisher.objects.create(
        name='Test Publisher', country=country, year_began=1990))
    issue = Issue.objects.create(number='1', series=series, sort_code=1,
                                 publication_date='1990',
                                 key_date='1990-01-00')
    story_type = StoryType.objects.get_or_create(
      name='Some Type', defaults={'sort_code': 942})[0]
    return Story.objects.create(issue=issue, type=story_type,
                                sequence_number=1, title='Some Story',
                                script='Some Writer')


@pytest.mark.parametrize('template', TEMPLATES)
@pytest.mark.parametrize('lang, page_count, shown', [
  ('de', '1', '1 Seite'), ('de', '2', '2 Seiten'), ('de', '0.5', '0.5 Seite'),
  ('en', '1', '1 page'), ('en', '2', '2 pages'), ('en', '0.5', '0.5 page')])
def test_page_count_is_followed_by_its_word(german, story, template, lang,
                                            page_count, shown):
    """The word follows the count rounded up, as before, in each language."""
    story.page_count = Decimal(page_count)

    with translation.override(lang):
        html = render_to_string(template, {'story': story})

    assert re.search(r'(?<![\d.])%s(?!\w)' % re.escape(shown),
                     re.sub(r'\s+', ' ', html))
