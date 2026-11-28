"""Tests for the "Page not found" and "Internal Server Error" pages."""

import pytest
from django.core.cache import cache
from django.urls import get_resolver, reverse

GITHUB_NEW_ISSUE = \
    'https://github.com/GrandComicsDatabase/gcd-django/issues/new'


def _contact_link():
    """The start of the link to the contact form of the site."""
    return '<a href="%s">let us know' % reverse('contact_form')


@pytest.fixture
def empty_cache():
    """Start and end with no request counted by the limits of the API."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_page_not_found_offers_the_contact_form_before_github(client):
    """
    A bad link leads to the contact form first, and to a new issue on
    GitHub, with the address of the page, second.
    """
    response = client.get('/no-such-page/')
    content = response.content.decode()

    assert response.status_code == 404
    assert _contact_link() in content
    assert GITHUB_NEW_ISSUE + \
        '?body=Occurred+at+http%3A//testserver/no-such-page/' in content
    assert content.index(_contact_link()) < content.index(GITHUB_NEW_ISSUE)


@pytest.mark.django_db
@pytest.mark.parametrize('path', ['/api/no-such-page/',
                                  '/api/v2/no-such-page/'])
def test_unknown_api_path_answers_like_the_api(client, path):
    """
    A path under /api/ that no route matches gets the short JSON answer
    of the API, not the page of the site.
    """
    response = client.get(path)

    assert response.status_code == 404
    assert response['Content-Type'] == 'application/json'
    assert response.json() == {'detail': 'Not found.'}


@pytest.mark.django_db
def test_unknown_path_like_the_api_one_gets_the_page_of_the_site(client):
    """Only paths under /api/ answer in JSON: /apiary/ is not one."""
    response = client.get('/apiary/')

    assert response.status_code == 404
    assert response['Content-Type'].startswith('text/html')
    assert _contact_link() in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize('path', ['/api/issue/0/', '/api/v2/issues/0/'])
def test_missing_api_object_keeps_the_answer_of_the_api(client, empty_cache,
                                                        path):
    """
    An API route that finds no object still gives the answer of the API
    itself, which names the kind of record.
    """
    response = client.get(path, HTTP_ACCEPT='application/json')

    assert response.status_code == 404
    assert response['Content-Type'] == 'application/json'
    assert response.json() == {
        'detail': 'No Issue matches the given query.'}


def test_server_error_offers_the_contact_form_before_github(rf):
    """
    The page of the error handler of the site leads to the contact form
    first and to a new issue on GitHub second.
    """
    handler = get_resolver().resolve_error_handler(500)
    response = handler(rf.get('/'))
    content = response.content.decode()

    assert response.status_code == 500
    assert _contact_link() in content
    assert GITHUB_NEW_ISSUE in content
    assert content.index(_contact_link()) < content.index(GITHUB_NEW_ISSUE)
