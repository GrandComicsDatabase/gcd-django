"""Tests for the "Page not found" and "Internal Server Error" pages."""

import re

import pytest
from django.urls import get_resolver

GITHUB_NEW_ISSUE = \
    'https://github.com/GrandComicsDatabase/gcd-django/issues/new'


def _let_us_know_target(content):
    """The address of the link "let us know." of an error page."""
    match = re.search(r'<a href="([^"]*)">\s*let\s+us\s+know\.</a>',
                      content)
    assert match
    return match.group(1)


@pytest.mark.django_db
def test_page_not_found_reports_on_github(client):
    """
    "let us know." on a bad link opens a new issue on GitHub with the
    address of the page.
    """
    response = client.get('/no-such-page/')

    assert response.status_code == 404
    assert _let_us_know_target(response.content.decode()) == \
        GITHUB_NEW_ISSUE + \
        '?body=Occurred+at+http%3A//testserver/no-such-page/'


def test_server_error_reports_on_github(rf):
    """
    "let us know." on the page of the error handler of the site opens a
    new issue on GitHub.
    """
    handler = get_resolver().resolve_error_handler(500)
    response = handler(rf.get('/'))

    assert response.status_code == 500
    assert _let_us_know_target(response.content.decode()) == \
        GITHUB_NEW_ISSUE
