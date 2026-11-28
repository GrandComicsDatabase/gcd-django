# -*- coding: utf-8 -*-
"""Tests of the title and the description for link previews."""

import pytest
from django.urls import reverse

from apps.gcd.models import Publisher, Series
from apps.stddata.models import Country, Language


def _series(name='Test Series', **fields):
    """Return a series of Test Publisher, not saved unless asked."""
    country = Country(code='lp', name='Testland')
    data = dict(name=name, sort_name=name, year_began=1999,
                country=country, language=Language(code='lp', name='Testish'),
                publisher=Publisher(name='Test Publisher', country=country),
                is_comics_publication=True, issue_count=293)
    data.update(fields)
    return Series(**data)


@pytest.mark.parametrize(('fields', 'sentence'), (
  ({'is_current': True},
   'Comic series published in Testish (Testland) since 1999; 293 issues.'),
  ({'year_ended': 2005, 'year_ended_uncertain': True, 'issue_count': 1},
   'Comic series published in Testish (Testland) from 1999 to 2005 ?;'
   ' 1 issue.'),
  ({'is_comics_publication': False, 'year_began_uncertain': True},
   'Series published in Testish (Testland) from 1999 ?; 293 issues.'),
), ids=('current', 'ended', 'not-comics'))
def test_series_sentence(fields, sentence):
    """The sentence states language, country, years and issues."""
    assert _series(**fields).meta_description() == sentence


@pytest.mark.parametrize(('years', 'sentence'), (
  ({'year_began': 1985}, 'Comics publisher (Testland) from 1985.'),
  ({'year_began': 1985, 'year_ended': 2005, 'year_ended_uncertain': True},
   'Comics publisher (Testland) from 1985 until 2005 ?.'),
  ({}, 'Comics publisher (Testland).'),
), ids=('ongoing', 'ended', 'no-years'))
def test_publisher_sentence(years, sentence):
    """The sentence states the country and the known years."""
    publisher = Publisher(name='Test Publisher',
                          country=Country(code='lp', name='Testland'),
                          **years)

    assert publisher.meta_description() == sentence


@pytest.fixture
def series(db):
    """A saved series whose names need escaping in an attribute."""
    country = Country.objects.create(code='lp964', name='Testland')
    language = Language.objects.create(code='lp964', name='Testish')
    publisher = Publisher.objects.create(name='Smith & "Sons"',
                                         country=country, year_began=1985)
    return Series.objects.create(
        name='Cats & "Dogs"', sort_name='Cats', year_began=1999,
        is_current=True, country=country, language=language,
        publisher=publisher, is_comics_publication=True,
        publication_dates='1999')


def _page(client, url_name, keyword, item):
    """Return the html of the detail page of `item`."""
    response = client.get(reverse(url_name, kwargs={keyword: item.id}))
    assert response.status_code == 200
    return response.content.decode()


def test_series_page_has_title_and_description(client, series):
    """The series page states both lines, with its names escaped."""
    page = _page(client, 'show_series', 'series_id', series)

    assert ('<meta property="og:title" content="Cats &amp; &quot;Dogs&quot;'
            ' (Smith &amp; &quot;Sons&quot;, 1999 series)">') in page
    assert ('<meta name="description" property="og:description"\n'
            '        content="Comic series published in Testish (Testland)'
            ' since 1999; 0 issues.">') in page
    assert '"Dogs"' not in page.split('</head>')[0]


def test_publisher_page_has_title_and_description(client, series):
    """The publisher page states both lines, with its name escaped."""
    page = _page(client, 'show_publisher', 'publisher_id', series.publisher)

    assert ('<meta property="og:title"'
            ' content="Smith &amp; &quot;Sons&quot;">') in page
    assert ('<meta name="description" property="og:description"\n'
            '        content="Comics publisher (Testland) from 1985.">'
            ) in page
    assert '"Sons"' not in page.split('</head>')[0]
