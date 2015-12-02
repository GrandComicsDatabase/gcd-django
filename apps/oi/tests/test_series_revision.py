# -*- coding: utf-8 -*-

import pytest
import mock

from apps.gcd.models import Publisher, Series, Country, Language
from apps.oi.models import Changeset, SeriesRevision, IssueRevision


COUNTRY_ONE = mock.MagicMock(spec=Country)
COUNTRY_TWO = mock.MagicMock(spec=Country)
LANGUAGE_ONE = mock.MagicMock(spec=Language)
LANGUAGE_TWO = mock.MagicMock(spec=Language)
PUBLISHER_ONE = mock.MagicMock(spec=Publisher)
PUBLISHER_TWO = mock.MagicMock(spec=Publisher)
NO_DB_CHANGESET = mock.MagicMock(spec=Changeset)


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
            mock.patch('apps.oi.models.IssueRevision') as ir_class:
        remover.return_value = sort_name
        sr.commit_to_display()
    assert updater.called_once_with('series', 1,
                                    language=sr.language, country=sr.country)

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
                                     after=None,
                                     number='[nn]',
                                     publication_date=sr.year_began)
    assert ir.key_date == '%d-00-00' % sr.year_began
    assert ir.series == sr.series
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
                                     after=None,
                                     number='[nn]',
                                     publication_date=sr.year_began)
    assert ir.key_date == '%d-00-00' % sr.year_began
    assert ir.series == sr.series
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


@pytest.yield_fixture
def patched_series_class():
    """ Patches foreign keys to prevent database access. """
    with mock.patch('apps.oi.models.Series.country'), \
            mock.patch('apps.oi.models.Series.language'), \
            mock.patch('apps.oi.models.Series.publisher'), \
            mock.patch('apps.oi.models.SeriesRevision.changeset'), \
            mock.patch('apps.oi.models.SeriesRevision.series'), \
            mock.patch('apps.oi.models.SeriesRevision.country'), \
            mock.patch('apps.oi.models.SeriesRevision.language'), \
            mock.patch('apps.oi.models.SeriesRevision.publisher'):
        yield


def test_get_major_changes_all_change(patched_series_class):
    old = Series(country=COUNTRY_ONE,
                 language=LANGUAGE_ONE,
                 publisher=PUBLISHER_ONE,
                 is_comics_publication=True,
                 is_current=True,
                 is_singleton=False)
    new = SeriesRevision(changeset=NO_DB_CHANGESET,
                         series=old,
                         country=COUNTRY_TWO,
                         language=LANGUAGE_TWO,
                         publisher=PUBLISHER_TWO,
                         is_comics_publication=False,
                         is_current=False,
                         is_singleton=True)

    c = new._get_major_changes()
    assert c == {
        'publisher changed': True,
        'country changed': True,
        'language changed': True,
        'is comics changed': True,
        'singleton changed': True,
        'is current changed': True,
        'to comics': False,
        'from comics': True,
        'to singleton': True,
        'from singleton': False,
        'to current': False,
        'from current': True,
        'old publisher': PUBLISHER_ONE,
        'new publisher': PUBLISHER_TWO,
        'old country': COUNTRY_ONE,
        'new country': COUNTRY_TWO,
        'old language': LANGUAGE_ONE,
        'new language': LANGUAGE_TWO,
        'changed': True,
    }


def test_get_major_changes_no_change(patched_series_class):
    old = Series(country=COUNTRY_ONE,
                 language=LANGUAGE_ONE,
                 publisher=PUBLISHER_ONE,
                 is_comics_publication=False,
                 is_current=False,
                 is_singleton=True)
    new = SeriesRevision(changeset=NO_DB_CHANGESET,
                         series=old,
                         country=COUNTRY_ONE,
                         language=LANGUAGE_ONE,
                         publisher=PUBLISHER_ONE,
                         is_comics_publication=False,
                         is_current=False,
                         is_singleton=True)

    c = new._get_major_changes()
    assert c == {
        'publisher changed': False,
        'country changed': False,
        'language changed': False,
        'is comics changed': False,
        'singleton changed': False,
        'is current changed': False,
        'to comics': False,
        'from comics': False,
        'to singleton': False,
        'from singleton': False,
        'to current': False,
        'from current': False,
        'old publisher': PUBLISHER_ONE,
        'new publisher': PUBLISHER_ONE,
        'old country': COUNTRY_ONE,
        'new country': COUNTRY_ONE,
        'old language': LANGUAGE_ONE,
        'new language': LANGUAGE_ONE,
        'changed': False,
    }


def test_get_major_changes_added(patched_series_class):
    new = SeriesRevision(changeset=NO_DB_CHANGESET,
                         series=None,
                         country=COUNTRY_TWO,
                         language=LANGUAGE_TWO,
                         publisher=PUBLISHER_TWO,
                         is_comics_publication=True,
                         is_current=True,
                         is_singleton=False)

    c = new._get_major_changes()
    assert c == {
        'publisher changed': True,
        'country changed': True,
        'language changed': True,
        'is comics changed': True,
        'singleton changed': True,
        'is current changed': True,
        'to comics': True,
        'from comics': False,
        'to singleton': False,
        'from singleton': False,
        'to current': True,
        'from current': False,
        'old publisher': None,
        'new publisher': PUBLISHER_TWO,
        'old country': None,
        'new country': COUNTRY_TWO,
        'old language': None,
        'new language': LANGUAGE_TWO,
        'changed': True,
    }


def test_get_major_changes_deleted(patched_series_class):
    old = Series(country=COUNTRY_ONE,
                 language=LANGUAGE_ONE,
                 publisher=PUBLISHER_ONE,
                 is_comics_publication=True,
                 is_current=True,
                 is_singleton=False)
    new = SeriesRevision(changeset=NO_DB_CHANGESET,
                         series=old,
                         country=COUNTRY_ONE,
                         language=LANGUAGE_ONE,
                         publisher=PUBLISHER_ONE,
                         is_comics_publication=True,
                         is_current=True,
                         is_singleton=False,
                         deleted=True)

    c = new._get_major_changes()
    assert c == {
        'publisher changed': True,
        'country changed': True,
        'language changed': True,
        'is comics changed': True,
        'singleton changed': True,
        'is current changed': True,
        'to comics': False,
        'from comics': True,
        'to singleton': False,
        'from singleton': False,
        'to current': False,
        'from current': True,
        'old publisher': PUBLISHER_ONE,
        'new publisher': None,
        'old country': COUNTRY_ONE,
        'new country': None,
        'old language': LANGUAGE_ONE,
        'new language': None,
        'changed': True,
    }


@pytest.yield_fixture
def series_and_revision():
    """
    Tuple of series, series revision, and mock of Revision._adjust_stats()

    For use with _adjust_stats() testing.  The series and series revision
    are connected but not saved, and database access is patched.
    """
    # Don't use the "constant" PUBLISHER_ONE/TWO as we expect
    # the mock call state to be changed.
    old_pub = mock.MagicMock()
    new_pub = mock.MagicMock()
    with mock.patch('apps.gcd.models.series.Series.update_cached_counts'), \
            mock.patch('apps.gcd.models.series.Series.publisher'), \
            mock.patch('apps.gcd.models.series.Series.save'), \
            mock.patch('apps.gcd.models.publisher.Publisher.save'), \
            mock.patch('apps.oi.models.SeriesRevision.changeset'), \
            mock.patch('apps.oi.models.SeriesRevision.publisher'), \
            mock.patch('apps.oi.models.Revision._adjust_stats') as super_mock:
        s = Series(publisher=old_pub)

        rev = SeriesRevision(changeset=mock.MagicMock(),
                             series=s,
                             publisher=new_pub)
        yield s, rev, super_mock


def test_adjust_stats_pub_changed(series_and_revision):
    s, rev, super_mock = series_and_revision
    changes = {
        'publisher changed': True,
        'old publisher': s.publisher,
        'new publisher': rev.publisher,
    }

    rev._adjust_stats(changes, {'issues': 20}, {'issues': 5})

    super_mock.assert_called_once_with(changes, {'issues': 20}, {'issues': 5})

    s.publisher.update_cached_counts.assert_called_once_with({'issues': 20},
                                                             negate=True)
    s.publisher.save.assert_called_once_with()

    rev.publisher.update_cached_counts.assert_called_once_with({'issues': 5})
    rev.publisher.save.assert_called_once_with()

    s.update_cached_counts.assert_called_once_with({'issues': -15})
    s.save.assert_called_once_with()


def test_adjust_stats_only_counts_changed(series_and_revision):
    s, rev, super_mock = series_and_revision
    changes = {'publisher changed': False}

    rev._adjust_stats(changes, {'issues': 20}, {'issues': 5})

    super_mock.assert_called_once_with(changes, {'issues': 20}, {'issues': 5})

    s.publisher.update_cached_counts.assert_called_once_with({'issues': -15})
    s.publisher.save.assert_called_once_with()

    s.update_cached_counts.assert_called_once_with({'issues': -15})
    s.save.assert_called_once_with()


def test_adjust_stats_no_changes(series_and_revision):
    s, rev, super_mock = series_and_revision
    changes = {'publisher changed': False}

    rev._adjust_stats(changes, {'issues': 10}, {'issues': 10})

    super_mock.assert_called_once_with(changes, {'issues': 10}, {'issues': 10})

    assert not s.publisher.update_cached_counts.called
    assert not s.publisher.save.called

    assert not s.update_cached_counts.called
    assert not s.save.called
