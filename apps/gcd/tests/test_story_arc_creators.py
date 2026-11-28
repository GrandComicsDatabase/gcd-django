# -*- coding: utf-8 -*-
"""Tests of the list of the creators of a story arc."""

import re
from types import SimpleNamespace

import pytest
from django.urls import reverse

from apps.gcd.models import (CreditType, Issue, Publisher, Series, Story,
                             StoryArc, StoryCredit, StoryType)
from apps.gcd.models.creator import Creator, CreatorNameDetail
from apps.gcd.models.story import CREDIT_TYPES, STORY_TYPES
from apps.stddata.models import Country, Date, Language, Script


def _story(issue, story_arc=None):
    """Return a new comic story of `issue`, in `story_arc` if given."""
    story_type = StoryType.objects.get_or_create(
        id=STORY_TYPES['comic story'],
        defaults={'name': 'arc-creators-story', 'sort_code': 99070})[0]
    story = Story.objects.create(issue=issue, type=story_type,
                                 sequence_number=0)
    if story_arc:
        story.story_arc.add(story_arc)
    return story


def _creator(name, credits):
    """
    Return a new creator called `name`, with a credit of each pair of
    `credits`: a story and a credit type, or a story, a type and True for
    a deleted credit.
    """
    creator = Creator.objects.create(gcd_official_name=name, sort_name=name,
                                     birth_date=Date.objects.create())
    creator_name = CreatorNameDetail.objects.create(
        name=name, creator=creator, is_official_name=True)
    for story, credit_type, *deleted in credits:
        StoryCredit.objects.create(
            creator=creator_name, story=story, deleted=bool(deleted),
            credit_type=CreditType.objects.get_or_create(
                id=CREDIT_TYPES[credit_type],
                defaults={'name': credit_type,
                          'sort_code': CREDIT_TYPES[credit_type]})[0])
    return creator


@pytest.fixture
def arc(db):
    """
    A story arc in the first of two issues. The writer has a script
    credit in both issues; the others have no shown credit in the arc.
    """
    Script.objects.get_or_create(
        id=Script.LATIN_PK,
        defaults={'code': 'Latn', 'number': Script.LATIN_PK,
                  'name': 'Latin'})
    country = Country.objects.get_or_create(
        id=912, defaults={'code': 'q1', 'name': 'Testland E'})[0]
    language = Language.objects.get_or_create(
        id=912, defaults={'code': 'q2', 'name': 'Testish E'})[0]
    publisher = Publisher.objects.create(
        name='Test Publisher', country=country, year_began=1965)
    series = Series.objects.create(
        name='Arc Test Series', sort_name='Arc Test Series',
        year_began=1965, country=country, language=language,
        publisher=publisher, is_comics_publication=True, has_gallery=False,
        publication_dates='1965')
    in_arc, outside = [Issue.objects.create(
        number=str(number), series=series, sort_code=number,
        publication_date='1965', key_date='1965-0%d-00' % number)
        for number in (1, 2)]
    story_arc = StoryArc.objects.create(
        name='Test Arc', sort_name='Test Arc', language=language)
    arc_story, other_story = _story(in_arc, story_arc), _story(outside)
    return SimpleNamespace(
      story_arc=story_arc, in_arc=in_arc, outside=outside,
      writer=_creator('Some Writer', [(arc_story, 'script'),
                                      (other_story, 'script')]),
      others=[_creator('Some Editor', [(arc_story, 'editing')]),
              _creator('Some Inker', [(arc_story, 'inks', True)]),
              _creator('Some Penciller', [(other_story, 'pencils')])])


def _page(client, url):
    """Return the page at `url`."""
    response = client.get(url)
    assert response.status_code == 200
    return response.content.decode()


def test_the_story_arc_page_links_to_its_creator_list(client, arc):
    """The Creator List link of the story arc page opens the list."""
    page = _page(client, arc.story_arc.get_absolute_url())

    links = re.findall(r'<a href="([^"]+)">Creator List</a>', page)

    assert links == [reverse('story_arc_creators',
                             kwargs={'story_arc_id': arc.story_arc.id})]
    assert arc.writer.get_absolute_url() in _page(client, links[0])


def test_the_creator_list_shows_the_shown_credits_in_the_arc(client, arc):
    """
    Only a creator with a script to letters credit in the arc is listed,
    with the issue count leading to the issues in the arc.
    """
    page = _page(client, reverse('story_arc_creators',
                                 kwargs={'story_arc_id': arc.story_arc.id}))

    count = reverse('story_arc_creator_issues',
                    kwargs={'story_arc_id': arc.story_arc.id,
                            'creator_id': arc.writer.id})
    assert '<a href="%s">1</a>' % count in page
    assert 'script (1)' in page
    for creator in arc.others:
        assert creator.get_absolute_url() not in page


def test_the_issue_count_opens_the_issues_in_the_arc(client, arc):
    """The issues of the count are those of the creator in the arc."""
    page = _page(client, reverse('story_arc_creator_issues',
                                 kwargs={'story_arc_id': arc.story_arc.id,
                                         'creator_id': arc.writer.id}))

    assert 'for creator Some Writer on story arc Test Arc' in page
    assert arc.in_arc.get_absolute_url() in page
    assert arc.outside.get_absolute_url() not in page
