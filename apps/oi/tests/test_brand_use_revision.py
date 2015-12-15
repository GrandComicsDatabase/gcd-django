# -*- coding: utf-8 -*-

import pytest
import mock

from apps.oi.models import BrandUseRevision


@pytest.mark.django_db
def test_create_add_revision(any_added_brand_use_rev,
                             brand_use_add_values,
                             any_changeset):
    bur = any_added_brand_use_rev

    for k, v in brand_use_add_values.iteritems():
        assert getattr(bur, k) == v
    assert bur.brand_use is None

    assert bur.changeset == any_changeset

    assert bur.source is None
    assert bur.source_name == 'brand_use'


@pytest.mark.django_db
def test_commit_added_revision(any_added_brand_use_rev,
                               brand_use_add_values):
    bur = any_added_brand_use_rev
    with mock.patch('apps.oi.models.update_count') as updater:
        bur.commit_to_display()
    assert updater.called_once_with('brand_uses', 1)

    assert bur.brand_use is not None
    assert bur.source is bur.brand_use

    for k, v in brand_use_add_values.iteritems():
        assert getattr(bur.brand_use, k) == v


@pytest.mark.django_db
def test_create_edit_revision(any_added_brand_use, brand_use_add_values,
                              any_changeset):
    bur = BrandUseRevision.objects.clone_revision(
        instance=any_added_brand_use,
        changeset=any_changeset)

    for k, v in brand_use_add_values.iteritems():
        assert getattr(bur, k) == v
    assert bur.brand_use is any_added_brand_use

    assert bur.changeset == any_changeset

    assert bur.source is any_added_brand_use
    assert bur.source_name == 'brand_use'
