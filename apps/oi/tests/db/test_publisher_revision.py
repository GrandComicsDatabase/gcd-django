# -*- coding: utf-8 -*-

import pytest
import mock

from apps.oi.models import PublisherRevision


@pytest.mark.django_db
def test_create_add_revision(any_added_publisher_rev, publisher_add_values,
                             any_adding_changeset, keywords):
    rev = any_added_publisher_rev

    for k, v in publisher_add_values.items():
        assert getattr(rev, k) == v
    assert rev.publisher is None

    assert rev.changeset == any_adding_changeset
    assert rev.date_inferred is False

    assert rev.source is None
    assert rev.source_name == 'publisher'


@pytest.mark.django_db
def test_commit_added_revision(any_added_publisher_rev, publisher_add_values,
                               keywords):
    rev = any_added_publisher_rev
    update_all = 'apps.stats.models.CountStats.objects.update_all_counts'
    with mock.patch(update_all) as updater:
        rev.commit_to_display()

    updater.assert_has_calls([
        mock.call({}, country=None, language=None, negate=True),
        mock.call({'publishers': 1},
                  country=rev.publisher.country, language=None),
    ])
    assert updater.call_count == 2

    assert rev.publisher is not None
    assert rev.source is rev.publisher

    for k, v in publisher_add_values.items():
        if k == 'keywords':
            pub_kws = [k for k in rev.publisher.keywords.names()]
            pub_kws.sort()
            assert pub_kws == keywords['list']
        else:
            assert getattr(rev.publisher, k) == v
    assert rev.publisher.brand_count == 0
    assert rev.publisher.series_count == 0
    assert rev.publisher.issue_count == 0


@pytest.mark.django_db
def test_create_edit_revision(any_added_publisher, publisher_add_values,
                              any_editing_changeset, keywords):
    rev = PublisherRevision.clone(
        data_object=any_added_publisher,
        changeset=any_editing_changeset)

    for k, v in publisher_add_values.items():
        assert getattr(rev, k) == v
    assert rev.publisher is any_added_publisher

    assert rev.changeset == any_editing_changeset
    assert rev.date_inferred is False

    assert rev.source is any_added_publisher
    assert rev.source_name == 'publisher'
