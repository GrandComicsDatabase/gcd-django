# -*- coding: utf-8 -*-

import pytest
import mock

from apps.oi.models import BrandRevision


@pytest.mark.django_db
def test_create_add_revision(any_added_brand_rev, brand_add_values,
                             any_added_brand_group1,
                             any_adding_changeset, keywords):
    rev = any_added_brand_rev

    for k, v in brand_add_values.items():
        assert getattr(rev, k) == v
    groups = list(rev.group.order_by('id'))
    assert groups == [any_added_brand_group1]
    assert rev.brand is None

    assert rev.changeset == any_adding_changeset

    assert rev.source is None
    assert rev.source_name == 'brand'


@pytest.mark.django_db
def test_commit_added_revision(any_added_brand_rev, brand_add_values,
                               any_added_brand_group1,
                               keywords):
    rev = any_added_brand_rev
    update_all = 'apps.oi.models.CountStats.objects.update_all_counts'
    with mock.patch(update_all) as updater:
        rev.commit_to_display()

    updater.assert_has_calls([
    ])
    assert updater.call_count == 0

    assert rev.brand is not None
    assert rev.source is rev.brand

    for k, v in brand_add_values.items():
        if k == 'keywords':
            pub_kws = [k for k in rev.brand.keywords.names()]
            pub_kws.sort()
            assert pub_kws == keywords['list']
        else:
            assert getattr(rev.brand, k) == v
    groups = list(rev.brand.group.order_by('id'))
    assert groups == [any_added_brand_group1]
    assert rev.brand.issue_count == 0


@pytest.mark.django_db
def test_create_edit_revision(any_added_brand, brand_add_values,
                              any_added_brand_group1,
                              any_editing_changeset, keywords):
    rev = BrandRevision.clone(
        data_object=any_added_brand,
        changeset=any_editing_changeset)

    for k, v in brand_add_values.items():
        assert getattr(rev, k) == v
    assert rev.brand is any_added_brand
    groups = list(rev.group.order_by('id'))
    assert groups == [any_added_brand_group1]

    assert rev.changeset == any_editing_changeset

    assert rev.source is any_added_brand
    assert rev.source_name == 'brand'
