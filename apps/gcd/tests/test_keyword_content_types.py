# -*- coding: utf-8 -*-
"""Tests of the keyword pages on a database with its own content type ids.

The test database numbers its content types in its own order, unlike the
production database, so these pages must find them by model.
"""

import pytest
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.gcd.models import Issue, Publisher, Series
from apps.gcd.models.series import SeriesTable
from apps.mycomics.models import CollectionItem, Collector, \
                                 ConditionGradeScale
from apps.stddata.models import Country, Language

KEYWORD = 'Keyword Test'


@pytest.fixture
def series(db):
    """A series with the keyword."""
    country = Country.objects.get_or_create(
        code='q7', defaults={'name': 'Testland C'})[0]
    language = Language.objects.get_or_create(
        code='q8', defaults={'name': 'Testish C'})[0]
    publisher = Publisher.objects.create(
        name='Test Publisher', country=country, year_began=1965)
    series = Series.objects.create(
        name='Keyword Test Series', sort_name='Keyword Test Series',
        year_began=1965, country=country, language=language,
        publisher=publisher, is_comics_publication=True, has_gallery=False,
        publication_dates='1965')
    series.keywords.add(KEYWORD)
    return series


@pytest.fixture
def collection(series):
    """A collection of my.comics.org with the keyword."""
    user = User.objects.create_user('keyword_test_collector')
    Collector.objects.create_collector(
        user,
        grade_system=ConditionGradeScale.objects.create(name='Test scale'),
        default_language=series.language)
    collection = user.collector.default_have_collection
    collection.name = 'Keyword Test Collection'
    collection.save()
    collection.keywords.add(KEYWORD)
    return collection


@pytest.fixture
def collection_item(series, collection):
    """An item of the collection with the keyword."""
    issue = Issue.objects.create(
        number='1', series=series, sort_code=0,
        publication_date='1965', key_date='1965-01-00')
    item = CollectionItem.objects.create(issue=issue)
    item.collections.add(collection)
    item.keywords.add(KEYWORD)
    return item


def _table(client, url_name, data=None):
    """Return the table on the page of the keyword."""
    response = client.get(reverse(url_name, kwargs={'keyword': KEYWORD}),
                          data)
    assert response.status_code == 200
    return response.context['table']


def test_keyword_list_counts_only_the_catalog(client, series, collection,
                                              collection_item):
    """The keywords of a collection and of its item are not usages."""
    table = _table(client, 'keyword_by_name')

    assert [(row.record.name, row.record.objects_count)
            for row in table.rows] == [(KEYWORD, 1)]


def test_keyword_page_leaves_out_the_collections(client, series,
                                                 collection,
                                                 collection_item):
    """
    The page of the keyword lists the series, not the collection or its
    item; the item gave an error page.
    """
    table = _table(client, 'show_keyword')

    assert [row.record.content_object for row in table.rows] == [series]


def test_keyword_page_filtered_by_series_shows_the_series(client, series):
    """Choosing the series in the filter of the page gives their table."""
    content_type = ContentType.objects.get_for_model(Series)

    table = _table(client, 'show_keyword', {'content_type': content_type.id})

    assert isinstance(table, SeriesTable)
    assert [row.record for row in table.rows] == [series]
