# -*- coding: utf-8 -*-


import pytest
import mock

from apps.gcd.models import Publisher, Series, Issue
from apps.oi.models import Changeset, Revision, SeriesRevision, IssueRevision
from apps.stddata.models import Country, Language

CSTATS = 'apps.stats.models.CountStats'
SERIES = 'apps.gcd.models.series.Series'
SREV = 'apps.oi.models.SeriesRevision'
IREV = 'apps.oi.models.IssueRevision'

COUNTRY_ONE = mock.MagicMock(spec=Country)
COUNTRY_TWO = mock.MagicMock(spec=Country)
LANGUAGE_ONE = mock.MagicMock(spec=Language)
LANGUAGE_TWO = mock.MagicMock(spec=Language)
PUBLISHER_ONE = mock.MagicMock(spec=Publisher)
PUBLISHER_TWO = mock.MagicMock(spec=Publisher)
NO_DB_CHANGESET = mock.MagicMock(spec=Changeset)


def test_excluded_fields():
    assert SeriesRevision._get_excluded_field_names() == {
        'open_reserve',
        'publication_dates',
    } | Revision._get_excluded_field_names()


@pytest.yield_fixture
def patched_series_class():
    """ Patches foreign keys to prevent database access. """
    with mock.patch('%s.previous_revision' % SREV) as pr, \
            mock.patch('apps.oi.models.Series.country'), \
            mock.patch('apps.oi.models.Series.language'), \
            mock.patch('apps.oi.models.Series.publisher'), \
            mock.patch('%s.changeset' % SREV), \
            mock.patch('%s.series' % SREV), \
            mock.patch('%s.country' % SREV), \
            mock.patch('%s.language' % SREV), \
            mock.patch('%s.publisher' % SREV):
        # previous_revision needs to read as False by default so that the
        # Revision.added property behaves normally be default.
        pr.__nonzero__.return_value = False
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
                         is_singleton=True,
                         previous_revision=SeriesRevision())

    c = new._get_major_changes()
    assert c == {
        'publisher changed': True,
        'country changed': True,
        'language changed': True,
        'is_comics_publication changed': True,
        'is_singleton changed': True,
        'is_current changed': True,
        'to is_comics_publication': False,
        'from is_comics_publication': True,
        'to is_singleton': True,
        'from is_singleton': False,
        'to is_current': False,
        'from is_current': True,
        'old publisher': PUBLISHER_ONE,
        'new publisher': PUBLISHER_TWO,
        'old country': COUNTRY_ONE,
        'new country': COUNTRY_TWO,
        'old language': LANGUAGE_ONE,
        'new language': LANGUAGE_TWO,
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
                         is_singleton=True,
                         previous_revision=SeriesRevision())

    c = new._get_major_changes()
    assert c == {
        'publisher changed': False,
        'country changed': False,
        'language changed': False,
        'is_comics_publication changed': False,
        'is_singleton changed': False,
        'is_current changed': False,
        'to is_comics_publication': False,
        'from is_comics_publication': False,
        'to is_singleton': False,
        'from is_singleton': False,
        'to is_current': False,
        'from is_current': False,
        'old publisher': PUBLISHER_ONE,
        'new publisher': PUBLISHER_ONE,
        'old country': COUNTRY_ONE,
        'new country': COUNTRY_ONE,
        'old language': LANGUAGE_ONE,
        'new language': LANGUAGE_ONE,
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
        'is_comics_publication changed': True,
        'is_singleton changed': True,
        'is_current changed': True,
        'to is_comics_publication': True,
        'from is_comics_publication': False,
        'to is_singleton': False,
        'from is_singleton': False,
        'to is_current': True,
        'from is_current': False,
        'old publisher': None,
        'new publisher': PUBLISHER_TWO,
        'old country': None,
        'new country': COUNTRY_TWO,
        'old language': None,
        'new language': LANGUAGE_TWO,
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
                         previous_revision=SeriesRevision(),
                         deleted=True)

    c = new._get_major_changes()
    assert c == {
        'publisher changed': True,
        'country changed': True,
        'language changed': True,
        'is_comics_publication changed': True,
        'is_singleton changed': True,
        'is_current changed': True,
        'to is_comics_publication': False,
        'from is_comics_publication': True,
        'to is_singleton': False,
        'from is_singleton': False,
        'to is_current': False,
        'from is_current': True,
        'old publisher': PUBLISHER_ONE,
        'new publisher': None,
        'old country': COUNTRY_ONE,
        'new country': None,
        'old language': LANGUAGE_ONE,
        'new language': None,
    }


@pytest.yield_fixture
def series_and_revision():
    """
    Tuple of series, series revision, and a mock of update_all_counts.

    For use with _adjust_stats() testing.  The series and series revision
    are connected but not saved, and database access is patched.
    """
    # Don't use the "constant" PUBLISHER_ONE/TWO as we expect
    # the mock call state to be changed.
    old_pub = mock.MagicMock()
    new_pub = mock.MagicMock()
    with mock.patch('%s.update_cached_counts' % SERIES), \
            mock.patch('%s.publisher' % SERIES), \
            mock.patch('%s.save' % SERIES), \
            mock.patch('apps.gcd.models.publisher.Publisher.save'), \
            mock.patch('%s.changeset' % SREV), \
            mock.patch('%s.publisher' % SREV), \
            mock.patch('%s.objects.update_all_counts' % CSTATS) as uac_mock:
        s = Series(publisher=old_pub)

        rev = SeriesRevision(changeset=mock.MagicMock(),
                             series=s,
                             publisher=new_pub)
        yield s, rev, uac_mock


def test_adjust_stats_pub_changed(series_and_revision):
    s, rev, uac_mock = series_and_revision
    changes = {
        'publisher changed': True,
        'old publisher': s.publisher,
        'new publisher': rev.publisher,
    }

    rev._adjust_stats(changes, {'issues': 20}, {'issues': 5})

    s.publisher.update_cached_counts.assert_called_once_with({'issues': 20},
                                                             negate=True)
    s.publisher.save.assert_called_once_with()

    rev.publisher.update_cached_counts.assert_called_once_with({'issues': 5})
    rev.publisher.save.assert_called_once_with()

    s.update_cached_counts.assert_called_once_with({'issues': -15})
    s.save.assert_called_once_with()


def test_adjust_stats_only_counts_changed(series_and_revision):
    s, rev, uac_mock = series_and_revision
    # un-change the publisher.  Easier than writing another fixture.
    rev.publisher = s.publisher
    changes = {
        'publisher changed': False,
        'old publisher': s.publisher,
        'new publisher': rev.publisher,
    }

    rev._adjust_stats(changes, {'issues': 20}, {'issues': 5})

    s.publisher.update_cached_counts.assert_called_once_with({'issues': -15})
    s.publisher.save.assert_called_once_with()

    s.update_cached_counts.assert_called_once_with({'issues': -15})
    s.save.assert_called_once_with()


def test_adjust_stats_no_changes(series_and_revision):
    s, rev, uac_mock = series_and_revision
    # un-change the publisher.  Easier than writing another fixture.
    rev.publisher = s.publisher
    changes = {
        'publisher changed': False,
        'old publisher': s.publisher,
        'new publisher': rev.publisher,
    }

    rev._adjust_stats(changes, {'issues': 10}, {'issues': 10})

    assert not s.publisher.update_cached_counts.called
    assert not s.publisher.save.called

    assert not s.update_cached_counts.called
    assert not s.save.called


def test_handle_prerequisites_deleted_singleton():
    ir_mock = mock.MagicMock()
    with mock.patch('%s.clone' % IREV,
                    return_value=ir_mock,
                    spec=IssueRevision), \
            mock.patch('%s.series' % SREV), \
            mock.patch('%s.save' % SREV), \
            mock.patch('%s.commit_to_display' % SREV):
        s = SeriesRevision(changeset=Changeset(),
                           previous_revision=SeriesRevision())
        s.deleted = True
        s.series.is_singleton = True

        # TODO currently cannot delete is_singleton with issues directly
        #i = Issue()
        #s.series.issue_set.__getitem__.side_effect = (
            #lambda x: i if x == 0 else None)

        #s._handle_prerequisites({})

        #IssueRevision.clone.assert_called_once_with(
            #instance=i, changeset=s.changeset)
        #assert ir_mock.deleted is True
        #ir_mock.save.assert_called_once_with()
        #ir_mock.commit_to_display.assert_called_once_with()


@pytest.mark.parametrize('is_singleton, deleted',
                         [(False, True), (True, False), (False, False)])
def test_handle_prerequisites_deleted_no_issue_revision(is_singleton,
                                                        deleted):
    with mock.patch('apps.oi.models.IssueRevision.clone') \
            as cr_mock:
        SeriesRevision(series=Series(), previous_revision=SeriesRevision(),
                       is_singleton=is_singleton, deleted=deleted)
        assert not cr_mock.called


@pytest.mark.parametrize('leading_article, name, sort_name',
                         [(True, 'The Test Series', 'Test Series'),
                          (False, 'The Test Series', 'The Test Series')])
def test_post_assign_fields_leading_article(leading_article, name, sort_name):
    s = Series(name=name)
    sr = SeriesRevision(leading_article=leading_article, name=name, series=s)
    sr._post_assign_fields({})
    assert s.sort_name == sort_name


@pytest.yield_fixture
def pre_save_mocks():
    with mock.patch('%s.get_ongoing_reservation' % SERIES) as get_ongoing, \
      mock.patch('apps.gcd.models.series.Series.scan_count',
                 new_callable=mock.PropertyMock) as scan_count:
        yield SeriesRevision(series=Series()), get_ongoing, scan_count


def test_pre_save_object_from_current(pre_save_mocks):
    sr, get_ongoing_mock, scan_count_mock = pre_save_mocks

    sr._pre_save_object({
        'from is_current': True,
        'to is_comics_publication': False,
    })

    get_ongoing_mock.assert_called_once_with()
    get_ongoing_mock.return_value.delete.assert_called_once_with()
    assert scan_count_mock.called is False


@pytest.mark.parametrize('scan_count, has_gallery', [(42, True), (0, False)])
def test_pre_save_object_to_comics(pre_save_mocks, scan_count, has_gallery):
    sr, get_ongoing_mock, scan_count_mock = pre_save_mocks
    scan_count_mock.return_value = scan_count

    sr._pre_save_object({
        'from is_current': False,
        'to is_comics_publication': True,
    })

    assert get_ongoing_mock.called is False
    scan_count_mock.assert_called_once_with()
    assert sr.series.has_gallery is has_gallery


def test_pre_save_object_neither(pre_save_mocks):
    sr, get_ongoing_mock, scan_count_mock = pre_save_mocks

    sr._pre_save_object({
        'from is_current': False,
        'to is_comics_publication': False,
    })

    assert get_ongoing_mock.called is False
    assert scan_count_mock.called is False


@pytest.mark.parametrize('year_began, key_date',
                         [(1990, '1990-00-00'), (0, '')])
def test_handle_dependents_to_singleton(year_began, key_date):
    with mock.patch('%s.save' % IREV) as save_mock, \
            mock.patch('%s.commit_to_display' % IREV) as commit_mock:
        # Make the IssueRevision that would be returned by the patched
        # constructor call.  Only patch the methods for this.
        s = Series()
        c = Changeset()
        ir_params = {
            'changeset': c,
            'series': s,
            'after': None,
            'number': '[nn]',
            'publication_date': year_began,
        }
        ir = IssueRevision(**ir_params)

        with mock.patch(IREV) as ir_class_mock:
            # Now patch the IssueRevision constructor itself.
            ir_class_mock.return_value = ir
            sr = SeriesRevision(changeset=c, series=s, is_singleton=True,
                                year_began=year_began)

            sr._handle_dependents({'to is_singleton': True})

            ir_class_mock.assert_called_once_with(**ir_params)
            assert ir.key_date == key_date
            save_mock.assert_called_once_with()
            assert not commit_mock.called


def test_handle_dependents_no_singleton():
        with mock.patch(IREV) as ir_class_mock:
            sr = SeriesRevision()
            sr._handle_dependents({'to is_singleton': False})
            assert ir_class_mock.called is False
