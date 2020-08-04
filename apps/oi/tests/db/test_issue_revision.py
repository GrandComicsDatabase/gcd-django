# -*- coding: utf-8 -*-


import mock
import pytest

from apps.gcd.models import Series, Issue
from apps.oi.models import Changeset, IssueRevision, CoverRevision, CTYPES
from apps.oi import states


EXCLUDED_FORK_FIELDS = {
    'publication_date': '',
    'key_date': '',
    'year_on_sale': None,
    'month_on_sale': None,
    'day_on_sale': None,
    'on_sale_date_uncertain': False,
    'price': '',
    'brand': None,
    'no_brand': False,
    'isbn': '',
    'no_isbn': False,
    'barcode': '',
    'no_barcode': False,
    'keywords': '',
}

UPDATE_ALL = 'apps.stats.models.CountStats.objects.update_all_counts'


@pytest.mark.django_db
def test_create_add_revision(any_added_issue_rev, issue_add_values,
                             any_adding_changeset):
    rev = any_added_issue_rev
    for k, v in issue_add_values.items():
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
    for k, v in variant_add_values.items():
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

    with mock.patch(UPDATE_ALL) as updater:
        rev.commit_to_display()

    updater.has_calls([
      mock.call({}, language=None, country=None, negate=True),
      mock.call({'issues': 1}, 
                language=rev.series.language, country=rev.series.country),
    ])

    assert updater.call_count == 2

    assert rev.issue is not None
    assert rev.source is rev.issue

    on_sale_revision_fields = ('year_on_sale', 'month_on_sale', 'day_on_sale')
    for k, v in issue_add_values.items():
        if k == 'keywords':
            kws = [k for k in rev.issue.keywords.names()]
            kws.sort()
            assert kws == keywords['list']
        elif k in on_sale_revision_fields:
            # These are covered below.
            continue
        else:
            assert getattr(rev.issue, k) == v
    assert rev.issue.on_sale_date == '%04d-%02d-%02d' % (
        issue_add_values['year_on_sale'],
        issue_add_values['month_on_sale'],
        issue_add_values['day_on_sale'])
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
    } == {k: v + 1 for k, v in old_brand_group_counts.items()}
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

    with mock.patch(UPDATE_ALL) as updater:
        rev.commit_to_display()

    updater.has_calls([
      mock.call({}, language=None, country=None, negate=True),
      mock.call({'variant issues': 1}, 
                language=rev.series.language, country=rev.series.country),
    ])

    assert updater.call_count == 2

    assert rev.issue is not None
    assert rev.source is rev.issue

    for k, v in variant_add_values.items():
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

    for k, v in issue_add_values.items():
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

    for k, v in variant_add_values.items():
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
    } == {k: v - 1 for k, v in old_brand_group_counts.items()}
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
    with mock.patch(UPDATE_ALL) as updater:
        s_rev.commit_to_display()

    updater.has_calls([
      mock.call({}, language=None, country=None, negate=True),
      mock.call({'series': 1}, 
                language=s_rev.series.language, country=s_rev.series.country),
    ])

    assert updater.call_count == 2

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

    with mock.patch(UPDATE_ALL) as updater:
        i_rev.commit_to_display()
    # Changeset must be approved so we can re-edit this later.
    i_rev.changeset.state = states.APPROVED
    i_rev.changeset.save()

    updater.has_calls([
      mock.call({}, language=None, country=None, negate=True),
      mock.call({'stories': 0, 'covers': 0}, 
                language=i_rev.series.language, country=i_rev.series.country),
    ])

    assert updater.call_count == 2

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

    with mock.patch(UPDATE_ALL) as updater:
        v_rev.commit_to_display()
    # Changeset must be approved so we can re-edit this later.
    v_rev.changeset.state = states.APPROVED
    v_rev.changeset.save()

    updater.has_calls([
      mock.call({'stories': 0, 'covers': 0}, language=None, country=None,
                negate=True),
      mock.call({'stories': 0, 'covers': 0}, 
                language=i_rev.series.language, country=i_rev.series.country),
    ])

    assert updater.call_count == 2

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
    with mock.patch(UPDATE_ALL) as updater:
        del_v_rev.commit_to_display()

    del_v_rev = IssueRevision.objects.get(pk=del_v_rev.pk)

    updater.has_calls([
      mock.call({'stories': 0, 'covers': 0}, language=None, country=None,
                negate=True),
      mock.call({'stories': 0, 'covers': 0}, 
                language=i_rev.series.language, country=i_rev.series.country),
    ])
    assert updater.call_count == 2

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

    with mock.patch(UPDATE_ALL) as updater:
        del_i_rev.commit_to_display()

    del_i_rev = IssueRevision.objects.get(pk=del_v_rev.pk)
    updater.has_calls([
      mock.call({'stories': 0, 'covers': 0}, language=None, country=None,
                negate=True),
      mock.call({'stories': 0, 'covers': 0}, 
                language=i_rev.series.language, country=i_rev.series.country),
    ])
    assert updater.call_count == 2
    s = Series.objects.get(pk=del_i_rev.series.pk)
    i = Issue.objects.get(pk=del_i_rev.issue.pk)

    # Series issue counts are adjusted even for non comics.
    assert s.issue_count == old_series_issue_count - 1
    assert s.publisher.issue_count == old_publisher_issue_count
    assert i.brand.issue_count == old_brand_issue_count
    assert {group.pk: group.issue_count
            for group in i.brand.group.all()} == old_brand_group_counts
    assert i.indicia_publisher.issue_count == old_ind_pub_issue_count


@pytest.mark.django_db
def test_fork_variant_for_cover_no_reserve(any_added_issue,
                                           any_editing_changeset):
    # Make it a wraparound to test cover sequence page count logic.
    cover_rev = CoverRevision(changeset=any_editing_changeset,
                              is_wraparound=2)
    issue_rev, story_rev = IssueRevision.fork_variant(
        any_added_issue,
        any_editing_changeset,
        variant_name='any variant name',
        variant_cover_revision=cover_rev)

    for name in IssueRevision._get_regular_fields():
        if name == 'variant_of':
            assert issue_rev.variant_of == any_added_issue
        elif name == 'variant_name':
            assert issue_rev.variant_name == 'any variant name'
        elif name == 'on_sale_date':
            assert issue_rev.year_on_sale is None
            assert issue_rev.month_on_sale is None
            assert issue_rev.day_on_sale is None
        elif name in EXCLUDED_FORK_FIELDS:
            assert getattr(issue_rev, name) == EXCLUDED_FORK_FIELDS[name]
        else:
            assert getattr(issue_rev, name) == getattr(any_added_issue, name)

    assert issue_rev.add_after == any_added_issue
    assert issue_rev.reservation_requested is False

    assert story_rev.changeset == issue_rev.changeset
    assert story_rev.issue is None
    assert story_rev.sequence_number == 0
    assert story_rev.page_count == 2
    assert story_rev.type.name == 'cover'
    assert story_rev.script == ''
    assert story_rev.no_script is True
    assert story_rev.inks == '?'
    assert story_rev.no_inks is False
    assert story_rev.colors == '?'
    assert story_rev.no_colors is False
    assert story_rev.letters == ''
    assert story_rev.no_letters is True
    assert story_rev.editing == ''
    assert story_rev.no_editing is True

    for name in ('pencils', 'inks', 'colors'):
        assert getattr(story_rev, name) == '?'
    for name in ('script', 'letters', 'editing'):
        assert getattr(story_rev, name) == ''


@pytest.mark.django_db
def test_fork_variant_reserve_no_cover_with_variants(any_added_issue,
                                                     any_added_variant,
                                                     any_editing_changeset):
    issue_rev, story_rev = IssueRevision.fork_variant(
        any_added_issue,
        any_editing_changeset,
        variant_name='any variant name',
        reservation_requested=True)

    # Don't bother testing most fields as it is the same as above.
    # Just test the reservation & no cover revision implications.
    assert issue_rev.reservation_requested is True
    assert story_rev is None

    # Because we built a variant in the fixtures, the new variant
    # should be sorted just after the existing variant.
    assert issue_rev.add_after == any_added_variant
