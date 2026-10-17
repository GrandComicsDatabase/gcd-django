"""Regression tests for Haystack search index preparation."""

from datetime import date

import pytest

from apps.gcd.models import Creator
from apps.gcd.search_indexes import CreatorIndex
from apps.stddata.models import Date


def test_creator_index_handles_missing_birth_date():
    """Creators without a birth date can still be added to the index."""
    creator = Creator(birth_date=None)
    index = CreatorIndex()

    assert index.prepare_year(creator) == 9999
    assert index.prepare_date(creator) is None


@pytest.mark.parametrize('birth_year, expected_year, expected_date', [
    ('1920', 1920, date(1920, 1, 1)),
    ('19??', 9999, None),
    ('', 9999, None),
])
def test_creator_index_preserves_existing_birth_year_handling(
    birth_year, expected_year, expected_date
):
    """Known, uncertain, and empty birth years keep their existing values."""
    creator = Creator(birth_date=Date(year=birth_year))
    index = CreatorIndex()

    assert index.prepare_year(creator) == expected_year
    assert index.prepare_date(creator) == expected_date
