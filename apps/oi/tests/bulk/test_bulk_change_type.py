"""The bulk change type: names, queues, history and approval."""
from datetime import timedelta

import pytest

from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from apps.gcd.models import (
    Creator, CreatorNameDetail, CreditType, Issue, IssueCredit,
    StoryCredit)
from apps.gcd.models.story import CREDIT_TYPES
from apps.gcd.templatetags.display import (
    changed_fields, changed_story_list)
from apps.oi import states
from apps.oi.models import (
    Changeset, IssueCreditRevision, IssueRevision, RevisionLock,
    SeriesRevision, StoryCreditRevision, StoryRevision, ACTION_MODIFY,
    CTYPES)
from apps.oi.templatetags.compare import field_value
from apps.oi.templatetags.editing import header_link
from apps.stddata.models import Script


@pytest.mark.django_db
def test_revisions_come_in_canonical_order(sequence_change,
                                           approved_stories):
    """The issues that anchor the sequences come first."""
    changeset = sequence_change(approved_stories, title='New')

    assert [type(revision) for revision in changeset.revisions] == \
        [IssueRevision, IssueRevision, StoryRevision, StoryRevision]


@pytest.mark.django_db
def test_names_of_an_issue_bulk_change(bulk_change, approved_issues):
    """The first issue and the number of the others name the change."""
    changeset = bulk_change(approved_issues, IssueRevision,
                            price='0.25 USD')
    first = changeset.issuerevisions.order_by('id')[0]

    assert changeset.queue_name() == '%s and 2 other issues' % first
    assert str(changeset) == changeset.queue_name()
    assert changeset.queue_descriptor() == '[BULK]'
    assert changeset.changeset_action() == ACTION_MODIFY


@pytest.mark.django_db
def test_name_of_a_sequence_bulk_change(sequence_change, approved_stories):
    """Sequences are named by issue and number; anchors are not counted."""
    changeset = sequence_change(approved_stories, title='New')

    assert changeset.queue_name() == '%s sequence 1 and 1 other sequence' \
        % approved_stories[0].issue


@pytest.mark.django_db
def test_series_bulk_change_has_a_name_and_no_header_link(
        bulk_change, any_added_series):
    """A change without issue revisions is named and needs no issue."""
    changeset = bulk_change([any_added_series], SeriesRevision,
                            notes='New notes')

    assert changeset.queue_name() == \
        str(changeset.seriesrevisions.get())
    assert header_link(changeset) == ''


def _kept(credit):
    """The values of credit as stored, to compare after an approval."""
    return type(credit).objects.filter(id=credit.id).values(
      'creator', 'credit_type', 'deleted').get()


@pytest.mark.django_db
def test_linked_credits_stay_unchanged(sequence_change, approved_stories,
                                       any_adding_changeset, approve_change):
    """
    A bulk change clones no credits, and removes none: its approval keeps
    the credit of the sequence as it was.
    """
    story = approved_stories[0]
    name = CreatorNameDetail.objects.create(
      name='Test Creator', creator=Creator.objects.create(
        gcd_official_name='Test Creator', sort_name='Test Creator'),
      in_script=Script.objects.get_or_create(code='Tst', number=999,
                                             name='Test Script')[0])
    script = CreditType.objects.get_or_create(
      id=CREDIT_TYPES['script'],
      defaults={'name': 'script', 'sort_code': 1})[0]
    credit = StoryCredit.objects.create(story=story, creator=name,
                                        credit_type=script)
    StoryCreditRevision.objects.create(
      changeset=any_adding_changeset, story_credit=credit, creator=name,
      credit_type=script,
      story_revision=story.revisions.get(committed=True))
    kept = _kept(credit)
    changeset = sequence_change([story], title='New')
    revision = changeset.storyrevisions.get()

    revision.compare_changes()

    assert [field for field, changed in revision.changed.items()
            if changed] == ['title']
    assert not changeset.storycreditrevisions.exists()
    approve_change(changeset)
    assert list(story.active_credits) == [credit]
    assert _kept(credit) == kept


@pytest.mark.django_db
def test_submit_and_approve(bulk_change, approved_issues, any_approver):
    """Approval writes the values and frees every lock."""
    changeset = bulk_change(approved_issues, IssueRevision,
                            price='0.25 USD')

    changeset.submit()
    assert changeset.state == states.PENDING
    changeset.assign(any_approver)
    changeset.approve()

    assert changeset.state == states.APPROVED
    assert set(Issue.objects.filter(id__in=[issue.id for issue
                                            in approved_issues])
                            .values_list('price', flat=True)) == \
        {'0.25 USD'}
    assert not RevisionLock.objects.filter(changeset=changeset).exists()
    assert not changeset.issuerevisions.exclude(committed=True).exists()


@pytest.mark.django_db
def test_bulk_change_in_the_pending_queue(client, bulk_change,
                                          approved_issues, any_approver):
    """The pending queue lists the change among the bulk changes."""
    changeset = bulk_change(approved_issues, IssueRevision,
                            price='0.25 USD')
    changeset.submit()
    client.force_login(any_approver)

    response = client.get(reverse('pending'))

    assert response.status_code == 200
    content = response.content.decode()
    assert 'Bulk Changes' in content
    assert 'Issue Bulk Changes' not in content
    assert escape(changeset.queue_name()) in content
    assert '[BULK]' in content


@pytest.mark.django_db
def test_approved_list_names_bulk_changes(client, bulk_change,
                                          approved_issues, approve_change):
    """The list of approved changes of the indexer has the change."""
    changeset = bulk_change(approved_issues, IssueRevision,
                            price='0.25 USD')
    approve_change(changeset)
    changeset.indexer.user_permissions.add(Permission.objects.get(
      content_type__app_label='indexer', codename='can_reserve'))
    client.force_login(changeset.indexer)

    response = client.get(reverse('approved'))

    assert response.status_code == 200
    content = response.content.decode()
    assert '">bulk changes</a>' in content
    assert escape(str(changeset)) in content


@pytest.mark.django_db
def test_change_history_of_an_issue_lists_its_sequences(
        client, sequence_change, approved_stories, approve_change):
    """The history of an issue shows only its own changed sequences."""
    changeset = sequence_change(approved_stories, title='New')
    first_issue = approved_stories[0].issue

    output = changed_story_list(changeset, first_issue)
    assert 'Sequence 1 : Title' in output
    assert 'Sequence 2' not in output

    approve_change(changeset)
    response = client.get(reverse('change_history',
                                  kwargs={'model_name': 'issue',
                                          'id': first_issue.id}))

    # the fixtures added both sequences in one change, listed as added
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Sequence 1 : Title' in content
    assert 'Sequence 2 : Title' not in content


@pytest.mark.django_db
def test_old_bulk_change_is_discarded_not_submitted(
        client, bulk_change, approved_issues, any_approver):
    """The clearing of old reservations never submits a bulk change."""
    changeset = bulk_change(approved_issues, IssueRevision,
                            price='0.25 USD')
    Changeset.objects.filter(id=changeset.id).update(
      created=timezone.now() - timedelta(weeks=4))
    any_approver.user_permissions.add(Permission.objects.get(
      content_type__app_label='oi', codename='change_ongoingreservation'))
    client.force_login(any_approver)

    response = client.get(reverse('clear_issues'))

    assert response.status_code == 200
    changeset.refresh_from_db()
    assert changeset.state == states.DISCARDED
    assert not RevisionLock.objects.filter(changeset=changeset).exists()
    assert changeset.comments.filter(
      text='This is an automatic discard of a bulk change which was not '
           'submitted in time.').exists()


@pytest.mark.django_db
def test_clearing_page_escapes_the_name_of_a_change(
        client, bulk_change, approved_issues, any_approver):
    """
    The name of a change, here from the variant name of its first issue,
    shows as text on the clearing page, in the link to the change.
    """
    changeset = bulk_change(approved_issues[:1], IssueRevision,
                            variant_name='<b>Variant</b>')
    Changeset.objects.filter(id=changeset.id).update(
      created=timezone.now() - timedelta(weeks=4))
    any_approver.user_permissions.add(Permission.objects.get(
      content_type__app_label='oi', codename='change_ongoingreservation'))
    client.force_login(any_approver)

    response = client.get(reverse('clear_issues'))

    content = response.content.decode()
    assert '<b>Variant</b>' not in content
    assert 'Change: %s</a>' % escape(str(changeset)) in content
    assert reverse('compare', kwargs={'id': changeset.id}) in content


@pytest.mark.django_db
def test_issue_bulk_change_keeps_its_behaviour(bulk_change,
                                               approved_issues):
    """A historical issue bulk change keeps its name and points."""
    changeset = bulk_change(approved_issues, IssueRevision,
                            price='0.25 USD')
    Changeset.objects.filter(id=changeset.id).update(
      change_type=CTYPES['issue_bulk'])
    changeset = Changeset.objects.get(id=changeset.id)

    assert changeset.queue_name() == '%s and 2 other issues' \
        % changeset.issuerevisions.all()[0]
    assert changeset.queue_descriptor() != '[BULK]'
    changeset.calculate_imps()
    assert changeset.imps == 1


def _test_creator():
    """The official name of a creator, for credits."""
    return CreatorNameDetail.objects.create(
      name='Test Creator', is_official_name=True,
      creator=Creator.objects.create(
        gcd_official_name='Test Creator', sort_name='Test Creator'),
      in_script=Script.objects.get_or_create(code='Tst', number=999,
                                             name='Test Script')[0])


@pytest.mark.django_db
def test_issue_credits_stay_unchanged(bulk_change, approved_issues,
                                      any_adding_changeset, approve_change):
    """
    A bulk change of issues keeps their credits, unchanged: it clones
    none, and its approval keeps the credit of the issue as it was.
    """
    issue = approved_issues[0]
    name = _test_creator()
    editing = CreditType.objects.get_or_create(
      id=CREDIT_TYPES['editing'],
      defaults={'name': 'editing', 'sort_code': 6})[0]
    credit = IssueCredit.objects.create(issue=issue, creator=name,
                                        credit_type=editing)
    IssueCreditRevision.objects.create(
      changeset=any_adding_changeset, issue_credit=credit, creator=name,
      credit_type=editing,
      issue_revision=issue.revisions.get(committed=True))
    kept = _kept(credit)
    changeset = bulk_change([issue], IssueRevision, price='0.25 USD')
    revision = changeset.issuerevisions.get()

    revision.compare_changes()

    assert [field for field, changed in revision.changed.items()
            if changed] == ['price']
    assert not changeset.issuecreditrevisions.exists()
    approve_change(changeset)
    assert list(issue.active_credits) == [credit]
    assert _kept(credit) == kept


@pytest.mark.django_db
def test_compare_shows_the_kept_issue_credits(bulk_change, approved_issues):
    """
    The compare value of the editing field of a bulk change of issues
    shows the credits the issue keeps, as for an issue bulk change.
    """
    issue = approved_issues[0]
    editing = CreditType.objects.get_or_create(
      id=CREDIT_TYPES['editing'],
      defaults={'name': 'editing', 'sort_code': 6})[0]
    IssueCredit.objects.create(issue=issue, creator=_test_creator(),
                               credit_type=editing)
    changeset = bulk_change([issue], IssueRevision, price='0.25 USD')

    shown = field_value(changeset.issuerevisions.get(), 'editing')

    assert 'Test Creator' in shown


@pytest.mark.django_db
def test_empty_bulk_change(any_indexer):
    """A bulk change without revisions has a name and an action."""
    changeset = Changeset.objects.create(
      indexer=any_indexer, state=states.OPEN, change_type=CTYPES['bulk'])

    assert str(changeset) == 'Empty bulk change'
    assert changeset.changeset_action() == ACTION_MODIFY
    assert changeset.queue_descriptor() == '[BULK]'


@pytest.mark.django_db
def test_history_lists_the_exact_changes(client, bulk_change,
                                         sequence_change, approved_stories,
                                         approve_change):
    """
    The history of an issue lists a change of spaces only, and of case
    only in its sequences, as the page of the change shows them.
    """
    issue = approved_stories[0].issue
    prices = bulk_change([issue], IssueRevision, price='0.10 USD ')
    approve_change(prices)
    approve_change(sequence_change(approved_stories[:1], genre='Superhero'))

    response = client.get(reverse('change_history',
                                  kwargs={'model_name': 'issue',
                                          'id': issue.id}))

    content = response.content.decode()
    assert 'Price' in content
    assert 'Sequence 1 : Genre' in content
    assert changed_fields(prices, issue) == 'Price'


@pytest.mark.django_db
def test_sequences_listed_only_for_an_issue(sequence_change,
                                            approved_stories):
    """The sequences of a bulk change are listed only for an issue."""
    changeset = sequence_change(approved_stories, title='New')

    series = approved_stories[0].issue.series

    assert changed_story_list(changeset, series) == ''
