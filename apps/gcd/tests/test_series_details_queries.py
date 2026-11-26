# -*- coding: utf-8 -*-
"""Tests of the queries of the details and the timeline of a series.

Both pages load the indicia publishers and the brand emblems that their
rows show with the issues, so their number of queries does not grow with
the number of issues.
"""

import pytest
from django.db import connection, reset_queries
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import Brand, IndiciaPublisher, Issue, Publisher, Series
from apps.stddata.models import Country, Language

PAGES = ('series_details', 'series_timeline')
KINDS = ('Dated', 'Undated')


@pytest.fixture
def series(db):
    """Return a new series with no issue."""
    country = Country.objects.get_or_create(
        id=912, defaults={'code': 'r2', 'name': 'Testland S'})[0]
    language = Language.objects.get_or_create(
        id=912, defaults={'code': 'r2', 'name': 'Testish S'})[0]
    publisher = Publisher.objects.create(name='Test Publisher',
                                         country=country, year_began=1965)
    return Series.objects.create(
        name='Test Series', sort_name='Test Series', year_began=1965,
        country=country, language=language, publisher=publisher,
        is_comics_publication=True, has_gallery=False,
        publication_dates='1965')


def _add(series, number, emblems):
    """Add an issue with a key date and one without, as row `number`.

    The first has its place in the timeline, the second is listed after
    the issues with a key date. Each has its own indicia publisher and,
    with `emblems`, its own brand emblem.
    """
    for kind in KINDS:
        name = '%s %d' % (kind, number)
        indicia_publisher = IndiciaPublisher.objects.create(
            name='%s Indicia' % name, parent=series.publisher,
            country=series.country, year_began=1965)
        dated = kind == 'Dated'
        issue = Issue.objects.create(
            number=name, series=series,
            sort_code=number if dated else 100 + number,
            key_date='1965-%02d-00' % number if dated else '',
            publication_date='1965', indicia_publisher=indicia_publisher)
        if emblems:
            issue.brand_emblem.add(Brand.objects.create(
                name='%s Emblem' % name, year_began=1965))


def _queries(client, url_name, series, rows, emblems):
    """Return the number of queries of the page, which lists the rows."""
    url = reverse(url_name, kwargs={'series_id': series.id})
    # the log holds a limited number of queries: start it empty
    reset_queries()
    with CaptureQueriesContext(connection) as context:
        response = client.get(url)
    assert response.status_code == 200
    page = response.content.decode()
    names = ['%s %d' % (kind, number)
             for kind in KINDS for number in range(1, rows + 1)]
    places = [page.find('%s Indicia' % name) for name in names]
    assert -1 not in places
    # the issues with a key date in its order, then the others
    assert places == sorted(places)
    for name in names:
        assert ('%s Emblem' % name in page) == emblems
    return len(context.captured_queries)


@pytest.mark.parametrize('emblems', (True, False),
                         ids=('with_emblems', 'without_emblems'))
@pytest.mark.parametrize('url_name', PAGES)
def test_queries_do_not_grow_with_the_issues(client, series, url_name,
                                             emblems):
    """The page with 5 rows of issues runs the queries of the page with 1."""
    _add(series, 1, emblems)
    # the first page also fills the caches of the site
    _queries(client, url_name, series, 1, emblems)
    one_row = _queries(client, url_name, series, 1, emblems)
    for number in range(2, 6):
        _add(series, number, emblems)

    five_rows = _queries(client, url_name, series, 5, emblems)

    assert five_rows == one_row
