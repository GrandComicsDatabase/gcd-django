# -*- coding: utf-8 -*-
"""Tests of the lists of issues of a creator name for one object."""

import re

import pytest

from apps.gcd.models import (CreditType, Issue, Publisher, Series, Story,
                             StoryCredit, StoryType)
from apps.gcd.models.creator import Creator, CreatorNameDetail
from apps.stddata.models import Country, Date, Language, Script


def _credited_series(name, creator_name):
    """Create a series with one issue, with a sequence by the creator name."""
    country = Country.objects.get_or_create(
        code='zn', defaults={'name': 'Testland N'})[0]
    language = Language.objects.get_or_create(
        code='zn', defaults={'name': 'Testish N'})[0]
    publisher = Publisher.objects.create(
        name='Publisher of %s' % name, country=country, year_began=1950)
    series = Series.objects.create(
        name=name, sort_name=name, year_began=1950, country=country,
        language=language, publisher=publisher, is_comics_publication=True,
        has_gallery=False, publication_dates='1950')
    issue = Issue.objects.create(number='1', series=series, sort_code=0,
                                 publication_date='1950',
                                 key_date='1950-01-00')
    story = Story.objects.create(
        issue=issue, sequence_number=0,
        type=StoryType.objects.get(name='comic story'))
    StoryCredit.objects.create(
        creator=creator_name, story=story,
        credit_type=CreditType.objects.get_or_create(
            id=1, defaults={'name': 'script', 'sort_code': 1})[0])
    return series


@pytest.fixture
def credited_name(db):
    """A creator name credited in the series First and Second."""
    script = Script.objects.get_or_create(
        id=Script.LATIN_PK,
        defaults={'code': 'Latn', 'number': Script.LATIN_PK,
                  'name': 'Latin'})[0]
    creator = Creator.objects.create(
        gcd_official_name='Test Person', sort_name='Test Person',
        birth_date=Date.objects.create(), death_date=Date.objects.create())
    return CreatorNameDetail.objects.create(name='Test Person',
                                            creator=creator, in_script=script)


def _assert_only_first(response, heading):
    """Check the page shows the series First with that heading only."""
    assert response.status_code == 200
    content = response.content.decode()
    assert heading in content
    assert 'First' in content and 'Second' not in content


def test_the_link_of_the_names_of_a_publisher_lists_its_issues(
        client, credited_name):
    """The issue count on the list of names opens the issues there."""
    first = _credited_series('First', credited_name)
    _credited_series('Second', credited_name)
    publisher = Publisher.objects.get(id=first.publisher_id)

    names = client.get('/publisher/%d/creator_names/' % publisher.id)
    link = re.search(r'href="(/publisher/\d+/creator_name/\d+/issues/)"',
                     names.content.decode()).group(1)

    _assert_only_first(client.get(link), 'for publisher %s' % publisher)


def test_the_issues_of_a_name_in_a_series(client, credited_name):
    """The address with a creator name and a series lists those issues."""
    first = _credited_series('First', credited_name)
    _credited_series('Second', credited_name)

    response = client.get('/creator_name/%d/series/%d/issues/'
                          % (credited_name.id, first.id))

    _assert_only_first(response, 'on series %s' % first)
