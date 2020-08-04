# -*- coding: utf-8 -*-

import pytest
import mock

from apps.oi.models import BrandUseRevision


@pytest.mark.django_db
def test_create_add_revision(any_added_brand_use_rev,
                             brand_use_add_values,
                             any_adding_changeset):
    rev = any_added_brand_use_rev

    for k, v in brand_use_add_values.items():
        assert getattr(rev, k) == v
    assert rev.brand_use is None

    assert rev.changeset == any_adding_changeset

    assert rev.source is None
    assert rev.source_name == 'brand_use'


@pytest.mark.django_db
def test_commit_added_revision(any_added_brand_use_rev,
                               brand_use_add_values):
    rev = any_added_brand_use_rev
    update_all = 'apps.oi.models.CountStats.objects.update_all_counts'
    with mock.patch(update_all) as updater:
        rev.commit_to_display()

    # We do not currently track statistics for brand uses.
    assert not updater.called

    assert rev.brand_use is not None
    assert rev.source is rev.brand_use

    for k, v in brand_use_add_values.items():
        assert getattr(rev.brand_use, k) == v


@pytest.mark.django_db
def test_create_edit_revision(any_added_brand_use, brand_use_add_values,
                              any_editing_changeset):
    rev = BrandUseRevision.clone(
        data_object=any_added_brand_use,
        changeset=any_editing_changeset)

    for k, v in brand_use_add_values.items():
        assert getattr(rev, k) == v
    assert rev.brand_use is any_added_brand_use

    assert rev.changeset == any_editing_changeset

    assert rev.source is any_added_brand_use
    assert rev.source_name == 'brand_use'
