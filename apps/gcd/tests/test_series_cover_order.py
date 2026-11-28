# -*- coding: utf-8 -*-
"""Tests of the order of the lists of series by their covers."""

import pytest

from apps.gcd.models import Cover, Issue, Publisher, Series
from apps.gcd.models.series import SeriesTable
from apps.stddata.models import Country, Language


@pytest.fixture
def publisher(db):
    """A publisher for the series of the tests."""
    country = Country.objects.get_or_create(
        id=911, defaults={'code': 'q5', 'name': 'Testland E'})[0]
    return Publisher.objects.create(
        name='Test Publisher', country=country, year_began=1990)


def _series(publisher, name, *issues):
    """
    A series with one issue per entry of `issues`.

    Each entry is the price of the issue and the states of its covers,
    'active' or 'deleted'.
    """
    language = Language.objects.get_or_create(
        id=911, defaults={'code': 'q6', 'name': 'Testish E'})[0]
    series = Series.objects.create(
        name=name, sort_name=name, year_began=1990,
        country=publisher.country, language=language, publisher=publisher,
        is_comics_publication=True, has_gallery=True, is_current=True,
        issue_count=len(issues), publication_dates='1990')
    created = []
    for number, (price, covers) in enumerate(issues, 1):
        issue = Issue.objects.create(
            number=str(number), series=series, sort_code=number,
            price=price, publication_date='1990', key_date='1990-01-00')
        for state in covers:
            Cover.objects.create(issue=issue, deleted=state == 'deleted')
        created.append(issue)
    Series.objects.filter(pk=series.pk).update(first_issue=created[0],
                                               last_issue=created[-1])
    return series


def _order(client, url, params):
    """Return the series of the list at `url`, in the order shown."""
    response = client.get(url, params)
    assert response.status_code == 200
    table = response.context['table']
    return [row.record for row in table.paginated_rows]


@pytest.mark.parametrize('url', ['/publisher/%d/',
                                 '/publisher/%d/current_series/'])
def test_series_are_ordered_by_their_covers(client, publisher, url):
    """Deleted covers do not count; equal counts follow the name."""
    one = _series(publisher, 'One Cover',
                  ('', ['active']), ('', ['deleted', 'deleted']))
    none = _series(publisher, 'No Cover', ('', ['deleted']))
    three = _series(publisher, 'Three Covers',
                    ('', ['active', 'active']), ('', ['active']))
    also_one = _series(publisher, 'Also One Cover', ('', ['active']))
    url = url % publisher.id

    assert _order(client, url, {'sort': '-covers'}) == [
      three, also_one, one, none]
    assert _order(client, url, {'sort': 'covers'}) == [
      none, also_one, one, three]


def test_the_covers_order_has_no_group_by(publisher):
    """The cover count of the order does not group the series rows."""
    _series(publisher, 'One Cover', ('', ['active']))
    series = Series.objects.filter(publisher=publisher)

    ordered, done = SeriesTable(series).order_covers(series, True)

    assert done is True
    assert ordered.query.group_by is None


def test_search_with_issue_terms_orders_by_all_covers(client, publisher):
    """
    The order follows the Covers column, which counts all the covers
    of a series, also those of the issues the search did not find.
    """
    found_one = _series(publisher, 'Found One Of Three',
                        ('1.00 USD', ['active']),
                        ('2.00 USD', ['active', 'active']))
    found_two = _series(publisher, 'Found Two Of Two',
                        ('1.00 USD', ['active', 'active']),
                        ('2.00 USD', ['deleted', 'deleted']))
    _series(publisher, 'Not Found', ('2.00 USD', ['active'] * 4))

    shown = _order(client, '/search/advanced/process/', {
      'target': 'series', 'method': 'icontains', 'price': '1.00',
      'sort': '-covers'})

    assert shown == [found_one, found_two]
    assert [series.scan_count for series in shown] == [3, 2]
