# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import mock
import pytest

from apps.gcd.models import Series, Issue, INDEXED
from apps.oi.models import Changeset, Revision, IssueRevision

RECENT = 'apps.gcd.models.recent.RecentIndexedIssue.objects.update_recents'
ACTION = 'apps.oi.models.Changeset.changeset_action'
CSET = 'apps.oi.models.Changeset'
IREV = 'apps.oi.models.IssueRevision'


def test_excluded_fields():
    assert IssueRevision._get_excluded_field_names() == \
        Revision._get_excluded_field_names()


def test_classification():
    meta = Issue._meta
    gf = meta.get_field
    regular_fields = {
        'number': gf('number'),
        'title': gf('title'),
        'no_title': gf('no_title'),
        'volume': gf('volume'),
        'no_volume': gf('no_volume'),
        'display_volume_with_number': gf('display_volume_with_number'),
        'variant_of': gf('variant_of'),
        'variant_name': gf('variant_name'),
        'isbn': gf('isbn'),
        'no_isbn': gf('no_isbn'),
        'barcode': gf('barcode'),
        'no_barcode': gf('no_barcode'),
        'rating': gf('rating'),
        'no_rating': gf('no_rating'),
        'publication_date': gf('publication_date'),
        'key_date': gf('key_date'),
        'on_sale_date_uncertain': gf('on_sale_date_uncertain'),
        'indicia_frequency': gf('indicia_frequency'),
        'no_indicia_frequency': gf('no_indicia_frequency'),
        'price': gf('price'),
        'page_count': gf('page_count'),
        'page_count_uncertain': gf('page_count_uncertain'),
        'editing': gf('editing'),
        'no_editing': gf('no_editing'),
        'notes': gf('notes'),
        'keywords': gf('keywords'),
        'series': gf('series'),
        'indicia_publisher': gf('indicia_publisher'),
        'indicia_pub_not_printed': gf('indicia_pub_not_printed'),
        'brand': gf('brand'),
        'no_brand': gf('no_brand'),
    }

    irregular_fields = {
        'valid_isbn': gf('valid_isbn'),
        'on_sale_date': gf('on_sale_date'),
        'sort_code': gf('sort_code'),
        'is_indexed': gf('is_indexed'),
    }

    assert IssueRevision._get_regular_fields() == regular_fields
    assert IssueRevision._get_irregular_fields() == irregular_fields

    single_value_fields = regular_fields.copy()
    del single_value_fields['keywords']
    assert IssueRevision._get_single_value_fields() == single_value_fields

    assert IssueRevision._get_multi_value_fields() == {}


def test_conditional_field_mapping():
    assert IssueRevision._get_conditional_field_tuple_mapping() == {
        'volume': ('series', 'has_volume'),
        'no_volume': ('series', 'has_volume'),
        'display_volume_with_issue': ('series', 'has_volume'),
        'title': ('series', 'has_issue_title'),
        'no_title': ('series', 'has_issue_title'),
        'barcode': ('series', 'has_barcode'),
        'no_barcode': ('series', 'has_barcode'),
        'isbn': ('series', 'has_isbn'),
        'no_isbn': ('series', 'has_isbn'),
        'valid_isbn': ('series', 'has_isbn'),
        'indicia_frequency': ('series', 'has_indicia_frequency'),
        'no_indicia_frequency': ('series', 'has_indicia_frequency'),
    }


def test_parent_field_tuples():
    assert IssueRevision._get_parent_field_tuples() == {
        ('series',),
        ('series', 'publisher'),
        ('brand', 'group'),
        ('brand',),
        ('indicia_publisher',),
    }


def test_stats_category_field_tuples():
    assert IssueRevision._get_stats_category_field_tuples() == {
        ('series', 'country'),
        ('series', 'language'),
    }


# Some parameter combinations are omitted because they make no sense.
@pytest.mark.parametrize('deleted, has_prev, changed',
                         [(False, False, False),
                          (False, True, True),
                          (False, True, False),
                          (True, True, False)])
def test_series_changed(deleted, has_prev, changed):
    s1 = Series(name='One')
    s2 = Series(name='Two') if changed else s1
    with mock.patch('%s.previous_revision' % IREV,
                    new_callable=mock.PropertyMock) as prev_mock:
        rev = IssueRevision(series=s2)
        rev.deleted = deleted
        if has_prev:
            prev_mock.return_value = IssueRevision(series=s1)
        else:
            prev_mock.return_value = None
        sc = rev.series_changed
        assert sc is changed


def test_pre_initial_save_with_date():
    rev = IssueRevision(issue=Issue(on_sale_date='2016-01-31'))
    rev._pre_initial_save()
    assert rev.year_on_sale == 2016
    assert rev.month_on_sale == 1
    assert rev.day_on_sale == 31


def test_pre_initial_save_no_date():
    rev = IssueRevision(issue=Issue())
    rev._pre_initial_save()
    assert rev.year_on_sale is None
    assert rev.month_on_sale is None
    assert rev.day_on_sale is None


def test_post_commit_to_display():
    from apps.oi.models import ACTION_MODIFY

    with mock.patch(RECENT) as recent_mock, mock.patch(ACTION) as action_mock:
        action_mock.return_value = ACTION_MODIFY
        rev = IssueRevision(changeset=Changeset(),
                            issue=Issue(is_indexed=INDEXED['full']))

        rev._post_commit_to_display()

        recent_mock.assert_called_once_with(rev.issue)


def test_post_commit_to_display_not_a_modify():
    from apps.oi.models import ACTION_ADD

    with mock.patch(RECENT) as recent_mock, mock.patch(ACTION) as action_mock:
        action_mock.return_value = ACTION_ADD
        rev = IssueRevision(changeset=Changeset(),
                            issue=Issue(is_indexed=INDEXED['full']))

        rev._post_commit_to_display()

        assert not recent_mock.called


def test_post_commit_to_display_skeleton():
    from apps.oi.models import ACTION_MODIFY

    with mock.patch(RECENT) as recent_mock, mock.patch(ACTION) as action_mock:
        action_mock.return_value = ACTION_MODIFY
        rev = IssueRevision(changeset=Changeset(),
                            issue=Issue(is_indexed=INDEXED['skeleton']))

        rev._post_commit_to_display()

        assert not recent_mock.called


def test_same_series_revisions():
    with mock.patch('%s.issuerevisions' % CSET) as irevs_mock:
        series = Series()
        ss_revs = mock.MagicMock()
        irevs_mock.filter.return_value = ss_revs
        rev = IssueRevision(changeset=Changeset(), series=series)

        assert rev._same_series_revisions() == ss_revs
        irevs_mock.filter.assert_called_once_with(series=series)


def test_same_series_open_with_after():
    with mock.patch('%s._same_series_revisions' % IREV) as ssrevs_mock:
        ssowa_revs = mock.MagicMock()
        ssrevs_mock.return_value.filter.return_value = ssowa_revs
        rev = IssueRevision()

        assert rev._same_series_open_with_after() == ssowa_revs
        ssrevs_mock.return_value.filter.assert_called_once_with(
            after__isnull=False, committed=None)


@pytest.mark.parametrize('deleted', (True, False))
def test_open_prereq_revisions(deleted):
    if deleted:
        # Sort prereqs from last to first- delete from end of series back.
        sort = '-revision_sort_code'
    else:
        # Add or move from first to last, so that each "after" is in place.
        sort = 'revision_sort_code'

    with mock.patch('%s._same_series_revisions' % IREV) as ssrevs_mock:
        op_revs = mock.MagicMock()
        ssrevs_mock.return_value.exclude.return_value \
                                .filter.return_value \
                                .order_by.return_value = op_revs
        rev = IssueRevision()
        rev.id = 1234
        rev.deleted = deleted

        assert rev._open_prereq_revisions() == op_revs
        ssrevs_mock.return_value.exclude.assert_has_calls([
            mock.call(id=1234),
            mock.call().filter(committed=None),
            mock.call().filter().order_by(sort)])


@pytest.mark.parametrize('deleted', (True, False))
def test_committed_prereq_revisions(deleted):
    # We sort commited reversed from open so that we effectively append
    # to committed as we commit each revision as we walk through open.
    if deleted:
        sort = 'revision_sort_code'
    else:
        sort = '-revision_sort_code'

    with mock.patch('%s._same_series_revisions' % IREV) as ssrevs_mock:
        c_revs = mock.MagicMock()
        ssrevs_mock.return_value.exclude.return_value \
                                .filter.return_value \
                                .order_by.return_value = c_revs
        rev = IssueRevision()
        rev.id = 1234
        rev.deleted = deleted

        assert rev._committed_prereq_revisions() == c_revs
        ssrevs_mock.return_value.exclude.assert_has_calls([
            mock.call(id=1234),
            mock.call().filter(committed=True),
            mock.call().filter().order_by(sort)])
