"""
An approval that makes a site-wide total reach a multiple of
STATS_MILESTONE_STEP mails the main list, once the approval is committed.
"""
from unittest import mock

import pytest
from django.db import transaction
from django.db.models import F

from apps.gcd.models import Cover
from apps.oi import states
from apps.oi.models import Changeset, CoverRevision, CTYPES, RevisionLock
from apps.stats.models import CountStats, CountStatsManager

MAIN_LIST = 'main-list@example.org'
MAIL_2000 = ([MAIN_LIST], 'GCD milestone: 2,000 covers')

pytestmark = pytest.mark.django_db


@pytest.fixture
def milestones(settings):
    settings.BETA = False
    settings.EMAIL_STATS_MILESTONE = MAIN_LIST
    settings.STATS_MILESTONE_STEP = 1000
    return settings


def _covers(count):
    """Set the site-wide total of covers."""
    CountStats.objects.filter(name='covers', language=None,
                              country=None).update(count=count)


def _approve(indexer, issue, adds=1, deleted=None):
    """Approve a cover change with adds new covers and deleted removed."""
    changeset = Changeset.objects.create(
      indexer=indexer, approver=indexer, state=states.REVIEWING,
      change_type=CTYPES['cover'])
    changeset.comments.create(commenter=indexer, text='',
                              old_state=states.OPEN,
                              new_state=states.REVIEWING)
    for x in range(adds):
        CoverRevision.objects.create(changeset=changeset, issue=issue)
    if deleted:
        RevisionLock.objects.create(locked_object=deleted,
                                    changeset=changeset)
        CoverRevision.objects.create(changeset=changeset, issue=issue,
                                     cover=deleted, deleted=True)
    with mock.patch('apps.oi.covers.copy_approved_cover'):
        changeset.approve()


def _mails(mailoutbox):
    return [(mail.to, mail.subject) for mail in mailoutbox]


def test_cover_approval_mails_the_milestone_once_committed(
      milestones, any_added_issue, any_indexer, mailoutbox,
      django_capture_on_commit_callbacks):
    _covers(1999)

    with django_capture_on_commit_callbacks(execute=True):
        _approve(any_indexer, any_added_issue)
        assert mailoutbox == []

    assert _mails(mailoutbox) == [MAIL_2000]
    assert 'now has 2,000 covers' in mailoutbox[0].body


def test_rolled_back_approval_mails_nothing(
      milestones, any_added_issue, any_indexer, mailoutbox,
      django_capture_on_commit_callbacks):
    _covers(1999)

    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError), transaction.atomic():
            _approve(any_indexer, any_added_issue)
            raise RuntimeError
        _approve(any_indexer, any_added_issue)

    assert _mails(mailoutbox) == [MAIL_2000]


def test_approval_goes_by_the_total_after_its_update(
      milestones, any_added_issue, any_indexer, mailoutbox,
      django_capture_on_commit_callbacks):
    """
    Another approval commits 9 covers between the reading of the total
    and its update: 1990 read, 1999 + 1 written.
    """
    _covers(1990)
    get = CountStatsManager.get

    def another_approval_meanwhile(manager, **kwargs):
        stat = get(manager, **kwargs)
        if kwargs == {'name': 'covers', 'language': None, 'country': None}:
            CountStats.objects.filter(id=stat.id).update(
              count=F('count') + 9)
        return stat

    with django_capture_on_commit_callbacks(execute=True), \
            mock.patch.object(CountStatsManager, 'get', autospec=True,
                              side_effect=another_approval_meanwhile):
        _approve(any_indexer, any_added_issue)

    assert _mails(mailoutbox) == [MAIL_2000]


def test_approval_mails_each_milestone_it_reaches(
      milestones, any_added_issue, any_indexer, mailoutbox,
      django_capture_on_commit_callbacks):
    milestones.STATS_MILESTONE_STEP = 1
    _covers(1998)

    with django_capture_on_commit_callbacks(execute=True):
        _approve(any_indexer, any_added_issue, adds=2)

    assert [mail.subject for mail in mailoutbox] == [
      'GCD milestone: 1,999 covers', 'GCD milestone: 2,000 covers']


def test_total_that_goes_down_and_back_mails_nothing_again(
      milestones, any_added_issue, any_indexer, mailoutbox,
      django_capture_on_commit_callbacks):
    """
    The second approval removes a cover and adds one, as an edit takes
    away its old counts and adds the new ones: 2000, 1999, 2000.
    """
    _covers(1999)
    old = Cover.objects.create(issue=any_added_issue)

    with django_capture_on_commit_callbacks(execute=True):
        _approve(any_indexer, any_added_issue)
        _approve(any_indexer, any_added_issue, deleted=old)

    assert _mails(mailoutbox) == [MAIL_2000]


def test_beta_mails_nothing(milestones, any_added_issue, any_indexer,
                            mailoutbox, django_capture_on_commit_callbacks):
    milestones.BETA = True
    _covers(1999)

    with django_capture_on_commit_callbacks(execute=True):
        _approve(any_indexer, any_added_issue)

    assert mailoutbox == []
