# -*- coding: utf-8 -*-

import pytest
import mock

from apps.oi.models import PublisherRevision


@pytest.mark.django_db
def test_create_add_revision(any_added_publisher_rev, publisher_add_values,
                             any_changeset, keywords):
    pr = any_added_publisher_rev

    for k, v in publisher_add_values.iteritems():
        assert getattr(pr, k) == v
    assert pr.publisher is None

    assert pr.changeset == any_changeset
    assert pr.date_inferred is False

    assert pr.source is None
    assert pr.source_name == 'publisher'


@pytest.mark.django_db
def test_commit_added_revision(any_added_publisher_rev, publisher_add_values,
                               keywords):
    pr = any_added_publisher_rev
    with mock.patch('apps.oi.models.update_count') as updater:
        pr.commit_to_display()
    assert updater.called_once_with('publishers', 1, pr.country)

    assert pr.publisher is not None
    assert pr.source is pr.publisher

    for k, v in publisher_add_values.iteritems():
        if k == 'keywords':
            pub_kws = [k for k in pr.publisher.keywords.names()]
            pub_kws.sort()
            assert pub_kws == keywords['list']
        else:
            assert getattr(pr.publisher, k) == v
    assert pr.publisher.brand_count == 0
    assert pr.publisher.series_count == 0
    assert pr.publisher.issue_count == 0


@pytest.mark.django_db
def test_create_edit_revision(any_added_publisher, publisher_add_values,
                              any_changeset, keywords):
    pr = PublisherRevision.objects.clone_revision(
        instance=any_added_publisher,
        changeset=any_changeset)

    for k, v in publisher_add_values.iteritems():
        assert getattr(pr, k) == v
    assert pr.publisher is any_added_publisher

    assert pr.changeset == any_changeset
    assert pr.date_inferred is False

    assert pr.source is any_added_publisher
    assert pr.source_name == 'publisher'
