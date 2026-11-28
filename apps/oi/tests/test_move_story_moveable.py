"""
In a variant-add change a sequence moves between the base issue and the new
variant only when StoryRevision.moveable() allows it, the same rule that
shows the "Move To Other Issue" button on the change page.
"""

import pytest

from django.urls import reverse

from apps.gcd.models import StoryType
from apps.oi import states
from apps.oi.models import Changeset, StoryRevision, CTYPES
from apps.oi.views import _do_reserve

MOVE_ERROR = 'This sequence cannot be moved to the other issue.'


def _add_story(issue, indexer, sequence_number, type_name):
    changeset = Changeset(state=states.OPEN, indexer=indexer,
                          change_type=CTYPES['issue'])
    changeset.save()
    revision = StoryRevision(
      changeset=changeset, issue=issue, sequence_number=sequence_number,
      title='Test Title', type=StoryType.objects.get(name=type_name),
      feature='Test Feature', page_count=1, script='Writer',
      pencils='Penciller', inks='Inker', no_colors=True, letters='Letterer',
      no_editing=True)
    revision.save()
    revision.commit_to_display()
    changeset.state = states.APPROVED
    changeset.save()
    return revision.story


@pytest.fixture
def change(client, any_indexer, any_added_issue, any_added_variant_rev):
    """
    A variant-add change with the base issue and its three sequences: a
    cover, a comic story and a second cover.
    """
    # superuser passes the permission checks of the OI views, enough
    # reservations so that the open changesets of the fixtures don't count
    any_indexer.is_superuser = True
    any_indexer.save()
    any_indexer.indexer.max_reservations = 10
    any_indexer.indexer.save()
    client.force_login(any_indexer)
    stories = [_add_story(any_added_issue, any_indexer, number, type_name)
               for number, type_name in enumerate(
                 ['cover', 'comic story', 'cover'])]
    changeset = any_added_variant_rev.changeset
    assert _do_reserve(any_indexer, any_added_issue, 'issue',
                       changeset=changeset)
    revisions = [changeset.storyrevisions.get(story=story)
                 for story in stories]
    return {'issue': any_added_issue, 'changeset': changeset,
            'cover': revisions[0], 'comic story': revisions[1],
            'second cover': revisions[2]}


def _move(client, story_revision):
    return client.post(reverse('move_story_revision',
                               kwargs={'id': story_revision.id}))


def _issue_of(story_revision):
    return StoryRevision.objects.get(id=story_revision.id).issue


@pytest.mark.django_db
def test_move_refuses_non_cover_sequence(client, change):
    story = change['comic story']
    assert not story.moveable()

    response = _move(client, story)

    assert _issue_of(story) == change['issue']
    assert response.status_code == 200
    assert MOVE_ERROR in response.content.decode()


@pytest.mark.django_db
def test_move_refuses_second_sequence(client, change):
    assert _move(client, change['cover']).status_code == 302
    second_cover = StoryRevision.objects.get(id=change['second cover'].id)
    assert not second_cover.moveable()

    response = _move(client, second_cover)

    assert _issue_of(second_cover) == change['issue']
    assert response.status_code == 200
    assert MOVE_ERROR in response.content.decode()
    assert change['changeset'].storyrevisions.filter(issue=None).count() == 1


@pytest.mark.django_db
def test_move_cover_into_variant_and_back(client, change):
    cover = change['cover']
    assert cover.moveable()

    assert _move(client, cover).status_code == 302
    assert _issue_of(cover) is None

    moved = StoryRevision.objects.get(id=cover.id)
    assert moved.moveable()
    assert _move(client, moved).status_code == 302
    assert _issue_of(cover) == change['issue']
