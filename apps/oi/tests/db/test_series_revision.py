# -*- coding: utf-8 -*-

import pytest
import mock

from apps.gcd.models import Publisher
from apps.oi.models import SeriesRevision, IssueRevision


@pytest.mark.django_db
def test_create_add_revision(any_added_series_rev, series_add_values,
                             any_changeset):
    sr = any_added_series_rev

    for k, v in series_add_values.iteritems():
        assert getattr(sr, k) == v

    assert sr.series is None

    assert sr.reservation_requested is False
    assert sr.changeset == any_changeset
    assert sr.date_inferred is False

    assert sr.source is None
    assert sr.source_name == 'series'


@pytest.mark.django_db
def test_commit_added_revision(any_added_series_rev, series_add_values,
                               any_changeset, keywords):
    sr = any_added_series_rev

    old_publisher_series_count = sr.publisher.series_count

    # Simple version of this for mocking.  Real article testing elsewhere.
    sort_name = sr.name[sr.name.index(' ') + 1:]
    with mock.patch('apps.oi.models.update_count') as updater, \
            mock.patch('apps.oi.models.remove_leading_article') as remover, \
            mock.patch('apps.oi.models.IssueRevision') as ir_class, \
            mock.patch('apps.oi.models.SeriesRevision.save') as save:
        remover.return_value = sort_name
        sr.commit_to_display()
    assert updater.called_once_with('series', 1,
                                    language=sr.language, country=sr.country)
    assert save.called_once_with()

    assert sr.series is not None
    assert sr.source is sr.series

    for k, v in series_add_values.iteritems():
        if k == 'keywords':
            kws = [k for k in sr.publisher.keywords.names()]
            kws.sort()
            assert kws == keywords['list']
        else:
            assert getattr(sr.series, k) == v

    assert remover.called_once_with(sr.name)
    assert sr.series.sort_name == sort_name

    # This is needed to get an integer count instead of an F() object.
    publisher = Publisher.objects.get(pk=sr.publisher.pk)
    assert publisher.series_count == old_publisher_series_count + 1
    assert sr.series.issue_count == 0

    assert ir_class.called == 0


@pytest.mark.django_db
def test_commit_add_rev_no_leading_article(any_added_series_rev):
    sr = any_added_series_rev
    sr.leading_article = False
    sr.save()

    with mock.patch('apps.oi.models.update_count'), \
            mock.patch('apps.oi.models.remove_leading_article') as remover:
        # Not testing actual remover logic here, just that it's not called.
        remover.return_value = sr.name
        sr.commit_to_display()

    # Assume everything else worked as tested in the general add case.
    assert remover.called is False
    assert sr.series.name == sr.name
    assert sr.series.sort_name == sr.name


@pytest.mark.django_db
def test_commit_add_rev_singleton(any_added_series_rev):
    sr = any_added_series_rev
    sr.is_singleton = True
    sr.save()

    with mock.patch('apps.oi.models.update_count') as updater, \
            mock.patch('apps.oi.models.IssueRevision') as ir_class:
        ir = mock.MagicMock(spec=IssueRevision)
        ir_class.return_value = ir

        sr.commit_to_display()

    assert updater.called_once_with('series', 1,
                                    language=sr.language, country=sr.country)
    ir_class.assert_called_once_with(changeset=sr.changeset,
                                     series=sr.series,
                                     after=None,
                                     number='[nn]',
                                     publication_date=sr.year_began)
    assert ir.key_date == '%d-00-00' % sr.year_began
    ir.save.assert_called_once_with()


@pytest.mark.django_db
def test_commit_add_rev_non_comics(any_added_series_rev):
    sr = any_added_series_rev
    sr.is_comics_publication = False
    sr.save()

    old_publisher_series_count = sr.publisher.series_count

    with mock.patch('apps.oi.models.update_count') as updater:
        sr.commit_to_display()

    assert updater.called == 0
    new_publisher = Publisher.objects.get(pk=sr.publisher.pk)
    assert new_publisher.series_count == old_publisher_series_count


@pytest.mark.django_db
def test_commit_add_rev_non_comics_singleton(any_added_series_rev):
    sr = any_added_series_rev
    sr.is_comics_publication = False
    sr.is_singleton = True

    with mock.patch('apps.oi.models.update_count') as updater, \
            mock.patch('apps.oi.models.IssueRevision') as ir_class:
        ir = mock.MagicMock(spec=IssueRevision)
        ir_class.return_value = ir

        sr.commit_to_display()

    assert updater.called == 0

    ir_class.assert_called_once_with(changeset=sr.changeset,
                                     series=sr.series,
                                     after=None,
                                     number='[nn]',
                                     publication_date=sr.year_began)
    assert ir.key_date == '%d-00-00' % sr.year_began
    ir.save.assert_called_once_with()


@pytest.mark.django_db
def test_create_edit_revision(any_added_series, series_add_values,
                              any_changeset):
    # Simple version of this for mocking.  Real article testing elsewhere.
    sort_name = any_added_series.name[any_added_series.name.index(' ') + 1:]
    with mock.patch('apps.oi.models.remove_leading_article') as remover:
        remover.return_value = sort_name
        sr = SeriesRevision.objects.clone_revision(instance=any_added_series,
                                                   changeset=any_changeset)

    for k, v in series_add_values.iteritems():
        assert getattr(sr, k) == v

    assert sr.series is any_added_series

    assert sr.reservation_requested is False
    assert sr.changeset == any_changeset
    assert sr.date_inferred is False

    assert sr.source is any_added_series
    assert sr.source_name == 'series'
