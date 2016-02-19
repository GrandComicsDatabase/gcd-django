# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import mock
import pytest

from apps.gcd.models import Cover, Issue, Series

# TODO: Should not be importing from oi into gcd.
from apps.oi import states


FILTER_PATH = 'apps.oi.models.RevisionManager.filter'


@pytest.fixture
def count_zero():
    """ Filter return value that has a count() of 0 """
    zero = mock.MagicMock()
    zero.count.return_value = 0
    return zero


@pytest.fixture
def count_one():
    """ Filter return value that has a count() of 1 """
    one = mock.MagicMock()
    one.count.return_value = 1
    return one


@pytest.fixture
def cover():
    return Cover(issue=Issue(series=Series(name='n', year_began=2000,
                                           is_comics_publication=True)))


def test_deletable(count_zero, count_one):
    with mock.patch(FILTER_PATH) as f:
        # Make filter return 0 only if deletable calls with correct kwargs.
        f.side_effect = (
            lambda **kwargs:
            count_zero if kwargs == {'changeset__state__in': states.ACTIVE}
            else count_one)
        assert Cover().deletable()


def test_not_deletable(count_zero, count_one):
    with mock.patch(FILTER_PATH) as f:
        # Make filter return 1 only if deletable calls with correct kwargs.
        f.side_effect = (
            lambda **kwargs:
            count_one if kwargs == {'changeset__state__in': states.ACTIVE}
            else count_zero)
        assert not Cover().deletable()


def test_stat_counts_comics(cover):
    assert cover.stat_counts() == {'covers': 1}


def test_stat_counts_non_comics(cover):
    # As many stats are collected on only comics publications, ensure
    # that covers are always collected.
    cover.issue.series.is_comics_publication = False
    assert cover.stat_counts() == {'covers': 1}


def test_stat_counts_deleted(cover):
    cover.deleted = True
    assert cover.stat_counts() == {}
