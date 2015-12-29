# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import mock
import pytest

from apps.oi.models import Revision
from apps.oi.tests.conftest import DummyRevision
from apps.gcd.models import Country, Language


def test_added():
    rev = DummyRevision()
    added = rev.added
    assert added


def test_added_committed():
    rev = DummyRevision()
    rev.committed = True
    added = rev.added
    assert added


def test_not_added_because_previous_revision():
    rev = DummyRevision()
    rev.previous_revision = DummyRevision()
    added = rev.added
    assert not added


def test_not_added_because_discarded():
    rev = DummyRevision()
    rev.committed = False
    added = rev.added
    assert not added


def test_added_with_source():
    # We should no longer be checking for source.  This test is only here
    # to test that we have not regressed to the prior implementation.
    with mock.patch('apps.oi.models.Revision.source') as source_mock:
        rev = DummyRevision()
        added = rev.added
        assert not source_mock.__nonzero__.called
        assert added


def test_edited():
    rev = DummyRevision()
    rev.previous_revision = DummyRevision()
    edited = rev.edited
    assert edited


def test_edited_committed():
    rev = DummyRevision()
    rev.previous_revision = DummyRevision()
    rev.committed = True
    edited = rev.edited
    assert edited


def test_not_edited_because_added():
    rev = DummyRevision(deleted=True)
    edited = rev.edited
    assert not edited


def test_not_edited_because_deleted():
    rev = DummyRevision(deleted=True)
    edited = rev.edited
    assert not edited


def test_not_edited_because_discarded():
    rev = DummyRevision()
    rev.previous_revision = DummyRevision()
    rev.committed = False
    edited = rev.edited
    assert not edited


def test_committed():
    rev = DummyRevision(committed=True)
    assert not rev.open
    assert not rev.discarded


def test_discarded():
    rev = DummyRevision(committed=False)
    assert not rev.open
    assert rev.discarded


def test_open():
    rev = DummyRevision(committed=None)
    assert rev.open
    assert not rev.discarded


def test_get_major_changes():
    with pytest.raises(NotImplementedError):
        DummyRevision()._get_major_changes()


def test_get_source():
    with pytest.raises(NotImplementedError):
        DummyRevision().source


def test_set_source():
    with pytest.raises(NotImplementedError):
        DummyRevision().source = object()


def test_get_source_class():
    with pytest.raises(NotImplementedError):
        DummyRevision().source_class


def test_get_source_name():
    with pytest.raises(NotImplementedError):
        DummyRevision().source_name


@pytest.yield_fixture
def mock_update_all():
    with mock.patch('apps.oi.models.CountStats.objects.update_all_counts') \
            as uac_mock:
        yield uac_mock


def test_adjust_stats_neither(mock_update_all):
    rev = DummyRevision()

    old_counts = {'foo': 1}
    new_counts = {'foo': 2}

    rev._adjust_stats({}, old_counts, new_counts)

    mock_update_all.assert_has_calls([
        mock.call(old_counts, country=None, language=None, negate=True),
        mock.call(new_counts, country=None, language=None)])
    assert mock_update_all.call_count == 2


def test_adjust_stats_both(mock_update_all):
    rev = DummyRevision()

    old_counts = {'foo': 1}
    new_counts = {'foo': 2}

    changes = {
        'country changed': True,
        'language changed': True,
        'old country': mock.MagicMock(spec=Country),
        'new country': mock.MagicMock(spec=Country),
        'old language': mock.MagicMock(spec=Language),
        'new language': mock.MagicMock(spec=Language),
    }

    rev._adjust_stats(changes, old_counts, new_counts)

    mock_update_all.assert_has_calls([
        mock.call(old_counts, country=changes['old country'],
                  language=changes['old language'], negate=True),
        mock.call(new_counts, country=changes['new country'],
                  language=changes['new language'])])
    assert mock_update_all.call_count == 2


@pytest.yield_fixture
def patched_dummy():
    p = 'apps.oi.tests.conftest.Revision'
    with mock.patch('%s._copy_assignable_fields_to' % p), \
            mock.patch('%s._pre_commit_check' % p), \
            mock.patch('%s._pre_stats_measurement' % p), \
            mock.patch('%s._post_create_for_add' % p), \
            mock.patch('%s._post_assign_fields' % p), \
            mock.patch('%s._pre_save_object' % p), \
            mock.patch('%s._post_save_object' % p), \
            mock.patch('%s._post_adjust_stats' % p), \
            mock.patch('%s._get_major_changes' % p) as gmc_mock, \
            mock.patch('%s._adjust_stats' % p), \
            mock.patch('%s.save' % p), \
            mock.patch('%s.source' % p,
                       new_callable=mock.PropertyMock) as s_mock, \
            mock.patch('%s.source_class' % p,
                       new_callable=mock.PropertyMock) as sc_mock:

        changes = {'does not matter': True}
        gmc_mock.return_value = changes

        data_obj = mock.MagicMock()
        data_obj.reserved = True
        sc_mock.return_value.return_value = data_obj

        # Since our definition of added is based on previous_revision, we can
        # get away with source always returning the mocked data object.
        s_mock.return_value = data_obj

        yield DummyRevision(), s_mock, sc_mock, data_obj, changes


def test_commit_added(patched_dummy):
    d, source, source_class, data_obj, changes = patched_dummy

    # Stats are only called on the thing returned from source after it is set.
    stats = {'whatever': 42}
    data_obj.stat_counts.return_value = stats

    d.commit_to_display()

    d._pre_commit_check.assert_called_once_with()
    d._get_major_changes.assert_called_once_with()
    d._pre_stats_measurement.assert_called_once_with(changes)

    assert d.source.delete.called is False

    # We should have written the data_obj to source, among many read calls.
    source_class.assert_called_once_with()
    source.assert_any_call(data_obj)
    d.save.assert_called_once_with()
    d._post_create_for_add.assert_called_once_with(changes)

    d._copy_assignable_fields_to.assert_called_once_with(d.source)
    d._post_assign_fields.assert_called_once_with(changes)

    assert d.source.reserved is False

    d._pre_save_object.assert_called_once_with(changes)
    source.return_value.save.assert_called_once_with()

    # stat_counts only called once for add.
    d.source.stat_counts.assert_called_once_with()
    d._adjust_stats.assert_called_once_with(changes, {}, stats)
    d._post_adjust_stats.assert_called_once_with(changes)


def test_commit_deleted(patched_dummy):
    d, source, source_class, data_obj, changes = patched_dummy

    # Set up a pre-existing data obj, and then mark it as deleted.
    # Stats will be fetched twice in this scenario.
    d.previous_revision = DummyRevision()
    stats = ({'whatever': 42}, {'whatever': 100, 'other': 2})
    data_obj.stat_counts.side_effect = stats
    d.deleted = True

    d.commit_to_display()

    d._pre_commit_check.assert_called_once_with()
    d._get_major_changes.assert_called_once_with()
    d._pre_stats_measurement.assert_called_once_with(changes)

    d.source.delete.assert_called_once_with()

    # Make sure we never re-assigned to source or did other add/edit stuff.
    assert source_class.called is False
    assert mock.call(data_obj) not in source.calls
    assert d.save.called is False
    assert d._post_create_for_add.called is False
    assert d._copy_assignable_fields_to.called is False
    assert d._post_assign_fields.called is False

    assert d.source.reserved is False

    d._pre_save_object.assert_called_once_with(changes)
    data_obj.save.assert_called_once_with()

    # stat_counts called twice for deletes, at beginning and end.
    d.source.stat_counts.has_calls([mock.call(), mock.call()])
    assert d.source.stat_counts.call_count == 2
    d._adjust_stats.assert_called_once_with(changes, stats[0], stats[1])
    d._post_adjust_stats.assert_called_once_with(changes)


def test_commit_edited_dont_clear(patched_dummy):
    d, source, source_class, data_obj, changes = patched_dummy

    # Set up a pre-existing data obj, making this an edit.
    # Stats will be called twice in this scenario.
    d.previous_revision = DummyRevision()
    stats = ({'whatever': 42}, {'whatever': 100, 'other': 2})
    data_obj.stat_counts.side_effect = stats

    # Nothing currently uses clear_reservation=True, but test it here anyway.
    # We should make sure to not break it on accident, and it's easy to change
    # the test if we decide it will never be needed.  The historical reason
    # for it being there is a bit unclear, probably related to the
    # idea of "approve and re-edit", which we've never implemented.
    d.commit_to_display(clear_reservation=False)

    d._pre_commit_check.assert_called_once_with()
    d._get_major_changes.assert_called_once_with()
    d._pre_stats_measurement.assert_called_once_with(changes)

    assert d.source.delete.called is False

    # Make sure we never re-assigned to source, but do copy fields for edit.
    assert source_class.called is False
    assert mock.call(data_obj) not in source.calls
    assert d.save.called is False
    assert d._post_create_for_add.called is False
    d._copy_assignable_fields_to.assert_called_once_with(d.source)
    d._post_assign_fields.assert_called_once_with(changes)

    assert d.source.reserved is True

    d._pre_save_object.assert_called_once_with(changes)
    data_obj.save.assert_called_once_with()

    # stat_counts called twice for deletes, at beginning and end.
    d.source.stat_counts.has_calls([mock.call(), mock.call()])
    assert d.source.stat_counts.call_count == 2
    d._adjust_stats.assert_called_once_with(changes, stats[0], stats[1])
    d._post_adjust_stats.assert_called_once_with(changes)


def test_assignable_fields():
    assert Revision._assignable_fields() == frozenset()


def test_non_assignable_fields():
    assert Revision._non_assignable_fields() == frozenset()


def test_conditional_fields():
    assert Revision._conditional_fields() == {}


def test_parent_fields():
    assert Revision._parent_fields() == frozenset()


def test_many_to_many_fields():
    assert Revision._many_to_many_fields() == frozenset()


def test_major_flags():
    assert Revision._major_flags() == frozenset()


def test_deprecated_fields():
    assert Revision._deprecated_fields() == frozenset()


def test_pre_initial_save():
    assert DummyRevision()._pre_initial_save() is None


def test_post_m2m_add():
    assert DummyRevision()._post_m2m_add() is None
