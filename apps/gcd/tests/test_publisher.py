# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import mock
import pytest

from django.db.models import query
from apps.gcd.models import (
    Publisher, BrandGroup, Brand, BrandUse, IndiciaPublisher)


BRAND_COUNT = 10
IPUB_COUNT = 20
SERIES_COUNT = 30
ISSUE_COUNT = 40

DELTAS = {
    'brands': 1,
    'indicia publishers': 2,
    'series': 3,
    'issues': 4,
}


@pytest.yield_fixture
def f_mock():
    with mock.patch('apps.gcd.models.publisher.F') as f_mock:

        # Normally, F() results in a lazy evaluation object, but
        # for testing we'll just have it return a number.
        def f_function(field):
            if field == 'brand_count':
                return BRAND_COUNT
            if field == 'indicia_publisher_count':
                return IPUB_COUNT
            if field == 'series_count':
                return SERIES_COUNT
            if field == 'issue_count':
                return ISSUE_COUNT
            # Shouldn't get here.
            assert False

        f_mock.side_effect = f_function
        yield f_mock


def test_update_cached_counts_none(f_mock):
    p = Publisher()
    p.update_cached_counts({})

    assert p.brand_count == 0
    assert p.indicia_publisher_count == 0
    assert p.series_count == 0
    assert p.issue_count == 0


def test_update_cached_counts_add(f_mock):
    p = Publisher()
    p.update_cached_counts(DELTAS)

    assert p.brand_count == BRAND_COUNT + DELTAS['brands']
    assert p.indicia_publisher_count == (IPUB_COUNT +
                                         DELTAS['indicia publishers'])
    assert p.series_count == SERIES_COUNT + DELTAS['series']
    assert p.issue_count == ISSUE_COUNT + DELTAS['issues']


def test_update_cached_counts_subtract(f_mock):
    p = Publisher()
    p.update_cached_counts(DELTAS, negate=True)

    assert p.brand_count == BRAND_COUNT - DELTAS['brands']
    assert p.indicia_publisher_count == (IPUB_COUNT -
                                         DELTAS['indicia publishers'])
    assert p.series_count == SERIES_COUNT - DELTAS['series']
    assert p.issue_count == ISSUE_COUNT - DELTAS['issues']


def test_update_cached_counts_imprints():
    p = Publisher()
    with pytest.raises(ValueError):
        p.update_cached_counts({'imprints': 1})


@pytest.mark.parametrize("derived_class",
                         [BrandGroup, Brand, IndiciaPublisher])
def test_base_update_cached_counts_none(derived_class, f_mock):
    dc = derived_class(issue_count=0)
    dc.update_cached_counts({})

    assert dc.issue_count == 0


@pytest.mark.parametrize("derived_class",
                         [BrandGroup, Brand, IndiciaPublisher])
def test_base_update_cached_counts_add(derived_class, f_mock):
    dc = derived_class(issue_count=0)
    dc.update_cached_counts(DELTAS)

    assert dc.issue_count == ISSUE_COUNT + DELTAS['issues']


@pytest.mark.parametrize("derived_class",
                         [BrandGroup, Brand, IndiciaPublisher])
def test_base_update_cached_counts_subtract(derived_class, f_mock):
    dc = derived_class(issue_count=0)
    dc.update_cached_counts(DELTAS, negate=True)

    assert dc.issue_count == ISSUE_COUNT - DELTAS['issues']


def test_brand_use_active_issues():
    with mock.patch('apps.gcd.models.publisher.BrandUse.emblem') as em_mock:
        mock_qs = mock.MagicMock(query.QuerySet)
        em_mock.issue_set.exclude.return_value.filter.return_value = mock_qs

        bu = BrandUse(publisher=Publisher())
        ai = bu.active_issues()
        assert ai is mock_qs
        em_mock.issue_set.exclude.assert_called_once_with(deleted=True)
        em_mock.issue_set.exclude.return_value.filter.assert_called_once_with(
            issue__series__publisher=bu.publisher)
