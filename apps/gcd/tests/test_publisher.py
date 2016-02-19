# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import mock
import pytest

from django.db.models import query
from apps.gcd.models import (
    Publisher, BrandGroup, Brand, BrandUse, IndiciaPublisher)


PATH = 'apps.gcd.models.publisher'

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
    with mock.patch('%s.F' % PATH) as f_mock:

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
    with mock.patch('%s.BrandUse.emblem' % PATH) as em_mock:
        mock_qs = mock.MagicMock(query.QuerySet)
        em_mock.issue_set.exclude.return_value.filter.return_value = mock_qs

        bu = BrandUse(publisher=Publisher())
        ai = bu.active_issues()
        assert ai is mock_qs
        em_mock.issue_set.exclude.assert_called_once_with(deleted=True)
        em_mock.issue_set.exclude.return_value.filter.assert_called_once_with(
            issue__series__publisher=bu.publisher)


@pytest.yield_fixture
def pub_child_set_mocks():
    p = '%s.Publisher' % PATH
    with mock.patch('%s.active_indicia_publishers' % p) as ip_mock, \
            mock.patch('%s.active_brand_emblems' % p) as be_mock, \
            mock.patch('%s.active_series' % p) as s_mock:
        ip_mock.return_value.exists.return_value = False
        be_mock.return_value.exists.return_value = False
        s_mock.return_value.exists.return_value = False

        yield {'indicia_publishers': ip_mock,
               'brand_emblems': be_mock,
               'series': s_mock}


def test_publisher_stat_counts(pub_child_set_mocks):
    counts = Publisher().stat_counts()
    assert counts == {'publishers': 1}


@pytest.mark.parametrize("mock_set",
                         ['indicia_publishers', 'brand_emblems', 'series'])
def test_publisher_stat_counts_errors(pub_child_set_mocks, mock_set):
    pub_child_set_mocks[mock_set].return_value.exists.return_value = True
    with pytest.raises(AssertionError):
        Publisher().stat_counts()


def test_ipub_stat_counts():
    with mock.patch('%s.IndiciaPublisher.active_issues' % PATH) as is_mock:
        is_mock.return_value.exists.return_value = False
        counts = IndiciaPublisher().stat_counts()
        assert counts == {'indicia publishers': 1}


def test_ipub_stat_counts_issues():
    with mock.patch('%s.IndiciaPublisher.active_issues' % PATH) as is_mock:
        is_mock.return_value.exists.return_value = True
        with pytest.raises(AssertionError):
            IndiciaPublisher().stat_counts()


def test_brand_group_stat_counts():
    with mock.patch('%s.BrandGroup.active_issues' % PATH) as is_mock, \
            mock.patch('%s.BrandGroup.active_emblems' % PATH) as em_mock:
        is_mock.return_value.exists.return_value = False
        em_mock.return_value.count.return_value = 42
        counts = BrandGroup().stat_counts()
        assert counts == {'brands': 42}


def test_brand_group_stat_counts_issues():
    with mock.patch('%s.BrandGroup.active_issues' % PATH) as is_mock:
        is_mock.return_value.exists.return_value = True
        with pytest.raises(AssertionError):
            BrandGroup().stat_counts()


def test_brand_stat_counts():
    with mock.patch('%s.Brand.active_issues' % PATH) as is_mock:
        is_mock.return_value.exists.return_value = False
        counts = Brand().stat_counts()
        assert counts == {'brands': 1}


def test_brand_stat_counts_issues():
    with mock.patch('%s.Brand.active_issues' % PATH) as is_mock:
        is_mock.return_value.exists.return_value = True
        with pytest.raises(AssertionError):
            Brand().stat_counts()


@pytest.mark.parametrize("derived_class",
                         [Publisher, BrandGroup, Brand, IndiciaPublisher])
def test_stat_counts_deleted(derived_class):
    obj = derived_class()
    obj.deleted = True
    assert obj.stat_counts() == {}
