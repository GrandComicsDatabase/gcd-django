# -*- coding: utf-8 -*-

import pytest
import mock

from apps.oi.models import BrandRevision


@pytest.mark.django_db
def test_create_add_revision(any_added_brand_rev, brand_add_values,
                             any_added_brand_group1,
                             any_adding_changeset, keywords):
    br = any_added_brand_rev

    for k, v in brand_add_values.iteritems():
        assert getattr(br, k) == v
    groups = list(br.group.order_by('id'))
    assert groups == [any_added_brand_group1]
    assert br.brand is None

    assert br.changeset == any_adding_changeset

    assert br.source is None
    assert br.source_name == 'brand'


@pytest.mark.django_db
def test_commit_added_revision(any_added_brand_rev, brand_add_values,
                               any_added_brand_group1,
                               keywords):
    br = any_added_brand_rev
    with mock.patch('apps.oi.models.update_count') as updater:
        br.commit_to_display()
    assert updater.called_once_with('brands', 1)

    assert br.brand is not None
    assert br.source is br.brand

    for k, v in brand_add_values.iteritems():
        if k == 'keywords':
            pub_kws = [k for k in br.brand.keywords.names()]
            pub_kws.sort()
            assert pub_kws == keywords['list']
        else:
            assert getattr(br.brand, k) == v
    groups = list(br.brand.group.order_by('id'))
    assert groups == [any_added_brand_group1]
    assert br.brand.issue_count == 0


@pytest.mark.django_db
def test_create_edit_revision(any_added_brand, brand_add_values,
                              any_added_brand_group1,
                              any_editing_changeset, keywords):
    br = BrandRevision.clone(
        data_object=any_added_brand,
        changeset=any_editing_changeset)

    for k, v in brand_add_values.iteritems():
        assert getattr(br, k) == v
    assert br.brand is any_added_brand
    groups = list(br.group.order_by('id'))
    assert groups == [any_added_brand_group1]

    assert br.changeset == any_editing_changeset

    assert br.source is any_added_brand
    assert br.source_name == 'brand'
