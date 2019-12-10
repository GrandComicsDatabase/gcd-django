# -*- coding: utf-8 -*-



import itertools
import mock
import pytest

from django.db.models import QuerySet, Count

from apps.gcd.models import Series, Issue, Story
from apps.gcd.models.issue import INDEXED


SERIES_PATH = 'apps.gcd.models.series.Series'
REVMGR_PATH = 'apps.oi.models.RevisionManager'

# Exact count/delta numbers not significant.
# For use with update_cached_counts testing.
ISSUE_COUNT = 40
DELTAS = {
    # Issues should be ignored, only series issues should be relevant.
    'issues': 999,
    'series issues': 4,
}


def test_has_keywords():
    with mock.patch('%s.keywords' % SERIES_PATH) as kw_mock:
        s = Series()

        kw_mock.exists.return_value = False
        assert s.has_keywords() is False

        kw_mock.exists.return_value = True
        assert s.has_keywords() is True


def test_has_series_bonds():
    to_path = '%s.to_series_bond' % SERIES_PATH
    from_path = '%s.from_series_bond' % SERIES_PATH
    with mock.patch(to_path) as to_mock, mock.patch(from_path) as from_mock:
        s = Series()

        to_mock.exists.return_value = False
        from_mock.exists.return_value = False
        assert s.has_series_bonds() is False

        to_mock.exists.return_value = True
        assert s.has_series_bonds() is True

        from_mock.exists.return_value = True
        assert s.has_series_bonds() is True

        to_mock.exists.return_value = False
        assert s.has_series_bonds() is True


def test_has_tracking():
    with mock.patch('%s.has_series_bonds' % SERIES_PATH) as sb_mock:
        s = Series()

        s.tracking_notes = ''
        sb_mock.return_value = False
        assert s.has_tracking() is False

        s.tracking_notes = 'any text'
        assert s.has_tracking() == 'any text'

        sb_mock.return_value = True
        assert s.has_tracking() == 'any text'

        s.tracking_notes = ''
        assert s.has_tracking() is True


def test_series_relative_bonds():
    FILTER_ARGS = {'any_filter': 'any_value'}
    FIRST_RESULTS = [1, 2, 3]
    SECOND_RESULTS = [4, 5]
    ITER_RESULTS = itertools.chain(FIRST_RESULTS, SECOND_RESULTS)

    srb_path = 'apps.gcd.models.seriesbond.SeriesRelativeBond.__new__'
    to_path = '%s.to_series_bond' % SERIES_PATH
    from_path = '%s.from_series_bond' % SERIES_PATH
    with mock.patch(srb_path) as srb_mock, \
            mock.patch(to_path) as to_mock, mock.patch(from_path) as from_mock:

        to_mock.filter.return_value = FIRST_RESULTS
        from_mock.filter.return_value = SECOND_RESULTS

        # Make the SRB constructor return a different value each time so
        # that we can verify that the calls went through in the right order.
        srb_mock.side_effect = lambda self, series, x: -x

        s = Series()

        srb = s.series_relative_bonds(**FILTER_ARGS)

        to_mock.filter.assert_called_once_with(**FILTER_ARGS)
        from_mock.filter.assert_called_once_with(**FILTER_ARGS)
        assert srb == [-x for x in ITER_RESULTS]


def test_delete():
    with mock.patch('%s.save' % SERIES_PATH):
        s = Series()

        s.delete()

        assert s.deleted is True
        s.save.assert_called_once_with()


@pytest.mark.parametrize('issues, issue_revisions', [
    (True, True), (True, False), (False, True), (False, False)])
def test_has_dependents(issues, issue_revisions):
    with mock.patch('%s.active_issues' % SERIES_PATH) as is_mock, \
            mock.patch('%s.active_set' % REVMGR_PATH) as rev_mock:
        rev_mock.return_value.exists.return_value = issue_revisions
        s = Series()
        is_mock.return_value.exists.return_value = issues

        assert s.has_dependents() is any((issue_revisions, issues))


@pytest.yield_fixture
def issues_qs():
    """
    Provides a queryset mock for active_issues().exclude(...)
    """
    with mock.patch('%s.active_issues' % SERIES_PATH) as active_issues:
        qs = mock.MagicMock(spec=QuerySet)
        active_issues.return_value.exclude.return_value = qs
        yield qs


def test_active_base_issues(issues_qs):
    s = Series()
    assert s.active_base_issues() == issues_qs
    s.active_issues.return_value.exclude.assert_called_once_with(
        variant_of__series=s)


def test_active_non_base_variants(issues_qs):
    s = Series()
    assert s.active_non_base_variants() == issues_qs
    s.active_issues.return_value.exclude.assert_called_once_with(
        variant_of=None)


def test_active_indexed_issues(issues_qs):
    s = Series()
    assert s.active_indexed_issues() == issues_qs
    s.active_issues.return_value.exclude.assert_called_once_with(
        is_indexed=INDEXED['skeleton'])


def test_active_base_issues_variant_count():
    with mock.patch('%s.active_base_issues' % SERIES_PATH) as ab_issues, \
            mock.patch('apps.gcd.models.series.Count') as count_class_mock:
        count_mock = mock.MagicMock(spec=Count)
        count_class_mock.return_value = count_mock
        ab_issues.return_value.annotate.return_value = 100

        s = Series()
        assert s.active_base_issues_variant_count() == 100
        s.active_base_issues.return_value.annotate.assert_called_once_with(
            variant_count=count_mock)


def test_counts_comics():
    series_path = 'apps.gcd.models.series.Series'
    issues_path = '%s.active_base_issues' % series_path
    variants_path = '%s.active_non_base_variants' % series_path
    indexes_path = '%s.active_indexed_issues' % series_path
    cover_count_path = '%s.scan_count' % series_path

    with mock.patch('apps.gcd.models.story.Story.objects'), \
            mock.patch(issues_path) as is_mock, \
            mock.patch(variants_path) as v_mock, \
            mock.patch(indexes_path) as ix_mock, \
            mock.patch(cover_count_path,
                       new_callable=mock.PropertyMock) as cc_mock:

        is_mock.return_value.filter.return_value.count.return_value = 30
        v_mock.return_value.count.return_value = 20
        ix_mock.return_value.count.return_value = 10
        cc_mock.return_value = 15

        Story.objects.filter.return_value \
                     .exclude.return_value \
                     .count.return_value = 100

        s = Series(is_comics_publication=True)

        assert s.stat_counts() == {
            'series': 1,
            'issues': 30,
            'variant issues': 20,
            'issue indexes': 10,
            'covers': 15,
            'stories': 100,
        }
        Story.objects.filter.assert_called_once_with(issue__series=s)
        Story.objects.filter.return_value.exclude.assert_called_once_with(
            deleted=True)
        is_mock.return_value.filter.assert_called_once_with(variant_of=None)


def test_counts_non_comics():
    with mock.patch('apps.gcd.models.story.Story.objects'), \
            mock.patch('apps.gcd.models.series.Series.scan_count',
                       new_callable=mock.PropertyMock) as cc_mock:

        cc_mock.return_value = 15
        Story.objects.filter.return_value \
                     .exclude.return_value \
                     .count.return_value = 100

        s = Series(is_comics_publication=False)
        assert s.stat_counts() == {
            'covers': 15,
            'stories': 100,
            'publisher series': 1,
        }


def test_counts_deleted():
    s = Series(is_comics_publication=True)
    s.deleted = True
    assert s.stat_counts() == {}


@pytest.yield_fixture
def f_mock():
    with mock.patch('apps.gcd.models.series.F') as f_mock:

        # Normally, F() results in a lazy evaluation object, but
        # for testing we'll just have it return a number.
        f_mock.return_value = ISSUE_COUNT
        yield f_mock


def test_update_cached_counts_none(f_mock):
    s = Series(issue_count=0)
    s.update_cached_counts({})

    assert s.issue_count == 0


def test_update_cached_counts_add(f_mock):
    s = Series(issue_count=0)
    s.update_cached_counts(DELTAS)

    assert s.issue_count == ISSUE_COUNT + DELTAS['series issues']


def test_update_cached_counts_subtract(f_mock):
    s = Series(issue_count=0)
    s.update_cached_counts(DELTAS, negate=True)

    assert s.issue_count == ISSUE_COUNT - DELTAS['series issues']


def test_set_first_last_issues_empty():
    with mock.patch('apps.gcd.models.series.Series.save'), \
            mock.patch('apps.gcd.models.series.models.QuerySet.order_by') \
            as order_mock, \
            mock.patch('apps.gcd.models.issue.Issue.series'):

        # Create some issues that are set as first/last even though no longer
        # attached to the series.
        i1 = Issue(number='1', sort_code=0)
        i2 = Issue(number='2', sort_code=1)
        issue_list = [i1, i2]
        s = Series(issue_count=0, first_issue=i1, last_issue=i2)

        # Ensure that the active issues list is empty (i1 & i2 not attached).
        def index_faker(index):
            return issue_list[index]

        qs = mock.MagicMock(spec=QuerySet)
        qs.count.return_value = 0
        qs.__getitem__.side_effect = index_faker

        order_mock.return_value = qs

        s.set_first_last_issues()

        assert s.first_issue is None
        assert s.last_issue is None
        s.save.assert_called_once_with()


def test_set_first_last_issues_nonempty():
    with mock.patch('apps.gcd.models.series.Series.save'), \
            mock.patch('apps.gcd.models.series.models.QuerySet.order_by') \
            as order_mock, \
            mock.patch('apps.gcd.models.issue.Issue.series'):

        s = Series(issue_count=0)

        # Create some issues attached to the series (but not first/last).
        i1 = Issue(number='1', sort_code=0, series=s)
        i2 = Issue(number='2', sort_code=1, series=s)
        issue_list = [i1, i2]

        # Ensure that the active issues list is empty (i1 & i2 not attached).
        def index_faker(index):
            return issue_list[index]

        qs = mock.MagicMock(spec=QuerySet)
        qs.count.return_value = 2
        qs.__getitem__.side_effect = index_faker
        qs.__iter__.return_value = iter(issue_list)

        order_mock.return_value = qs

        s.set_first_last_issues()

        assert s.first_issue is i1
        assert s.last_issue is i2
        s.save.assert_called_once_with()
