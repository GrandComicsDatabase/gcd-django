# -*- coding: utf-8 -*-
"""Tests of the tables of the detail pages when they have no rows."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.gcd.models import (Brand, BrandGroup, BrandUse, IndiciaPublisher,
                             Issue, Publisher, Series)
from apps.indexer.models import Indexer
from apps.stddata.models import Country, Language

# For each detail page: the name of its url, the keyword of the object in
# the url and the sentence of its list with no row.
PAGES = (
  ('show_publisher', 'publisher_id', 'No series found.'),
  ('show_indicia_publisher', 'indicia_publisher_id', 'No issues found.'),
  ('show_brand_group', 'brand_group_id', 'No issues found.'),
  ('show_brand', 'brand_id', 'No issues found.'),
  ('show_brand_use', 'brand_use_id', 'No issues found.'),
  ('series_details', 'series_id', 'No issues found.'),
)
PAGE_IDS = [page[0] for page in PAGES]

# The lines under the table: for a signed-in user, then for a visitor.
DOWNLOAD_LINES = ('Download the shown data', 'Login required to download')

# The heading of the emblems of a brand group.
EMBLEMS_HEADING = "Publisher's Brand Emblems:"


@pytest.fixture
def country(db):
    """A country for the publishers and the user."""
    return Country.objects.get_or_create(
        id=910, defaults={'code': 'q9', 'name': 'Testland D'})[0]


@pytest.fixture
def member(country):
    """A signed-in user, who sees the download lines."""
    user = User.objects.create_user('detail_empty_member')
    Indexer.objects.create(user=user, country=country)
    return user


def _publisher(name, country):
    """Return a new publisher named `name`."""
    return Publisher.objects.create(name=name, country=country,
                                    year_began=1965)


def _series(name, publisher):
    """Return a new series named `name` of `publisher`."""
    language = Language.objects.get_or_create(
        id=910, defaults={'code': 'q0', 'name': 'Testish D'})[0]
    return Series.objects.create(
        name=name, sort_name=name, year_began=1965,
        country=publisher.country, language=language, publisher=publisher,
        is_comics_publication=True, has_gallery=False,
        publication_dates='1965')


def _children(publisher, name):
    """Return an indicia publisher, a brand group and an emblem in use."""
    indicia_publisher = IndiciaPublisher.objects.create(
        name='%s Indicia' % name, parent=publisher,
        country=publisher.country, year_began=1965)
    group = BrandGroup.objects.create(name='%s Group' % name,
                                      parent=publisher, year_began=1965)
    brand = Brand.objects.create(name='%s Emblem' % name, year_began=1965)
    use = BrandUse.objects.create(publisher=publisher, emblem=brand,
                                  year_began=1965)
    return indicia_publisher, group, brand, use


@pytest.fixture
def empty(country):
    """For each page, an object with no row in its list."""
    publisher = _publisher('Detail Empty Publisher', country)
    series = _series('Detail Empty Series', publisher)
    indicia_publisher, group, brand, use = _children(publisher,
                                                     'Detail Empty')
    return {
      'show_publisher': _publisher('Detail Empty Lone Publisher', country),
      'show_indicia_publisher': indicia_publisher,
      'show_brand_group': group,
      'show_brand': brand,
      'show_brand_use': use,
      'series_details': series,
    }


@pytest.fixture
def filled(country):
    """For each page, an object and the url of the one row of its list."""
    publisher = _publisher('Detail Filled Publisher', country)
    series = _series('Detail Filled Series', publisher)
    indicia_publisher, group, brand, use = _children(publisher,
                                                     'Detail Filled')
    brand.group.add(group)
    issue = Issue.objects.create(
        number='1', series=series, sort_code=0, publication_date='1965',
        key_date='1965-01-00', indicia_publisher=indicia_publisher)
    issue.brand_emblem.add(brand)
    row = issue.get_absolute_url()
    return {
      'show_publisher': (publisher, series.get_absolute_url()),
      'show_indicia_publisher': (indicia_publisher, row),
      'show_brand_group': (group, row),
      'show_brand': (brand, row),
      'show_brand_use': (use, row),
      'series_details': (series, row),
    }


def _page(client, url_name, keyword, item):
    """Return the detail page of `item`."""
    response = client.get(reverse(url_name, kwargs={keyword: item.id}))
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.parametrize('signed_in', (False, True),
                         ids=('visitor', 'member'))
@pytest.mark.parametrize(('url_name', 'keyword', 'sentence'), PAGES,
                         ids=PAGE_IDS)
def test_an_empty_list_says_nothing_was_found(client, member, empty,
                                              url_name, keyword, sentence,
                                              signed_in):
    """A page with no row: one sentence, no table, no download line."""
    if signed_in:
        client.force_login(member)

    page = _page(client, url_name, keyword, empty[url_name])

    assert sentence in page
    assert 'sortable_heading' not in page
    for line in DOWNLOAD_LINES:
        assert line not in page


@pytest.mark.parametrize(('url_name', 'keyword', 'sentence'), PAGES,
                         ids=PAGE_IDS)
def test_a_list_with_rows_shows_its_table(client, member, filled, url_name,
                                          keyword, sentence):
    """A page with a row shows the table and the download lines."""
    client.force_login(member)
    item, row = filled[url_name]

    page = _page(client, url_name, keyword, item)

    assert sentence not in page
    assert 'sortable_heading' in page
    assert row in page
    assert DOWNLOAD_LINES[0] in page


def test_a_brand_group_without_emblems_has_no_emblem_list(client, empty):
    """A brand group with no emblem shows no heading of its emblems."""
    page = _page(client, 'show_brand_group', 'brand_group_id',
                 empty['show_brand_group'])

    assert EMBLEMS_HEADING not in page


def test_a_brand_group_with_an_emblem_lists_it(client, filled):
    """A brand group with an emblem shows the heading and the emblem."""
    group = filled['show_brand_group'][0]
    emblem = group.active_emblems().get()

    page = _page(client, 'show_brand_group', 'brand_group_id', group)

    assert EMBLEMS_HEADING in page
    assert emblem.get_absolute_url() in page
