# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import mock
import pytest

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
