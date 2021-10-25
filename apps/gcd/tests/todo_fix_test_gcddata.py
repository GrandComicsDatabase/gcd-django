# -*- coding: utf-8 -*-



import mock
import pytest

from apps.gcd.models.gcddata import GcdBase, GcdData, GcdLink

GCDDATA = 'apps.gcd.models.gcddata'
REVMGR = 'apps.oi.models.RevisionManager'


@pytest.mark.parametrize('revisions, dependents', [
    (True, True), (True, False), (False, True), (False, False)
])
def test_deletable(revisions, dependents):
    with mock.patch('%s.GcdBase.has_dependents' % GCDDATA) as dep_mock:
        dep_mock.return_value = dependents
        base = GcdBase()
        base.revisions = mock.MagicMock()
        base.revisions.active_set.return_value.exists.return_value = revisions

        deletable = base.deletable()
        assert deletable is not any((revisions, dependents))


def test_has_dependents():
    assert GcdBase().has_dependents() is False


def test_stat_counts():
    assert GcdBase().stat_counts() == {}


def test_update_cached_counts():
    # Just make sure it doesn't blow up or return anything.
    assert GcdBase().update_cached_counts({}) is None


def test_data_delete():
    with mock.patch('django.db.models.Model.save') as save_mock, \
            mock.patch('django.db.models.Model.delete') as del_mock:
        data = GcdData(deleted=False)

        data.delete()

        # We intercept delete calls as we do not ever delete data objects.
        assert not del_mock.called
        assert data.deleted is True
        save_mock.assert_called_once_with()
