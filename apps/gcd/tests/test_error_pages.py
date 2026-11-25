"""Tests for the "Page not found" and "Internal Server Error" pages."""

import pytest
from django.urls import get_resolver, reverse

GITHUB_NEW_ISSUE = \
    'https://github.com/GrandComicsDatabase/gcd-django/issues/new'


def _contact_link():
    """The start of the link to the contact form of the site."""
    return '<a href="%s">let us know' % reverse('contact_form')


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
