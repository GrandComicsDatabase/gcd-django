# -*- coding: utf-8 -*-
"""Tests of the lists of the name searches when they find nothing."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.gcd.models import Issue, Publisher, Series, Story, StoryType
from apps.indexer.models import Indexer
from apps.stddata.models import Country, Language, Script

FOUND = 'Empty List Test'
NOT_FOUND = 'Zqxwv'

# For each kind of list: the name of its url, the keyword of the searched
# text in the url, the sentence of the list with no row and the text of the
# row of the story fixture.
LISTS = (
  ('series_by_name', 'series_name', 'No series found.',
   '%s Series' % FOUND),
  ('writer_by_name', 'writer', 'No stories found.', '%s Writer' % FOUND),
)

# The lines under the table: for a signed-in user, then for a visitor.
DOWNLOAD_LINES = ('Download the shown data', 'Login required to download')


@pytest.fixture
def country(db):
    """A country for the publisher, the series and the user."""
    Script.objects.get_or_create(
        id=Script.LATIN_PK,
        defaults={'code': 'Latn', 'number': Script.LATIN_PK,
                  'name': 'Latin'})
    return Country.objects.get_or_create(
        id=908, defaults={'code': 'q5', 'name': 'Testland B'})[0]


@pytest.fixture
def member(country):
    """A signed-in user, who sees the download lines."""
    user = User.objects.create_user('empty_list_member')
    Indexer.objects.create(user=user, country=country)
    return user


@pytest.fixture
def story(country):
    """A story in a series named FOUND, by a writer named FOUND."""
    language = Language.objects.get_or_create(
        id=908, defaults={'code': 'q6', 'name': 'Testish B'})[0]
    publisher = Publisher.objects.create(
        name='Test Publisher', country=country, year_began=1965)
    series = Series.objects.create(
        name='%s Series' % FOUND, sort_name='%s Series' % FOUND,
        year_began=1965, country=country, language=language,
        publisher=publisher, is_comics_publication=True, has_gallery=False,
        publication_dates='1965')
    issue = Issue.objects.create(
        number='1', series=series, sort_code=0,
        publication_date='1965', key_date='1965-01-00')
    story_type = StoryType.objects.get_or_create(
        name='empty-list-sequence', defaults={'sort_code': 99020})[0]
    return Story.objects.create(
        issue=issue, type=story_type, sequence_number=0,
        script='%s Writer' % FOUND)


def _page(client, url_name, keyword, text):
    """Return the page of the list of the given search."""
    url = reverse(url_name, kwargs={keyword: text})
    return client.get(url).content.decode()


@pytest.mark.parametrize('signed_in', (False, True),
                         ids=('visitor', 'member'))
@pytest.mark.parametrize(('url_name', 'keyword', 'sentence', 'row'), LISTS,
                         ids=('series', 'writer'))
def test_an_empty_list_says_nothing_was_found(client, settings, member,
                                              url_name, keyword, sentence,
                                              row, signed_in):
    """A search that finds nothing: one sentence, no table, no download."""
    settings.USE_ELASTICSEARCH = False
    if signed_in:
        client.force_login(member)

    page = _page(client, url_name, keyword, NOT_FOUND)

    assert sentence in page
    assert 'sortable_heading' not in page
    for line in DOWNLOAD_LINES:
        assert line not in page


@pytest.mark.parametrize(('url_name', 'keyword', 'sentence', 'row'), LISTS,
                         ids=('series', 'writer'))
def test_a_list_with_rows_shows_its_table(client, settings, member, story,
                                          url_name, keyword, sentence, row):
    """A search that finds a row shows the table and the download lines."""
    settings.USE_ELASTICSEARCH = False
    client.force_login(member)

    page = _page(client, url_name, keyword, FOUND)

    assert sentence not in page
    assert 'sortable_heading' in page
    assert row in page
    assert DOWNLOAD_LINES[0] in page
