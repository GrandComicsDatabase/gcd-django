# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import itertools
import mock

from apps.gcd.models import Series

# TODO: We really shouldn't be depending on the OI here.
from apps.oi import states


SERIES_PATH = 'apps.gcd.models.series.Series'


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
        s.reserved = True

        s.delete()

        assert s.deleted is True
        assert s.reserved is False
        s.save.assert_called_once_with()


def test_deletable():
    with mock.patch('%s.issue_revisions' % SERIES_PATH) as ir_mock:
        s = Series()
        s.issue_count = 0
        ir_mock.filter.return_value.count.return_value = 0

        assert s.deletable() is True
        ir_mock.filter.assert_called_once_with(
            changeset__state__in=states.ACTIVE)


def test_not_deletable_issue_count():
    with mock.patch('%s.issue_revisions' % SERIES_PATH) as ir_mock:
        s = Series()
        s.issue_count = 1
        ir_mock.filter.return_value.count.return_value = 0

        assert s.deletable() is False


def test_not_deletable_active_count():
    with mock.patch('%s.issue_revisions' % SERIES_PATH) as ir_mock:
        s = Series()
        s.issue_count = 0
        ir_mock.filter.return_value.count.return_value = 1

        assert s.deletable() is False
