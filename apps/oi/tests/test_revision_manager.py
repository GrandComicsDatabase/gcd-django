# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import mock
import pytest

from apps.oi import models


def test_clone_revision_positive():
    mgr = models.RevisionManager()
    mgr._do_create_revision = mock.Mock()

    rev = mock.MagicMock(spec=models.Revision)
    mgr._do_create_revision.return_value = rev
    changeset = mock.MagicMock(spec=models.Changeset)

    test_object = 'any string'
    r = mgr.clone_revision(instance=test_object,
                           changeset=changeset)
    mgr._do_create_revision.assert_called_once_with(test_object,
                                                    changeset=changeset)
    assert r is rev


def test_assignable_field_list():
    with pytest.raises(NotImplementedError):
        models.RevisionManager.assignable_field_list()
