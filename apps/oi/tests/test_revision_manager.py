# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import mock
import pytest

from apps.oi import models


# Make a non-abstract class that acts like a Revision, but can have
# a manager, i.e. DummyRevision.objects.
class DummyRevision(models.Revision):
    pass


def test_clone_revision_positive():
    DummyRevision.objects._do_create_revision = mock.Mock()

    rev = mock.MagicMock(spec=models.Revision)
    DummyRevision.objects._do_create_revision.return_value = rev
    changeset = mock.MagicMock(spec=models.Changeset)

    test_object = 'any string'
    r = DummyRevision.objects.clone_revision(instance=test_object,
                                             changeset=changeset)
    DummyRevision.objects._do_create_revision.assert_called_once_with(
        test_object, changeset=changeset)
    assert r is rev


def test_assignable_field_list():
    with pytest.raises(NotImplementedError):
        DummyRevision.objects.assignable_field_list()
