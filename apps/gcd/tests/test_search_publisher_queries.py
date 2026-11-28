# -*- coding: utf-8 -*-
"""Tests of the queries of the name searches of publishers and printers.

A page of results loads the countries and the parent publishers that its
rows show with the search, so its number of queries does not grow with
the number of rows.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import BrandGroup, IndiciaPublisher, Publisher
from apps.gcd.models.publisher import Printer
from apps.stddata.models import Country

NAME = 'Query Count Test'


def _country():
    """Return the country of the records of the tests."""
    return Country.objects.get_or_create(
        id=911, defaults={'code': 'r1', 'name': 'Testland R'})[0]


def _parent(number):
    """Return a new publisher that does not match, a parent of a match."""
    return Publisher.objects.create(name='Some Publisher %d' % number,
                                    country=_country(), year_began=1965)


def _publisher(number):
    """Add a publisher that matches."""
    return Publisher.objects.create(name='%s %d' % (NAME, number),
                                    country=_country(), year_began=1965)


def _indicia_publisher(number):
    """Add an indicia publisher, with its own parent, that matches."""
    return IndiciaPublisher.objects.create(
        name='%s %d' % (NAME, number), parent=_parent(number),
        country=_country(), year_began=1965)


def _brand_group(number):
    """Add a brand group, with its own parent, that matches."""
    return BrandGroup.objects.create(
        name='%s %d' % (NAME, number), parent=_parent(number),
        year_began=1965)


def _printer(number):
    """Add a printer that matches."""
    return Printer.objects.create(name='%s %d' % (NAME, number),
                                  country=_country(), year_began=1965)


# For each search: the name of its url, the keyword of the searched text in
# the url and the function that adds a matching record.
SEARCHES = (
  ('publisher_by_name', 'publisher_name', _publisher),
  ('indicia_publisher_by_name', 'ind_pub_name', _indicia_publisher),
  ('brand_group_by_name', 'brand_group_name', _brand_group),
  ('printer_by_name', 'printer_name', _printer),
)


class _SearchEngine:
    """Stand in for the search engine, which finds the matching records."""

    def filter(self, **kwargs):
        """Keep the search, which only looks for the name of the tests."""
        return self

    def models(self, model):
        """Search the records of `model`."""
        self.model = model
        return self

    def values_list(self, *fields, **kwargs):
        """Return the ids of the matching records, as the engine does."""
        return list(self.model.objects.filter(name__startswith=NAME)
                                      .values_list('pk', flat=True))


def _queries(client, url_name, keyword, rows):
    """Return the number of queries of the page, which lists the rows."""
    url = reverse(url_name, kwargs={keyword: NAME})
    with CaptureQueriesContext(connection) as context:
        response = client.get(url)
    assert response.status_code == 200
    page = response.content.decode()
    places = [page.find('%s %d' % (NAME, number))
              for number in range(1, rows + 1)]
    assert -1 not in places
    # the rows are in the order of their names
    assert places == sorted(places)
    return len(context.captured_queries)


@pytest.mark.parametrize('engine', (False, True),
                         ids=('database', 'search_engine'))
@pytest.mark.parametrize(('url_name', 'keyword', 'add'), SEARCHES,
                         ids=('publisher', 'indicia_publisher',
                              'brand_group', 'printer'))
def test_queries_do_not_grow_with_the_rows(client, settings, monkeypatch, db,
                                           engine, url_name, keyword, add):
    """The page with 5 rows runs the queries of the page with 1."""
    settings.USE_ELASTICSEARCH = engine
    monkeypatch.setattr('apps.gcd.views.search.SearchQuerySet',
                        _SearchEngine)
    add(1)
    # the first page also fills the caches of the site
    _queries(client, url_name, keyword, 1)
    one_row = _queries(client, url_name, keyword, 1)
    for number in range(2, 6):
        add(number)

    five_rows = _queries(client, url_name, keyword, 5)

    assert five_rows == one_row
