# -*- coding: utf-8 -*-
"""The series lists of a publisher show the language when it varies."""
import csv
import io
import json
import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.gcd.models import Publisher, Series
from apps.stddata.models import Country, Language

PAGES = ['', 'current_series/']
COLUMNS = 6

# The publisher with series in two languages and two countries: name, year,
# country, language. Created in this order, so that the database ids of the
# series, the countries and the languages follow no sorted order.
SERIES = [('D', 2000, 'Aaland', 'Bbish'), ('C', 1990, 'Zzland', 'Yyish'),
          ('C', 1985, 'Zzland', 'Yyish'), ('B', 2005, 'Aaland', 'Yyish'),
          ('A', 1980, 'Zzland', 'Bbish')]
SHOWN = {('%s %s' % (name, year), language)
         for name, year, country, language in SERIES}

# The publisher with series in one language: three names, two countries.
ONE_LANGUAGE_SERIES = [('F', 1995, 'Zzland', 'Yyish'),
                       ('G', 1975, 'Aaland', 'Yyish'),
                       ('E', 2010, 'Zzland', 'Yyish')]
ONE_LANGUAGE_ORDER = ['E 2010', 'F 1995', 'G 1975']


def add_series(publisher, name, year, country, language, **fields):
    """Create a series of the publisher, current unless fields say so."""
    values = dict(name=name, sort_name=name, year_began=year,
                  publisher=publisher,
                  country=Country.objects.get(name=country),
                  language=Language.objects.get(name=language),
                  is_current=True, is_comics_publication=True,
                  has_gallery=False, publication_dates=str(year))
    values.update(fields)
    return Series.objects.create(**values)


def add_publisher(name, series):
    """Create a publisher of Zzland with the given series, in that order."""
    publisher = Publisher.objects.create(
        name=name, country=Country.objects.get(name='Zzland'),
        year_began=1960)
    for series_name, year, country, language in series:
        add_series(publisher, series_name, year, country, language)
    return publisher


@pytest.fixture
def places(db):
    """The made-up countries and languages of the series."""
    for number, name in enumerate(['Zzland', 'Aaland']):
        Country.objects.create(code='zq%d' % number, name=name)
    for number, name in enumerate(['Yyish', 'Bbish']):
        Language.objects.create(code='zq%d' % number, name=name)


@pytest.fixture
def publisher(places):
    """A publisher with the series of SERIES, in two languages."""
    return add_publisher('Test Publisher', SERIES)


@pytest.fixture
def one_language_publisher(places):
    """A publisher with the series of ONE_LANGUAGE_SERIES, in one language."""
    return add_publisher('Other Test Publisher', ONE_LANGUAGE_SERIES)


def table_head(response):
    """Return the rendered heading of the series table."""
    page = response.content.decode()
    return page.split('<thead', 1)[1].split('</thead>', 1)[0]


def table_rows(response):
    """Return the rendered cells of each row of the series table."""
    page = response.content.decode()
    body = page.split('<tbody class="sortable_listing', 1)[1]
    body = body.split('</tbody>', 1)[0]
    return [re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
            for row in re.findall(r'<tr>(.*?)</tr>', body, re.S)]


def row_series(row):
    """Return the name and the year shown in a row of the series table."""
    return '%s %s' % (re.sub('<[^>]+>', '', row[0]).strip(), row[1].strip())


def series_order(response):
    """Return the series of the table in the order of the page."""
    return [row_series(row) for row in table_rows(response)]


def click_heading(client, url, response, column):
    """Follow the sorting link that the page has on the heading of a column."""
    link = re.search(r'href="([^"]*sort=-?%s\b[^"]*)"' % column,
                     table_head(response))
    assert link, 'the %s heading has no sorting link' % column
    return client.get(url + link.group(1))


def download(client, url, export):
    """Return the rows of the download of a list, as dictionaries."""
    body = client.get(url, {'_export': export}).content.decode()
    return (json.loads(body) if export == 'json'
            else list(csv.DictReader(io.StringIO(body))))


def language_queries(client, url):
    """Return a page, its queries on the languages and its language checks."""
    with CaptureQueriesContext(connection) as context:
        response = client.get(url)
    queries = [query['sql'] for query in context.captured_queries]
    return (response,
            [sql for sql in queries if 'stddata_language' in sql],
            [sql for sql in queries
             if re.match(r'SELECT DISTINCT \S*language_id\S* (AS \S+ )?FROM',
                         sql)])


@pytest.mark.parametrize('page', PAGES)
def test_several_languages_show_the_language_of_each_series(client, publisher,
                                                            page):
    """With series in two languages each row shows the name of its own."""
    response = client.get(publisher.get_absolute_url() + page)

    assert 'Language' in table_head(response)
    assert 'Country' not in table_head(response)
    rows = table_rows(response)
    assert [len(row) for row in rows] == [COLUMNS] * len(SERIES)
    assert {(row_series(row), row[2].strip()) for row in rows} == SHOWN


@pytest.mark.parametrize('page', PAGES)
def test_one_language_keeps_the_list_as_it_was(client, one_language_publisher,
                                               page):
    """With series in one language the list has no new column, nor query."""
    with CaptureQueriesContext(connection) as context:
        response = client.get(one_language_publisher.get_absolute_url() +
                              page)

    assert 'Language' not in table_head(response)
    assert 'Country' not in table_head(response)
    rows = table_rows(response)
    assert [len(row) for row in rows] == [COLUMNS - 1] * 3
    assert series_order(response) == ONE_LANGUAGE_ORDER
    assert [query['sql'] for query in context.captured_queries
            if 'stddata_language' in query['sql']] == []


@pytest.mark.parametrize('page', PAGES)
def test_language_heading_sorts_by_name_then_series_and_year(client,
                                                             publisher, page):
    """Clicking Language sorts by the name shown; ties by series and year."""
    url = publisher.get_absolute_url() + page
    first_click = click_heading(client, url, client.get(url), 'language')
    assert series_order(first_click) == ['A 1980', 'D 2000', 'B 2005',
                                         'C 1985', 'C 1990']

    second_click = click_heading(client, url, first_click, 'language')
    assert series_order(second_click) == ['B 2005', 'C 1985', 'C 1990',
                                          'A 1980', 'D 2000']


@pytest.mark.parametrize('page', PAGES)
@pytest.mark.parametrize('export', ['csv', 'json'])
def test_download_has_the_language_when_the_page_has_it(
        client, publisher, one_language_publisher, page, export):
    """The download has the language by name only when the page shows it."""
    rows = download(client, publisher.get_absolute_url() + page, export)
    assert {('%s %s' % (row.get('Series'), row.get('Year')),
             row.get('Language')) for row in rows} == SHOWN
    assert [row for row in rows if 'Country' in row] == []

    rows = download(client, one_language_publisher.get_absolute_url() + page,
                    export)
    assert len(rows) == 3
    assert [row for row in rows
            if 'Language' in row or 'Country' in row] == []


@pytest.mark.parametrize('page', PAGES)
def test_deleted_series_does_not_count(client, one_language_publisher, page):
    """A deleted series in a second language does not bring the column."""
    add_series(one_language_publisher, 'H', 2001, 'Zzland', 'Bbish',
               deleted=True)

    response = client.get(one_language_publisher.get_absolute_url() + page)
    assert 'Language' not in table_head(response)
    assert series_order(response) == ONE_LANGUAGE_ORDER


def test_current_series_list_looks_at_current_series_only(
        client, one_language_publisher):
    """A series no longer current brings the column to the full list only."""
    add_series(one_language_publisher, 'H', 2001, 'Zzland', 'Bbish',
               is_current=False)
    url = one_language_publisher.get_absolute_url()

    assert 'Language' in table_head(client.get(url))
    assert 'Language' not in table_head(client.get(url + 'current_series/'))


@pytest.mark.parametrize('page', PAGES)
def test_sorting_by_a_language_not_shown_is_ignored(client,
                                                    one_language_publisher,
                                                    page):
    """A sort on the language of a one-language list gives the plain list."""
    response = client.get(one_language_publisher.get_absolute_url() + page,
                          {'sort': 'language'})

    assert response.status_code == 200
    assert 'Language' not in table_head(response)
    assert series_order(response) == ONE_LANGUAGE_ORDER


@pytest.mark.parametrize('page', PAGES)
def test_language_needs_no_query_per_series(client, publisher, page):
    """The language comes with the series; the check runs once a page."""
    url = publisher.get_absolute_url() + page
    client.get(url)
    _, before, checks = language_queries(client, url)
    assert len(checks) == 1, checks

    for number in range(5):
        add_series(publisher, 'E%d' % number, 1970 + number, 'Aaland',
                   'Yyish')
    response, after, checks = language_queries(client, url)

    rows = table_rows(response)
    assert [len(row) for row in rows] == [COLUMNS] * (len(SERIES) + 5)
    assert len(after) == len(before), after
    assert len(checks) == 1, checks


def test_only_the_publisher_lists_gain_the_column(client, publisher):
    """Another page that lists series keeps the columns it had."""
    assert 'Language' in table_head(client.get(publisher.get_absolute_url()))

    for series in publisher.active_series():
        series.keywords.add('kw')
    keyword_head = table_head(client.get('/keyword/kw/series/'))
    assert 'Series' in keyword_head
    assert 'Language' not in keyword_head
    assert 'Country' not in keyword_head
