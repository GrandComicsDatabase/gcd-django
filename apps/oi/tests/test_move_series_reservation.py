"""A series move that cannot reserve all its issues leaves nothing locked."""

from types import SimpleNamespace

import pytest

from django.urls import reverse

from apps.gcd.models import (Creator, CreatorNameDetail, CreditType, Issue,
                             Publisher)
from apps.oi import states
from apps.oi.models import (Changeset, CTYPES, StoryCreditRevision,
                            _get_revision_lock)
from apps.oi.templatetags.editing import is_locked
from apps.stddata.models import Date, Script


def _credit_on(story_revision):
    """Add a credit to the story of the revision, through an approved one."""
    script, _ = Script.objects.get_or_create(
      id=Script.LATIN_PK,
      defaults={'code': 'Latn', 'number': Script.LATIN_PK, 'name': 'Latin'})
    creator = Creator.objects.create(
      gcd_official_name='A Creator', birth_date=Date.objects.create(),
      death_date=Date.objects.create())
    name = CreatorNameDetail.objects.create(
      name='A Creator', sort_name='A Creator', creator=creator,
      in_script=script)
    revision = StoryCreditRevision.objects.create(
      changeset=story_revision.changeset, story_revision=story_revision,
      creator=name, credit_type=CreditType.objects.get_or_create(
        name='script', defaults={'sort_code': 1})[0])
    revision.commit_to_display()
    return revision.story_credit


@pytest.fixture
def blocked_move(client, any_indexer, any_country, any_added_story,
                 any_added_story_rev):
    """A series move with its second issue reserved by another change."""
    issue = any_added_story.issue
    credit = _credit_on(any_added_story_rev)
    blocked = Issue.objects.create(series=issue.series, number='2',
                                   sort_code=issue.sort_code + 1)
    other = Changeset.objects.create(indexer=any_indexer, state=states.OPEN,
                                     change_type=CTYPES['issue'])
    assert _get_revision_lock(blocked, changeset=other)

    any_indexer.is_superuser = True
    any_indexer.save()
    any_indexer.indexer.max_reservations = 10
    any_indexer.indexer.save()
    client.force_login(any_indexer)
    client.post(reverse('reserve_revision',
                        kwargs={'model_name': 'series',
                                'id': issue.series.id}))
    changeset = Changeset.objects.get(seriesrevisions__series=issue.series,
                                      state=states.OPEN)
    publisher = Publisher.objects.create(name='New Publisher',
                                         country=any_country, year_began=1940)
    url = reverse('move_series',
                  kwargs={'series_revision_id':
                          changeset.seriesrevisions.get().id,
                          'publisher_id': publisher.id})
    return SimpleNamespace(url=url, changeset=changeset, issue=issue,
                           blocked=blocked, credit=credit, other=other)


@pytest.mark.django_db
def test_a_failed_reservation_leaves_only_the_series_locked(client,
                                                            blocked_move):
    """The credit of the issue reserved before the failure is free again."""
    response = client.post(blocked_move.url, {'comments': ''}, follow=True)

    assert 'Error while reserving issues.' in response.content.decode()
    changeset = blocked_move.changeset
    assert not changeset.issuerevisions.exists()
    assert not changeset.storyrevisions.exists()
    assert [lock.locked_object for lock in changeset.revision_locks.all()] \
        == [blocked_move.issue.series]
    assert not is_locked(blocked_move.credit)


@pytest.mark.django_db
def test_discarding_after_the_failure_frees_everything(client, blocked_move,
                                                       any_indexer):
    """Nothing of the failed move stays locked once the change is discarded."""
    client.post(blocked_move.url, {'comments': ''}, follow=True)

    blocked_move.changeset.discard(any_indexer)

    assert not blocked_move.changeset.revision_locks.exists()
    assert not is_locked(blocked_move.credit)


@pytest.mark.django_db
def test_the_move_works_after_the_failure(client, blocked_move):
    """Once the other reservation is gone the same move goes through."""
    client.post(blocked_move.url, {'comments': ''}, follow=True)
    blocked_move.other.revision_locks.all().delete()
    blocked_move.blocked.deleted = True
    blocked_move.blocked.save()

    client.post(blocked_move.url, {'comments': ''})

    changeset = blocked_move.changeset
    assert changeset.issuerevisions.get().issue == blocked_move.issue
    assert changeset.storycreditrevisions.get().story_credit \
        == blocked_move.credit
