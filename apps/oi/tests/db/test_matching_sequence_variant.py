# -*- coding: utf-8 -*-
"""Which sequences a reprint link may create in the issue being edited."""

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import Issue, StoryType, VCS_Codes
from apps.oi import states
from apps.oi.models import (
    CTYPES, Changeset, IssueRevision, ReprintRevision, RevisionLock,
    StoryRevision)

NOT_DIFFERENT = ('A cover sequence can only be added to a variant if its '
                 'cover artwork is different from the base issue.')
ONLY_COVER = 'Only a cover sequence can be added to a variant issue.'
ONLY_ONE = 'You cannot add more than one cover sequence to a variant issue.'
ROUTES = ['confirm', 'create', 'edit', 'edit_qualifier']
BUTTONS = ['matching_sequence', 'matching_sequence_with_qualifiers']


@pytest.fixture
def indexer_client(client, any_indexer):
    """Return a client of the indexer holding the changesets."""
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)
    return client


@pytest.fixture
def cover_story(any_added_story):
    """Return an approved cover sequence."""
    any_added_story.type = StoryType.objects.get(name='cover')
    any_added_story.save()
    return any_added_story


def set_cover_status(variant, status):
    """Give the variant and its approved revision the status."""
    Issue.objects.filter(pk=variant.pk).update(variant_cover_status=status)
    IssueRevision.objects.filter(issue=variant.pk).update(
      variant_cover_status=status)
    variant.refresh_from_db()


def add_approved_cover(variant, indexer, story_add_values):
    """Give the variant an approved cover sequence of its own."""
    changeset = Changeset(state=states.OPEN, indexer=indexer,
                          change_type=CTYPES['issue_add'])
    changeset.save()
    values = dict(story_add_values, issue=variant, sequence_number=0,
                  type=StoryType.objects.get(name='cover'))
    revision = StoryRevision(changeset=changeset, **values)
    revision.save()
    revision.commit_to_display()
    changeset.state = states.APPROVED
    changeset.save()


def reserve(issue, indexer):
    """Return a changeset holding a revision of the issue and its sequences."""
    changeset = Changeset(state=states.OPEN, indexer=indexer,
                          change_type=CTYPES['issue'])
    changeset.save()
    RevisionLock.objects.create(locked_object=issue, changeset=changeset)
    IssueRevision.clone(data_object=issue, changeset=changeset).save()
    for story in issue.active_stories():
        RevisionLock.objects.create(locked_object=story, changeset=changeset)
        StoryRevision.clone(data_object=story, changeset=changeset)
    return changeset


def link_to_issue(story, issue, changeset, issue_is_target=True):
    """Return a reprint revision between the story and the whole issue."""
    if issue_is_target:
        reprint = ReprintRevision(changeset=changeset, origin=story,
                                  target_issue=issue)
    else:
        reprint = ReprintRevision(changeset=changeset, target=story,
                                  origin_issue=issue)
    reprint.save()
    return reprint


def approved_link(story, issue, indexer):
    """Return an approved reprint link from the story to the whole issue."""
    changeset = Changeset(state=states.OPEN, indexer=indexer,
                          change_type=CTYPES['issue'])
    changeset.save()
    revision = ReprintRevision(changeset=changeset, origin=story,
                               target_issue=issue)
    revision.save()
    revision.commit_to_display()
    changeset.state = states.APPROVED
    changeset.save()
    return ReprintRevision.objects.get(pk=revision.pk).reprint


def confirm_new_link(client, button, changeset, story, issue,
                     direction='from'):
    """Press a button of the page which confirms a new reprint link."""
    url = reverse('save_issue_story_reprint', kwargs={
      'reprint_revision_id': 'new', 'issue_one_id': issue.id,
      'changeset_id': changeset.id, 'story_two_id': story.id})
    return client.post(url, {'direction': direction, button: '',
                             'reprint_link_notes': 'A note',
                             'comments': 'A comment'})


def press_on_approved_link(client, button, link, changeset):
    """Press a button of the reprint overview on an approved link."""
    return client.post(reverse('reserve_reprint', kwargs={
      'reprint_id': link.id, 'changeset_id': changeset.id}), {button: ''})


def link_lock_exists(link, changeset):
    """Return whether the changeset holds the lock of the approved link."""
    return RevisionLock.objects.filter(
      changeset=changeset, object_id=link.id,
      content_type=ContentType.objects.get_for_model(link)).exists()


def request_sequence(client, route, reprint, story, issue):
    """Ask for the corresponding sequence the way the given route does."""
    kwargs = {'reprint_revision_id': reprint.id, 'story_id': story.id,
              'issue_id': issue.id}
    if route == 'confirm':
        return client.get(reverse('create_matching_sequence', kwargs=kwargs))
    if route == 'create':
        return client.post(reverse('create_matching_sequence', kwargs=kwargs),
                           {'create': 'Create Sequence'})
    name = {'edit': 'create_edit_matching_sequence',
            'edit_qualifier': 'create_edit_matching_sequence_qualifier'}
    return client.get(reverse(name[route], kwargs=kwargs))


def added_sequences(changeset):
    """Return the revisions of sequences new in the changeset."""
    return StoryRevision.objects.filter(changeset=changeset,
                                        previous_revision=None)


def assert_refused(response, message, changeset, reprint, issue_is_target):
    """Check for the message, no new sequence, and the link left alone."""
    assert response.status_code == 200
    assert message in response.content.decode()
    assert not added_sequences(changeset).exists()
    reprint.refresh_from_db()
    if issue_is_target:
        assert reprint.target_issue_id is not None
        assert reprint.target_revision_id is None
    else:
        assert reprint.origin_issue_id is not None
        assert reprint.origin_revision_id is None


@pytest.mark.django_db
@pytest.mark.parametrize('route', ROUTES)
def test_variant_refuses_a_sequence_which_is_no_cover(
      indexer_client, any_indexer, any_added_story, any_added_variant, route):
    set_cover_status(any_added_variant, VCS_Codes.ARTWORK_DIFFERENCE)
    changeset = reserve(any_added_variant, any_indexer)
    reprint = link_to_issue(any_added_story, any_added_variant, changeset)

    response = request_sequence(indexer_client, route, reprint,
                                any_added_story, any_added_variant)

    assert_refused(response, ONLY_COVER, changeset, reprint, True)


@pytest.mark.django_db
def test_variant_refuses_a_sequence_from_a_link_in_the_other_direction(
      indexer_client, any_indexer, any_added_story, any_added_variant):
    set_cover_status(any_added_variant, VCS_Codes.ARTWORK_DIFFERENCE)
    changeset = reserve(any_added_variant, any_indexer)
    reprint = link_to_issue(any_added_story, any_added_variant, changeset,
                            issue_is_target=False)

    response = request_sequence(indexer_client, 'create', reprint,
                                any_added_story, any_added_variant)

    assert_refused(response, ONLY_COVER, changeset, reprint, False)


@pytest.mark.django_db
@pytest.mark.parametrize('route', ROUTES)
def test_variant_refuses_a_second_sequence(
      indexer_client, any_indexer, cover_story, any_added_variant,
      story_add_values, route):
    set_cover_status(any_added_variant, VCS_Codes.ARTWORK_DIFFERENCE)
    add_approved_cover(any_added_variant, any_indexer, story_add_values)
    changeset = reserve(any_added_variant, any_indexer)
    reprint = link_to_issue(cover_story, any_added_variant, changeset)

    response = request_sequence(indexer_client, route, reprint, cover_story,
                                any_added_variant)

    assert_refused(response, ONLY_ONE, changeset, reprint, True)


@pytest.mark.django_db
@pytest.mark.parametrize('status', [VCS_Codes.NO_DIFFERENCE,
                                    VCS_Codes.ONLY_SCAN_DIFFERENCE])
@pytest.mark.parametrize('route', ROUTES)
def test_variant_with_the_cover_of_the_base_refuses_a_cover_sequence(
      indexer_client, any_indexer, cover_story, any_added_variant, status,
      route):
    set_cover_status(any_added_variant, status)
    changeset = reserve(any_added_variant, any_indexer)
    reprint = link_to_issue(cover_story, any_added_variant, changeset)

    response = request_sequence(indexer_client, route, reprint, cover_story,
                                any_added_variant)

    assert_refused(response, NOT_DIFFERENT, changeset, reprint, True)


@pytest.mark.django_db
@pytest.mark.parametrize('route', ['create', 'edit', 'edit_qualifier'])
def test_variant_with_different_artwork_gets_its_cover_sequence(
      indexer_client, any_indexer, cover_story, any_added_variant, route):
    set_cover_status(any_added_variant, VCS_Codes.ARTWORK_DIFFERENCE)
    changeset = reserve(any_added_variant, any_indexer)
    reprint = link_to_issue(cover_story, any_added_variant, changeset)

    response = request_sequence(indexer_client, route, reprint, cover_story,
                                any_added_variant)

    added = added_sequences(changeset).get()
    assert added.type.name == 'cover'
    assert added.issue == any_added_variant
    assert response.status_code == 302
    assert response.url == reverse(
      'edit_revision', kwargs={'model_name': 'story', 'id': added.id})
    reprint.refresh_from_db()
    assert reprint.target_revision == added
    assert reprint.target_issue is None


@pytest.mark.django_db
def test_confirmation_page_stays_for_a_cover_of_a_different_variant(
      indexer_client, any_indexer, cover_story, any_added_variant):
    set_cover_status(any_added_variant, VCS_Codes.ARTWORK_DIFFERENCE)
    changeset = reserve(any_added_variant, any_indexer)
    reprint = link_to_issue(cover_story, any_added_variant, changeset)

    response = request_sequence(indexer_client, 'confirm', reprint,
                                cover_story, any_added_variant)

    assert response.status_code == 200
    assert 'Create Matching Sequence' in response.content.decode()
    assert not added_sequences(changeset).exists()


@pytest.mark.django_db
def test_variant_takes_a_cover_sequence_when_its_own_is_marked_deleted(
      indexer_client, any_indexer, cover_story, any_added_variant,
      story_add_values):
    set_cover_status(any_added_variant, VCS_Codes.ARTWORK_DIFFERENCE)
    add_approved_cover(any_added_variant, any_indexer, story_add_values)
    changeset = reserve(any_added_variant, any_indexer)
    changeset.storyrevisions.update(deleted=True)
    reprint = link_to_issue(cover_story, any_added_variant, changeset)

    response = request_sequence(indexer_client, 'create', reprint,
                                cover_story, any_added_variant)

    assert response.status_code == 302
    assert added_sequences(changeset).get().type.name == 'cover'


@pytest.mark.django_db
def test_sequence_is_added_with_the_issue_revision_locked(
      indexer_client, any_indexer, cover_story, any_added_variant):
    set_cover_status(any_added_variant, VCS_Codes.ARTWORK_DIFFERENCE)
    changeset = reserve(any_added_variant, any_indexer)
    reprint = link_to_issue(cover_story, any_added_variant, changeset)

    with CaptureQueriesContext(connection) as queries:
        request_sequence(indexer_client, 'create', reprint, cover_story,
                         any_added_variant)

    table = IssueRevision._meta.db_table
    assert any(table in query['sql'] and 'FOR UPDATE' in query['sql']
               for query in queries)


@pytest.mark.django_db
@pytest.mark.parametrize('direction', ['from', 'to'])
@pytest.mark.parametrize('button', BUTTONS)
def test_refused_sequence_leaves_a_new_link_unsaved(
      indexer_client, any_indexer, any_added_story, any_added_variant, button,
      direction):
    set_cover_status(any_added_variant, VCS_Codes.ARTWORK_DIFFERENCE)
    changeset = reserve(any_added_variant, any_indexer)

    response = confirm_new_link(indexer_client, button, changeset,
                                any_added_story, any_added_variant, direction)

    assert response.status_code == 200
    assert ONLY_COVER in response.content.decode()
    assert not ReprintRevision.objects.filter(changeset=changeset).exists()
    assert not added_sequences(changeset).exists()


@pytest.mark.django_db
def test_allowed_sequence_saves_the_new_link_and_goes_on(
      indexer_client, any_indexer, cover_story, any_added_variant):
    set_cover_status(any_added_variant, VCS_Codes.ARTWORK_DIFFERENCE)
    changeset = reserve(any_added_variant, any_indexer)

    response = confirm_new_link(indexer_client, 'matching_sequence',
                                changeset, cover_story, any_added_variant)

    link = ReprintRevision.objects.get(changeset=changeset)
    assert response.status_code == 302
    assert response.url == reverse(
      'create_edit_matching_sequence',
      kwargs={'reprint_revision_id': link.id, 'story_id': cover_story.id,
              'issue_id': any_added_variant.id})


@pytest.mark.django_db
def test_new_link_without_a_sequence_is_still_saved_on_a_variant(
      indexer_client, any_indexer, any_added_story, any_added_variant):
    set_cover_status(any_added_variant, VCS_Codes.ARTWORK_DIFFERENCE)
    changeset = reserve(any_added_variant, any_indexer)

    response = confirm_new_link(indexer_client, 'add_reprint_view',
                                changeset, any_added_story, any_added_variant)

    assert response.status_code == 302
    assert ReprintRevision.objects.filter(changeset=changeset).exists()


@pytest.mark.django_db
def test_refused_sequence_leaves_an_approved_link_unreserved(
      indexer_client, any_indexer, any_added_story, any_added_variant):
    set_cover_status(any_added_variant, VCS_Codes.ARTWORK_DIFFERENCE)
    link = approved_link(any_added_story, any_added_variant, any_indexer)
    changeset = reserve(any_added_variant, any_indexer)

    response = press_on_approved_link(indexer_client, 'matching_sequence',
                                      link, changeset)

    assert response.status_code == 200
    assert ONLY_COVER in response.content.decode()
    assert not ReprintRevision.objects.filter(changeset=changeset).exists()
    assert not link_lock_exists(link, changeset)


@pytest.mark.django_db
def test_allowed_sequence_reserves_the_approved_link_and_goes_on(
      indexer_client, any_indexer, cover_story, any_added_variant):
    set_cover_status(any_added_variant, VCS_Codes.ARTWORK_DIFFERENCE)
    link = approved_link(cover_story, any_added_variant, any_indexer)
    changeset = reserve(any_added_variant, any_indexer)

    response = press_on_approved_link(indexer_client, 'matching_sequence',
                                      link, changeset)

    revision = ReprintRevision.objects.get(changeset=changeset)
    assert response.status_code == 302
    assert response.url == reverse(
      'edit_reprint', kwargs={'id': revision.id,
                              'which_side': 'matching_sequence'})
    assert link_lock_exists(link, changeset)


@pytest.mark.django_db
def test_other_buttons_still_reserve_an_approved_link_of_a_variant(
      indexer_client, any_indexer, any_added_story, any_added_variant):
    set_cover_status(any_added_variant, VCS_Codes.ARTWORK_DIFFERENCE)
    link = approved_link(any_added_story, any_added_variant, any_indexer)
    changeset = reserve(any_added_variant, any_indexer)

    response = press_on_approved_link(indexer_client, 'delete', link,
                                      changeset)

    assert response.status_code == 302
    assert link_lock_exists(link, changeset)


@pytest.mark.django_db
def test_issue_which_is_no_variant_takes_any_sequence(
      indexer_client, any_indexer, any_added_story, any_added_variant):
    # The link needs an issue other than the one of the sequence.
    base = Issue.objects.get(pk=any_added_variant.variant_of_id)
    any_added_story.issue = any_added_variant
    any_added_story.save()
    changeset = reserve(base, any_indexer)
    reprint = link_to_issue(any_added_story, base, changeset)

    response = request_sequence(indexer_client, 'create', reprint,
                                any_added_story, base)

    added = added_sequences(changeset).get()
    assert added.type.name == 'comic story'
    assert added.issue == base
    assert response.status_code == 302
