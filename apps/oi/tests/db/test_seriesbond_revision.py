# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import pytest
import mock

from apps.gcd.models import SeriesBond
from apps.oi.models import SeriesBondRevision


@pytest.mark.django_db
def test_create_add_revision(any_added_series_bond_rev, series_bond_add_values,
                             any_adding_changeset):
    rev = any_added_series_bond_rev

    for k, v in series_bond_add_values.iteritems():
        assert getattr(rev, k) == v

    assert rev.series_bond is None
    assert rev.previous_revision is None
    assert rev.changeset == any_adding_changeset

    assert rev.source is None
    assert rev.source_name == 'series_bond'
    assert rev.source_class is SeriesBond


@pytest.mark.django_db
def test_commit_added_revision(any_added_series_bond_rev,
                               series_bond_add_values,
                               any_adding_changeset):
    rev = any_added_series_bond_rev

    with mock.patch('apps.oi.models.SeriesBondRevision.save') as mock_save:
        rev.commit_to_display()

    mock_save.assert_called_once_with()
    assert rev.source is rev.series_bond

    for k, v in series_bond_add_values.iteritems():
        assert getattr(rev.series_bond, k) == v


@pytest.mark.django_db
def test_create_edit_revision(any_added_series_bond, series_bond_add_values,
                              any_added_series_bond_rev,
                              any_editing_changeset):
    rev = SeriesBondRevision.clone(data_object=any_added_series_bond,
                                   changeset=any_editing_changeset)

    assert rev.previous_revision == any_added_series_bond_rev
    for k, v in series_bond_add_values.iteritems():
        assert getattr(rev, k) == v

    assert rev.series_bond is any_added_series_bond
    assert rev.changeset == any_editing_changeset

    assert rev.source is any_added_series_bond


@pytest.mark.django_db
def test_delete_series_bond(any_added_series_bond, any_deleting_changeset,
                            any_added_series_bond_rev):
    rev = SeriesBondRevision.clone(data_object=any_added_series_bond,
                                   changeset=any_deleting_changeset)

    assert rev.previous_revision == any_added_series_bond_rev
    series_bond_id = rev.series_bond_id
    rev.deleted = True

    # TODO: Pre-refactor code relies on the revision having been saved
    #       at least once before committing.  Take this out after refactor?
    rev.save()
    rev.refresh_from_db()

    # We do not mock out the saving in this case because we want to
    # see that the revision unhook actually made it through to the database.
    rev.commit_to_display()

    # Ensure new read of saved row.
    # refresh_from_db apparently does not refresh all related objects.
    rev.refresh_from_db()
    rev.previous_revision.refresh_from_db()

    assert rev.deleted is True
    assert rev.series_bond is None
    assert rev.previous_revision.series_bond is None
    assert SeriesBond.objects.filter(id=series_bond_id).count() == 0
