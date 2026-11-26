# -*- coding: utf-8 -*-
"""Tests of the queries of the advanced search of brands and publishers.

A page of results loads the countries, the parent publishers and the
emblem images that its rows show with the search, so its number of
queries does not grow with the number of rows.
"""

import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext

from apps.gcd.models import Brand, BrandGroup, IndiciaPublisher, Publisher
from apps.gcd.models.image import Image
from apps.gcd.views.search import do_advanced_search
from apps.indexer.models import Indexer
from apps.mycomics.models import Collector
from apps.stddata.models import Country, Language

NAME = 'Query Count Test'
# The type of the images of brand emblems.
EMBLEM_TYPE = 3


def _country():
    """Return the country of the records of the tests."""
    return Country.objects.get_or_create(
        id=914, defaults={'code': 'r4', 'name': 'Testland T'})[0]


def _parent(number):
    """Return a new publisher that does not match, a parent of a match."""
    return Publisher.objects.create(name='Some Publisher %d' % number,
                                    country=_country(), year_began=1960)


def _image(brand, **kwargs):
    """Add an image without a file to `brand`, by default its emblem."""
    return Image.objects.create(
        content_type=ContentType.objects.get_for_model(Brand),
        object_id=brand.id, type_id=kwargs.pop('type_id', EMBLEM_TYPE),
        **kwargs)


def _indicia_publisher(number):
    """Add an indicia publisher, with its own parent, that matches."""
    return IndiciaPublisher.objects.create(
        name='%s %d' % (NAME, number), parent=_parent(number),
        country=_country(), year_began=1960 + number)


def _brand_group(number):
    """Add a brand group, with its own parent, that matches."""
    return BrandGroup.objects.create(
        name='%s %d' % (NAME, number), parent=_parent(number),
        year_began=1960 + number)


def _brand_emblem(number):
    """Add an emblem with its image and a group with its own parent."""
    emblem = Brand.objects.create(name='%s %d' % (NAME, number),
                                  year_began=1960 + number)
    emblem.group.add(BrandGroup.objects.create(
        name='Some Group %d' % number, parent=_parent(number),
        year_began=1960))
    _image(emblem)
    return emblem


# For each target: the search field of its name and the function that
# adds a matching record.
TARGETS = (
  ('indicia_publisher', 'indicia_publisher', _indicia_publisher),
  ('brand_group', 'brand_group', _brand_group),
  ('brand_emblem', 'brand_emblem', _brand_emblem),
)


def _member():
    """Return a user with the records of a member of the site."""
    user = User.objects.create_user('advanced_search_member')
    Indexer.objects.create(user=user, country=_country())
    Collector.objects.create(user=user, grade_system_id=1,
                             default_language=Language.objects.get(
                               code='en'))
    return user


def _search(target, field):
    """Return the parameters of the search of the records of the tests."""
    return {'target': target, 'method': 'icontains', field: NAME,
            'order1': 'date'}


def _queries(client, target, field, rows):
    """Return the number of queries of the page, which lists the rows."""
    with CaptureQueriesContext(connection) as context:
        response = client.get('/search/advanced/process/',
                              _search(target, field))
    assert response.status_code == 200
    page = response.content.decode()
    places = [page.find('%s %d' % (NAME, number))
              for number in range(1, rows + 1)]
    assert -1 not in places
    # the rows are in the order of their years
    assert places == sorted(places)
    return len(context.captured_queries)


@pytest.mark.parametrize('member', (False, True),
                         ids=('visitor', 'member'))
@pytest.mark.parametrize(('target', 'field', 'add'), TARGETS,
                         ids=[target[0] for target in TARGETS])
def test_queries_do_not_grow_with_the_rows(client, db, member, target,
                                           field, add):
    """The page with 5 rows runs the queries of the page with 1."""
    if member:
        client.force_login(_member())
    add(1)
    # the first page also fills the caches of the site
    _queries(client, target, field, 1)
    one_row = _queries(client, target, field, 1)
    for number in range(2, 6):
        add(number)

    five_rows = _queries(client, target, field, 5)

    assert five_rows == one_row


def test_an_emblem_has_its_current_image(db):
    """An emblem has its image that is not deleted, in a list and alone."""
    with_image = Brand.objects.create(name='%s 1' % NAME, year_began=1961)
    image = _image(with_image)
    Brand.objects.create(name='%s 2' % NAME, year_began=1962)
    replaced = Brand.objects.create(name='%s 3' % NAME, year_began=1963)
    _image(replaced, deleted=True)
    replacement = _image(replaced)
    _image(Brand.objects.create(name='%s 4' % NAME, year_began=1964),
           type_id=1)
    request = RequestFactory().get('/search/advanced/process/',
                                   _search('brand_emblem', 'brand_emblem'))
    request.user = AnonymousUser()
    expected = [image, None, replacement, None]

    items, _target = do_advanced_search(request)

    assert [emblem.emblem for emblem in items] == expected
    assert [Brand.objects.get(id=emblem.id).emblem
            for emblem in items] == expected
