# -*- coding: utf-8 -*-

import pytest
import mock

from apps.gcd.models import Publisher
from apps.oi.models import SeriesRevision, IssueRevision


ONE_SERIES_ONLY = {
    'series': 1,
    'issues': 0,
    'variant issues': 0,
    'issue indexes': 0,
    'covers': 0,
    'stories': 0,
}

UPDATE_ALL = 'apps.stats.models.CountStats.objects.update_all_counts'


@pytest.mark.django_db
def test_create_add_revision(any_added_series_rev, series_add_values,
                             any_adding_changeset):
    rev = any_added_series_rev

    for k, v in series_add_values.items():
        assert getattr(rev, k) == v

    assert rev.series is None

    assert rev.reservation_requested is False
    assert rev.changeset == any_adding_changeset
    assert rev.date_inferred is False

    assert rev.source is None
    assert rev.source_name == 'series'


@pytest.mark.django_db
def test_commit_added_revision(any_added_series_rev, series_add_values,
                               any_adding_changeset, keywords):
    rev = any_added_series_rev

    old_publisher_series_count = rev.publisher.series_count

    # Simple version of this for mocking.  Real article testing elsewhere.
    sort_name = rev.name[rev.name.index(' ') + 1:]
    with mock.patch(UPDATE_ALL) as updater, \
            mock.patch('apps.oi.models.remove_leading_article') as remover, \
            mock.patch('apps.oi.models.IssueRevision') as ir_class, \
            mock.patch('apps.oi.models.SeriesRevision.save') as save:

        remover.return_value = sort_name
        rev.commit_to_display()

    updater.assert_has_calls([
        mock.call({}, language=None, country=None, negate=True),
        mock.call(ONE_SERIES_ONLY,
                  language=rev.series.language, country=rev.series.country),
    ])
    assert updater.call_count == 2

    # We call save once in _adjust_stats() and once in commit_to_display()
    save.assert_has_calls([mock.call(), mock.call()])
    assert save.call_count == 2

    assert rev.series is not None
    assert rev.source is rev.series

    for k, v in series_add_values.items():
        if k == 'keywords':
            kws = [k for k in rev.publisher.keywords.names()]
            kws.sort()
            assert kws == keywords['list']
        else:
            assert getattr(rev.series, k) == v

    remover.assert_called_once_with(rev.name)
    assert rev.series.sort_name == sort_name

    # This is needed to get an integer count instead of an F() object.
    publisher = Publisher.objects.get(pk=rev.publisher.pk)
    assert publisher.series_count == old_publisher_series_count + 1
    assert rev.series.issue_count == 0

    assert not ir_class.called


@pytest.mark.django_db
def test_commit_add_rev_no_leading_article(any_added_series_rev):
    rev = any_added_series_rev
    rev.leading_article = False
    rev.save()

    with mock.patch(UPDATE_ALL), \
            mock.patch('apps.oi.models.remove_leading_article') as remover:
        # Not testing actual remover logic here, just that it's not called.
        remover.return_value = rev.name
        rev.commit_to_display()

    # Assume everything else worked as tested in the general add case.
    assert remover.called is False
    assert rev.series.name == rev.name
    assert rev.series.sort_name == rev.name


@pytest.mark.django_db
def test_commit_add_rev_singleton(any_added_series_rev):
    rev = any_added_series_rev
    rev.is_singleton = True
    rev.save()

    with mock.patch(UPDATE_ALL) as updater, \
            mock.patch('apps.oi.models.IssueRevision') as ir_class:
        ir = mock.MagicMock(spec=IssueRevision)
        ir_class.return_value = ir

        rev.commit_to_display()

    updater.assert_has_calls([
        mock.call({}, language=None, country=None, negate=True),
        mock.call(ONE_SERIES_ONLY,
                  language=rev.series.language, country=rev.series.country),
    ])
    assert updater.call_count == 2

    # We know that the series revision save() was called if the issue revision
    # construction happens- otherwise there woulnd't be an rev.series to use.
    ir_class.assert_called_once_with(changeset=rev.changeset,
                                     series=rev.series,
                                     after=None,
                                     number='[nn]',
                                     publication_date=rev.year_began)
    assert ir.key_date == '%d-00-00' % rev.year_began
    ir.save.assert_called_once_with()
    assert not ir.commit_to_display.called


@pytest.mark.django_db
def test_commit_add_rev_non_comics(any_added_series_rev):
    rev = any_added_series_rev
    rev.is_comics_publication = False
    rev.save()

    old_publisher_series_count = rev.publisher.series_count

    with mock.patch(UPDATE_ALL) as updater, \
            mock.patch('apps.oi.models.IssueRevision') as ir_class:
        rev.commit_to_display()

    updater.assert_has_calls([
        mock.call({}, language=None, country=None, negate=True),
        mock.call({'covers': 0, 'stories': 0, 'publisher series': 1},
                  language=rev.series.language, country=rev.series.country),
    ])
    assert updater.call_count == 2

    new_publisher = Publisher.objects.get(pk=rev.publisher.pk)
    assert new_publisher.series_count == old_publisher_series_count + 1

    assert not ir_class.called


@pytest.mark.django_db
def test_commit_add_rev_non_comics_singleton(any_added_series_rev):
    rev = any_added_series_rev
    rev.is_comics_publication = False
    rev.is_singleton = True

    with mock.patch(UPDATE_ALL) as updater, \
            mock.patch('apps.oi.models.IssueRevision') as ir_class:
        ir = mock.MagicMock(spec=IssueRevision)
        ir_class.return_value = ir

        rev.commit_to_display()

    updater.assert_has_calls([
        mock.call({}, language=None, country=None, negate=True),
        mock.call({'covers': 0, 'stories': 0, 'publisher series': 1},
                  language=rev.series.language, country=rev.series.country),
    ])
    assert updater.call_count == 2

    ir_class.assert_called_once_with(changeset=rev.changeset,
                                     series=rev.series,
                                     after=None,
                                     number='[nn]',
                                     publication_date=rev.year_began)
    assert ir.key_date == '%d-00-00' % rev.year_began
    ir.save.assert_called_once_with()
    assert not ir.commit_to_display.called


@pytest.mark.django_db
def test_create_edit_revision(any_added_series, series_add_values,
                              any_editing_changeset):
    # Simple version of this for mocking.  Real article testing elsewhere.
    sort_name = any_added_series.name[any_added_series.name.index(' ') + 1:]
    with mock.patch('apps.oi.models.remove_leading_article') as remover:
        remover.return_value = sort_name
        rev = SeriesRevision.clone(data_object=any_added_series,
                                   changeset=any_editing_changeset)

    for k, v in series_add_values.items():
        assert getattr(rev, k) == v

    assert rev.series is any_added_series

    assert rev.reservation_requested is False
    assert rev.changeset == any_editing_changeset
    assert rev.date_inferred is False

    assert rev.source is any_added_series
    assert rev.source_name == 'series'
