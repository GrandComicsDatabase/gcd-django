# -*- coding: utf-8 -*-
"""Tests of the queries of the name searches of the data of creators.

A page of results loads the records that its rows show with the search,
so its number of queries does not grow with the number of rows.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models.creator import Creator, CreatorArtInfluence, \
                                    CreatorMembership, CreatorNonComicWork, \
                                    MembershipType, NonComicWorkRole, \
                                    NonComicWorkType
from apps.stddata.models import Date

NAME = 'Query Count Test'


def _creator(name):
    """Return a new creator with a birth date, which the rows show."""
    return Creator.objects.create(
        gcd_official_name=name, sort_name=name,
        birth_date=Date.objects.create(year='1950'))


def _membership(number):
    """Add a membership, with its own creator and type, that matches."""
    return CreatorMembership.objects.create(
        creator=_creator('Some Creator %d' % number),
        organization_name='%s %d' % (NAME, number),
        membership_type=MembershipType.objects.create(
            type='Test Type %d' % number))


def _art_influence(number):
    """Add an influence, with its own creator, linked to a match."""
    return CreatorArtInfluence.objects.create(
        creator=_creator('Some Creator %d' % number),
        influence_link=_creator('%s %d' % (NAME, number)))


def _non_comic_work(number):
    """Add a work, with its own creator, type and role, that matches."""
    return CreatorNonComicWork.objects.create(
        creator=_creator('Some Creator %d' % number),
        publication_title='%s %d' % (NAME, number),
        work_type=NonComicWorkType.objects.create(
            type='Test Type %d' % number),
        work_role=NonComicWorkRole.objects.create(
            role_name='Test Role %d' % number))


# For each search: the name of its url, the keyword of the searched text in
# the url and the function that adds a matching record.
SEARCHES = (
  ('creator_membership_by_name', 'creator_membership_name', _membership),
  ('creator_art_influence_by_name', 'creator_art_influence_name',
   _art_influence),
  ('creator_non_comic_work_by_name', 'creator_non_comic_work_name',
   _non_comic_work),
)


def _queries(client, url_name, keyword, rows):
    """Return the number of queries of the page, which lists the rows."""
    url = reverse(url_name, kwargs={keyword: NAME})
    with CaptureQueriesContext(connection) as context:
        response = client.get(url)
    assert response.status_code == 200
    page = response.content.decode()
    for number in range(1, rows + 1):
        assert '%s %d' % (NAME, number) in page
    return len(context.captured_queries)


@pytest.mark.parametrize(('url_name', 'keyword', 'add'), SEARCHES,
                         ids=('membership', 'art_influence',
                              'non_comic_work'))
def test_queries_do_not_grow_with_the_rows(client, settings, db,
                                           url_name, keyword, add):
    """The page with 5 rows runs the queries of the page with 1."""
    settings.USE_ELASTICSEARCH = False
    add(1)
    # the first page also fills the caches of the site
    _queries(client, url_name, keyword, 1)
    one_row = _queries(client, url_name, keyword, 1)
    for number in range(2, 6):
        add(number)

    five_rows = _queries(client, url_name, keyword, 5)

    assert five_rows == one_row
