"""
The list of the issues with several covers says how many issues it holds.
"""
import re

import pytest
from django.urls import reverse

from apps.gcd.models import Cover, Issue, Publisher, Series
from apps.stddata.models import Country, Language

# The page lists the issues of this publisher when none is chosen.
DEFAULT_PUBLISHER_ID = 709


@pytest.fixture
def series(db):
    """A series of the publisher whose issues the page lists by default."""
    country = Country.objects.get_or_create(
      id=944, defaults={'code': 'n6', 'name': 'Testland C'})[0]
    language = Language.objects.get_or_create(
      id=944, defaults={'code': 'n6', 'name': 'Testish C'})[0]
    return Series.objects.create(
      name='Some Series', sort_name='Some Series', year_began=1990,
      country=country, language=language, is_comics_publication=True,
      publication_dates='1990',
      publisher=Publisher.objects.create(
        id=DEFAULT_PUBLISHER_ID, name='Test Publisher', country=country,
        year_began=1990))


def _issue(series, number, covers):
    """Add an issue with that many covers to the series."""
    issue = Issue.objects.create(number=str(number), series=series,
                                 sort_code=number, publication_date='1990',
                                 key_date='1990-01-00')
    for _ in range(covers):
        Cover.objects.create(issue=issue)


@pytest.mark.parametrize('issues, sentence', [
  (1, 'Displaying 1 to 1 of 1 issue with several covers.'),
  (2, 'Displaying 1 to 2 of 2 issues with several covers.')])
def test_sentence_above_the_list_gives_the_count(client, series, issues,
                                                 sentence):
    """The sentence names the number of issues, then "issue" or "issues"."""
    for number in range(1, issues + 1):
        _issue(series, number, covers=2)
    _issue(series, 9, covers=1)

    response = client.get(reverse('issues_with_several_covers'))

    assert response.status_code == 200
    assert sentence in re.sub(r'\s+', ' ', response.content.decode())
