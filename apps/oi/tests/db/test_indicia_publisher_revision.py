# -*- coding: utf-8 -*-


import pytest
import mock

from apps.oi.models import IndiciaPublisherRevision


@pytest.mark.django_db
def test_create_add_revision(any_added_indicia_publisher_rev,
                             indicia_publisher_add_values,
                             any_adding_changeset, keywords):
    rev = any_added_indicia_publisher_rev

    for k, v in indicia_publisher_add_values.items():
        assert getattr(rev, k) == v
    assert rev.indicia_publisher is None

    assert rev.changeset == any_adding_changeset

    assert rev.source is None
    assert rev.source_name == 'indicia_publisher'


@pytest.mark.django_db
def test_commit_added_revision(any_added_indicia_publisher_rev,
                               indicia_publisher_add_values,
                               keywords):
    rev = any_added_indicia_publisher_rev
    update_all = 'apps.oi.models.CountStats.objects.update_all_counts'
    with mock.patch(update_all) as updater:
        rev.commit_to_display()

    updater.assert_has_calls([
    ])
    assert updater.call_count == 0

    assert rev.indicia_publisher is not None
    assert rev.source is rev.indicia_publisher

    for k, v in indicia_publisher_add_values.items():
        if k == 'keywords':
            pub_kws = [k for k in rev.indicia_publisher.keywords.names()]
            pub_kws.sort()
            assert pub_kws == keywords['list']
        else:
            assert getattr(rev.indicia_publisher, k) == v
    assert rev.indicia_publisher.issue_count == 0


@pytest.mark.django_db
def test_create_edit_revision(any_added_indicia_publisher,
                              indicia_publisher_add_values,
                              any_editing_changeset, keywords):
    rev = IndiciaPublisherRevision.clone(
        data_object=any_added_indicia_publisher,
        changeset=any_editing_changeset)

    for k, v in indicia_publisher_add_values.items():
        assert getattr(rev, k) == v
    assert rev.indicia_publisher is any_added_indicia_publisher

    assert rev.changeset == any_editing_changeset

    assert rev.source is any_added_indicia_publisher
    assert rev.source_name == 'indicia_publisher'
