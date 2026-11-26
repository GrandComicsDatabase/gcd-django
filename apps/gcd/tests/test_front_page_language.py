"""The language chosen on a start page is kept on the following pages."""

from html.parser import HTMLParser

import pytest
from django.conf import settings
from django.utils import translation

from apps.stddata.models import Language

NEXT_PAGE = '/privacy/'


class _LinkParser(HTMLParser):
    """Keeps the addresses of the links of a page, by the text of a link."""

    def __init__(self):
        super().__init__()
        self.href = None
        self.text = ''
        self.links = {}

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.href = dict(attrs).get('href')
            self.text = ''

    def handle_endtag(self, tag):
        if tag == 'a' and self.href is not None:
            text = ' '.join(self.text.split())
            self.links.setdefault(text, []).append(self.href)
            self.href = None

    def handle_data(self, data):
        if self.href is not None:
            self.text += data


def _links(response, text):
    """The addresses of the links of the page with the text."""
    parser = _LinkParser()
    parser.feed(response.content.decode())
    assert text in parser.links, 'no link "%s" on the page' % text
    return parser.links[text]


def _language(client, address):
    """The language of the request for the address."""
    response = client.get(address)
    assert response.status_code == 200
    return response.wsgi_request.LANGUAGE_CODE


@pytest.fixture(autouse=True)
def _active_language_back_after_the_test():
    """The language a request activates does not reach the next tests."""
    with translation.override(translation.get_language()):
        yield


@pytest.fixture
def start_page_languages():
    """The languages of the start pages, as the front page looks them up."""
    for code, name in settings.LANGUAGES:
        Language.objects.get_or_create(code=code, defaults={'name': name})


@pytest.mark.django_db
@pytest.mark.parametrize('language', ['de', 'it', 'nl', 'pt', 'sv'])
def test_start_page_language_is_kept_on_the_next_page(client, language):
    """A page after a start page is in the language of that start page."""
    assert _language(client, '/?lang=%s' % language) == language

    assert _language(client, NEXT_PAGE) == language


@pytest.mark.django_db
def test_front_page_keeps_the_chosen_start_page(
        client, start_page_languages):
    """The front page without a language is the start page chosen last."""
    client.get('/?lang=de')

    response = client.get('/')

    assert response.status_code == 200
    assert getattr(response.context['language'], 'code', None) == 'de'


@pytest.mark.django_db
def test_other_start_page_replaces_the_language(client):
    """Choosing another start page changes the language of the next pages."""
    client.get('/?lang=de')
    client.get('/?lang=it')

    assert _language(client, NEXT_PAGE) == 'it'


@pytest.mark.django_db
def test_english_start_page_link_goes_back_to_english(
        client, start_page_languages):
    """The English start page link of a start page ends the choice."""
    german_start_page = client.get('/?lang=de')
    assert _language(client, NEXT_PAGE) == 'de'

    addresses = _links(german_start_page, 'English start page')
    assert len(set(addresses)) == 1, addresses

    english_start_page = addresses[0]
    assert _language(client, english_start_page) == 'en'
    assert _language(client, NEXT_PAGE) == 'en'


@pytest.mark.django_db
@pytest.mark.parametrize('language', ['fr', 'es', 'xx'])
def test_language_without_start_page_is_not_kept(client, language):
    """
    The front page takes any language, to show the counts of that
    language; only a language with a start page is kept.
    """
    client.get('/?lang=de')

    assert _language(client, '/?lang=%s' % language) == language
    assert _language(client, NEXT_PAGE) == 'de'


@pytest.mark.django_db
def test_language_is_written_only_when_it_changes(client):
    """The session is saved for a new choice, not for each page."""
    first = client.get('/?lang=de')
    again = client.get('/?lang=de')
    next_page = client.get(NEXT_PAGE)

    assert first.wsgi_request.session.modified
    assert not again.wsgi_request.session.modified
    assert not next_page.wsgi_request.session.modified


@pytest.mark.django_db
@pytest.mark.parametrize('address', ['/', '/?lang=en', NEXT_PAGE])
def test_english_without_a_choice_starts_no_session(client, address):
    """A reader who chooses no other language gets no session."""
    response = client.get(address)

    assert response.status_code == 200
    assert _language(client, address) == 'en'
    assert settings.SESSION_COOKIE_NAME not in response.cookies
