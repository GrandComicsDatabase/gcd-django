"""
The page of a series, its details and timeline pages, and the series lists
of a publisher, a creator and a character show their texts in the language
of the page when the message file translates them. The tests use six
languages with different plural rules; any language of the site works the
same way.
"""
import html
import re
from html.parser import HTMLParser

import polib
import pytest
from django.contrib.auth.models import Permission, User
from django.urls import reverse

from apps.gcd.models import (
    Award, Brand, Character, CharacterNameDetail, Cover, CreditType,
    IndiciaPublisher, Issue, Publisher, ReceivedAward, Series, SeriesBond,
    SeriesBondType, SeriesPublicationType, Story, StoryCredit, StoryType)
from apps.gcd.models.creator import Creator, CreatorNameDetail
from apps.gcd.models.issue import INDEXED as INDEX_STATUS
from apps.gcd.models.story import StoryCharacter
from apps.indexer.models import Indexer
from apps.oi.models import OngoingReservation
from apps.stddata.models import Country, Date, Language, Script

DOCUMENTATION = (
  'https://docs.comics.org/wiki/Qualifying_and_Non_Qualifying_Publications'
  '#Non-Comics_Publications_with_some_comics_content')
# The marked texts as their msgids.
SERIES_PAGE = (
  'Series', 'Published in %(language)s', 'Cover Gallery', 'Publisher:',
  'Details by Issue', 'Series Monthly Timeline',
  'Cover and Main Story Overview', 'Creator List', 'Creator Name List',
  'Character List', 'Number of Issues Published:', 'Format:', 'Color:',
  'Dimensions:', 'Paper Stock:', 'Binding:', 'Publishing Format:',
  'Publication Type:', 'Keywords:', "Publisher's Brands:",
  "no publisher's brand",
  "without publisher's brand data", 'Indicia Publishers:',
  'without indicia publisher data', 'Awards:', 'Tracking:', 'Notes:',
  'Index Status', 'Cover Status', 'Image Resources Status',
  "We don't accept cover scans on series that don't have enough "
  "comics-related content.",
  'See our <a href="%(url)s">documentation</a> for more details.',
  'Add Issues', 'Reorder Issues', 'Edit Series Bonds', 'Add Series Bond',
  'Reserve Upcoming Issues',
  'The ongoing issue reservation for this series is held by %(indexer)s.',
  'Free ongoing reservation', 'present')
LEGENDS = (
  'Indexed', 'Partially Indexed', 'Some Data', 'Skeleton Data Only',
  'Pending Approval', 'Reserved', 'Scan Available',
  'Scan Needs Replacement', 'No Scan Available',
  'Statement of Ownership and Indicia', 'Indicia', 'Statement of Ownership',
  'No Scans')
DETAILS = (
  'Details', 'See series monthly timeline',
  '(depends on key dates being set correctly).', 'No issues found.')
TIMELINE = (
  'Timeline', 'See series details by issue',
  '(displays one row per issue with no gaps, by the regular issue sort '
  'order)',
  'This page attempts to show how the issues in this series were published '
  'over time by laying them out in a monthly timeline with alternately '
  'colored rows roughly corresponding to months.  The coloring is not '
  'meaningful for bi-monthly, quarterly or annual books.  Weekly or other '
  'more-frequent-than-monthly issues are grouped into the same color row by '
  'month.',
  'The timeline feature depends on the key date field to order issues into '
  'a monthly timeline. Please note that if the key dates are not filled out '
  'to correspond to the publication months of the issues, then the '
  'timeline will not be accurate.',
  'Not all issues in this series have usable key dates, so not all can be '
  'sorted into a timeline.  The following issues can be sorted:',
  'Not all issues in this series have key dates, so not all can be sorted '
  'into a timeline.  The following issues can be sorted:',
  'No issues in this series have usable key dates, so none can be sorted '
  'into a timeline. The following table is the same as the regular series '
  'detail table:',
  'No issues in this series have key dates, so none can be sorted into a '
  'timeline. The following table is the same as the regular series detail '
  'table:',
  'These issues have no usable key date and cannot be placed in a '
  'timeline:',
  'These issues have no key date and cannot be placed in a timeline:')
COLUMNS = (
  'Key Date', 'Pub. Date', 'On-sale date', 'Volume', 'Number', 'Title',
  'Indicia Publisher', "Publisher's Brand", 'Pages', 'Price', 'Frequency',
  'Barcode', "Publisher's Age Guidelines")
LISTS = (
  'Year', 'Issues', 'Covers', 'Published', 'Publisher', 'First Appearance',
  'First Credit', 'Role', 'No Covers', 'Gallery (%(count)d)',
  'Have %(count)d', 'Need %(count)d', 'Add')
# The texts with a singular and a plural form.
MIGRATE = ("<a href='%(page_url)s'>%(counter)s issue</a> with content to "
           "migrate.",
           "<a href='%(page_url)s'>%(counter)s issues</a> with content to "
           "migrate.")
DATES = ('Publication Date:', 'Publication Dates:')
ISSUES = ('%(counter)s issue', '%(counter)s issues')
# One form in English; a language gives it the forms of its plural rule.
INDEXED = ('%(counter)s indexed', '%(counter)s indexed')
DISPLAYING = ('Displaying %(start)s to %(end)s of %(counter)s issue.',
              'Displaying %(start)s to %(end)s of %(counter)s issues.')
PLURALS = (MIGRATE, INDEXED, DATES, ISSUES, DISPLAYING)


def _serbian(n):
    """The plural form of the number in Serbian: 1, 2 to 4, 5 and more."""
    if n % 10 == 1 and n % 100 != 11:
        return 0
    if 2 <= n % 10 <= 4 and not 10 <= n % 100 < 20:
        return 1
    return 2


# The languages of the tests with the plural rule of their message files:
# French takes the singular for 0, Serbian has three forms, Japanese one.
TWO_FORMS = ('nplurals=2; plural=(n != 1);', lambda n: int(n != 1))
RULES = {
  'it': TWO_FORMS, 'de': TWO_FORMS, 'es': TWO_FORMS,
  'fr': ('nplurals=2; plural=(n > 1);', lambda n: int(n > 1)),
  'sr': ('nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && '
         'n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);', _serbian),
  'ja': ('nplurals=1; plural=0;', lambda n: 0),
}
CODES = ['en'] + list(RULES)
MARK = re.compile(r'\[(%s)(?::\d)?\] ' % '|'.join(RULES))


class _Language:
    """The texts as a page in one language shows them."""

    def __init__(self, code):
        """The language of the code; English has no message file."""
        self.code = code

    def __call__(self, text):
        """The test translation of a text: the text after "[<code>] "."""
        if self.code == 'en':
            return text
        return '[%s] %s' % (self.code, text)

    def plural(self, texts, number):
        """
        The test translation of the form of a text with a singular and a
        plural that goes with the number: the form after "[<code>:<form>] ".
        """
        one, more = texts
        if self.code == 'en':
            return one if number == 1 else more
        form = RULES[self.code][1](number)
        return '[%s:%d] %s' % (self.code, form, more if form else one)


LANGUAGES = [_Language(code) for code in CODES]


@pytest.fixture
def message_files(settings, tmp_path):
    """
    The message file of each language of the tests holds a test translation
    of each marked text, with as many plural forms as the language has; a
    page asked with ?lang=<code> uses it.
    """
    texts = sorted(set(SERIES_PAGE + LEGENDS + DETAILS + TIMELINE +
                       COLUMNS + LISTS))
    for code, (forms, _) in RULES.items():
        language = _Language(code)
        catalog = polib.POFile()
        catalog.metadata = {'Content-Type': 'text/plain; charset=UTF-8',
                            'Plural-Forms': forms}
        for text in texts:
            catalog.append(polib.POEntry(msgid=text, msgstr=language(text)))
        count = int(forms.split(';')[0].split('=')[1])
        for one, more in PLURALS:
            catalog.append(polib.POEntry(
              msgid=one, msgid_plural=more, msgstr_plural={
                form: '[%s:%d] %s' % (code, form, more if form else one)
                for form in range(count)}))
        folder = tmp_path / code / 'LC_MESSAGES'
        folder.mkdir(parents=True)
        catalog.save_as_mofile(str(folder / 'django.mo'))
    settings.LOCALE_PATHS = [str(tmp_path)]


def _issue(id, series, number, key_date='', indexed=False, **fields):
    """An issue of the series with the number as its sort code."""
    return Issue.objects.create(
      id=id, series=series, number=str(number), sort_code=number,
      key_date=key_date,
      is_indexed=INDEX_STATUS['full' if indexed else 'skeleton'], **fields)


def _series(id, name, publisher, issues=0, **fields):
    """A series of the publisher, in the language of the tests."""
    return Series.objects.create(
      id=id, name=name, sort_name=name, year_began=1990,
      country=publisher.country, language_id=963, publisher=publisher,
      publication_dates='1990', issue_count=issues, **fields)


def _first_and_last(series):
    """Points the series to its first and last issue."""
    issues = series.active_issues().order_by('sort_code')
    series.first_issue = issues.first()
    series.last_issue = issues.last()
    series.save()


@pytest.fixture
def country(db):
    """The country and the language of the tests."""
    Language.objects.get_or_create(
      id=963, defaults={'code': 's3', 'name': 'Testish S'})
    return Country.objects.get_or_create(
      id=963, defaults={'code': 's3', 'name': 'Testland S'})[0]


@pytest.fixture
def member(country):
    """
    A member who can approve changes and holds the ongoing reservation of
    the main series.
    """
    user = User.objects.create_user('some.indexer', first_name='Some',
                                    last_name='Indexer')
    user.user_permissions.add(Permission.objects.get(
      codename='can_approve', content_type__app_label='indexer'))
    Indexer.objects.create(user=user, country=country)
    return user


@pytest.fixture
def catalog(country, member):
    """
    A publisher with five series that between them show every text of the
    pages: the main series with every field, brands, indicia publishers, a
    cover, an award, a bond, an ongoing reservation, an issue to migrate,
    issues with good, bad and no key dates; a series that is not of comics;
    a one-issue series with a cover; a current series of five issues with
    no reservation; an empty series. One issue of the main series and every
    issue of the other series is indexed. A creator and a character appear
    in the main series. The ids are fixed so that the pages are the same on
    every run.
    """
    Script.objects.get_or_create(
      id=Script.LATIN_PK,
      defaults={'code': 'Latn', 'number': Script.LATIN_PK, 'name': 'Latin'})
    publisher = Publisher.objects.create(
      id=9631, name='Test Publisher', country=country, year_began=1990)
    kind = SeriesPublicationType.objects.create(id=9631,
                                                name='Some Kind', notes='')
    main = _series(
      9631, 'Test Series', publisher, issues=4, is_current=True,
      is_comics_publication=True, has_gallery=True, format='Some Format',
      color='Some Color', dimensions='Some Dimensions',
      paper_stock='Some Paper', binding='Some Binding',
      publishing_format='Some Publishing Format', publication_type=kind,
      notes='Some series notes.', tracking_notes='Some tracking notes.',
      has_volume=True, has_issue_title=True, has_indicia_frequency=True,
      has_isbn=True, has_barcode=True, has_rating=True)
    main.keywords.add('some keyword')
    imprint = IndiciaPublisher.objects.create(
      id=9631, name='Test Indicia Publisher', parent=publisher,
      country=country, year_began=1990)
    first = _issue(
      9631, main, 1, '1990-01-00', publication_date='January 1990',
      on_sale_date='1989-12-01', volume='1', title='Some Title',
      indicia_frequency='monthly', isbn='9780000000002',
      barcode='012345678905', rating='All Ages', price='1.00 USD',
      indicia_publisher=imprint, indexed=True)
    first.brand_emblem.add(Brand.objects.create(
      id=9631, name='Test Brand', year_began=1990))
    _issue(9632, main, 2, '1990-02-00', publication_date='February 1990',
           no_brand=True, indicia_publisher=imprint,
           editing='Some Editor')
    _issue(9633, main, 3)
    _issue(9634, main, 4, '1700-01-00')
    _first_and_last(main)
    Cover.objects.create(id=9631, issue=first, limit_display=True)
    ReceivedAward.objects.create(
      id=9631, recipient=main, award_name='Best Test Series',
      award=Award.objects.create(id=9631, name='Some Award'),
      award_year=1991)

    magazine = _series(9632, 'Test Magazine', publisher, issues=2,
                       is_comics_publication=False)
    _issue(9635, magazine, 1, indexed=True)
    _issue(9636, magazine, 2, indexed=True)
    _first_and_last(magazine)
    annual = _series(9633, 'Test Annual', publisher, issues=1,
                     is_comics_publication=True, has_gallery=True)
    Cover.objects.create(id=9632, limit_display=True,
                         issue=_issue(9637, annual, 1, '1700-01-00',
                                      indexed=True))
    _first_and_last(annual)
    weekly = _series(9634, 'Test Weekly', publisher, issues=5,
                     is_current=True, is_comics_publication=True)
    _issue(9638, weekly, 1, '1991-01-00', indexed=True)
    for number in range(2, 6):
        _issue(9637 + number, weekly, number, indexed=True)
    _first_and_last(weekly)
    empty = _series(9635, 'Test Empty', publisher,
                    is_comics_publication=True)

    SeriesBond.objects.create(
      id=9631, origin=main, target=weekly,
      bond_type=SeriesBondType.objects.get_or_create(
        id=9631, defaults={'name': 'some bond', 'description': ''})[0])
    OngoingReservation.objects.create(indexer=member, series=main)

    story = Story.objects.create(
      id=9631, issue=first, sequence_number=0,
      type=StoryType.objects.get_or_create(
        id=19, defaults={'name': 'comic story', 'sort_code': 19})[0])
    birth = Date.objects.create(year='1950')
    creator = Creator.objects.create(
      id=9631, gcd_official_name='Some Creator', sort_name='Some Creator',
      birth_date=birth, death_date=Date.objects.create(year=''))
    StoryCredit.objects.create(
      story=story, creator=CreatorNameDetail.objects.create(
        id=9631, creator=creator, name='Some Creator',
        sort_name='Some Creator', is_official_name=True,
        in_script_id=Script.LATIN_PK),
      credit_type=CreditType.objects.get_or_create(
        id=1, defaults={'name': 'script', 'sort_code': 1})[0])
    character = Character.objects.create(
      id=9631, name='Some Hero', sort_name='Some Hero', language_id=963,
      description='', notes='')
    StoryCharacter.objects.create(
      story=story, character=CharacterNameDetail.objects.create(
        id=9631, character=character, name='Some Hero',
        sort_name='Some Hero', is_official_name=True), notes='')
    return {'main': main, 'magazine': magazine, 'annual': annual,
            'weekly': weekly, 'empty': empty, 'publisher': publisher,
            'creator': creator, 'character': character}


class _Headers(HTMLParser):
    """
    Reads the texts of the header cells of the tables of a page, without
    the arrow of the sorted column.
    """

    def __init__(self):
        """Starts outside any header cell."""
        super().__init__()
        self.depth = 0
        self.headers = []

    def handle_starttag(self, tag, attrs):
        """Opens a header cell."""
        if tag == 'th':
            self.depth += 1
            self.headers.append('')

    def handle_endtag(self, tag):
        """Closes a header cell."""
        if tag == 'th' and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        """Adds a text to the open header cell."""
        if self.depth:
            text = (self.headers[-1] + data).replace('\u25b2', '')
            self.headers[-1] = ' '.join(text.replace('\u25bc', '').split())


def _get(client, address, language):
    """The page at the address in the language, as its HTML."""
    if language.code != 'en':
        address += '?lang=' + language.code
    response = client.get(address)
    assert response.status_code == 200
    return response.content.decode()


def _text(page):
    """The page as a reader gets it, every run of white space one space."""
    return ' '.join(html.unescape(page).split())


def _missing(page, texts):
    """The texts of the list that the page does not show."""
    shown = _text(page)
    return [text for text in texts if ' '.join(text.split()) not in shown]


def _headers(page):
    """The texts of the header cells of the page."""
    parser = _Headers()
    parser.feed(page)
    return parser.headers


def _url(name, item, key='series_id'):
    """The address of a page of the object."""
    return reverse(name, kwargs={key: item.id})


def _marks(page):
    """The codes of the languages whose test translations the page shows."""
    return set(MARK.findall(page))


def _series_page(tr):
    """The texts of the page of the main series in the language."""
    return [
      'GCD :: %s :: Test Series' % tr('Series'),
      tr('Published in %(language)s') % {'language': 'Testish S'},
      tr('Cover Gallery') + '</a>',
      tr('Publisher:') + '</span> <a href="/publisher/9631/">',
      tr('Details by Issue') + '</a>', tr('Series Monthly Timeline'),
      tr('Cover and Main Story Overview'), tr('Creator List') + '</a>',
      tr('Creator Name List'), tr('Character List'),
      tr.plural(MIGRATE, 1) % {
        'page_url': '/series/9631/issues_to_migrate/', 'counter': 1},
      tr.plural(DATES, 4) + '</span> January 1990 - ' + tr('present'),
      tr('Number of Issues Published:') + '</span> 4 (#1 - Some Title - #4)',
      tr('Format:') + '</span> Some Format',
      tr('Color:') + '</span> Some Color',
      tr('Dimensions:') + '</span> Some Dimensions',
      tr('Paper Stock:') + '</span> Some Paper',
      tr('Binding:') + '</span> Some Binding',
      tr('Publishing Format:') + '</span> Some Publishing Format',
      tr('Publication Type:') + '</span> Some Kind',
      tr('Keywords:') + '</span>',
      "<h3>%s</h3>" % tr("Publisher's Brands:"),
      '>%s</a>)' % (tr.plural(ISSUES, 1) % {'counter': 1}),
      '>%s</a>)' % (tr.plural(ISSUES, 2) % {'counter': 2}),
      tr("no publisher's brand") + ' (<a',
      tr("without publisher's brand data") + ' (<a',
      '<h3>%s</h3>' % tr('Indicia Publishers:'),
      tr('without indicia publisher data') + ' (<a',
      '<h3>%s</h3>' % tr('Awards:'), '<h3> %s </h3>' % tr('Tracking:'),
      '<h3 class="mt-2">%s</h3>' % tr('Notes:'),
      '> %s </h3>' % tr('Index Status'), '> %s </h3>' % tr('Cover Status'),
      '> %s </h3>' % tr('Image Resources Status'),
      tr('Add Issues') + '</a>', tr('Reorder Issues') + '</a>',
      tr('Edit Series Bonds') + '</a>', tr('Add Series Bond') + '</a>',
      tr('The ongoing issue reservation for this series is held by '
         '%(indexer)s.') % {'indexer': 'Some Indexer'},
      'value="%s"' % tr('Free ongoing reservation')] + [
      ' %s </td>' % tr(legend) for legend in LEGENDS]


@pytest.mark.parametrize('tr', LANGUAGES, ids=CODES)
@pytest.mark.django_db
def test_series_page(client, message_files, catalog, member, tr):
    """
    The title, the labels, the links, the headings, the legends of the
    status tables and the buttons of the page of a series are in the
    language of the page, and no text is in another language of the tests.
    """
    client.force_login(member)
    page = _get(client, _url('show_series', catalog['main']), tr)

    assert _missing(page, _series_page(tr)) == []
    assert _marks(page) == ({tr.code} - {'en'})


@pytest.mark.parametrize('tr', LANGUAGES, ids=CODES)
@pytest.mark.django_db
def test_series_pages_with_other_texts(client, message_files, catalog,
                                       member, tr):
    """
    The page of a series that is not of comics says why it takes no
    covers, and a current series with no reservation offers one, in the
    language of the page.
    """
    client.force_login(member)
    magazine = _get(client, _url('show_series', catalog['magazine']), tr)
    weekly = _get(client, _url('show_series', catalog['weekly']), tr)

    assert _missing(magazine, [
      tr("We don't accept cover scans on series that don't have enough "
         "comics-related content.") + ' ' +
      tr('See our <a href="%(url)s">documentation</a> for more details.')
      % {'url': DOCUMENTATION}]) == []
    assert _missing(weekly, [
      'value="%s"' % tr('Reserve Upcoming Issues')]) == []


@pytest.mark.parametrize('tr', LANGUAGES, ids=CODES)
@pytest.mark.django_db
def test_details_pages(client, message_files, catalog, tr):
    """
    The details page of a series links its timeline and says when it has
    no issue, in the language of the page.
    """
    main = _get(client, _url('series_details', catalog['main']), tr)
    empty = _get(client, _url('series_details', catalog['empty']), tr)
    timeline = '%s</a> %s' % (
      tr('See series monthly timeline'),
      tr('(depends on key dates being set correctly).'))

    assert _missing(main, [
      'GCD :: %s :: Test Series :: %s' % (tr('Series'), tr('Details')),
      tr('Publisher:') + '</span> <a href="/publisher/9631/">',
      timeline]) == []
    assert _missing(empty, ['<p>%s</p>' % tr('No issues found.')]) == []
    assert _marks(main) == ({tr.code} - {'en'})


@pytest.mark.parametrize('tr', LANGUAGES, ids=CODES)
@pytest.mark.django_db
def test_timeline_pages(client, message_files, catalog, tr):
    """
    The timeline page of a series explains itself, names the issues it
    cannot place, with or without bad key dates, and heads its columns in
    the language of the page.
    """
    pages = {name: _get(client, _url('series_timeline', catalog[name]), tr)
             for name in ('main', 'weekly', 'magazine', 'annual')}
    details = '%s</a> %s' % (
      tr('See series details by issue'),
      tr('(displays one row per issue with no gaps, by the regular issue '
         'sort order)'))

    assert _missing(pages['main'], [
      'GCD :: %s :: Test Series :: %s' % (tr('Series'), tr('Timeline')),
      tr('Publisher:') + '</span> <a href="/publisher/9631/">', details] +
      [tr(text) for text in TIMELINE[3:6]] + [tr(TIMELINE[9])]) == []
    assert _missing(pages['weekly'], [tr(TIMELINE[6]),
                                      tr(TIMELINE[10])]) == []
    assert _missing(pages['annual'], [tr(TIMELINE[7])]) == []
    assert _missing(pages['magazine'], [tr(TIMELINE[8])]) == []
    # Both tables, the second one without the title; ISBN is a code.
    columns = [tr(column) for column in COLUMNS]
    first = columns[:11] + ['ISBN'] + columns[11:]
    assert _headers(pages['main']) == first + first[:5] + first[6:]


@pytest.mark.parametrize('tr', LANGUAGES, ids=CODES)
@pytest.mark.django_db
def test_series_lists(client, message_files, catalog, tr):
    """
    The series lists of a publisher, a creator and a character head their
    columns and give the cover status in the language of the page.
    """
    publisher = _get(client, _url('show_publisher', catalog['publisher'],
                                  'publisher_id'), tr)
    creator = _get(client, _url('creator_series', catalog['creator'],
                                'creator_id'), tr)
    character = _get(client, _url('character_series', catalog['character'],
                                  'character_id'), tr)

    assert _headers(publisher) == [
      tr(column) for column in
      ('Series', 'Year', 'Issues', 'Covers', 'Published')]
    assert _missing(publisher, [
      tr('No Covers'), tr('Gallery (%(count)d)') % {'count': 1},
      '%s</a> (<a href="/series/9631/scans/">%s</a>)' % (
        tr('Have %(count)d') % {'count': 1},
        tr('Need %(count)d') % {'count': 3}),
      '<a href="/series/9634/scans/">%s</a>' % tr('Add'),
      'January 1990 - ' + tr('present')]) == []
    assert _headers(creator) == [
      tr(column) for column in
      ('Series', 'Year', 'Publisher', 'First Credit', 'Issues', 'Role')]
    assert _headers(character) == [
      tr(column) for column in
      ('Series', 'Year', 'Publisher', 'First Appearance', 'Issues')]


@pytest.mark.parametrize('tr', LANGUAGES, ids=CODES)
@pytest.mark.django_db
def test_counts(client, message_files, catalog, tr):
    """
    The series of 0, 1, 2, 4 and 5 issues give their count on the details
    page, the label of their publication dates and their count in the list
    of the publisher in the plural form that the language gives the number:
    in French 0 takes the singular, Serbian has one form for 1, one for 2
    to 4 and one for 5 and more, Japanese has one form for every number.
    In that list the count of the indexed issues, 0, 1, 2, 1 and 5, takes
    the form of its own number.
    """
    publisher = _get(client, _url('show_publisher', catalog['publisher'],
                                  'publisher_id'), tr)
    missing = []
    for key, count, indexed in (('empty', 0, 0), ('annual', 1, 1),
                                ('magazine', 2, 2), ('main', 4, 1),
                                ('weekly', 5, 5)):
        details = _get(client, _url('series_details', catalog[key]), tr)
        page = _get(client, _url('show_series', catalog[key]), tr)
        missing += _missing(details, [tr.plural(DISPLAYING, count) % {
          'start': min(count, 1), 'end': count, 'counter': count}])
        missing += _missing(page, [tr.plural(DATES, count) + '</span>'])
        missing += _missing(publisher, ['%s (%s)' % (
          tr.plural(ISSUES, count) % {'counter': count},
          tr.plural(INDEXED, indexed) % {'counter': indexed})])

    assert missing == []
