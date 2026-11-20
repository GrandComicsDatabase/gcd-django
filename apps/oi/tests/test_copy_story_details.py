"""Tests of leaving out the story details when a sequence is copied."""
import re

import pytest
from django.template import Context
from django.template.loader import get_template
from django.template.loader_tags import BlockNode
from django.urls import reverse

from apps.gcd.models import StoryArc, StoryType, Universe
from apps.oi.models import CTYPES, IssueRevision, StoryRevision


@pytest.fixture
def indexer_client(client, any_indexer):
    """Return a client logged in as the holder of the changeset."""
    any_indexer.is_superuser = True
    any_indexer.save()
    client.force_login(any_indexer)
    return client


@pytest.fixture
def story_with_details(any_added_story, any_language):
    """Return an approved sequence with a value in each of the details."""
    story = any_added_story
    story.first_line = 'It was a dark night.'
    story.save()
    story.story_arc.add(StoryArc.objects.create(
      name='Some Arc', sort_name='Some Arc', language=any_language))
    story.universe.add(Universe.objects.create(name='Some Universe',
                                               designation='Earth-1'))
    return story


@pytest.fixture
def issue_revision(any_added_issue, any_editing_changeset):
    """Return the revision of an issue that a sequence can be copied into."""
    any_editing_changeset.change_type = CTYPES['issue']
    any_editing_changeset.save()
    return IssueRevision.clone(data_object=any_added_issue,
                               changeset=any_editing_changeset)


def _assert_details_left_out(revision):
    """Check that a revision has none of the details."""
    for field in ('first_line', 'job_number', 'keywords', 'synopsis', 'notes',
                  'reprint_notes'):
        assert getattr(revision, field) == '', field
    assert not revision.story_arc.exists()
    assert not revision.universe.exists()


def _assert_job_kept(revision):
    """Check that a revision still has what the option does not touch."""
    assert revision.title == 'Test Story Title'
    assert revision.feature == 'Test Feature'
    assert revision.script == 'Test Person One'
    assert revision.genre == 'something contentious'
    assert revision.page_count == 8


def _assert_details_kept(revision):
    """Check that a revision has all the details of the original."""
    assert revision.first_line == 'It was a dark night.'
    assert revision.job_number == '1234'
    assert revision.synopsis == 'Stuff happened.'
    assert revision.notes == 'Random extra info'
    assert revision.reprint_notes == 'Not bothering to format this properly.'
    assert revision.story_arc.count() == 1
    assert revision.universe.count() == 1


def _confirm_copy_url(issue_revision, story):
    """Return the address the confirmation page of a copy posts to."""
    return reverse('confirm_copy_story',
                   kwargs={'issue_revision_id': issue_revision.id,
                           'story_id': story.id, 'sequence_number': 1})


def _new_revision(changeset, exclude=None):
    """Return the only revision of a sequence the copy has added."""
    revisions = changeset.storyrevisions.all()
    if exclude:
        revisions = revisions.exclude(id=exclude.id)
    return revisions.get()


def test_details_are_the_fields_the_option_names():
    """The set must match the list of fields in the label of the option."""
    from apps.oi.models import STORY_DETAIL_FIELDS

    assert STORY_DETAIL_FIELDS == {
      'first_line', 'job_number', 'story_arc', 'universe', 'keywords',
      'synopsis', 'notes', 'reprint_notes'}


@pytest.mark.django_db
def test_detail_fields_are_all_fields_of_a_sequence():
    """A name that is not a field would be ignored without a word."""
    from apps.oi.models import STORY_DETAIL_FIELDS

    fields = (set(StoryRevision._get_single_value_fields()) |
              set(StoryRevision._get_multi_value_fields()) |
              set(StoryRevision._get_regular_fields()))
    assert STORY_DETAIL_FIELDS <= fields


@pytest.mark.django_db
def test_copied_revision_can_leave_out_the_details(story_with_details,
                                                   issue_revision):
    """Copying a sequence with the option leaves the details empty."""
    revision = StoryRevision.copied_revision(
      story_with_details, issue_revision.changeset,
      issue_revision=issue_revision, omit_story_details=True)

    _assert_details_left_out(revision)
    _assert_job_kept(revision)


@pytest.mark.django_db
def test_copied_revision_keeps_the_details_by_default(story_with_details,
                                                      issue_revision):
    """Copying a sequence without the option works as it always did."""
    revision = StoryRevision.copied_revision(
      story_with_details, issue_revision.changeset,
      issue_revision=issue_revision)

    _assert_details_kept(revision)
    assert revision.keywords != ''
    _assert_job_kept(revision)


@pytest.mark.django_db
def test_leaving_out_the_details_keeps_the_characters(story_with_details,
                                                      issue_revision):
    """The characters depend only on their own option."""
    revision = StoryRevision.copied_revision(
      story_with_details, issue_revision.changeset,
      issue_revision=issue_revision, copy_characters=True,
      omit_story_details=True)

    assert revision.characters == 'Blah Blah [Whatever]'
    _assert_details_left_out(revision)


@pytest.mark.django_db
def test_clone_revision_can_leave_out_the_details(story_with_details,
                                                  any_edit_story_rev):
    """Copying a revision with the option leaves the details empty."""
    changeset = any_edit_story_rev.changeset

    revision = StoryRevision.clone_revision(
      any_edit_story_rev, changeset,
      issue_revision=changeset.issuerevisions.get(), omit_story_details=True)

    _assert_details_left_out(revision)
    _assert_job_kept(revision)


@pytest.mark.django_db
def test_clone_revision_keeps_the_details_by_default(story_with_details,
                                                     any_edit_story_rev):
    """Copying a revision without the option works as it always did."""
    changeset = any_edit_story_rev.changeset

    revision = StoryRevision.clone_revision(
      any_edit_story_rev, changeset,
      issue_revision=changeset.issuerevisions.get())

    _assert_details_kept(revision)
    _assert_job_kept(revision)


@pytest.mark.django_db
def test_copy_page_leaves_out_the_details_when_ticked(
  indexer_client, story_with_details, issue_revision):
    """The confirmation page passes the option on."""
    response = indexer_client.post(
      _confirm_copy_url(issue_revision, story_with_details),
      {'confirm': 'Confirm Copy', 'omit_story_details': 'True'})

    assert response.status_code == 302
    _assert_details_left_out(_new_revision(issue_revision.changeset))


@pytest.mark.django_db
def test_copy_page_keeps_the_details_when_not_ticked(
  indexer_client, story_with_details, issue_revision):
    """Without the tick the confirmation page copies everything."""
    response = indexer_client.post(
      _confirm_copy_url(issue_revision, story_with_details),
      {'confirm': 'Confirm Copy'})

    assert response.status_code == 302
    _assert_details_kept(_new_revision(issue_revision.changeset))


@pytest.mark.django_db
@pytest.mark.parametrize('ticked', [True, False])
def test_choice_survives_the_review_of_a_cover_copy(
  indexer_client, story_with_details, issue_revision, ticked):
    """The page that reviews a cover copy keeps what the indexer chose."""
    story_with_details.type = StoryType.objects.get(name='cover')
    story_with_details.save()
    data = {'confirm': 'Confirm Copy'}
    if ticked:
        data['omit_story_details'] = 'True'

    response = indexer_client.post(
      _confirm_copy_url(issue_revision, story_with_details), data)

    assert response.status_code == 200
    found = re.search(r'name="omit_story_details"[^>]*checked',
                      response.content.decode())
    assert bool(found) is ticked
    assert not issue_revision.changeset.storyrevisions.exists()


@pytest.mark.django_db
def test_copy_of_a_revision_leaves_out_the_details_when_ticked(
  indexer_client, story_with_details, any_edit_story_rev):
    """The confirmation page of a revision copy passes the option on."""
    changeset = any_edit_story_rev.changeset
    target = changeset.issuerevisions.get()
    url = reverse('confirm_copy_story_revision',
                  kwargs={'issue_revision_id': target.id,
                          'story_revision_id': any_edit_story_rev.id})

    response = indexer_client.post(url, {'confirm': 'Confirm Copy',
                                         'omit_story_details': 'True'})

    assert response.status_code == 302
    _assert_details_left_out(_new_revision(changeset, any_edit_story_rev))


@pytest.mark.django_db
@pytest.mark.parametrize('ticked', [True, False])
def test_each_row_of_a_bulk_copy_has_the_option(story_with_details, ticked):
    """A row posts its own sequence and shows the choice already made."""
    template = get_template('oi/edit/confirm_copy_sequence.html').template
    body = next(block
                for block in template.nodelist.get_nodes_by_type(BlockNode)
                if block.name == 'view_body')
    context = Context({
      'bulk_copy': True, 'stories': [story_with_details],
      'select_key': 'batch', 'label': 'stories',
      'preview_rows': [{'story': story_with_details, 'position': 0,
                        'copy_type': 'comic story',
                        'omit_story_details': ticked}]})

    with context.bind_template(template):
        html = body.nodelist.render(context)

    found = re.search(r'name="omit_story_details_ids"\s+value="%d"\s*(checked)?'
                      % story_with_details.id, html)
    assert found
    assert bool(found.group(1)) is ticked
