# -*- coding: utf-8 -*-

import pytest
import mock

from apps.oi.models import BrandGroupRevision


@pytest.mark.django_db
def test_create_add_revision(any_added_brand_group_rev1,
                             brand_group_add_values,
                             any_adding_changeset, keywords):
    rev = any_added_brand_group_rev1

    for k, v in brand_group_add_values.items():
        assert getattr(rev, k) == v
    assert rev.brand_group is None

    assert rev.changeset == any_adding_changeset

    assert rev.source is None
    assert rev.source_name == 'brand_group'


@pytest.mark.django_db
def test_commit_added_revision(any_added_brand_group_rev1,
                               brand_group_add_values,
                               keywords):
    rev = any_added_brand_group_rev1
    update_all = 'apps.stats.models.CountStats.objects.update_all_counts'
    with mock.patch(update_all) as updater:
        rev.commit_to_display()

    # BrandGroups are not counted in the site stats
    updater.assert_has_calls([
    ])
    assert updater.call_count == 0

    assert rev.brand_group is not None
    assert rev.source is rev.brand_group

    for k, v in brand_group_add_values.items():
        if k == 'keywords':
            pub_kws = [k for k in rev.brand_group.keywords.names()]
            pub_kws.sort()
            assert pub_kws == keywords['list']
        else:
            assert getattr(rev.brand_group, k) == v
    assert rev.brand_group.issue_count == 0


@pytest.mark.django_db
def test_create_edit_revision(any_added_brand_group1, brand_group_add_values,
                              any_editing_changeset, keywords):
    rev = BrandGroupRevision.clone(
        data_object=any_added_brand_group1,
        changeset=any_editing_changeset)

    for k, v in brand_group_add_values.items():
        assert getattr(rev, k) == v
    assert rev.brand_group is any_added_brand_group1

    assert rev.changeset == any_editing_changeset

    assert rev.source is any_added_brand_group1
    assert rev.source_name == 'brand_group'
