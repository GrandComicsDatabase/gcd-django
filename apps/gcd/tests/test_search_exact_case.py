# -*- coding: utf-8 -*-
"""Tests of the case-sensitive exact match of the advanced search."""

from apps.gcd.models import Publisher, Series
from apps.stddata.models import Country, Language

LABEL = 'Matches Exactly (case sensitive)'


def _series(name):
    """Create a series with the given name and return it."""
    country = Country.objects.get_or_create(
        code='zx', defaults={'name': 'Testland X'})[0]
    language = Language.objects.get_or_create(
        code='zx', defaults={'name': 'Testish X'})[0]
    publisher = Publisher.objects.get_or_create(
        name='Exact Case Publisher', country=country, year_began=1960)[0]
    return Series.objects.create(
        name=name, sort_name=name, year_began=1960, country=country,
        language=language, publisher=publisher, is_comics_publication=True,
        has_gallery=False, publication_dates='1960')


def test_the_search_form_offers_the_case_sensitive_exact_match(client, db):
    """The method can be chosen on the advanced search page."""
    response = client.get('/search/advanced/')
    assert LABEL in response.content.decode()


def test_the_exact_match_respects_case_and_accents(client, db):
    """Only the series written with the same case and accents is listed."""
    same = _series('Exact Case Test')
    other_case = _series('exact case test')
    other_accent = _series('Exact Case T\u00e9st')

    response = client.get('/search/advanced/process/', {
        'target': 'series', 'method': 'exact', 'series': 'Exact Case Test'})

    page = response.content.decode()
    assert '/series/%d/' % same.id in page
    assert '/series/%d/' % other_case.id not in page
    assert '/series/%d/' % other_accent.id not in page
