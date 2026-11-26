# -*- coding: utf-8 -*-
"""Tests of the queries of the name searches of creators and characters.

The name searches of creators, characters, groups and features load the
birth dates, countries, languages and feature types that the rows of a
page show with the search, so its number of queries does not grow with
the number of rows.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import Character, Creator, Feature, Group
from apps.gcd.models.feature import FeatureType
from apps.stddata.models import Country, Date, Language

NAME = 'Query Count Test'


def _country():
    """Return the country of birth of the creators of the tests."""
    return Country.objects.get_or_create(
        id=912, defaults={'code': 'r2', 'name': 'Testland R2'})[0]


def _language():
    """Return the language of the records of the tests."""
    return Language.objects.get_or_create(
        id=912, defaults={'code': 'r2', 'name': 'Testish R2'})[0]


def _feature_type():
    """Return a feature type, whose initial the rows of features show."""
    return FeatureType.objects.get_or_create(
        id=912, defaults={'name': 'Test Type'})[0]


def _creator(number):
    """Add a creator, with a date and country of birth, that matches."""
    name = '%s %d' % (NAME, number)
    return Creator.objects.create(
        gcd_official_name=name, sort_name=name,
        birth_date=Date.objects.create(year='1950'),
        birth_country=_country())


def _character(number):
    """Add a character that matches."""
    name = '%s %d' % (NAME, number)
    return Character.objects.create(name=name, sort_name=name,
                                    language=_language())


def _group(number):
    """Add a group that matches."""
    name = '%s %d' % (NAME, number)
    return Group.objects.create(name=name, sort_name=name,
                                language=_language())


def _feature(number):
    """Add a feature, with its language and type, that matches."""
    name = '%s %d' % (NAME, number)
    return Feature.objects.create(name=name, sort_name=name, genre='',
                                  language=_language(),
                                  feature_type=_feature_type())


# For each search: the name of its url, the keyword of the searched text in
# the url and the function that adds a matching record.
SEARCHES = (
  ('creator_by_name', 'creator_name', _creator),
  ('character_by_name', 'character_name', _character),
  ('group_by_name', 'group_name', _group),
  ('feature_by_name', 'feature_name', _feature),
)


class _SearchEngine:
    """Stand in for the search engine, which finds the matching records."""

    def filter(self, **kwargs):
        """Keep the searched field, where the name of the tests is."""
        self.field = next(iter(kwargs))
        return self

    def models(self, model):
        """Search the records of `model`."""
        self.model = model
        return self

    def values_list(self, *fields, **kwargs):
        """Return the ids of the matching records, as the engine does."""
        return list(self.model.objects
                              .filter(**{self.field + '__startswith': NAME})
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
                         ids=('creator', 'character', 'group', 'feature'))
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
