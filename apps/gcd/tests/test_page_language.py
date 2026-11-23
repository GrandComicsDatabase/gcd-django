"""Every page states its language in the lang attribute of <html>."""

from html.parser import HTMLParser

import pytest
from django.conf import settings
from django.template.loader import render_to_string
from django.urls import get_resolver, reverse
from django.utils import translation


class _HtmlTagParser(HTMLParser):
    """Keeps the attributes of the <html> tag of a page."""

    def __init__(self):
        super().__init__()
        self.attributes = None

    def handle_starttag(self, tag, attrs):
        if tag == 'html' and self.attributes is None:
            self.attributes = dict(attrs)


def _page_language(content):
    """The lang attribute of the <html> tag of the page."""
    parser = _HtmlTagParser()
    parser.feed(content if isinstance(content, str) else content.decode())
    assert parser.attributes is not None, 'the page has no <html> tag'
    return parser.attributes.get('lang')


@pytest.fixture(autouse=True)
def _active_language_back_after_the_test():
    """The language a request activates does not reach the next tests."""
    with translation.override(translation.get_language()):
        yield


@pytest.mark.django_db
def test_page_without_a_language_states_english(client):
    """A page without a language in its address is in English."""
    response = client.get('/')

    assert response.status_code == 200
    assert _page_language(response.content) == 'en'


@pytest.mark.django_db
@pytest.mark.parametrize('language', ['de', 'it', 'nl', 'pt', 'sv'])
def test_start_page_states_its_language(client, language):
    """The start page of a language of the site is in that language."""
    response = client.get('/?lang=%s' % language)

    assert response.status_code == 200
    assert _page_language(response.content) == language


@pytest.mark.django_db
@pytest.mark.parametrize('language', ['fr', 'es', 'xx'])
def test_start_page_states_english_for_a_language_without_texts(
      client, language):
    """
    The front page also takes a language the site has no texts for, to
    show the counts of that language; the page itself is in English.
    """
    response = client.get('/?lang=%s' % language)

    assert response.status_code == 200
    assert language not in dict(settings.LANGUAGES)
    assert _page_language(response.content) == 'en'


@pytest.mark.django_db
@pytest.mark.parametrize('address, language', [
    ('/privacy/', 'en'),
    ('/privacy/?lang=it', 'it'),
])
def test_page_on_the_older_base_states_its_language(
      client, address, language):
    """A page on gcd/base.html states the active language as well."""
    response = client.get(address)

    assert response.status_code == 200
    assert _page_language(response.content) == language


@pytest.mark.django_db
@pytest.mark.parametrize('query, language', [('', 'en'), ('?lang=de', 'de')])
def test_daily_creators_page_states_its_language(client, query, language):
    """The list of creators born on the day states the active language."""
    response = client.get(reverse('daily_creators') + query)

    assert response.status_code == 200
    assert _page_language(response.content) == language


@pytest.mark.parametrize('active, language', [('en', 'en'), ('it', 'it'),
                                              ('fr', 'en')])
def test_my_comics_base_states_its_language(rf, active, language):
    """The base page of my.comics.org states the active language."""
    with translation.override(active):
        content = render_to_string('mycomics/base.html',
                                   request=rf.get('/'))

    assert _page_language(content) == language


def test_server_error_page_states_english(rf):
    """The page of the error handler is written in English only."""
    handler = get_resolver().resolve_error_handler(500)
    with translation.override('de'):
        response = handler(rf.get('/'))

    assert response.status_code == 500
    assert _page_language(response.content) == 'en'


def test_site_down_page_states_english():
    """The page shown while the site is down is written in English only."""
    with translation.override('de'):
        content = render_to_string('site_down.html', {'settings': settings})

    assert _page_language(content) == 'en'
