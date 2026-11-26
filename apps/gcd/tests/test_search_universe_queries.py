# -*- coding: utf-8 -*-
"""Tests of the queries of the search of universes by name.

A page of results loads the multiverse that each row shows with the
search, so its number of queries does not grow with the number of rows.
"""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models.character import Multiverse, Universe

NAME = 'Query Count Test'


def _universe(number):
    """Add a universe that matches, in a multiverse of its own."""
    mainstream = Universe.objects.create(name='Some Mainstream %d' % number)
    verse = Multiverse.objects.create(name='Some Multiverse %d' % number,
                                      mainstream=mainstream)
    return Universe.objects.create(name='%s %d' % (NAME, number),
                                   verse=verse)


def _queries(client, rows):
    """Return the number of queries of the page, which lists the rows."""
    url = reverse('universe_by_name', kwargs={'universe_name': NAME})
    with CaptureQueriesContext(connection) as context:
        response = client.get(url)
    assert response.status_code == 200
    page = response.content.decode()
    for number in range(1, rows + 1):
        assert 'Some Multiverse %d : %s %d' % (number, NAME, number) in page
    return len(context.captured_queries)


def test_queries_do_not_grow_with_the_rows(client, settings, db):
    """The page with 5 rows runs the queries of the page with 1."""
    settings.USE_ELASTICSEARCH = False
    _universe(1)
    # the first page also fills the caches of the site
    _queries(client, 1)
    one_row = _queries(client, 1)
    for number in range(2, 6):
        _universe(number)

    five_rows = _queries(client, 5)

    assert five_rows == one_row
