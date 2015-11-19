# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import mock
import pytest

from apps.oi import models
from apps.oi import coordination as coord


@pytest.fixture
def mock_revision_list():
    return [mock.MagicMock(spec=models.Revision) for x in range(3)]


@pytest.fixture
def mocked_coordinator(mock_revision_list):
    c = mock.MagicMock(spec=models.Changeset)
    rc = coord.RevisionCoordinator(changeset=c)

    for r in mock_revision_list:
        rc.add_revision(r)

    return rc


def test_create_coordinator():
    c = mock.MagicMock(spec=models.Changeset)

    rc = coord.RevisionCoordinator(changeset=c)
    assert rc._changeset is c
    assert rc._revisions == []


def test_add_revisions(mocked_coordinator, mock_revision_list):
    assert mocked_coordinator._revisions == mock_revision_list


def test_commit_all(mocked_coordinator, mock_revision_list):

    helper = mock.MagicMock()
    helper.first = mock_revision_list[0]
    helper.second = mock_revision_list[1]
    helper.third = mock_revision_list[2]

    mocked_coordinator.commit_all_to_display()

    # I've never figured out how to determing what "self" was for call
    # objects or inside a side_effect fucntion.  Nor how to create equivalent
    # call objects for calls to methods of attributes of a higher object,
    # but these need to be attached to the higher object so that something
    # records the call order, as that is the point of this test.
    #
    # So we just compare to the string format of the call objects as
    # that is entirely predictable.
    call_list = [unicode(c) for c in helper.method_calls]
    assert call_list == ['call.first.commit_to_display()',
                         'call.second.commit_to_display()',
                         'call.third.commit_to_display()']
