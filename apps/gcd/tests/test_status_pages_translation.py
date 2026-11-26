"""
The pages of the data download, the international statistics, the daily
changes, the covers to replace, the weekly on-sale list of My Comics, the
projects, the donations, the privacy policy and the site-down notice show
their texts in the language of the page when the message file translates
them, and their counts take the plural forms of the language.
"""
import html
import importlib
import re
from datetime import date, timedelta
from types import SimpleNamespace

import polib
import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.contenttypes.models import ContentType
from django.template.loader import render_to_string
from django.test import override_settings
from django.urls import clear_url_caches, reverse
from django.utils import translation
from django.utils.translation import trans_real

from apps.gcd.models import (
    Brand, BrandGroup, Cover, Creator, Image, ImageType, IndiciaPublisher,
    Issue, Publisher, Series, SeriesBond, SeriesBondType)
from apps.gcd.views import read_only
from apps.indexer.models import Indexer
from apps.mycomics import urls as mycomics_urls
from apps.oi import states
from apps.oi.models import (
    CTYPES, BrandGroupRevision, BrandRevision, Changeset, CreatorRevision,
    ImageRevision, IndiciaPublisherRevision, SeriesBondRevision)
from apps.stats.models import CountStats, Download
from apps.stddata.forms import DateForm
from apps.stddata.models import Country, Date, Language

# The marked texts as the English page shows them, long ones by their
# first words; the test translation puts "[it] " before each.
DOWNLOAD = (
    'GCD Data Dumps', 'Data License', 'By downloading the data dump',
    'For details, please read the following Board Resolutions:',
    'Data License (Creative Commons 3.0 Unported) and crediting guidelines',
    'Data distribution policy', 'Upgrade Data License to CC BY-SA 4.0',
    'Technical and Licensing Contact Information',
    'All questions about licensing', 'A mailing list you may join',
    'A low-traffic announcement-only list', 'Documentation',
    'Currently, the dump is only available', 'We used to offer a dump',
    'Additional formats are under investigation',
    '<a href="http://docs.comics.org/wiki/Current_Schema">Schema',
    'Downloads', 'Data last updated:', 'never', '[Optional] Purpose:',
    'Private use', 'Public / Non-Commercial use', 'Public / Commercial use',
    '[Optional] How or where do you plan to use the data?',
    'I have read and accept the GCD data licensing terms',
    'Download MySQL Dump', 'Download Name-Value Dump',
    'Download SQLite Dump')
STATISTICS = ('International Statistics', 'Reorder')
DAILY_CHANGES = (
    'Daily Changes', 'Images', 'Creator (1)', 'Brand Group (1)',
    'Brand (1)', 'Indicia Publisher (1)', 'Parent', '# Issues',
    'Year Began', 'Year Ended', 'Group', 'Surrogate?', 'Yes',
    'Numbering From', 'Continues In', 'Image', 'Change History')
COVERS = (
    'Covers To Replace', 'for series starting with T', 'all marked covers',
    'Displaying 1 to 1 of 1 cover needing replacement.',
    'A click on the cover leads', 'upload replacement cover')
ON_SALE = (
    'Displaying 1 to 1 of 1 issue on-sale the week',
    'Displaying 1 to 1 of 1 issue on-sale the week from',
    'Show With Variants')
SEVERAL_COVERS = (
    'Issues with Several Covers', 'Issues: [it] with several covers',
    'Submit', 'Publisher', 'Series', 'Issue')
PAGES = (
    ('projects_toc', ('Projects Overview',
                      'Overview of Current Data Projects',
                      'Issues with several covers to move to variants',
                      'Stories with type filler',
                      'Special projects page in the wiki')),
    ('donate', ('Donations', 'The GCD is available for public use',
                'Donations are accepted from most countries',
                'The Grand Comicbook Database Foundation, Inc.',
                'The Grand Comicbook Database Foundation Board')),
    ('donate_thanks', ('Donations', 'Thanks',
                       'Thank you for your donation!')),
    ('privacy', ('GCD Privacy Policy', 'Privacy Policy',
                 'The Grand Comics Database <strong>',
                 'We ask for personal information',
                 'When a visitor requests or reads a page',
                 'Please <a href="mailto:contact@comics.org">',
                 'Cookies and Web Beacons', 'We do use',
                 'This website uses ad networks',
                 'The ad networks may also transfer')),
    ('gcd_history_award', ('Comics History Award',)))


class _Bracketed(trans_real.DjangoTranslation):
    """The test translation: "[it] " before every marked text."""

    def gettext(self, message):
        """The message after "[it] "."""
        return '[it] ' + message

    def ngettext(self, singular, plural, number):
        """The form for the number after "[it] "."""
        return '[it] ' + (singular if number == 1 else plural)


@pytest.fixture
def italian(monkeypatch):
    """
    A page asked with ?lang=it, or rendered in Italian, uses the test
    translation.
    """
    monkeypatch.setitem(trans_real._translations, 'it', _Bracketed('it'))


def _text(content):
    """The page as a reader gets its text, white space collapsed."""
    if isinstance(content, bytes):
        content = content.decode()
    return ' '.join(html.unescape(content).split())


def _assert_italian(content, texts):
    """Each of the texts is on the page after "[it] "."""
    _assert_shown(content, ['[it] ' + text for text in texts])


def _assert_shown(content, texts):
    """Each of the texts is on the page."""
    page = _text(content)
    missing = [text for text in texts if _text(text) not in page]
    assert not missing


def site_data():
    """
    A member with an approved change of today of a creator, a brand group,
    a brand, an indicia publisher, a series bond and a brand emblem; the
    statistics of a language and a country; an issue on sale today with
    two covers, one marked for replacement, from the publisher that the
    list of issues with several covers shows first. Returns the member.
    """
    country = Country.objects.get_or_create(
      id=961, defaults={'code': 'q6', 'name': 'Testland Q'})[0]
    language = Language.objects.get_or_create(
      id=961, defaults={'code': 'q6', 'name': 'Testish Q'})[0]
    publisher = Publisher.objects.create(
      id=709, name='Test Publisher', country=country, year_began=1990)
    series = [Series.objects.create(
      id=9600 + number, name='Test Series %d' % number,
      sort_name='Test Series %d' % number, year_began=1990, country=country,
      language=language, publisher=publisher, is_comics_publication=True,
      publication_dates='1990') for number in (1, 2)]
    issue = Issue.objects.create(
      id=9601, number='1', series=series[0], sort_code=1,
      publication_date='1990', key_date='1990-01-00',
      on_sale_date=date.today().isoformat())
    Cover.objects.create(id=9601, issue=issue, marked=True)
    Cover.objects.create(id=9602, issue=issue)
    CountStats.objects.init_stats(language=language)
    CountStats.objects.init_stats(country=country)

    User.objects.get_or_create(username=settings.ANON_USER_NAME)
    member = User.objects.create_user('some.indexer')
    Indexer.objects.create(user=member, country=country, imps=1)
    creator = Creator.objects.create(
      id=9601, gcd_official_name='Some Creator', sort_name='Creator, Some',
      birth_date=Date.objects.create(year='1950'),
      death_date=Date.objects.create())
    brand_group = BrandGroup.objects.create(
      id=9601, name='Test Brand Group', parent=publisher, year_began=1990)
    brand = Brand.objects.create(id=9601, name='Test Brand',
                                 year_began=1990)
    brand.group.add(brand_group)
    indicia_publisher = IndiciaPublisher.objects.create(
      id=9601, name='Test Indicia Publisher', parent=publisher,
      country=country, is_surrogate=True)
    bond = SeriesBond.objects.create(
      id=9601, origin=series[0], target=series[1],
      bond_type=SeriesBondType.objects.get_or_create(
        id=1, defaults={'name': 'numbering',
                        'description': 'numbering continues'})[0])
    emblem = ImageType.objects.get_or_create(
      name='BrandScan', defaults={'description': 'brand emblem',
                                  'unique': True})[0]
    image = Image.objects.create(
      content_type=ContentType.objects.get_for_model(brand),
      object_id=brand.id, type=emblem)
    for change_type, model, values in (
      ('creator', CreatorRevision, {'creator': creator}),
      ('brand_group', BrandGroupRevision, {'brand_group': brand_group}),
      ('brand', BrandRevision, {'brand': brand}),
      ('indicia_publisher', IndiciaPublisherRevision,
       {'indicia_publisher': indicia_publisher, 'country': country}),
      ('series_bond', SeriesBondRevision, {'series_bond': bond}),
      ('image', ImageRevision,
       {'image': image, 'type': emblem})):
        model.objects.create(changeset=Changeset.objects.create(
          indexer=member, state=states.APPROVED,
          change_type=CTYPES[change_type]), **values)
    return member


# The texts with a number: singular, plural, and what the test translation
# shows after "[<language> <form>]".
PLURALS = (
    ('Displaying %(start)s to %(end)s of %(counter)s issue on-sale the '
     'week %(dates)s.',
     'Displaying %(start)s to %(end)s of %(counter)s issues on-sale the '
     'week %(dates)s.', 'week %(counter)s'),
    ('Displaying %(start)s to %(end)s of %(counter)s issue on-sale the '
     'week from %(dates)s.',
     'Displaying %(start)s to %(end)s of %(counter)s issues on-sale the '
     'week from %(dates)s.', 'week from %(counter)s'),
    ('Displaying %(start)s to %(end)s of %(counter)s cover needing '
     'replacement.',
     'Displaying %(start)s to %(end)s of %(counter)s covers needing '
     'replacement.', 'covers %(counter)s'),
    ('You have started a download of this file within the last '
     '%(minutes)d minute.  Please check your download window.  If you '
     'need to start a new download, please wait at least %(minutes)d '
     'minute in order to avoid consuming excess bandwidth.',
     'You have started a download of this file within the last '
     '%(minutes)d minutes.  Please check your download window.  If you '
     'need to start a new download, please wait at least %(minutes)d '
     'minutes in order to avoid consuming excess bandwidth.',
     'minutes %(minutes)d'))
PLAIN = ('Show With Variants', 'Covers To Replace', 'all marked covers')
# The plural rule of each language, and the form it gives 0, 1, 2 and 5.
PLURAL_FORMS = {
    'it': ('nplurals=2; plural=(n != 1);', {0: 1, 1: 0, 2: 1, 5: 1}),
    'de': ('nplurals=2; plural=(n != 1);', {0: 1, 1: 0, 2: 1, 5: 1}),
    'fr': ('nplurals=2; plural=(n > 1);', {0: 0, 1: 0, 2: 1, 5: 1}),
    'es': ('nplurals=2; plural=(n != 1);', {0: 1, 1: 0, 2: 1, 5: 1}),
    'sr': ('nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && '
           'n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);',
           {0: 2, 1: 0, 2: 1, 5: 2}),
    'ja': ('nplurals=1; plural=0;', {0: 0, 1: 0, 2: 0, 5: 0})}
# The series whose names start with these letters have 0, 1, 2 and 5
# covers to replace, and as many issues on sale in one week.
COUNTS = {0: 'D', 1: 'A', 2: 'B', 5: 'C'}


@pytest.fixture
def catalogs(settings, tmp_path):
    """
    A message file in each of the six languages, with its plural rule:
    each form of a text with a number is "[<language> <form>]" and the
    number, and a plain text is "[<language>]" and the text.
    """
    for language, (rule, _) in PLURAL_FORMS.items():
        catalog = polib.POFile()
        catalog.metadata = {'Content-Type': 'text/plain; charset=UTF-8',
                            'Plural-Forms': rule}
        forms = int(rule.split(';')[0].split('=')[1])
        for one, more, shown in PLURALS:
            catalog.append(polib.POEntry(
              msgid=one, msgid_plural=more, msgstr_plural={
                form: '[%s %d] %s' % (language, form, shown)
                for form in range(forms)}))
        for text in PLAIN:
            catalog.append(polib.POEntry(
              msgid=text, msgstr='[%s] %s' % (language, text)))
        folder = tmp_path / language / 'LC_MESSAGES'
        folder.mkdir(parents=True)
        catalog.save_as_mofile(str(folder / 'django.mo'))
    settings.LOCALE_PATHS = [str(tmp_path)]


@pytest.fixture
def counted(member):
    """
    For each count of COUNTS, a series with as many issues, all on sale in
    the same past week and each with a cover marked for replacement.
    Returns the year and week of each count.
    """
    publisher = Publisher.objects.get(id=709)
    language = Language.objects.get(id=961)
    today = date.today()
    weeks = {}
    for weeks_ago, (count, letter) in enumerate(COUNTS.items(), start=1):
        monday = today - timedelta(days=today.weekday(), weeks=weeks_ago)
        weeks[count] = monday.isocalendar()[:2]
        series = Series.objects.create(
          name='%s Series' % letter, sort_name='%s Series' % letter,
          year_began=1990, country=publisher.country, language=language,
          publisher=publisher, is_comics_publication=True,
          publication_dates='1990')
        for number in range(1, count + 1):
            Cover.objects.create(issue=Issue.objects.create(
              number=str(number), series=series, sort_code=number,
              publication_date='1990', key_date='1990-01-00',
              on_sale_date=monday.isoformat()), marked=True)
    return weeks


@pytest.fixture
def member(db):
    """The data of site_data(); its member is logged in."""
    return site_data()


def _reload_urls():
    """Builds the url patterns again from the current settings."""
    importlib.reload(mycomics_urls)
    importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
    clear_url_caches()


@pytest.fixture
def my_comics(member, client):
    """The member is logged in on My Comics, with its url patterns."""
    client.force_login(member)
    with override_settings(MYCOMICS=True):
        _reload_urls()
        yield
    _reload_urls()


@pytest.mark.django_db
@pytest.mark.parametrize('name, texts', PAGES)
def test_page_in_italian(client, italian, name, texts):
    """The texts of a page without data are in Italian."""
    response = client.get(reverse(name) + '?lang=it')

    assert response.status_code == 200
    _assert_italian(response.content, texts)


@pytest.mark.django_db
def test_calendar_in_italian(client, italian):
    """The title of the calendar is in Italian."""
    response = client.get('/calendar/?lang=it')

    _assert_italian(response.content, ('Calendar',))


def test_download_page_in_italian(client, italian, member, settings,
                                  tmp_path):
    """
    The texts of the download page, of its form and of a dump that is not
    there, and the error of a form sent without the license accepted, are
    in Italian.
    """
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(member)
    address = reverse('stats:download') + '?lang=it'

    _assert_italian(client.get(address).content, DOWNLOAD)
    _assert_italian(client.post(address).content, (
      'You must check the box indicating your acceptance',))


def test_second_download_in_italian(client, italian, member):
    """The error of a download started again too soon is in Italian."""
    Download.objects.create(user=member, description=repr(
      {'file': settings.MYSQL_DUMP}))
    client.force_login(member)

    response = client.post(reverse('stats:download') + '?lang=it',
                           {'accept_license': 'on'}, follow=True)

    _assert_italian(response.content, (
      'You have started a download of this file within the last %d '
      'minutes.' % settings.DOWNLOAD_DELTA,))


@pytest.mark.django_db
def test_countries_refused_in_italian(client, italian):
    """The refusal of the list of countries in use is in Italian."""
    response = client.get('/countries/?lang=it')

    _assert_italian(response.content, (
      'You are not allowed to access this page.',))


@pytest.mark.parametrize('kind, phrases', (
  ('language', ('Statistics by language, ordered by number of',
                'Statistics for comics in')),
  ('country', ('Statistics by country, ordered by number of',
               'Statistics for comics published in'))))
def test_international_statistics_in_italian(client, italian, member, kind,
                                             phrases):
    """The statistics by language and by country are in Italian."""
    response = client.get(reverse('international_stats_' + kind) +
                          '?lang=it')

    _assert_italian(response.content, STATISTICS + phrases)


@pytest.mark.parametrize('name, switch', (
  ('changes_by_date', 'my changes'), ('my_changes_by_date', ' all changes')))
def test_daily_changes_in_italian(client, italian, member, name, switch):
    """
    The headings and links of the changes of a day, and the link to the
    member's own changes or to all changes, are in Italian.
    """
    client.force_login(member)
    today = {'show_date': date.today().isoformat()}

    response = client.get(reverse(name, kwargs=today) + '?lang=it')

    _assert_italian(response.content, DAILY_CHANGES)
    assert re.search(r'\[it\] Switch to <a href="[^"]+">%s</a>\.' % switch,
                     response.content.decode())


def test_covers_to_replace_in_italian(client, italian, member):
    """The list of the covers marked for replacement is in Italian."""
    response = client.get('/covers_to_replace/with/T/?lang=it')

    _assert_italian(response.content, COVERS)


def test_issues_with_several_covers_in_italian(client, italian, member):
    """The list of the issues with several covers is in Italian."""
    response = client.get(reverse('issues_with_several_covers') +
                          '?lang=it')

    _assert_italian(response.content, SEVERAL_COVERS)


def test_on_sale_week_of_my_comics_in_italian(client, italian, my_comics):
    """The weekly on-sale list of My Comics is in Italian."""
    response = client.get(reverse('on_sale_this_week') + '?lang=it')

    _assert_italian(response.content, ON_SALE)


@pytest.mark.parametrize('back_up_at, texts', (
  ('', ('We are working to bring the site back online',)),
  ('10:00 UTC', ('We expect the site to be back up at 10:00 UTC.',))))
def test_site_down_page_in_italian(italian, back_up_at, texts):
    """The notice that the site is down is in Italian."""
    with translation.override('it'):
        page = render_to_string('site_down.html', {
          'settings': SimpleNamespace(SITE_DOWN_MESSAGE='',
                                      SITE_BACK_UP_AT=back_up_at)})

    _assert_italian(page, texts + (
      'GCD Down for Upgrade', 'The GCD is Down for Maintenance', 'thanks,',
      '-The GCD Tech Team'))


@pytest.mark.django_db
def test_read_only_notice_in_italian(rf, italian):
    """The notice that editing is turned off is in Italian."""
    request = rf.get('/queues/editing/')
    request.user = AnonymousUser()

    with translation.override('it'):
        response = read_only.dummy(request)

    _assert_italian(response.content, (
      'Online editing and change history are currently turned off.',))


def test_date_help_text_in_italian(italian):
    """The help text of a date field is in Italian."""
    with translation.override('it'):
        help_text = str(DateForm().fields['date'].help_text)

    assert help_text == ('[it] Enter date as YYYY-MM-DD. A ? can be used in '
                         'each part to indicate uncertainty.')


@pytest.mark.parametrize('language', PLURAL_FORMS)
def test_on_sale_count_in_six_languages(client, catalogs, counted,
                                        my_comics, language):
    """
    The counts of the weekly on-sale list of My Comics take the plural
    form of the language: in French 0 and 1 take the first form, in
    Serbian 1, 2 to 4 and 5 or more take three forms, in Japanese every
    number takes the one form.
    """
    forms = PLURAL_FORMS[language][1]
    for count, (year, week) in counted.items():
        address = reverse('on_sale_weekly', kwargs={'year': year,
                                                    'week': week})

        response = client.get(address + '?lang=' + language)

        tag = '[%s %d]' % (language, forms[count])
        _assert_shown(response.content, (
          '%s week %d' % (tag, count), '%s week from %d' % (tag, count),
          '[%s] Show With Variants' % language))


@pytest.mark.parametrize('language', PLURAL_FORMS)
def test_covers_count_in_six_languages(client, catalogs, counted, language):
    """The count of the covers to replace takes the plural form."""
    forms = PLURAL_FORMS[language][1]
    for count, letter in COUNTS.items():
        response = client.get('/covers_to_replace/with/%s/?lang=%s'
                              % (letter, language))

        _assert_shown(response.content, (
          '[%s %d] covers %d' % (language, forms[count], count),
          '[%s] Covers To Replace' % language,
          '[%s] all marked covers' % language))


@pytest.mark.parametrize('language', PLURAL_FORMS)
def test_download_minutes_in_six_languages(client, catalogs, member,
                                           settings, language):
    """
    The minutes of the error of a download started again too soon take
    the plural form.
    """
    forms = PLURAL_FORMS[language][1]
    Download.objects.create(user=member, description=repr(
      {'file': settings.MYSQL_DUMP}))
    client.force_login(member)
    for minutes in (1, 2, 5):
        settings.DOWNLOAD_DELTA = minutes

        response = client.post(
          reverse('stats:download') + '?lang=' + language,
          {'accept_license': 'on'}, follow=True)

        _assert_shown(response.content, (
          '[%s %d] minutes %d' % (language, forms[minutes], minutes),))


@pytest.mark.parametrize('letter, shown', (
  ('A', 'Displaying 1 to 1 of 1 cover needing replacement.'),
  ('B', 'Displaying 1 to 2 of 2 covers needing replacement.')))
def test_covers_count_in_english(client, counted, letter, shown):
    """In English one cover is "1 cover", more are "covers"."""
    response = client.get('/covers_to_replace/with/%s/' % letter)

    _assert_shown(response.content, (shown,))
