# -*- coding: utf-8 -*-
"""Tests of the search for received awards by name."""

import pytest
from django.urls import reverse

from apps.gcd.models import Award, Creator, ReceivedAward
from apps.stddata.models import Date


@pytest.fixture
def received_awards(db):
    """Two received awards named 'Test Prize ...' and one other."""
    award = Award.objects.create(name='Test Award')
    creator = Creator.objects.create(
        gcd_official_name='Test Recipient', sort_name='Test Recipient',
        birth_date=Date.objects.create(year='1950'))
    for name, year in (('Test Prize A', 2001), ('Test Prize B', 1999),
                       ('Other Honour', 2000)):
        ReceivedAward.objects.create(recipient=creator, award=award,
                                     award_name=name, award_year=year)


def _search(client, **kwargs):
    """Return the text of the received award search page for 'Test Prize'."""
    response = client.get(reverse(
        'received_award_by_name',
        kwargs=dict(received_award_name='Test Prize', **kwargs)))
    assert response.status_code == 200
    return response.content.decode()


def test_received_awards_found_by_name(client, received_awards):
    """The matching awards are listed by name, with their recipient."""
    content = _search(client)
    assert 'Test Recipient' in content
    assert 'Other Honour' not in content
    assert content.index('Test Prize A') < content.index('Test Prize B')


def test_received_awards_heading(client, received_awards):
    """The heading names the received awards once, after their count."""
    text = ' '.join(_search(client).split())
    assert ('2 received awards matching your query for '
            '&#x27;Test Prize&#x27;') in text
    assert 'ReceivedAward Search Results' not in text


def test_received_awards_sorted_by_year(client, received_awards):
    """The chronological order follows the year of the award."""
    content = _search(client, sort='chrono')
    assert content.index('Test Prize B') < content.index('Test Prize A')


def test_received_awards_uncertain_year(client, received_awards):
    """An uncertain year is shown with its question mark."""
    ReceivedAward.objects.filter(award_name='Test Prize B')         .update(award_year_uncertain=True)
    assert '1999?' in _search(client)
