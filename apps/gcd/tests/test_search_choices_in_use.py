# -*- coding: utf-8 -*-
"""Tests of the countries and languages offered by the advanced search."""

from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.gcd.forms.search import AdvancedSearch
from apps.gcd.models import Publisher, Series
from apps.stddata.models import Country, Language


def _offered(field):
    """Return the codes offered by a field of the advanced search form."""
    return {code for code, _name in AdvancedSearch().fields[field].choices}


def _series(code, deleted=False):
    """
    Create a series and its publisher, both with a new country and a new
    language with the given code, and both deleted if asked.
    """
    country = Country.objects.create(code=code, name='Testland %s' % code)
    language = Language.objects.create(code=code, name='Testish %s' % code)
    publisher = Publisher.objects.create(
        name='Publisher %s' % code, country=country, year_began=1950,
        deleted=deleted)
    Series.objects.create(
        name='Series %s' % code, sort_name='Series %s' % code,
        year_began=1950, country=country, language=language,
        publisher=publisher, is_comics_publication=True, has_gallery=False,
        publication_dates='1950', deleted=deleted)


def test_only_the_countries_of_publishers_are_offered(db):
    """The search filters publishers by country: no others are listed."""
    _series('zz-used')
    _series('zz-deleted', deleted=True)
    Country.objects.create(code='zz-unused', name='Testland unused')

    offered = _offered('country')
    assert 'zz-unused' not in offered
    assert 'zz-deleted' not in offered
    assert 'zz-used' in offered


def test_only_the_languages_of_series_are_offered(db):
    """The search filters series by language: no others are listed."""
    _series('zz-used')
    _series('zz-deleted', deleted=True)
    Language.objects.create(code='zz-unused', name='Testish unused')

    offered = _offered('language')
    assert 'zz-unused' not in offered
    assert 'zz-deleted' not in offered
    assert 'zz-used' in offered


def test_the_choices_take_one_query_each_whatever_their_number(db):
    """More countries and languages in use do not add queries."""
    _series('zz-one')
    with CaptureQueriesContext(connection) as few:
        AdvancedSearch()
    _series('zz-two')
    _series('zz-three')
    with CaptureQueriesContext(connection) as more:
        AdvancedSearch()
    assert len(few) == len(more) == 2
