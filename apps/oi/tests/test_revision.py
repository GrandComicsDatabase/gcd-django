# -*- coding: utf-8 -*-



import mock
import pytest

from apps.oi.models import Revision, RevisionManager, Changeset
from apps.stddata.models import Country, Language

from .dummy_models import (
    Dummy, DummyRevision, OtherDummy, OtherDummyRevision,
    SimpleSourceRevision, SimplestRevision)


def test_for_correct_manager():
    assert isinstance(DummyRevision.objects, RevisionManager)


def test_revision_init():
    rev = DummyRevision()
    assert rev.is_changed is False
    assert rev._regular_fields is None
    assert rev._irregular_fields is None
    assert rev._single_value_fields is None
    assert rev._multi_value_fields is None


def test_classify_fields():
    meta = Dummy._meta
    i = meta.get_field('i')
    b = meta.get_field('b')
    f = meta.get_field('f')
    o = meta.get_field('o')
    m = meta.get_field('m')
    z = meta.get_field('z')
    x = meta.get_field('x')
    c = meta.get_field('c')
    k = meta.get_field('keywords')

    rev = DummyRevision()
    rev._classify_fields()

    assert rev._regular_fields == {'i': i, 'b': b, 'f': f, 'o': o, 'm': m,
                                   'keywords': k}
    assert rev._irregular_fields == {'c': c, 'x': x}
    assert rev._single_value_fields == {'i': i, 'b': b, 'f': f, 'o': o}
    assert rev._multi_value_fields == {'m': m}
    assert rev._meta_fields == {'z': z}


def test_second_classify_fields():
    rev = DummyRevision()
    rev._classify_fields()
    rev._get_excluded_field_names = mock.MagicMock()
    rev._get_excluded_field_names.return_value = set()

    rev._classify_fields()

    # The first thing _classify_fields() does if it decides it needs
    # to run the whole classification is get the excluded field names.
    # So if this was not called, then the check for already having been
    # classified worked.
    assert not rev._get_excluded_field_names.called


@pytest.mark.parametrize('method', (Revision._get_regular_fields,
                                    Revision._get_irregular_fields,
                                    Revision._get_single_value_fields,
                                    Revision._get_multi_value_fields,
                                    Revision._get_meta_fields))
def test_classifying_methods(method):
    with mock.patch('apps.oi.models.Revision._classify_fields') as cl_mock:
        method()
        cl_mock.assert_called_once_with()


def test_excluded_fields():
    assert Revision._get_excluded_field_names() == frozenset({
        'id',
        'created',
        'modified',
        'deleted',
        'tagged_items',
        'image_resources',
    })


def test_conditional_fields():
    assert Revision._get_conditional_field_tuple_mapping() == {}


def test_parent_fields():
    assert Revision._get_parent_field_tuples() == frozenset()


def test_major_flags():
    assert Revision._get_major_flag_field_tuples() == frozenset()


def test_stats_category_field_tuples():
    assert Revision._get_stats_category_field_tuples() == set()


def test_deprecated_fields():
    assert Revision._get_deprecated_field_names() == frozenset()


def test_meta_fields():
    assert Revision._get_meta_field_names() == frozenset()


def test_added():
    rev = DummyRevision()
    added = rev.added
    assert added is True


def test_added_committed():
    rev = DummyRevision()
    rev.committed = True
    added = rev.added
    assert added is True


def test_not_added_because_previous_revision():
    rev = DummyRevision()
    rev.previous_revision = DummyRevision()
    added = rev.added
    assert added is False


def test_not_added_because_discarded():
    rev = DummyRevision()
    rev.committed = False
    added = rev.added
    assert added is False


def test_added_with_source():
    # We should no longer be checking for source.  This test is only here
    # to test that we have not regressed to the prior implementation.
    with mock.patch('apps.oi.models.Revision.source') as source_mock:
        rev = DummyRevision()
        added = rev.added
        assert not source_mock.__nonzero__.called
        assert added is True


def test_edited():
    rev = DummyRevision()
    rev.previous_revision = DummyRevision()
    edited = rev.edited
    assert edited is True


def test_edited_committed():
    rev = DummyRevision()
    rev.previous_revision = DummyRevision()
    rev.committed = True
    edited = rev.edited
    assert edited is True


def test_not_edited_because_added():
    rev = DummyRevision(deleted=True)
    edited = rev.edited
    assert edited is False


def test_not_edited_because_deleted():
    rev = DummyRevision(deleted=True)
    edited = rev.edited
    assert edited is False


def test_not_edited_because_discarded():
    rev = DummyRevision()
    rev.previous_revision = DummyRevision()
    rev.committed = False
    edited = rev.edited
    assert edited is False


def test_committed():
    rev = DummyRevision(committed=True)
    assert rev.open is False
    assert rev.discarded is False


def test_discarded():
    rev = DummyRevision(committed=False)
    assert rev.open is False
    assert rev.discarded is True


def test_open():
    rev = DummyRevision(committed=None)
    assert rev.open is True
    assert rev.discarded is False


def test_get_source():
    with pytest.raises(NotImplementedError):
        SimplestRevision().source


def test_set_source():
    with pytest.raises(NotImplementedError):
        SimplestRevision().source = object()


def test_source_class():
    assert Revision.source_class is NotImplemented
    assert DummyRevision.source_class is Dummy


#def test_source_name():
    #assert Revision.source_name is NotImplemented
    #assert DummyRevision.source_name == 'Dummy'


def test_get_major_changes():
    p = 'apps.oi.models.Revision._check_major_change'
    with mock.patch(p) as check_mock:
        # Make sure we return a valid dict.  Contents would be irrelevant.
        check_mock.side_effect = lambda tup: {}
        rev = DummyRevision()

        changes = rev._get_major_changes()

        assert changes == {}
        check_mock.assert_has_calls(
            [
                mock.call(('f',)),
                mock.call(('o',)),
                mock.call(('m',)),
                mock.call(('b',)),
            ],
            any_order=True,
        )
        assert check_mock.call_count == 4


def test_check_major_change_non_boolean():
    data = Dummy(i=1)
    rev = DummyRevision(dummy=data, i=2, previous_revision=DummyRevision())

    changes = rev._check_major_change(('i',))

    assert changes == {
        'i changed': True,
        'old i': 1,
        'new i': 2,
    }


def test_check_major_change_non_boolean_added():
    with mock.patch('apps.oi.models.Revision.previous_revision'):
        rev = DummyRevision(i=2)

        changes = rev._check_major_change(('i',))

        assert changes == {
            'i changed': True,
            'old i': None,
            'new i': 2,
        }


def test_check_major_change_boolean():
    data = Dummy(b=True)
    rev = DummyRevision(dummy=data, b=False, previous_revision=DummyRevision())

    changes = rev._check_major_change(('b',))

    assert changes == {
        'b changed': True,
        'to b': False,
        'from b': True,
    }


def test_check_major_change_boolean_deleted():
    data = Dummy(b=True)
    rev = DummyRevision(dummy=data, b=False, previous_revision=DummyRevision())
    rev.deleted = True

    changes = rev._check_major_change(('b',))

    assert changes == {
        'b changed': True,
        'to b': False,
        'from b': True,
    }


def test_check_major_change_no_changes():
    data = Dummy(b=True)
    rev = DummyRevision(dummy=data, b=True, previous_revision=DummyRevision())

    changes = rev._check_major_change(('b',))

    assert changes == {
        'b changed': False,
        'to b': False,
        'from b': False,
    }


@pytest.yield_fixture
def mock_update_all():
    with mock.patch(
            'apps.oi.models.CountStats.objects.update_all_counts') \
            as uac_mock:
        yield uac_mock


@pytest.yield_fixture
def patched_other_dummy():
    # Don't set a source- this way we can just fake the country/language stuff.
    # Note that OtherDummy.save must be patched before
    # OtherDummyRevision.other_dummy, as the new OtherDummy value must be
    # constructed under the patch.
    with mock.patch('apps.oi.tests.dummy_models.OtherDummy.save'), \
      mock.patch('apps.oi.tests.dummy_models.OtherDummyRevision.other_dummy',
                 new=OtherDummy()):
        # revision.other_dummy is mocked, so no need to set it in constructor.
        # attempting to set it without mocking triggers a database operation,
        # even if the object is never saved.
        yield OtherDummyRevision()


def test_adjust_stats_neither(mock_update_all, patched_other_dummy):
    rev = patched_other_dummy

    old_counts = {'foo': 1}
    new_counts = {'foo': 2}

    rev._adjust_stats({}, old_counts, new_counts)

    mock_update_all.assert_has_calls([
        mock.call(old_counts, country=None, language=None, negate=True),
        mock.call(new_counts, country=None, language=None)])
    assert mock_update_all.call_count == 2
    rev.source.save.assert_called_once_with()


def test_adjust_stats_both(mock_update_all, patched_other_dummy):
    rev = patched_other_dummy

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
    rev.source.save.assert_called_once_with()


def test_adjust_parent_counts_single(patched_other_dummy):
    rev = patched_other_dummy
    with mock.patch('apps.oi.relpath.RelPath.multi_valued', new=False), \
            mock.patch('apps.oi.relpath.RelPath.__init__', return_value=None):

        old_value = mock.MagicMock()
        new_value = mock.MagicMock()
        deltas = {'issues': 1}
        old_counts = {'issues': 10}
        new_counts = {'issues': 11}

        rev._adjust_parent_counts(
            ('foo',),
            {'foo changed': True, 'old foo': old_value, 'new foo': new_value},
            deltas, old_counts, new_counts,
        )

        old_value.update_cached_counts.assert_called_once_with(old_counts,
                                                               negate=True)
        old_value.save.assert_called_once_with()
        new_value.update_cached_counts.assert_called_once_with(new_counts)
        new_value.save.assert_called_once_with()


def test_adjust_parent_counts_single_no_change(patched_other_dummy):
    rev = patched_other_dummy
    with mock.patch('apps.oi.relpath.RelPath.multi_valued', new=False), \
            mock.patch('apps.oi.relpath.RelPath.__init__', return_value=None):

        # Values don't change, only counts.
        old_value = mock.MagicMock()
        new_value = old_value

        deltas = {'issues': 1}
        old_counts = {'issues': 10}
        new_counts = {'issues': 11}

        rev._adjust_parent_counts(
            ('foo',),
            {'foo changed': False, 'old foo': old_value, 'new foo': new_value},
            deltas, old_counts, new_counts,
        )

        new_value.update_cached_counts.assert_called_once_with(deltas)
        new_value.save.assert_called_once_with()


def test_adjust_parent_counts_multi(patched_other_dummy):
    rev = patched_other_dummy
    with mock.patch('apps.oi.relpath.RelPath.multi_valued', new=True), \
            mock.patch('apps.oi.relpath.RelPath.__init__', return_value=None):

        a, b, c, d = (mock.MagicMock(), mock.MagicMock(),
                      mock.MagicMock(), mock.MagicMock())
        old_value = {a, b, c}
        new_value = {d, b}
        deltas = {'issues': 1}
        old_counts = {'issues': 10}
        new_counts = {'issues': 11}

        rev._adjust_parent_counts(
            ('foo',),
            {'foo changed': True, 'old foo': old_value, 'new foo': new_value},
            deltas, old_counts, new_counts,
        )

        for o in old_value - new_value:
            o.update_cached_counts.assert_called_once_with(old_counts,
                                                           negate=True)
            o.save.assert_called_once_with()

        for n in new_value - old_value:
            n.update_cached_counts.assert_called_once_with(new_counts)
            n.save.assert_called_once_with()

        for i in new_value & old_value:
            i.update_cached_counts.assert_has_calls([
                mock.call(old_counts, negate=True),
                mock.call(new_counts),
            ])
            assert i.update_cached_counts.call_count == 2

            i.save.assert_has_calls([mock.call(), mock.call()])
            assert i.save.call_count == 2


def test_adjust_parent_counts_multi_no_change(patched_other_dummy):
    rev = patched_other_dummy
    with mock.patch('apps.oi.relpath.RelPath.multi_valued', new=True), \
            mock.patch('apps.oi.relpath.RelPath.__init__', return_value=None):

        a, b, c = (mock.MagicMock(), mock.MagicMock(), mock.MagicMock())
        old_value = frozenset({a, b, c})
        new_value = frozenset({a, b, c})
        deltas = {'issues': 1}
        old_counts = {'issues': 10}
        new_counts = {'issues': 11}

        rev._adjust_parent_counts(
            ('foo',),
            {'foo changed': False, 'old foo': old_value, 'new foo': new_value},
            deltas, old_counts, new_counts,
        )

        for v in new_value:
            v.update_cached_counts.assert_called_once_with(deltas)
            v.save.assert_called_once_with()


@pytest.yield_fixture
def patched_dummy():
    p = 'apps.oi.models.Revision'
    with mock.patch('%s._copy_fields_to' % p), \
            mock.patch('%s._pre_commit_check' % p), \
            mock.patch('%s._handle_prerequisites' % p), \
            mock.patch('%s._post_create_for_add' % p), \
            mock.patch('%s._post_assign_fields' % p), \
            mock.patch('%s._pre_save_object' % p), \
            mock.patch('%s._post_save_object' % p), \
            mock.patch('%s._handle_dependents' % p), \
            mock.patch('%s._get_major_changes' % p) as gmc_mock, \
            mock.patch('%s._adjust_stats' % p), \
            mock.patch('%s.save' % p), \
            mock.patch('%s.source' % p,
                       new_callable=mock.PropertyMock) as s_mock:

        changes = {'does not matter': True}
        gmc_mock.return_value = changes

        data_obj = mock.MagicMock()

        # Since our definition of added is based on previous_revision, we can
        # get away with source always returning the mocked data object.
        s_mock.return_value = data_obj
        rev = SimpleSourceRevision()

        yield rev, s_mock, data_obj, changes


def test_commit_added(patched_dummy):
    d, source, data_obj, changes = patched_dummy

    # Stats are only called on the thing returned from source after it is set.
    stats = {'whatever': 42}
    data_obj.stat_counts.return_value = stats

    d.commit_to_display()

    d._pre_commit_check.assert_called_once_with()
    d._get_major_changes.assert_called_once_with()
    d._handle_prerequisites.assert_called_once_with(changes)

    assert d.source.delete.called is False
    assert d.committed is True

    # We should have written the data_obj to source, among many read calls.
    source.assert_any_call(data_obj)
    d.save.assert_called_once_with()
    d._post_create_for_add.assert_called_once_with(changes)

    d._copy_fields_to.assert_called_once_with(d.source)
    d._post_assign_fields.assert_called_once_with(changes)

    d._pre_save_object.assert_called_once_with(changes)
    source.return_value.save.assert_called_once_with()

    # stat_counts only called once for add.
    d.source.stat_counts.assert_called_once_with()
    d._adjust_stats.assert_called_once_with(changes, {}, stats)
    d._handle_dependents.assert_called_once_with(changes)


def test_commit_deleted(patched_dummy):
    d, source, data_obj, changes = patched_dummy

    # Set up a pre-existing data obj, and then mark it as deleted.
    # Stats will be fetched twice in this scenario.
    d.previous_revision = SimpleSourceRevision()
    stats = ({'whatever': 42}, {'whatever': 100, 'other': 2})
    data_obj.stat_counts.side_effect = stats
    d.deleted = True

    d.commit_to_display()

    d._pre_commit_check.assert_called_once_with()
    d._get_major_changes.assert_called_once_with()
    d._handle_prerequisites.assert_called_once_with(changes)

    d.source.delete.assert_called_once_with()
    assert d.committed is True

    # Make sure we never re-assigned to source or did other add/edit stuff.
    assert mock.call(data_obj) not in source.calls
    d.save.assert_called_once_with()
    assert d._post_create_for_add.called is False
    assert d._copy_fields_to.called is False
    assert d._post_assign_fields.called is False

    d._pre_save_object.assert_called_once_with(changes)
    data_obj.save.assert_called_once_with()

    # stat_counts called twice for deletes, at beginning and end.
    d.source.stat_counts.has_calls([mock.call(), mock.call()])
    assert d.source.stat_counts.call_count == 2
    d._adjust_stats.assert_called_once_with(changes, stats[0], stats[1])
    d._handle_dependents.assert_called_once_with(changes)


def test_commit_edited_dont_clear(patched_dummy):
    d, source, data_obj, changes = patched_dummy

    # Set up a pre-existing data obj, making this an edit.
    # Stats will be called twice in this scenario.
    d.previous_revision = SimpleSourceRevision()
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
    d._handle_prerequisites.assert_called_once_with(changes)

    assert d.source.delete.called is False
    assert d.committed is True

    # Make sure we never re-assigned to source, but do copy fields for edit.
    assert mock.call(data_obj) not in source.calls
    d.save.assert_called_once_with()
    assert d._post_create_for_add.called is False
    d._copy_fields_to.assert_called_once_with(d.source)
    d._post_assign_fields.assert_called_once_with(changes)

    d._pre_save_object.assert_called_once_with(changes)
    data_obj.save.assert_called_once_with()

    # stat_counts called twice for deletes, at beginning and end.
    d.source.stat_counts.has_calls([mock.call(), mock.call()])
    assert d.source.stat_counts.call_count == 2
    d._adjust_stats.assert_called_once_with(changes, stats[0], stats[1])
    d._handle_dependents.assert_called_once_with(changes)


def test_pre_initial_save():
    assert DummyRevision()._pre_initial_save() is None


def test_post_m2m_add():
    assert DummyRevision()._post_m2m_add() is None


def test_clone_parameter_passthrough():
    with mock.patch('apps.oi.models.Revision._pre_initial_save',
                    return_value={}), \
            mock.patch('apps.oi.models.Revision._post_m2m_add',
                       return_value={}), \
            mock.patch('apps.oi.models.Revision.changeset'), \
            mock.patch('apps.oi.models.Revision.save'):
        exclude = {'whatever'}
        data_object = mock.MagicMock()
        data_object.keywords.all.return_value.order_by.return_value = {}
        rev = OtherDummyRevision.clone(data_object=data_object,
                                       changeset=Changeset(),
                                       fork=True,
                                       exclude=exclude)
        rev._pre_initial_save.assert_called_once_with(fork=True,
                                                      fork_source=data_object,
                                                      exclude=exclude)
        rev._post_m2m_add.assert_called_once_with(fork=True,
                                                  fork_source=data_object,
                                                  exclude=exclude)
