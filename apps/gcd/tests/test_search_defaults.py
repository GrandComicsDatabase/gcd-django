# -*- coding: utf-8 -*-
"""
Country and language filters kept in a cookie for the next "Everything"
searches started from the search bar.
"""
from urllib.parse import urlencode

import pytest
from django.http import HttpResponse

COOKIE = 'search_defaults'
BAR_SEARCH = {'search_type': 'haystack', 'query': 'x'}


def bar_search(client, cookie=None, **fields):
    """Search from the bar with an optional kept-filters cookie and return
    the address it sends the browser to."""
    if cookie is not None:
        client.cookies[COOKIE] = cookie
    response = client.get('/search/', dict(BAR_SEARCH, **fields))
    assert response.status_code == 302
    return response['Location']


@pytest.mark.django_db
def test_a_kept_country_goes_with_the_next_search(client):
    """A country in the cookie is added to the next bar search."""
    location = bar_search(client, urlencode({'country': 'Testland A'}))
    assert location == '/searchNew/?q=x&country=Testland+A'


@pytest.mark.django_db
def test_without_the_cookie_the_address_is_unchanged(client):
    """Without the cookie the bar search goes where it went before."""
    assert bar_search(client) == '/searchNew/?q=x'


@pytest.mark.django_db
def test_other_keys_in_the_cookie_are_ignored(client):
    """Only country and language are read from the cookie."""
    cookie = urlencode([('q', 'y'), ('publisher', 'Test Publisher'),
                        ('selected_facets', 'facet_model_name_exact:issue'),
                        ('country', 'Testland A'), ('language', '')])
    location = bar_search(client, cookie)
    assert location == '/searchNew/?q=x&country=Testland+A'


@pytest.mark.django_db
def test_two_countries_and_a_language_are_all_kept(client):
    """Every kept country and language goes with the search."""
    cookie = urlencode([('country', 'Testland A'), ('country', 'Testland B'),
                        ('language', 'q4')])
    location = bar_search(client, cookie)
    assert location == ('/searchNew/?q=x&country=Testland+A'
                        '&country=Testland+B&language=q4')


@pytest.mark.django_db
def test_the_sort_stays(client):
    """The sort of the bar search is kept with the filters."""
    location = bar_search(client, urlencode({'language': 'q4'}),
                          sort='chrono')
    assert location == '/searchNew/?q=x&sort=year&language=q4'


def test_keep_writes_a_cookie_for_a_year():
    """Keep stores the filters in a cookie that lasts a year."""
    from apps.gcd.views.search_haystack import default_filters, \
                                               set_default_filters
    kept = [('country', 'Testland A'), ('language', 'q4')]
    response = HttpResponse()
    set_default_filters(response, kept)
    cookie = response.cookies[COOKIE]
    assert default_filters(cookie.value) == kept
    assert cookie['max-age'] == 365 * 24 * 60 * 60
    assert cookie['httponly'] is True
    assert cookie['samesite'] == 'Lax'


def test_forget_deletes_the_cookie():
    """Forget deletes the cookie of the kept filters."""
    from apps.gcd.views.search_haystack import set_default_filters
    response = HttpResponse()
    set_default_filters(response, [])
    cookie = response.cookies[COOKIE]
    assert cookie.value == ''
    assert cookie['max-age'] == 0
