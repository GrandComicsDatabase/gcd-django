# -*- coding: utf-8 -*-

import pytest
import mock

from apps.oi.models import BrandGroupRevision


@pytest.mark.django_db
def test_create_add_revision(any_added_brand_group_rev1,
                             brand_group_add_values,
                             any_changeset, keywords):
    bgr = any_added_brand_group_rev1

    for k, v in brand_group_add_values.iteritems():
        assert getattr(bgr, k) == v
    assert bgr.brand_group is None

    assert bgr.changeset == any_changeset

    assert bgr.source is None
    assert bgr.source_name == 'brand_group'


@pytest.mark.django_db
def test_commit_added_revision(any_added_brand_group_rev1,
                               brand_group_add_values,
                               keywords):
    bgr = any_added_brand_group_rev1
    with mock.patch('apps.oi.models.update_count') as updater:
        bgr.commit_to_display()
    assert updater.called_once_with('brand_groups', 1)

    assert bgr.brand_group is not None
    assert bgr.source is bgr.brand_group

    for k, v in brand_group_add_values.iteritems():
        if k == 'keywords':
            pub_kws = [k for k in bgr.brand_group.keywords.names()]
            pub_kws.sort()
            assert pub_kws == keywords['list']
        else:
            assert getattr(bgr.brand_group, k) == v
    assert bgr.brand_group.issue_count == 0


@pytest.mark.django_db
def test_create_edit_revision(any_added_brand_group1, brand_group_add_values,
                              any_changeset, keywords):
    bgr = BrandGroupRevision.objects.clone_revision(
        instance=any_added_brand_group1,
        changeset=any_changeset)

    for k, v in brand_group_add_values.iteritems():
        assert getattr(bgr, k) == v
    assert bgr.brand_group is any_added_brand_group1

    assert bgr.changeset == any_changeset

    assert bgr.source is any_added_brand_group1
    assert bgr.source_name == 'brand_group'
