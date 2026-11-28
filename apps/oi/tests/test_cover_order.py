"""The order of the covers is checked when a change is submitted."""

import pytest

from django.test import RequestFactory

from apps.gcd.models import StoryType, STORY_TYPES
from apps.oi import states
from apps.oi.models import StoryRevision
from apps.oi.views import _covers_out_of_order, _do_reserve, submit, \
                          validate_changeset_revisions

COVER, STORY = STORY_TYPES['cover'], STORY_TYPES['comic story']


@pytest.mark.parametrize('types', [
    [], [STORY, STORY], [COVER], [COVER, STORY, STORY],
    [COVER, COVER, STORY], [COVER, STORY, COVER]])
def test_covers_in_wiki_order(types):
    """First the cover, then a dust jacket cover or a flip book cover last."""
    assert not _covers_out_of_order(types)


@pytest.mark.parametrize('types', [
    [STORY, COVER], [COVER, STORY, COVER, STORY],
    [COVER, COVER, STORY, COVER]])
def test_covers_out_of_wiki_order(types):
    """Cover not first, second cover in the middle, three covers."""
    assert _covers_out_of_order(types)


def _cover(story_add_values, changeset, sequence_number):
    """A cover sequence; the comic story of the issue is sequence 1."""
    return StoryRevision.objects.create(
      changeset=changeset,
      **dict(story_add_values, sequence_number=sequence_number,
             type=StoryType.objects.get(id=COVER)))


def _reserve(story, user, story_add_values, changeset, covers=()):
    """Approve the covers, then reserve the issue as the site does."""
    for sequence_number in covers:
        _cover(story_add_values, changeset,
               sequence_number).commit_to_display()
    return _do_reserve(user, story.issue, 'issue')


def _request(user, comments=''):
    request = RequestFactory().post('/submit/', {'comments': comments})
    request.user = user
    return request


def _cover_order_errors(changeset, user):
    """The revisions refused for the order of the covers."""
    return [revision for revision, errors
            in validate_changeset_revisions(changeset, _request(user))
            if errors[0].startswith('The cover must be the first sequence.')]


@pytest.mark.django_db
def test_reserved_issue_holds_all_its_sequences(
        any_added_story, story_add_values, any_adding_changeset,
        any_indexer):
    """A reservation holds every sequence; a flip book is submitted."""
    changeset = _reserve(any_added_story, any_indexer, story_add_values,
                         any_adding_changeset, covers=(0, 2))
    issue_revision = changeset.issuerevisions.get()
    assert [story.type_id for story in issue_revision.active_stories()] \
        == [COVER, STORY, COVER]

    submit.__wrapped__(_request(any_indexer, 'Checked.'), changeset.id)

    changeset.refresh_from_db()
    assert changeset.state == states.PENDING


@pytest.mark.django_db
def test_submission_refuses_cover_after_story(
        any_added_story, story_add_values, any_adding_changeset,
        any_indexer):
    changeset = _reserve(any_added_story, any_indexer, story_add_values,
                         any_adding_changeset)
    _cover(story_add_values, changeset, 2)
    issue_revision = changeset.issuerevisions.get()

    invalid = validate_changeset_revisions(changeset, _request(any_indexer))

    messages = [errors for revision, errors in invalid
                if revision == issue_revision]
    assert len(messages) == 1
    assert messages[0][0].startswith('The cover must be the first sequence.')
    assert 'Wiki "Type", Cover: "The front cover' in messages[0][0]


@pytest.mark.django_db
def test_deleting_the_first_cover_is_refused(
        any_added_story, story_add_values, any_adding_changeset,
        any_indexer):
    """Without the first cover of a flip book, a cover follows the story."""
    changeset = _reserve(any_added_story, any_indexer, story_add_values,
                         any_adding_changeset, covers=(0, 2))
    changeset.storyrevisions.get(sequence_number=0).toggle_deleted()

    assert _cover_order_errors(changeset, any_indexer) \
        == [changeset.issuerevisions.get()]


@pytest.mark.django_db
def test_approved_covers_out_of_order_stay_editable(
        any_added_story, story_add_values, any_adding_changeset,
        any_indexer):
    changeset = _reserve(any_added_story, any_indexer, story_add_values,
                         any_adding_changeset, covers=(2,))

    assert validate_changeset_revisions(
      changeset, _request(any_indexer)) == []
