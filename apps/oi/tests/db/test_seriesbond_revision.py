# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import pytest
import mock

from apps.gcd.models import SeriesBond
from apps.oi.models import SeriesBondRevision


@pytest.mark.django_db
def test_create_add_revision(any_added_series_bond_rev, series_bond_add_values,
                             any_adding_changeset):
    sbr = any_added_series_bond_rev

    for k, v in series_bond_add_values.iteritems():
        assert getattr(sbr, k) == v

    assert sbr.series_bond is None
    assert sbr.previous_revision is None
    assert sbr.changeset == any_adding_changeset

    assert sbr.source is None
    assert sbr.source_name == 'series_bond'
    assert sbr.source_class is SeriesBond


@pytest.mark.django_db
def test_commit_added_revision(any_added_series_bond_rev,
                               series_bond_add_values,
                               any_adding_changeset):
    sbr = any_added_series_bond_rev

    with mock.patch('apps.oi.models.SeriesBondRevision.save') as mock_save:
        sbr.commit_to_display()

    assert mock_save.called_once_with()
    assert sbr.source is sbr.series_bond

    for k, v in series_bond_add_values.iteritems():
        assert getattr(sbr.series_bond, k) == v


@pytest.mark.django_db
def test_create_edit_revision(any_added_series_bond, series_bond_add_values,
                              any_added_series_bond_rev,
                              any_editing_changeset):
    sbr = SeriesBondRevision.clone(data_object=any_added_series_bond,
                                   changeset=any_editing_changeset)

    assert sbr.previous_revision == any_added_series_bond_rev
    for k, v in series_bond_add_values.iteritems():
        assert getattr(sbr, k) == v

    assert sbr.series_bond is any_added_series_bond
    assert sbr.changeset == any_editing_changeset

    assert sbr.source is any_added_series_bond


@pytest.mark.django_db
def test_delete_series_bond(any_added_series_bond, any_deleting_changeset,
                            any_added_series_bond_rev, series_bond_add_values):
    sbr = SeriesBondRevision.clone(data_object=any_added_series_bond,
                                   changeset=any_deleting_changeset)

    assert sbr.previous_revision == any_added_series_bond_rev
    series_bond_id = sbr.series_bond_id
    sbr.deleted = True

    # TODO: Pre-refactor code relies on the revision having been saved
    #       at least once before committing.  Take this out after refactor?
    sbr.save()
    sbr.refresh_from_db()

    # We do not mock out the saving in this case because we want to
    # see that the revision unhook actually made it through to the database.
    sbr.commit_to_display()

    # Ensure new read of saved row.
    # refresh_from_db apparently does not refresh all related objects.
    sbr.refresh_from_db()
    sbr.previous_revision.refresh_from_db()

    assert sbr.deleted is True
    assert sbr.series_bond is None
    assert sbr.previous_revision.series_bond is None
    assert SeriesBond.objects.filter(id=series_bond_id).count() == 0
