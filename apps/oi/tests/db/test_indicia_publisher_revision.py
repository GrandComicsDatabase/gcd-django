# -*- coding: utf-8 -*-

import pytest
import mock

from apps.oi.models import IndiciaPublisherRevision


@pytest.mark.django_db
def test_create_add_revision(any_added_indicia_publisher_rev,
                             indicia_publisher_add_values,
                             any_adding_changeset, keywords):
    ipr = any_added_indicia_publisher_rev

    for k, v in indicia_publisher_add_values.iteritems():
        assert getattr(ipr, k) == v
    assert ipr.indicia_publisher is None

    assert ipr.changeset == any_adding_changeset

    assert ipr.source is None
    assert ipr.source_name == 'indicia_publisher'


@pytest.mark.django_db
def test_commit_added_revision(any_added_indicia_publisher_rev,
                               indicia_publisher_add_values,
                               keywords):
    ipr = any_added_indicia_publisher_rev
    with mock.patch('apps.oi.models.update_count') as updater:
        ipr.commit_to_display()
    assert updater.called_once_with('indicia_publishers', 1, ipr.country)

    assert ipr.indicia_publisher is not None
    assert ipr.source is ipr.indicia_publisher

    for k, v in indicia_publisher_add_values.iteritems():
        if k == 'keywords':
            pub_kws = [k for k in ipr.indicia_publisher.keywords.names()]
            pub_kws.sort()
            assert pub_kws == keywords['list']
        else:
            assert getattr(ipr.indicia_publisher, k) == v
    assert ipr.indicia_publisher.issue_count == 0


@pytest.mark.django_db
def test_create_edit_revision(any_added_indicia_publisher,
                              indicia_publisher_add_values,
                              any_editing_changeset, keywords):
    ipr = IndiciaPublisherRevision.clone(
        data_object=any_added_indicia_publisher,
        changeset=any_editing_changeset)

    for k, v in indicia_publisher_add_values.iteritems():
        assert getattr(ipr, k) == v
    assert ipr.indicia_publisher is any_added_indicia_publisher

    assert ipr.changeset == any_editing_changeset

    assert ipr.source is any_added_indicia_publisher
    assert ipr.source_name == 'indicia_publisher'
