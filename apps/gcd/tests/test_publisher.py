# -*- coding: utf-8 -*-



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


@pytest.yield_fixture
def pub_dep_mocks():
    p = '%s.Publisher' % PATH
    with mock.patch('%s.active_brands' % p) as ab_mock, \
            mock.patch('%s.brand_group_revisions' % p) as bg_mock, \
            mock.patch('%s.brand_use_revisions' % p) as bu_mock, \
            mock.patch('%s.indicia_publisher_revisions' % p) as ip_mock, \
            mock.patch('%s.series_revisions' % p) as s_mock:

        ab_mock.return_value.exists.return_value = False

        for m in (bg_mock, bu_mock, ip_mock, s_mock):
            m.active_set.return_value.exists.return_value = False
        yield {
            'ab': ab_mock,
            'bg': bg_mock.active_set,
            'bu': bu_mock.active_set,
            'ip': ip_mock.active_set,
            's': s_mock.active_set,
        }


def test_pub_has_no_dependents(pub_dep_mocks):
    pub = Publisher()
    has = pub.has_dependents()
    assert has is False

    # Check calls on this test case because it should hit all of them.
    for m in list(pub_dep_mocks.values()):
        m.return_value.exists.assert_called_once_with()


@pytest.mark.parametrize('which_exists', ['ab', 'bg', 'bu', 'ip', 's'])
def test_pub_has_dependents_revs_exist(pub_dep_mocks, which_exists):
    pub_dep_mocks[which_exists].return_value.exists.return_value = True
    pub = Publisher()
    has = pub.has_dependents()
    assert has is True


@pytest.mark.parametrize('which_count',
                         ['brand', 'series', 'issue'])
def test_pub_has_dependents_nonzero_counts(pub_dep_mocks, which_count):
    pub = Publisher(**{'%s_count' % which_count: 1})
    has = pub.has_dependents()
    assert has is True


@pytest.mark.parametrize('which_count',
                         ['indicia_publisher'])
def test_pub_has_non_dependents_nonzero_counts(pub_dep_mocks, which_count):
    pub = Publisher(**{'%s_count' % which_count: 1})
    has = pub.has_dependents()
    assert has is False


@pytest.yield_fixture
def ipub_dep_mock():
    ip = '%s.IndiciaPublisher' % PATH
    with mock.patch('%s.issue_revisions' % ip) as ip_mock:
        ip_mock.active_set.return_value.exists.return_value = False
        yield ip_mock


def test_ipub_has_no_dependents(ipub_dep_mock):
    ipub = IndiciaPublisher()
    has = ipub.has_dependents()
    assert has is False
    ipub_dep_mock.active_set.return_value.exists.assert_called_once_with()


def test_ipub_has_dependents_revs_exist(ipub_dep_mock):
    ipub_dep_mock.active_set.return_value.exists.return_value = True
    ipub = IndiciaPublisher()
    has = ipub.has_dependents()
    assert has is True


def test_ipub_has_dependents_issue_count(ipub_dep_mock):
    ipub = IndiciaPublisher(issue_count=1)
    has = ipub.has_dependents()
    assert has is True


@pytest.yield_fixture
def group_dep_mocks():
    g = '%s.BrandGroup' % PATH
    with mock.patch('%s.brand_revisions' % g) as br_mock, \
            mock.patch('%s.active_emblems' % g) as ae_mock:

        br_mock.active_set.return_value.exists.return_value = False
        ae_mock.return_value.exists.return_value = False

        # Do it this way so that we can look at
        # return_value.exists.return_value and parametrize the cases.
        yield {
            'br': br_mock.active_set,
            'ae': ae_mock,
        }


def test_group_has_no_dependents(group_dep_mocks):
    group = BrandGroup()
    has = group.has_dependents()
    assert has is False

    for m in list(group_dep_mocks.values()):
        m.return_value.exists.assert_called_once_with()


@pytest.mark.parametrize('which_exists', ['br', 'ae'])
def test_group_has_dependents_revs_exist(group_dep_mocks, which_exists):
    group_dep_mocks[which_exists].return_value.exists.return_value = True
    group = BrandGroup()
    has = group.has_dependents()
    assert has is True


def test_group_has_dependents_issue_count(group_dep_mocks):
    group = BrandGroup(issue_count=1)
    has = group.has_dependents()
    assert has is True


@pytest.yield_fixture
def brand_dep_mocks():
    b = '%s.Brand' % PATH
    with mock.patch('%s.use_revisions' % b) as bu_mock, \
            mock.patch('%s.issue_revisions' % b) as ish_mock, \
            mock.patch('%s.in_use' % b) as in_use_mock:

        for m in (bu_mock, ish_mock):
            m.active_set.return_value.exists.return_value = False
        in_use_mock.exists.return_value = False

        yield {
            'bu': bu_mock,
            'ish': ish_mock,
            'in_use': in_use_mock,
        }


def test_brand_has_no_dependents(brand_dep_mocks):
    brand = Brand()
    has = brand.has_dependents()
    assert has is False

    # Check calls on this test case because it should hit all of them.
    for m in ('bu', 'ish'):
        brand_dep_mocks[m].active_set.return_value \
                          .exists.assert_called_once_with()


@pytest.mark.parametrize('which_exists', ['bu', 'ish'])
def test_brand_has_dependents_revs_exist(brand_dep_mocks, which_exists):
    brand_dep_mocks[which_exists].active_set.return_value \
                                 .exists.return_value = True
    brand = Brand()
    has = brand.has_dependents()
    assert has is True


def test_brand_has_dependents_in_use(brand_dep_mocks):
    brand_dep_mocks['in_use'].exists.return_value = True
    brand = Brand()
    has = brand.has_dependents()
    assert has is False


def test_brand_has_dependents_issue_count(brand_dep_mocks):
    brand = Brand(issue_count=1)
    has = brand.has_dependents()
    assert has is True


def test_brand_stat_counts_issues(brand_dep_mocks):
    brand = Brand(issue_count=1)
    counts = brand.stat_counts()
    assert counts == {'issues': 1}


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


def test_ipub_stat_counts():
    with mock.patch('%s.IndiciaPublisher.active_issues' % PATH) as is_mock:
        is_mock.return_value.exists.return_value = False
        counts = IndiciaPublisher().stat_counts()
        assert counts == {'indicia publishers': 1}


def test_brand_group_stat_counts():
    with mock.patch('%s.BrandGroup.active_issues' % PATH) as is_mock, \
            mock.patch('%s.BrandGroup.active_emblems' % PATH) as em_mock:
        is_mock.return_value.exists.return_value = True
        em_mock.return_value.count.return_value = 42
        counts = BrandGroup().stat_counts()
        assert counts == {'brands': 1}

    with mock.patch('%s.BrandGroup.active_issues' % PATH) as is_mock, \
            mock.patch('%s.BrandGroup.active_emblems' % PATH) as em_mock:
        is_mock.return_value.exists.return_value = False
        em_mock.return_value.count.return_value = 42
        counts = BrandGroup().stat_counts()
        assert counts == {'brands': 1}

@pytest.mark.parametrize("derived_class",
                         [Publisher, BrandGroup, Brand, IndiciaPublisher])
def test_stat_counts_deleted(derived_class):
    obj = derived_class()
    obj.deleted = True
    assert obj.stat_counts() == {}
