"""The exact diff of bulk changes and their points."""
from datetime import timedelta

import pytest

from apps.gcd.models import Issue
from apps.oi.bulk import exact_diff
from apps.oi.models import IssueRevision, RevisionLock


@pytest.mark.django_db
def test_exact_diff_keeps_spaces_and_case(bulk_change, approved_issues,
                                          any_added_brand):
    """A trailing space, a capital and a removed brand all count."""
    changeset = bulk_change(approved_issues[:2], IssueRevision)
    changed, unchanged = changeset.issuerevisions.order_by('id')
    changed.price = '0.10 USD '
    changed.indicia_frequency = 'Monthly'
    changed.save()
    changed.brand_emblem.clear()

    diff = exact_diff(IssueRevision, [changed.id, unchanged.id])

    assert diff[unchanged.id] == {}
    assert diff[changed.id] == {
        'price': ('0.10 USD', '0.10 USD '),
        'indicia_frequency': ('monthly', 'Monthly'),
        'brand_emblem': (frozenset({any_added_brand.id}), frozenset()),
    }
    changed.compare_changes()
    assert not changed.changed['price']


@pytest.mark.django_db
def test_exact_diff_of_a_discarded_change(bulk_change, approved_issues):
    """Discarded revisions lose their link, not their changes."""
    changeset = bulk_change(approved_issues, IssueRevision,
                            price='0.25 USD')
    changeset.discard(changeset.indexer)
    revisions = changeset.issuerevisions.all()
    assert not revisions.filter(previous_revision__isnull=False).exists()

    diff = exact_diff(IssueRevision, [revision.id for revision in revisions])

    assert list(diff.values()) == \
        [{'price': ('0.10 USD', '0.25 USD')}] * 3
    assert not RevisionLock.objects.filter(changeset=changeset).exists()


@pytest.mark.django_db
def test_exact_diff_finds_the_previous_revision_of_a_discard(
      bulk_change, approved_issues, approve_change):
    """
    A discarded revision is compared with the latest approved revision of
    its object made before it, not with an earlier or a later one.
    """
    issue = approved_issues[0]
    approve_change(bulk_change([issue], IssueRevision, price='0.11 USD'))
    changeset = bulk_change([issue], IssueRevision, price='0.12 USD')
    changeset.discard(changeset.indexer)
    approve_change(bulk_change([issue], IssueRevision, price='0.15 USD'))
    revision = changeset.issuerevisions.get()

    diff = exact_diff(IssueRevision, [revision.id])

    assert diff == {revision.id: {'price': ('0.11 USD', '0.12 USD')}}


@pytest.mark.django_db
def test_exact_diff_of_a_discard_without_committed_flags(bulk_change,
                                                         approved_issues):
    """
    The previous revision of a discarded one is that of an approved
    change, also where its committed flag is not set.
    """
    IssueRevision.objects.update(committed=None)
    changeset = bulk_change(approved_issues[:1], IssueRevision,
                            price='0.25 USD')
    changeset.discard(changeset.indexer)
    revision = changeset.issuerevisions.get()

    diff = exact_diff(IssueRevision, [revision.id])

    assert diff == {revision.id: {'price': ('0.10 USD', '0.25 USD')}}


@pytest.mark.django_db
def test_exact_diff_needs_a_previous_revision(bulk_change,
                                              approved_issues):
    """A revision without any approved one before it is an error."""
    changeset = bulk_change(approved_issues[:1], IssueRevision)
    revision = changeset.issuerevisions.get()
    IssueRevision.objects.filter(id=revision.id).update(
      previous_revision=None)
    IssueRevision.objects.exclude(id=revision.id).update(
      created=revision.created + timedelta(days=1))

    with pytest.raises(ValueError):
        exact_diff(IssueRevision, [revision.id])


@pytest.mark.django_db
def test_points_count_each_logical_field_once(bulk_change,
                                              approved_issues):
    """
    Three changed prices are one field; volume and its flag in two
    issues are one more; a rating in the second issue only is a third.
    """
    changeset = bulk_change(approved_issues, IssueRevision,
                            price='0.25 USD')
    first, second = changeset.issuerevisions.order_by('id')[:2]
    first.volume = '2'
    first.save()
    second.no_volume = False
    second.rating = 'All Ages'
    second.save()

    changeset.calculate_imps()

    assert changeset.imps == 3


@pytest.mark.django_db
def test_points_of_a_rule_met_by_any_revision(bulk_change,
                                              approved_issues):
    """
    An uncertain page count earns a point where a page count is given,
    whichever changed issue has one, here neither the first nor the last.
    """
    for issue, page_count in zip(approved_issues, (None, 32, None)):
        Issue.objects.filter(id=issue.id).update(page_count=page_count)
        IssueRevision.objects.filter(issue=issue).update(
          page_count=page_count)
    issues = Issue.objects.filter(id__in=[issue.id for issue
                                          in approved_issues])
    changeset = bulk_change(issues, IssueRevision,
                            page_count_uncertain=True)
    name, revisions = changeset.bulk_target()

    changeset.calculate_imps()

    assert [revision.page_count for revision in revisions] == \
        [None, 32, None]
    assert changeset.imps == 1


@pytest.mark.django_db
def test_points_leave_out_the_anchors(sequence_change, approved_stories):
    """
    The issue revisions that anchor changed sequences add no points, even
    one that differs from its previous revision.
    """
    changeset = sequence_change(approved_stories, title='New')
    changeset.issuerevisions.filter(
      issue=approved_stories[0].issue).update(notes='Not from this change',
                                              price='9.99 USD')

    changeset.calculate_imps()

    assert changeset.imps == 1


@pytest.mark.django_db
def test_points_given_once_at_approval(bulk_change, approved_issues,
                                       approve_change):
    """The indexer gets the points of the change once."""
    changeset = bulk_change(approved_issues, IssueRevision,
                            price='0.25 USD')
    indexer = changeset.indexer.indexer
    imps_before = indexer.imps

    approve_change(changeset)

    assert changeset.imps == 1
    indexer.refresh_from_db()
    assert indexer.imps == imps_before + 1


@pytest.mark.django_db
def test_points_only_from_revisions_that_changed_the_field(
      bulk_change, approved_issues):
    """
    A rule that reads the values of a revision counts only for a revision
    that changed the field: an uncertain page count without a page count
    earns nothing, even where another changed issue has a page count.
    """
    for issue, page_count in zip(approved_issues, (None, 32)):
        Issue.objects.filter(id=issue.id).update(page_count=page_count)
        IssueRevision.objects.filter(issue=issue).update(
          page_count=page_count)
    issues = Issue.objects.filter(id__in=[issue.id for issue
                                          in approved_issues[:2]])
    changeset = bulk_change(issues, IssueRevision)
    first, other = changeset.bulk_target()[1]
    first.page_count_uncertain = True
    first.save()
    other.price = '0.25 USD'
    other.save()

    changeset.calculate_imps()

    assert changeset.imps == 1
