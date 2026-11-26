"""
The bar at the top of every page and the license image of its footer show
their texts in the language of the page when the message file translates
them.
"""
import html
import importlib
from html.parser import HTMLParser

import polib
import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import clear_url_caches

from apps.mycomics import urls as mycomics_urls

PAGE = '/donate/'
# The texts as their msgids: the search box with its two lists, the menus.
SEARCH = (
    'Everything', 'Series Name', 'Series Name &amp; Issue #', 'Creator Name',
    'Writer', 'Penciller', 'Inker', 'Colorist', 'Letterer', 'Editor',
    'Any Credit', 'Story Title', 'Feature', 'Character', 'Job Number',
    'Barcode', 'Feature Name', 'Character Name', 'Group Name', 'Keyword',
    'Publisher Name', 'Brand Group Name', 'Brand Emblem Name',
    'Indicia Publisher Name', 'Search...', 'Search', 'Name', 'Date')
MENUS = ('Menu', 'Advanced Query', 'User menu', 'Tutorial', 'Documentation',
         'Mailing Lists', 'Donate')
VISITOR = SEARCH + MENUS + ('Sign Up', 'Log In')
STAFF = SEARCH + MENUS + ('Editing', 'Profile', 'Admin', 'Log Out')
COLLECTOR = SEARCH + MENUS + ('Collections', 'Profile', 'Log Out')
LICENSE = 'Creative Commons License'
# The same in every language: the logo of the site and a code.
CODES = {'GCD', 'ISBN'}


def _italian(text):
    """The test translation of a text in the Italian message file."""
    return '[it] ' + text


def _shown(texts):
    """The texts as a reader gets them from the page."""
    return {html.unescape(text) for text in texts}


class _FrameParser(HTMLParser):
    """
    Reads the texts that a reader sees or hears in the top bar, the first
    <nav> of a page, and the text of the license image of the footer.
    """

    NAMES = ('placeholder', 'aria-label', 'alt', 'title')

    def __init__(self):
        """Starts before the top bar, with no text read."""
        super().__init__()
        self.nav_depth = 0
        self.top_bar_read = False
        self.hidden_depth = 0
        self.texts = []
        self.license = None

    def handle_starttag(self, tag, attrs):
        """
        Keeps the names of an element of the bar, the label of a submit
        button and the text of the license image.
        """
        attributes = dict(attrs)
        if tag == 'img' and 'cc_sa_license' in attributes.get('src', ''):
            self.license = attributes.get('alt')
        if self.top_bar_read:
            return
        if tag == 'nav':
            self.nav_depth += 1
        if not self.nav_depth:
            return
        if tag in ('svg', 'script'):
            self.hidden_depth += 1
        self.texts += [attributes[name] for name in self.NAMES
                       if attributes.get(name)]
        if tag == 'input' and attributes.get('type') == 'submit':
            self.texts.append(attributes['value'])

    def handle_endtag(self, tag):
        """Ends a drawing, a script or the top bar."""
        if self.top_bar_read:
            return
        if tag in ('svg', 'script') and self.hidden_depth:
            self.hidden_depth -= 1
        elif tag == 'nav' and self.nav_depth:
            self.nav_depth -= 1
            self.top_bar_read = not self.nav_depth

    def handle_data(self, data):
        """Keeps a text of the bar outside drawings and scripts."""
        text = ' '.join(data.split())
        if text and self.nav_depth and not self.hidden_depth:
            self.texts.append(text)


def _reload_urls():
    """Builds the url patterns again from the current settings."""
    importlib.reload(mycomics_urls)
    importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
    clear_url_caches()


def _read(client, address):
    """The texts of the top bar and the license image of the page."""
    response = client.get(address)
    assert response.status_code == 200
    page = _FrameParser()
    page.feed(response.content.decode())
    assert page.top_bar_read, 'the page has no top bar'
    return page


@pytest.fixture
def italian(settings, tmp_path):
    """
    The Italian message file holds a test translation of each text; a page
    asked with ?lang=it uses it. The search box offers Everything as well,
    as on a site with Elasticsearch.
    """
    catalog = polib.POFile()
    catalog.metadata = {'Content-Type': 'text/plain; charset=UTF-8'}
    for text in sorted(set(VISITOR + STAFF + COLLECTOR + (LICENSE,))):
        catalog.append(polib.POEntry(msgid=text, msgstr=_italian(text)))
    folder = tmp_path / 'it' / 'LC_MESSAGES'
    folder.mkdir(parents=True)
    catalog.save_as_mofile(str(folder / 'django.mo'))
    settings.LOCALE_PATHS = [str(tmp_path)]
    settings.USE_ELASTICSEARCH = True


@pytest.fixture
def my_comics(db, client):
    """A collector is logged in on My Comics, with its url patterns."""
    client.force_login(User.objects.create_user('some.collector'))
    with override_settings(MYCOMICS=True):
        _reload_urls()
        yield
    _reload_urls()


@pytest.mark.django_db
def test_top_bar_of_a_visitor_in_italian(client, italian):
    """
    The search box with its two lists, the buttons and the menu of a
    visitor are in Italian.
    """
    page = _read(client, PAGE + '?lang=it')

    assert set(page.texts) == _shown(map(_italian, VISITOR)) | CODES


@pytest.mark.django_db
def test_top_bar_of_a_staff_member_in_italian(client, italian):
    """The editing button and the menu of a staff member are in Italian."""
    client.force_login(User.objects.create_user('some.staff.member',
                                                is_staff=True))

    page = _read(client, PAGE + '?lang=it')

    assert set(page.texts) == _shown(map(_italian, STAFF)) | CODES


@pytest.mark.django_db
def test_top_bar_of_my_comics_in_italian(client, italian, my_comics):
    """The collections button of My Comics is in Italian."""
    page = _read(client, PAGE + '?lang=it')

    assert set(page.texts) == _shown(map(_italian, COLLECTOR)) | CODES


@pytest.mark.django_db
def test_license_image_in_italian(client, italian):
    """The text of the license image of the footer is in Italian."""
    assert _read(client, PAGE + '?lang=it').license == _italian(LICENSE)


@pytest.mark.django_db
def test_english_page_keeps_its_texts(client, italian):
    """In English the bar and the footer show the same texts as before."""
    page = _read(client, PAGE)

    assert set(page.texts) == _shown(VISITOR) | CODES
    assert page.license == LICENSE
