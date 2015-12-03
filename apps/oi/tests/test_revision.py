# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import mock
import pytest

from .conftest import DummyRevision
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
        DummyRevision()._get_source()


def test_get_source_name():
    with pytest.raises(NotImplementedError):
        DummyRevision()._get_source_name()


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
