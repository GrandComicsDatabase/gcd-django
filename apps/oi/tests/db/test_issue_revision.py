# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import mock
import pytest

from apps.gcd.models import Issue
from apps.oi.models import IssueRevision


@pytest.mark.django_db
def test_create_add_revision(any_added_issue_rev, issue_add_values,
                             any_adding_changeset):
    rev = any_added_issue_rev
    for k, v in issue_add_values.iteritems():
        assert getattr(rev, k) == v

    assert rev.issue is None
    assert rev.previous_revision is None
    assert rev.changeset == any_adding_changeset
    assert rev.date_inferred is False

    assert rev.source is None
    assert rev.source_name == 'issue'
    assert rev.source_class is Issue


@pytest.mark.django_db
def test_create_add_variant_revision(any_added_variant_rev, variant_add_values,
                                     any_variant_adding_changeset):
    rev = any_added_variant_rev
    for k, v in variant_add_values.iteritems():
        assert getattr(rev, k) == v

    assert rev.issue is None
    assert rev.previous_revision is None
    assert rev.changeset == any_variant_adding_changeset
    assert rev.date_inferred is False

    assert rev.source is None
    assert rev.source_name == 'issue'
    assert rev.source_class is Issue


@pytest.mark.django_db
def test_commit_added_revision(any_added_issue_rev, issue_add_values,
                               any_adding_changeset, keywords):
    rev = any_added_issue_rev

    old_series_issue_count = rev.series.issue_count
    old_ind_pub_issue_count = rev.indicia_publisher.issue_count
    old_brand_issue_count = rev.brand.issue_count
    old_publisher_issue_count = rev.series.publisher.issue_count

    with mock.patch('apps.oi.helpers.CountStats.objects.update_count') \
            as updater_mock:
        rev.commit_to_display()

    updater_mock.assert_called_once_with('issues', 1,
                                         language=rev.series.language,
                                         country=rev.series.country)
    assert rev.issue is not None
    assert rev.source is rev.issue

    for k, v in issue_add_values.iteritems():
        if k == 'keywords':
            kws = [k for k in rev.issue.keywords.names()]
            kws.sort()
            assert kws == keywords['list']
        else:
            assert getattr(rev.issue, k) == v

    rev.issue.refresh_from_db()
    rev.issue.series.refresh_from_db()
    rev.issue.series.publisher.refresh_from_db()
    rev.issue.indicia_publisher.refresh_from_db()
    rev.issue.brand.refresh_from_db()

    s = rev.issue.series
    assert s.issue_count == old_series_issue_count + 1
    assert s.publisher.issue_count == old_publisher_issue_count + 1
    assert rev.issue.brand.issue_count == old_brand_issue_count + 1
    assert rev.issue.indicia_publisher.issue_count == \
        old_ind_pub_issue_count + 1


@pytest.mark.django_db
def test_commit_variant_added_revision(any_added_variant_rev,
                                       variant_add_values,
                                       any_adding_changeset, keywords):
    # any_added_variant_rev.save()
    # rev = IssueRevision.objects.get(pk=any_added_variant_rev.pk)
    rev = any_added_variant_rev

    old_series_issue_count = rev.series.issue_count
    old_ind_pub_issue_count = rev.indicia_publisher.issue_count
    old_brand_issue_count = rev.brand.issue_count
    old_publisher_issue_count = rev.series.publisher.issue_count

    with mock.patch('apps.oi.helpers.CountStats.objects.update_count') \
            as updater_mock:
        rev.commit_to_display()

    updater_mock.assert_called_once_with('variant issues', 1,
                                         language=rev.series.language,
                                         country=rev.series.country)
    assert rev.issue is not None
    assert rev.source is rev.issue

    for k, v in variant_add_values.iteritems():
        if k == 'keywords':
            kws = [k for k in rev.issue.keywords.names()]
            kws.sort()
            assert kws == keywords['list']
        else:
            assert getattr(rev.issue, k) == v

    rev.issue.refresh_from_db()
    rev.issue.series.refresh_from_db()
    rev.issue.series.publisher.refresh_from_db()
    rev.issue.indicia_publisher.refresh_from_db()
    rev.issue.brand.refresh_from_db()

    s = rev.issue.series
    # Variants do not affect the issue counts.
    assert s.issue_count == old_series_issue_count
    assert s.publisher.issue_count == old_publisher_issue_count
    assert rev.issue.brand.issue_count == old_brand_issue_count
    assert rev.issue.indicia_publisher.issue_count == old_ind_pub_issue_count


@pytest.mark.django_db
def test_create_edit_revision(any_added_issue, issue_add_values,
                              any_editing_changeset):
    rev = IssueRevision.clone(data_object=any_added_issue,
                              changeset=any_editing_changeset)

    for k, v in issue_add_values.iteritems():
        assert getattr(rev, k) == v

    assert rev.issue is any_added_issue
    assert rev.source is rev.issue
    assert rev.changeset is any_editing_changeset
    assert rev.date_inferred is False


@pytest.mark.django_db
def test_create_variant_edit_revision(any_added_variant, variant_add_values,
                                      any_editing_changeset):
    rev = IssueRevision.clone(data_object=any_added_variant,
                              changeset=any_editing_changeset)

    for k, v in variant_add_values.iteritems():
        assert getattr(rev, k) == v

    assert rev.issue is any_added_variant
    assert rev.source is rev.issue
    assert rev.changeset is any_editing_changeset
    assert rev.date_inferred is False


@pytest.mark.django_db
def test_delete_issue(any_added_issue, any_deleting_changeset,
                      any_added_issue_rev):
    rev = IssueRevision.clone(data_object=any_added_issue,
                              changeset=any_deleting_changeset)
    rev.deleted = True

    # TODO: Pre-refactor code relies on the revision having been saved
    #       at least once before committing.  Take this out after refactor?
    rev.save()
    # refresh_from_db() doesn't refresh linked objects, so this is easier.
    rev = IssueRevision.objects.get(pk=rev.pk)
    old_issue = Issue.objects.get(pk=rev.issue.pk)

    old_series_issue_count = rev.series.issue_count
    old_ind_pub_issue_count = rev.indicia_publisher.issue_count
    old_brand_issue_count = rev.brand.issue_count
    old_publisher_issue_count = rev.series.publisher.issue_count

    rev.commit_to_display()

    # Ensure new read of saved row.
    # refresh_from_db() doesn't refresh linked objects, so this is easier.
    rev = IssueRevision.objects.get(pk=rev.pk)

    assert rev.deleted is True
    assert rev.issue == old_issue
    assert rev.issue.deleted is True
    assert rev.previous_revision.issue == old_issue

    s = rev.issue.series
    assert s.issue_count == old_series_issue_count - 1
    assert s.publisher.issue_count == old_publisher_issue_count - 1
    assert rev.issue.brand.issue_count == old_brand_issue_count - 1
    assert rev.issue.indicia_publisher.issue_count == \
        old_ind_pub_issue_count - 1


@pytest.mark.django_db
def test_delete_variant(any_added_variant, any_deleting_changeset,
                        any_added_variant_rev):
    rev = IssueRevision.clone(data_object=any_added_variant,
                              changeset=any_deleting_changeset)
    rev.deleted = True

    # TODO: Pre-refactor code relies on the revision having been saved
    #       at least once before committing.  Take this out after refactor?
    rev.save()
    # refresh_from_db() doesn't refresh linked objects, so this is easier.
    rev = IssueRevision.objects.get(pk=rev.pk)
    old_issue = Issue.objects.get(pk=rev.issue.pk)

    old_series_issue_count = rev.series.issue_count
    old_ind_pub_issue_count = rev.indicia_publisher.issue_count
    old_brand_issue_count = rev.brand.issue_count
    old_publisher_issue_count = rev.series.publisher.issue_count

    rev.commit_to_display()

    # Ensure new read of saved row.
    # refresh_from_db() doesn't refresh linked objects, so this is easier.
    rev = IssueRevision.objects.get(pk=rev.pk)

    assert rev.deleted is True
    assert rev.issue == old_issue
    assert rev.issue.deleted is True
    assert rev.previous_revision.issue == old_issue

    s = rev.issue.series
    # Variants do not affect issue counts.
    assert s.issue_count == old_series_issue_count
    assert s.publisher.issue_count == old_publisher_issue_count
    assert rev.issue.brand.issue_count == old_brand_issue_count
    assert rev.issue.indicia_publisher.issue_count == old_ind_pub_issue_count
