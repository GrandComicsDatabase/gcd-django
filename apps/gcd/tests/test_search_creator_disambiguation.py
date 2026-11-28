# -*- coding: utf-8 -*-
"""The creator name search shows the disambiguation of each creator."""
import pytest
from django.urls import reverse

from apps.gcd.models.creator import Creator, CreatorNameDetail
from apps.stddata.models import Date, Script

NAME = 'Test Person A'
MARK = 'Do not use - duplicate'


def make_creator(disambiguation=''):
    """Create a creator born in 1915 with NAME as official name."""
    script = Script.objects.get_or_create(
        id=Script.LATIN_PK,
        defaults={'code': 'Latn', 'number': Script.LATIN_PK,
                  'name': 'Latin'})[0]
    creator = Creator.objects.create(
        gcd_official_name=NAME, sort_name=NAME,
        disambiguation=disambiguation,
        birth_date=Date.objects.create(year='1915'),
        death_date=Date.objects.create())
    CreatorNameDetail.objects.create(
        name=NAME, sort_name=NAME, creator=creator,
        is_official_name=True, in_script=script)
    return creator


@pytest.fixture
def twins(db):
    """Two creators alike in name and birth year, one marked."""
    return make_creator(), make_creator(MARK)


def by_name_page(client):
    """Return the text of the Creator Name search for NAME."""
    url = reverse('creator_by_name',
                  kwargs={'creator_name': NAME, 'sort': 'alpha'})
    response = client.get(url)
    assert response.status_code == 200
    return response.content.decode()


def test_search_results_show_the_disambiguation(client, twins):
    plain, marked = twins

    page = by_name_page(client)

    assert '<a href="%s">%s (b. 1915)</a>' % (
        plain.get_absolute_url(), NAME) in page
    assert '<a href="%s">%s [%s] (b. 1915)</a>' % (
        marked.get_absolute_url(), NAME, MARK) in page


def test_inline_creator_search_shows_the_disambiguation(client, twins):
    marked = twins[1]

    response = client.post(reverse('creator_search_hx'), {'search': NAME})

    assert response.status_code == 200
    assert '<a href="%s">%s [%s] (b. 1915)</a>' % (
        marked.get_absolute_url(), NAME, MARK) in response.content.decode()


def test_the_disambiguation_is_escaped(client, db):
    make_creator('<b>marked</b>')

    page = by_name_page(client)

    assert '[&lt;b&gt;marked&lt;/b&gt;]' in page
    assert '<b>marked</b>' not in page
