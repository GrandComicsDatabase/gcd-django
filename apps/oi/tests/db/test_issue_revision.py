# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import mock
import pytest

from apps.gcd.models import Series, Issue
from apps.oi.models import Changeset, IssueRevision, CTYPES
from apps.oi import states


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
def test_create_add_more(any_added_issue, any_indexer):
    c1 = Changeset.objects.create(indexer=any_indexer,
                                  state=states.OPEN,
                                  change_type=CTYPES['issue_add'])
    any_added_issue = Issue.objects.get(pk=any_added_issue.pk)

    # With after=None, should insert the issue at the beginning.
    rev1 = IssueRevision(changeset=c1, series=any_added_issue.series)
    rev1.save()
    rev1.commit_to_display()

    # It's necessary to re-fetch (not just refresh) the various issues
    # to get the calculated sort codes loaded.
    original_issue = Issue.objects.get(pk=any_added_issue.pk)
    issue1 = Issue.objects.get(pk=rev1.issue.pk)

    assert issue1.sort_code < original_issue.sort_code

    c2 = Changeset.objects.create(indexer=any_indexer,
                                  state=states.OPEN,
                                  change_type=CTYPES['issue_add'])
    rev2 = IssueRevision(changeset=c2, series=any_added_issue.series,
                         after=rev1.issue)
    rev2.save()
    rev2.commit_to_display()

    # Again, re-fetch all the things.
    original_issue = Issue.objects.get(pk=any_added_issue.pk)
    issue1 = Issue.objects.get(pk=rev1.issue.pk)
    issue2 = Issue.objects.get(pk=rev2.issue.pk)

    assert issue2.sort_code < original_issue.sort_code
    assert issue1.sort_code < issue2.sort_code


@pytest.mark.django_db
def test_commit_added_revision(any_added_issue_rev, issue_add_values,
                               any_adding_changeset, keywords):
    rev = any_added_issue_rev

    old_series_issue_count = rev.series.issue_count
    old_ind_pub_issue_count = rev.indicia_publisher.issue_count
    old_brand_issue_count = rev.brand.issue_count
    old_publisher_issue_count = rev.series.publisher.issue_count
    old_brand_group_counts = {group.pk: group.issue_count
                              for group in rev.brand.group.all()}

    with mock.patch('apps.oi.helpers.CountStats.objects.update_count') \
            as updater_mock:
        rev.commit_to_display()

    updater_mock.assert_called_once_with(field='issues', delta=1,
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
    assert {
        group.pk: group.issue_count for group in rev.issue.brand.group.all()
    } == {k: v + 1 for k, v in old_brand_group_counts.iteritems()}
    assert rev.issue.indicia_publisher.issue_count == \
        old_ind_pub_issue_count + 1


@pytest.mark.django_db
def test_commit_variant_added_revision(any_added_variant_rev,
                                       variant_add_values,
                                       any_adding_changeset, keywords):
    rev = any_added_variant_rev

    old_series_issue_count = rev.series.issue_count
    old_ind_pub_issue_count = rev.indicia_publisher.issue_count
    old_brand_issue_count = rev.brand.issue_count
    old_brand_group_counts = {group.pk: group.issue_count
                              for group in rev.brand.group.all()}
    old_publisher_issue_count = rev.series.publisher.issue_count

    with mock.patch('apps.oi.helpers.CountStats.objects.update_count') \
            as updater_mock:
        rev.commit_to_display()

    updater_mock.assert_called_once_with(field='variant issues', delta=1,
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

    rev = IssueRevision.objects.get(pk=rev.pk)
    s = rev.issue.series
    # Variants do not affect the issue counts.
    assert s.issue_count == old_series_issue_count
    assert s.publisher.issue_count == old_publisher_issue_count
    assert rev.issue.brand.issue_count == old_brand_issue_count
    assert {group.pk: group.issue_count
            for group in rev.issue.brand.group.all()} == old_brand_group_counts
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
    old_brand_group_counts = {group.pk: group.issue_count
                              for group in rev.brand.group.all()}
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
    assert {
        group.pk: group.issue_count for group in rev.issue.brand.group.all()
    } == {k: v - 1 for k, v in old_brand_group_counts.iteritems()}
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
    old_brand_group_counts = {group.pk: group.issue_count
                              for group in rev.brand.group.all()}
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
    assert {group.pk: group.issue_count
            for group in rev.issue.brand.group.all()} == old_brand_group_counts
    assert rev.issue.indicia_publisher.issue_count == old_ind_pub_issue_count


@pytest.mark.django_db
def test_noncomics_counts(any_added_series_rev,
                          issue_add_values,
                          any_adding_changeset,
                          any_variant_adding_changeset,
                          any_deleting_changeset):
    # This is written out in long form because while it could be broken
    # up into fixtures and separate cases, it is only this one specific
    # sequence of operations that needs any of this code right now.
    s_rev = any_added_series_rev
    s_rev.is_comics_publication = False
    s_rev.save()
    s_rev.commit_to_display()
    series = Series.objects.get(pk=s_rev.series.pk)

    issue_add_values['series'] = series

    i_rev = IssueRevision(changeset=any_adding_changeset, **issue_add_values)
    i_rev.save()
    i_rev = IssueRevision.objects.get(pk=i_rev.pk)

    old_series_issue_count = i_rev.series.issue_count
    old_ind_pub_issue_count = i_rev.indicia_publisher.issue_count
    old_brand_issue_count = i_rev.brand.issue_count
    old_brand_group_counts = {group.pk: group.issue_count
                              for group in i_rev.brand.group.all()}
    old_publisher_issue_count = i_rev.series.publisher.issue_count

    with mock.patch('apps.oi.helpers.CountStats.objects.update_count') \
            as updater_mock:
        i_rev.commit_to_display()
    # Changeset must be approved so we can re-edit this later.
    i_rev.changeset.state = states.APPROVED
    i_rev.changeset.save()

    # Non-comics issues do not affect stats.
    assert not updater_mock.called

    i_rev = IssueRevision.objects.get(pk=i_rev.pk)
    s = i_rev.issue.series
    # Non-comics issues do not affect the issue counts EXCEPT on the series.
    assert s.issue_count == old_series_issue_count + 1
    assert s.publisher.issue_count == old_publisher_issue_count
    assert i_rev.issue.brand.issue_count == old_brand_issue_count
    assert {
        group.pk: group.issue_count for group in i_rev.issue.brand.group.all()
    } == old_brand_group_counts
    assert i_rev.issue.indicia_publisher.issue_count == old_ind_pub_issue_count

    # Now do it all again with a variant added to the new issue.
    v_rev = IssueRevision(changeset=any_variant_adding_changeset,
                          number='100',
                          variant_of=i_rev.issue,
                          variant_name='alternate cover',
                          series=i_rev.series,
                          brand=i_rev.brand,
                          indicia_publisher=i_rev.indicia_publisher)
    v_rev.save()
    v_rev = IssueRevision.objects.get(pk=v_rev.pk)

    old_series_issue_count = v_rev.series.issue_count
    old_ind_pub_issue_count = v_rev.indicia_publisher.issue_count
    old_brand_issue_count = v_rev.brand.issue_count
    old_brand_group_counts = {group.pk: group.issue_count
                              for group in v_rev.brand.group.all()}
    old_publisher_issue_count = v_rev.series.publisher.issue_count

    with mock.patch('apps.oi.helpers.CountStats.objects.update_count') \
            as updater_mock:
        v_rev.commit_to_display()
    # Changeset must be approved so we can re-edit this later.
    v_rev.changeset.state = states.APPROVED
    v_rev.changeset.save()

    # Non-comics variants do not affect stats.
    assert not updater_mock.called

    v_rev = IssueRevision.objects.get(pk=v_rev.pk)
    s = v_rev.issue.series
    # Non-comics variants do not affect the issue counts on anything.
    assert s.issue_count == old_series_issue_count
    assert s.publisher.issue_count == old_publisher_issue_count
    assert v_rev.issue.brand.issue_count == old_brand_issue_count
    assert {
        group.pk: group.issue_count
        for group in v_rev.issue.brand.group.all()
    } == old_brand_group_counts
    assert v_rev.issue.indicia_publisher.issue_count == old_ind_pub_issue_count

    # Now delete the variant, should still have the same counts.
    del_v_rev = IssueRevision.clone(
        changeset=any_deleting_changeset,
        data_object=Issue.objects.get(pk=v_rev.issue.pk))

    del_v_rev.deleted = True
    del_v_rev.save()
    del_v_rev = IssueRevision.objects.get(pk=del_v_rev.pk)
    with mock.patch('apps.oi.helpers.CountStats.objects.update_count') \
            as updater_mock:
        del_v_rev.commit_to_display()

    del_v_rev = IssueRevision.objects.get(pk=del_v_rev.pk)
    assert not updater_mock.called
    s = Series.objects.get(pk=del_v_rev.series.pk)
    i = Issue.objects.get(pk=del_v_rev.issue.pk)
    assert s.issue_count == old_series_issue_count
    assert s.publisher.issue_count == old_publisher_issue_count
    assert i.brand.issue_count == old_brand_issue_count
    assert {group.pk: group.issue_count
            for group in i.brand.group.all()} == old_brand_group_counts
    assert i.indicia_publisher.issue_count == old_ind_pub_issue_count

    # Finally, delete the base issue, check for only series.issue_count
    deleting_variant_changeset = Changeset(
        state=states.OPEN, change_type=0,
        indexer=any_deleting_changeset.indexer)
    deleting_variant_changeset.save()
    del_i_rev = IssueRevision.clone(
        changeset=deleting_variant_changeset,
        data_object=Issue.objects.get(pk=i_rev.issue.pk))

    del_i_rev.deleted = True
    del_i_rev.save()
    del_i_rev = IssueRevision.objects.get(pk=del_i_rev.pk)

    with mock.patch('apps.oi.helpers.CountStats.objects.update_count') \
            as updater_mock:
        del_i_rev.commit_to_display()

    del_i_rev = IssueRevision.objects.get(pk=del_v_rev.pk)
    assert not updater_mock.called
    s = Series.objects.get(pk=del_i_rev.series.pk)
    i = Issue.objects.get(pk=del_i_rev.issue.pk)

    # Series issue counts are adjusted even for non comics.
    assert s.issue_count == old_series_issue_count - 1
    assert s.publisher.issue_count == old_publisher_issue_count
    assert i.brand.issue_count == old_brand_issue_count
    assert {group.pk: group.issue_count
            for group in i.brand.group.all()} == old_brand_group_counts
    assert i.indicia_publisher.issue_count == old_ind_pub_issue_count
