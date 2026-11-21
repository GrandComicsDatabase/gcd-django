"""The order of the covers is checked when a change is submitted."""

import pytest

from django.test import RequestFactory

from apps.gcd.models import StoryType, STORY_TYPES
from apps.oi.models import StoryRevision
from apps.oi.views import _covers_out_of_order, validate_changeset_revisions

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


def _cover_after_story(story_add_values, changeset):
    """A cover sequence after the comic story of the issue."""
    return StoryRevision.objects.create(
      changeset=changeset,
      **dict(story_add_values, sequence_number=2,
             type=StoryType.objects.get(id=COVER)))


def _invalid(changeset, user):
    request = RequestFactory().post('/submit/', {'comments': ''})
    request.user = user
    return validate_changeset_revisions(changeset, request)


@pytest.mark.django_db
def test_submission_refuses_cover_after_story(
        any_edit_story_rev, story_add_values, any_indexer):
    changeset = any_edit_story_rev.changeset
    _cover_after_story(story_add_values, changeset)
    issue_revision = changeset.issuerevisions.get()

    invalid = _invalid(changeset, any_indexer)

    messages = [errors for revision, errors in invalid
                if revision == issue_revision]
    assert len(messages) == 1
    assert messages[0][0].startswith('The cover must be the first sequence.')
    assert 'Wiki "Type", Cover: "The front cover' in messages[0][0]


@pytest.mark.django_db
def test_approved_covers_out_of_order_stay_editable(
        any_edit_story_rev, story_add_values, any_adding_changeset,
        any_indexer):
    cover = _cover_after_story(story_add_values, any_adding_changeset)
    cover.commit_to_display()
    changeset = any_edit_story_rev.changeset
    StoryRevision.clone(data_object=cover.story, changeset=changeset)

    assert _invalid(changeset, any_indexer) == []
