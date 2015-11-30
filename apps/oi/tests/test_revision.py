# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import mock
import pytest

from apps.gcd.models import Country, Language
from apps.oi import models


@pytest.yield_fixture
def source_mock():
    """ Patches the source property, by default evaluates as True. """
    with mock.patch('apps.oi.models.Revision.source') as source_mock:
        source_mock.__nonzero__.return_value = True
        yield source_mock


def test_added(source_mock):
    source_mock.__nonzero__.return_value = False

    rev = models.Revision()
    added = rev.added
    source_mock.__nonzero__.assert_called_once_with()
    assert added


def test_not_added_because_source(source_mock):
    rev = models.Revision()
    added = rev.added
    source_mock.__nonzero__.assert_called_once_with()
    assert not added


def test_not_added_because_deleted(source_mock):
    # No source plus deleted doesn't make sense, but should
    # not read as added anyway.
    source_mock.__nonzero__.return_value = False

    rev = models.Revision(deleted=True)
    added = rev.added
    source_mock.__nonzero__.assert_called_once_with()
    assert not added


def test_edited(source_mock):
    rev = models.Revision()
    edited = rev.edited
    source_mock.__nonzero__.assert_called_once_with()
    assert edited


def test_not_edited_because_no_source(source_mock):
    # No source plus deleted doesn't make sense, but
    # definitely not an edit.
    source_mock.__nonzero__.return_value = False

    rev = models.Revision(deleted=True)
    edited = rev.edited
    source_mock.__nonzero__.assert_called_once_with()
    assert not edited


def test_not_edited_because_deleted(source_mock):
    rev = models.Revision(deleted=True)
    edited = rev.edited
    source_mock.__nonzero__.assert_called_once_with()
    assert not edited


def test_get_major_changes():
    with pytest.raises(NotImplementedError):
        models.Revision()._get_major_changes()


def test_get_source():
    with pytest.raises(NotImplementedError):
        models.Revision()._get_source()


def test_get_source_name():
    with pytest.raises(NotImplementedError):
        models.Revision()._get_source_name()


@pytest.yield_fixture
def mock_update_all():
    with mock.patch('apps.oi.models.CountStats.objects.update_all_counts') \
            as uac_mock:
        yield uac_mock


def test_adjust_stats_neither(mock_update_all):
    rev = models.Revision()

    old_counts = {'foo': 1}
    new_counts = {'foo': 2}

    rev._adjust_stats({}, old_counts, new_counts)

    mock_update_all.assert_has_calls([
        mock.call(old_counts, country=None, language=None, negate=True),
        mock.call(new_counts, country=None, language=None)])
    assert mock_update_all.call_count == 2


def test_adjust_stats_both(mock_update_all):
    rev = models.Revision()

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
