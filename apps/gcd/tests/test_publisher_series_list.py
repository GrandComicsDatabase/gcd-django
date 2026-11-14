# -*- coding: utf-8 -*-
"""The series lists of a publisher show country and language of each series."""
import csv
import io
import json
import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.gcd.models import Publisher, Series
from apps.gcd.templatetags.credits import get_country_flag
from apps.stddata.models import Country, Language

PAGES = ['', 'current_series/']
COLUMNS = 7

# Name, year, country, language. Created in this order, so that the database
# ids of the series, the countries and the languages follow no sorted order.
SERIES = [('D', 2000, 'Aaland', 'Bbish'), ('C', 1990, 'Zzland', 'Yyish'),
          ('C', 1985, 'Zzland', 'Yyish'), ('B', 2005, 'Aaland', 'Yyish'),
          ('A', 1980, 'Zzland', 'Bbish')]
SHOWN = {('%s %s' % (name, year), country, language)
         for name, year, country, language in SERIES}


def add_series(publisher, name, year, country, language):
    """Create a current series of the publisher."""
    return Series.objects.create(
        name=name, sort_name=name, year_began=year, publisher=publisher,
        country=country, language=language, is_current=True,
        is_comics_publication=True, has_gallery=False,
        publication_dates=str(year))


@pytest.fixture
def publisher(db):
    """A publisher with the series of SERIES, in that order."""
    countries = {name: Country.objects.create(code='zq%d' % i, name=name)
                 for i, name in enumerate(['Zzland', 'Aaland'])}
    languages = {name: Language.objects.create(code='zq%d' % i, name=name)
                 for i, name in enumerate(['Yyish', 'Bbish'])}
    publisher = Publisher.objects.create(
        name='Test Publisher', country=countries['Zzland'], year_began=1960)
    for name, year, country, language in SERIES:
        add_series(publisher, name, year, countries[country],
                   languages[language])
    return publisher


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


@pytest.mark.parametrize('page', PAGES)
def test_each_series_shows_its_country_and_language(client, publisher, page):
    """Each row has the flag of its country and the name of its language."""
    response = client.get(publisher.get_absolute_url() + page)

    assert 'Country' in table_head(response)
    assert 'Language' in table_head(response)
    rows = table_rows(response)
    assert [len(row) for row in rows] == [COLUMNS] * len(SERIES)
    flags = {name: str(get_country_flag(Country.objects.get(name=name)))
             for name in ('Aaland', 'Zzland')}
    assert {(row_series(row), row[2].strip(), row[3].strip())
            for row in rows} == {(series, flags[country], language)
                                 for series, country, language in SHOWN}


@pytest.mark.parametrize('page', PAGES)
@pytest.mark.parametrize('column, ascending, descending', [
    ('country',
     ['B 2005', 'D 2000', 'A 1980', 'C 1985', 'C 1990'],
     ['A 1980', 'C 1985', 'C 1990', 'B 2005', 'D 2000']),
    ('language',
     ['A 1980', 'D 2000', 'B 2005', 'C 1985', 'C 1990'],
     ['B 2005', 'C 1985', 'C 1990', 'A 1980', 'D 2000']),
])
def test_headings_sort_by_name_then_series_and_year(client, publisher, page,
                                                    column, ascending,
                                                    descending):
    """Clicking a new heading sorts by the name shown; ties by series, year."""
    url = publisher.get_absolute_url() + page
    first_click = click_heading(client, url, client.get(url), column)
    assert series_order(first_click) == ascending

    second_click = click_heading(client, url, first_click, column)
    assert series_order(second_click) == descending


@pytest.mark.parametrize('page', PAGES)
@pytest.mark.parametrize('export', ['csv', 'json'])
def test_download_has_the_names_not_the_flag(client, publisher, page, export):
    """The download of the list gives plain names for the new columns."""
    body = client.get(publisher.get_absolute_url() + page,
                      {'_export': export}).content.decode()

    rows = (json.loads(body) if export == 'json'
            else list(csv.DictReader(io.StringIO(body))))
    assert '<img' not in body
    assert {('%s %s' % (row.get('Series'), row.get('Year')),
             row.get('Country'), row.get('Language'))
            for row in rows} == SHOWN


def country_language_queries(client, url):
    """Return a page and its queries that read only country or language."""
    with CaptureQueriesContext(connection) as context:
        response = client.get(url)
    return response, [query['sql'] for query in context.captured_queries
                      if re.search(r'FROM .stddata_(country|language)\b.',
                                   query['sql'])]


@pytest.mark.parametrize('page', PAGES)
def test_new_columns_need_no_query_per_series(client, publisher, page):
    """Country and language come with the series, not one query per row."""
    url = publisher.get_absolute_url() + page
    client.get(url)
    _, before = country_language_queries(client, url)

    for number in range(5):
        add_series(publisher, 'E%d' % number, 1970 + number,
                   Country.objects.get(name='Aaland'),
                   Language.objects.get(name='Yyish'))
    response, after = country_language_queries(client, url)

    rows = table_rows(response)
    assert [len(row) for row in rows] == [COLUMNS] * (len(SERIES) + 5)
    assert len(after) == len(before), after


def test_only_the_publisher_lists_gain_the_columns(client, publisher):
    """Another page that lists series keeps the columns it had."""
    publisher_head = table_head(client.get(publisher.get_absolute_url()))
    assert 'Country' in publisher_head and 'Language' in publisher_head

    publisher.active_series().first().keywords.add('kw')
    keyword_head = table_head(client.get('/keyword/kw/series/'))
    assert 'Series' in keyword_head
    assert 'Country' not in keyword_head and 'Language' not in keyword_head
