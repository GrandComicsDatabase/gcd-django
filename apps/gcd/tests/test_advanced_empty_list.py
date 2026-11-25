# -*- coding: utf-8 -*-
"""Tests of the lists of the advanced search when they find nothing."""

import pytest

from apps.gcd.models import Publisher, Series
from apps.stddata.models import Country, Language

FOUND = 'Advanced Empty Test'
NOT_FOUND = 'Zqxwv'
# The line under the table for a visitor.
DOWNLOAD_LINE = 'Login required to download'

# For each target: the search field of a name and the sentence of the
# list with no row.
TARGETS = (
  ('series', 'series', 'No series found.'),
  ('issue', 'series', 'No issues found.'),
  ('publisher', 'pub_name', 'No publishers found.'),
)


@pytest.fixture
def series(db):
    """A series named FOUND."""
    country = Country.objects.get_or_create(
        id=909, defaults={'code': 'q7', 'name': 'Testland C'})[0]
    language = Language.objects.get_or_create(
        id=909, defaults={'code': 'q8', 'name': 'Testish C'})[0]
    publisher = Publisher.objects.create(
        name='%s Publisher' % FOUND, country=country, year_began=1965)
    return Series.objects.create(
        name=FOUND, sort_name=FOUND, year_began=1965, country=country,
        language=language, publisher=publisher,
        is_comics_publication=True, has_gallery=False,
        publication_dates='1965')


def _page(client, target, field, text):
    """Return the result page of an advanced search of `text`."""
    response = client.get('/search/advanced/process/', {
        'target': target, 'method': 'icontains', field: text})
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.parametrize(('target', 'field', 'sentence'), TARGETS,
                         ids=[target[0] for target in TARGETS])
def test_an_empty_list_says_nothing_was_found(client, db, target, field,
                                              sentence):
    """A search that finds nothing: one sentence, no table, no download."""
    page = _page(client, target, field, NOT_FOUND)

    assert sentence in page
    assert 'sortable_heading' not in page
    assert DOWNLOAD_LINE not in page


def test_a_list_with_rows_shows_its_table(client, series):
    """A search that finds a series shows the table and no sentence."""
    page = _page(client, 'series', 'series', FOUND)

    assert 'No series found.' not in page
    assert 'sortable_heading' in page
    assert DOWNLOAD_LINE in page
    assert series.get_absolute_url() in page
