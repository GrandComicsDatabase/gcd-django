# -*- coding: utf-8 -*-
"""Tests of the clean-up list of the series whose country is not the
country of their publisher."""

import re

import pytest

from django.urls import reverse

from apps.gcd.models import Publisher, Series
from apps.stddata.models import Country, Language


def _series(name, publisher, country, language, deleted=False):
    """Create a series of the publisher with the given country."""
    return Series.objects.create(
        name=name, sort_name=name, year_began=1950, country=country,
        language=language, publisher=publisher, is_comics_publication=True,
        has_gallery=False, publication_dates='1950', deleted=deleted)


@pytest.fixture
def catalog(db):
    """
    A publisher of one country, series of it and of another country.
    Return the language that the filter tests choose.
    """
    home = Country.objects.get_or_create(
        code='zu', defaults={'name': 'Testland U'})[0]
    away = Country.objects.get_or_create(
        code='zv', defaults={'name': 'Testland V'})[0]
    first = Language.objects.get_or_create(
        code='zu', defaults={'name': 'Testish U'})[0]
    second = Language.objects.get_or_create(
        code='zv', defaults={'name': 'Testish V'})[0]
    publisher = Publisher.objects.create(name='Test Publisher',
                                         country=home, year_began=1950)
    _series('Series At Home', publisher, home, first)
    _series('Series Abroad', publisher, away, first)
    _series('Series Abroad Second', publisher, away, second)
    _series('Series Removed', publisher, away, first, deleted=True)
    return first


def test_the_list_has_the_series_of_another_country(client, catalog):
    """Only the series not deleted with another country are listed."""
    response = client.get(reverse('series_with_other_country'))
    page = response.content.decode()
    assert response.status_code == 200
    assert 'Series Abroad<' in page
    assert 'Series Abroad Second<' in page
    assert 'Series At Home' not in page
    assert 'Series Removed' not in page
    assert '2 series' in page


def test_the_list_is_filtered_by_language(client, catalog):
    """The language filter keeps the series of that language."""
    response = client.get(reverse('series_with_other_country'),
                          {'language': catalog.id})
    page = response.content.decode()
    assert 'Series Abroad<' in page
    assert 'Series Abroad Second' not in page


def test_the_list_is_downloaded_with_both_countries(client, catalog,
                                                    django_user_model):
    """The download gives each series with the two country names."""
    user = django_user_model.objects.create_user('list_reader')
    client.force_login(user)
    response = client.get(reverse('series_with_other_country'),
                          {'_export': 'csv', 'language': catalog.id})
    lines = response.content.decode().splitlines()
    assert lines[1].startswith('Series Abroad,1950,Testland V,')
    assert 'Test Publisher,Testland U,' in lines[1]
    assert len(lines) == 2


def test_the_projects_page_leads_to_the_list(client, catalog):
    """The overview of the data projects has a link that opens the list."""
    page = client.get(reverse('projects_toc')).content.decode()
    link = re.search(r'<a href="([^"]+)">\s*Series whose country', page)
    assert link
    assert 'Series Abroad<' in client.get(link.group(1)).content.decode()
