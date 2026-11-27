"""The lang query parameter accepts only known language codes."""

import pytest
from django.test import RequestFactory
from django.utils import translation

from apps.gcd.locale_query import LocaleQueryMiddleware


@pytest.fixture(autouse=True)
def keep_active_language():
    """Give back, after each test, the language that was active before."""
    with translation.override(translation.get_language()):
        yield


def language_for(query, active='en'):
    """Return the language the middleware picks for a query string.

    active is the language left on the thread by an earlier request.
    """
    translation.activate(active)
    request = RequestFactory().get('/', query)
    LocaleQueryMiddleware(lambda request: None).process_request(request)
    assert translation.get_language() == request.LANGUAGE_CODE
    return request.LANGUAGE_CODE


def test_site_language_is_activated():
    """A code of settings.LANGUAGES is used as it is."""
    assert language_for({'lang': 'de'}) == 'de'


@pytest.mark.parametrize('code', ['fr', 'pt-br'])
def test_language_known_to_django_is_activated(code):
    """A language Django knows is used, for the front page statistics."""
    assert language_for({'lang': code}) == code


@pytest.mark.parametrize('value', ['xx', 'German', ''])
def test_unknown_value_gives_english(value):
    """A value that names no known language counts as no parameter."""
    assert language_for({'lang': value}, active='de') == 'en'


def test_language_added_to_settings_is_activated(settings):
    """settings.LANGUAGES is read when the request comes."""
    settings.LANGUAGES = [*settings.LANGUAGES, ('qx', 'Test Language')]
    assert language_for({'lang': 'qx'}) == 'qx'


def test_no_parameter_gives_english():
    """Without the parameter the page is in English, as before."""
    assert language_for({}, active='de') == 'en'
