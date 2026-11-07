# -*- coding: utf-8 -*-


import pytest

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, connection
from django.test.utils import CaptureQueriesContext
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.utils import timezone

from apps.gcd.models.cover import VALID_BOX_COVER
from apps.gcd.models import (
    Character, CharacterNameDetail, Cover, CoverCharacterBox,
    Issue,
    StoryCharacter, StoryType, Universe, STORY_TYPES)
from apps.gcd.models.story import CharacterRole
from apps.indexer.models import Indexer
from apps.oi.models import (
    Changeset, CoverCharacterBoxRevision, CoverRevision, IssueRevision,
    RevisionLock,
    StoryCharacterRevision, StoryRevision, CTYPES,
    _get_revision_lock)
from apps.oi import states
from apps.gcd.templatetags.display import changed_story_list


# Three corners of a rectangle turned a quarter counterclockwise, for art
# printed sideways: x in 1/10000 of the width of the front, y in 1/10000 of
# its height; the scan is 400 x 615 pixels.
BOX_VALUES = {
    'top_left_x': 1000,
    'top_left_y': 6500,
    'top_right_x': 1000,
    'top_right_y': 2000,
    'bottom_left_x': 4000,
    'bottom_left_y': 6500,
    'scan_aspect': 15375,
}


def make_name(name, any_language):
    """
    Creates a character and returns its official name.
    """
    character = Character.objects.create(
        name=name,
        sort_name=name,
        disambiguation='',
        language=any_language,
        description='',
        notes='')
    return CharacterNameDetail.objects.create(
        name=name,
        sort_name=name,
        character=character,
        is_official_name=True)


def make_appearance(name_detail, any_added_story_rev, any_added_story):
    """
    Creates an approved appearance of the character name in the story.
    """
    appearance = StoryCharacter.objects.create(
        character=name_detail,
        story=any_added_story,
        notes='')
    StoryCharacterRevision.objects.create(
        changeset=any_added_story_rev.changeset,
        committed=True,
        story_character=appearance,
        character=name_detail,
        story_revision=any_added_story_rev,
        notes='')
    return appearance


def make_box(appearance, cover, changeset):
    """
    Creates an approved box of the appearance on the cover.
    """
    box = CoverCharacterBox.objects.create(
        story_character=appearance, cover=cover, **BOX_VALUES)
    CoverCharacterBoxRevision.objects.create(
        changeset=changeset,
        committed=True,
        cover_character_box=box,
        story_character_revision=appearance.revisions.get(),
        cover=cover,
        **BOX_VALUES)
    return box


def make_variant(issue, status):
    """
    Creates a variant of the issue with the variant cover status.
    """
    return Issue.objects.create(
        number=issue.number, series=issue.series,
        sort_code=issue.sort_code + status,
        publication_date=issue.publication_date, key_date=issue.key_date,
        variant_of=issue, variant_name='Variant %d' % status,
        variant_cover_status=status)


@pytest.fixture
def box_world(any_added_story_rev, any_added_story, any_language,
              any_indexer):
    """
    A cover sequence with an approved appearance of Alpha and its approved
    box on the issue cover, drawn on art printed sideways; a second
    appearance of Alpha with a box on the same cover; and a function
    opening a changeset that edits the first appearance.
    """
    cover_type = StoryType.objects.get(id=STORY_TYPES['cover'])
    for sequence in (any_added_story, any_added_story_rev):
        sequence.type = cover_type
        sequence.save()
    name_detail = make_name('Alpha', any_language)
    changeset = any_added_story_rev.changeset
    cover = Cover.objects.create(issue=any_added_story.issue)
    appearance = make_appearance(name_detail, any_added_story_rev,
                                 any_added_story)
    box = make_box(appearance, cover, changeset)
    other_box = make_box(
        make_appearance(name_detail, any_added_story_rev, any_added_story),
        cover, changeset)

    def editing_revisions():
        """An open change with the revisions of the sequence and appearance."""
        changeset = Changeset.objects.create(
            state=states.OPEN,
            indexer=any_indexer,
            change_type=CTYPES['issue'])
        story_revision = StoryRevision.clone(
            any_added_story, changeset=changeset)
        character_revision = StoryCharacterRevision.clone(
            appearance,
            changeset=changeset,
            story_revision=story_revision)
        return changeset, story_revision, character_revision

    return {
        'appearance': appearance,
        'cover': cover,
        'box': box,
        'other_box': other_box,
        'editing_revisions': editing_revisions,
    }


def edited_box(box_world):
    """
    Opens a changeset editing the first appearance and clones its box,
    returning the changeset, the sequence, appearance and box revisions.
    """
    changeset, story_revision, character_revision = \
        box_world['editing_revisions']()
    revision = CoverCharacterBoxRevision.clone(
        box_world['box'],
        changeset=changeset,
        story_character_revision=character_revision)
    return changeset, story_revision, character_revision, revision


def commit_again(revision):
    """
    Commits the box revision read again from the database, as
    Changeset.approve does after the appearance, sequence and covers.
    """
    revision.refresh_from_db()
    revision.commit_to_display()


def move_box(revision):
    """
    Draws the box of the revision again a little to the right.
    """
    for name in ('top_left_x', 'top_right_x', 'bottom_left_x'):
        setattr(revision, name, getattr(revision, name) + 100)
    revision.save()


def issue_changeset(issue, indexer, delete=False):
    """
    Reserves the issue as the reservation view does: the issue is locked
    and cloned, then its dependent objects are locked and cloned.
    """
    changeset = Changeset.objects.create(
        state=states.UNRESERVED if delete else states.OPEN,
        indexer=indexer,
        change_type=CTYPES['issue'])
    _get_revision_lock(issue, changeset=changeset)
    revision = IssueRevision.clone(issue, changeset)
    if delete:
        revision.deleted = True
        revision.save()
    revision._create_dependent_revisions(delete=delete)
    return changeset


def box_locks(*boxes):
    """
    The revision locks held on the boxes.
    """
    return RevisionLock.objects.filter(
        content_type=ContentType.objects.get_for_model(CoverCharacterBox),
        object_id__in=[box.id for box in boxes])


@pytest.mark.django_db
def test_commit_adds_box_to_appearance(box_world, any_added_story_rev,
                                       any_added_story, any_language):
    """An added box is linked to the appearance and the cover."""
    other = make_appearance(make_name('Beta', any_language),
                            any_added_story_rev, any_added_story)
    changeset, story_revision, _ = box_world['editing_revisions']()
    character_revision = StoryCharacterRevision.clone(
        other, changeset=changeset, story_revision=story_revision)
    scan_date = timezone.now()
    revision = CoverCharacterBoxRevision.objects.create(
        changeset=changeset,
        story_character_revision=character_revision,
        cover=box_world['cover'],
        scan_date=scan_date,
        **BOX_VALUES)

    revision.commit_to_display()

    box = other.cover_boxes.get()
    assert revision.cover_character_box == box
    assert box.cover == box_world['cover']
    for field, value in BOX_VALUES.items():
        assert getattr(box, field) == value
    assert box.scan_date == scan_date


@pytest.mark.django_db
def test_commit_links_box_to_appearance_added_in_same_change(
      box_world, any_added_story, any_language):
    """A box can point to an appearance added in the same changeset."""
    changeset, story_revision, _ = box_world['editing_revisions']()
    character_revision = StoryCharacterRevision.objects.create(
        changeset=changeset,
        character=make_name('Gamma', any_language),
        story_revision=story_revision,
        notes='')
    revision = CoverCharacterBoxRevision.objects.create(
        changeset=changeset,
        story_character_revision=character_revision,
        cover=box_world['cover'],
        **BOX_VALUES)

    # As in Changeset.approve, the appearance is committed first and the
    # box revision is read again from the database.
    character_revision.commit_to_display()
    commit_again(revision)

    appearance = character_revision.story_character
    assert appearance.story == any_added_story
    assert revision.cover_character_box.story_character == appearance


@pytest.mark.django_db
def test_commit_edits_cloned_box(box_world):
    """A cloned box keeps its appearance and takes the edited values."""
    _, _, character_revision, revision = edited_box(box_world)
    assert revision.story_character_revision == character_revision
    assert revision.previous_revision is not None
    assert revision.top_left_y == 6500
    assert revision.scan_aspect == 15375
    # Redrawn upright on a new scan.
    revision.top_left_y = 2000
    revision.top_right_x = 4000
    revision.bottom_left_x = 1000
    revision.scan_aspect = 15000
    revision.save()

    revision.commit_to_display()

    box = CoverCharacterBox.objects.get(id=box_world['box'].id)
    assert (box.top_left_x, box.top_left_y, box.top_right_x,
            box.top_right_y, box.bottom_left_x,
            box.bottom_left_y) == (1000, 2000, 4000, 2000, 1000, 6500)
    assert box.scan_aspect == 15000
    assert box.story_character == box_world['appearance']
    assert box.cover == box_world['cover']


@pytest.mark.django_db
def test_commit_deletes_removed_box(box_world):
    """A removed box is deleted."""
    box_id = box_world['box'].id
    _, _, _, revision = edited_box(box_world)
    revision.deleted = True
    revision.save()

    revision.commit_to_display()

    assert not CoverCharacterBox.objects.filter(id=box_id).exists()
    assert revision.committed is True
    assert revision.cover_character_box is None


@pytest.mark.django_db
def test_commit_deletes_box_of_deleted_appearance(box_world):
    """
    The appearance is only marked as deleted, so its box is deleted
    explicitly.
    """
    box_id = box_world['box'].id
    _, _, character_revision, revision = edited_box(box_world)
    character_revision.deleted = True
    character_revision.save()

    character_revision.commit_to_display()
    commit_again(revision)

    box_world['appearance'].refresh_from_db()
    assert box_world['appearance'].deleted is True
    assert not CoverCharacterBox.objects.filter(id=box_id).exists()
    assert revision.deleted is True
    assert revision.committed is True


@pytest.mark.django_db
def test_commit_deletes_box_of_deleted_sequence(box_world):
    """A deleted sequence takes the boxes of its appearances along."""
    box_id = box_world['box'].id
    _, story_revision, _, revision = edited_box(box_world)
    # Only the sequence is marked, to check the rule of the sequence.
    story_revision.deleted = True
    story_revision.save()

    commit_again(revision)

    assert not CoverCharacterBox.objects.filter(id=box_id).exists()


@pytest.mark.django_db
def test_commit_deletes_box_of_sequence_no_longer_cover(box_world):
    """A sequence changed away from the cover type loses its boxes."""
    box_id = box_world['box'].id
    _, story_revision, _, revision = edited_box(box_world)
    story_revision.type = StoryType.objects.get(
        id=STORY_TYPES['comic story'])
    story_revision.save()

    commit_again(revision)

    assert not CoverCharacterBox.objects.filter(id=box_id).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('changed', ['character', 'universe'])
def test_commit_keeps_box_following_its_appearance(
      box_world, any_language, changed):
    """
    An appearance changed to another character or universe keeps its
    box, which goes with it to its new character pages.
    """
    _, _, character_revision, revision = edited_box(box_world)
    if changed == 'character':
        character_revision.character = make_name('Beta', any_language)
    else:
        character_revision.universe = Universe.objects.create(
            multiverse='', name='Second Earth', designation='Earth-2',
            description='', notes='')
    character_revision.save()

    character_revision.commit_to_display()
    commit_again(revision)

    box = CoverCharacterBox.objects.get(id=box_world['box'].id)
    assert box.story_character == box_world['appearance']
    assert box.story_character.character == character_revision.character
    assert box.story_character.universe == character_revision.universe


@pytest.mark.django_db
def test_commit_keeps_box_on_other_name_role_or_flashback(box_world):
    """
    Another name of the same character, a role, a flashback or notes keep
    the box of the appearance.
    """
    _, _, character_revision, revision = edited_box(box_world)
    character = character_revision.character.character
    character_revision.character = CharacterNameDetail.objects.create(
        name='Alpha Prime', sort_name='Alpha Prime', character=character)
    character_revision.role = CharacterRole.objects.create(
        name='Test role', sort_code=99999)
    character_revision.is_flashback = True
    character_revision.notes = 'as a child'
    character_revision.save()

    character_revision.commit_to_display()
    commit_again(revision)

    assert CoverCharacterBox.objects.filter(
        id=box_world['box'].id).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('target', ['variant', 'other issue'])
def test_commit_deletes_box_of_sequence_moved_to_variant(box_world, target):
    """
    A cover sequence moved to a variant, or to another issue as a change
    of two issues does, is no longer shown on the cover of the issue, so
    its boxes there are deleted.
    """
    box_id = box_world['box'].id
    _, story_revision, _, revision = edited_box(box_world)
    issue = story_revision.issue
    if target == 'variant':
        story_revision.issue = make_variant(issue, 2)
    else:
        story_revision.issue = Issue.objects.create(
            number='99', series=issue.series, sort_code=issue.sort_code + 99,
            publication_date=issue.publication_date, key_date=issue.key_date)
    story_revision.save()

    commit_again(revision)

    assert not CoverCharacterBox.objects.filter(id=box_id).exists()


@pytest.mark.django_db
def test_issue_deletion_clones_boxes_as_deleted(box_world,
                                                any_indexer):
    """
    Deleting the issue clones the boxes of its cover sequence as deleted,
    with their locks, and their commit deletes them.
    """
    boxes = (box_world['box'], box_world['other_box'])
    changeset = issue_changeset(box_world['cover'].issue, any_indexer,
                                delete=True)

    revisions = changeset.covercharacterboxrevisions.all()
    assert {revision.cover_character_box for revision in revisions} == \
        set(boxes)
    assert all(revision.deleted for revision in revisions)
    assert box_locks(*boxes).filter(changeset=changeset).count() == 2

    for revision in revisions:
        revision.commit_to_display()

    assert not CoverCharacterBox.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize('removed', ['box', 'appearance'])
def test_commit_of_box_added_and_removed_only_marks_it(box_world,
                                                       removed):
    """
    A box added and removed in the same changeset, by itself or with its
    appearance, writes nothing; the revision is only marked as committed.
    """
    changeset, _, character_revision = box_world['editing_revisions']()
    revision = CoverCharacterBoxRevision.objects.create(
        changeset=changeset,
        story_character_revision=character_revision,
        cover=box_world['cover'],
        deleted=removed == 'box',
        **BOX_VALUES)
    if removed == 'appearance':
        character_revision.deleted = True
        character_revision.save()

    commit_again(revision)

    assert revision.committed is True
    assert revision.deleted is True
    assert revision.cover_character_box is None
    assert CoverCharacterBox.objects.count() == 2


@pytest.mark.django_db
def test_commit_keeps_box_on_replaced_scan(box_world):
    """
    A replaced scan keeps the box, left out of the character page until
    it is saved on the new scan.
    """
    cover = box_world['cover']
    cover.last_upload = timezone.now()
    cover.save()
    _, _, _, revision = edited_box(box_world)

    commit_again(revision)

    box = CoverCharacterBox.objects.get(id=box_world['box'].id)
    assert box.scan_date != cover.last_upload


@pytest.mark.django_db
@pytest.mark.parametrize('field', ['deleted', 'limit_display'])
def test_commit_keeps_box_on_hidden_cover(box_world, field):
    """
    A deleted cover or one with a limited display only hides its boxes,
    so they are kept.
    """
    cover = box_world['cover']
    setattr(cover, field, True)
    cover.save()
    _, _, _, revision = edited_box(box_world)

    commit_again(revision)

    assert CoverCharacterBox.objects.filter(
        id=box_world['box'].id).exists()


@pytest.mark.django_db
def test_reservation_locks_boxes_and_discard_frees_them(box_world,
                                                        any_indexer):
    """
    Reserving the issue clones the boxes of the cover sequence with their
    locks; discarding the changeset frees them for the next reservation.
    """
    boxes = (box_world['box'], box_world['other_box'])
    issue = box_world['cover'].issue
    changeset = issue_changeset(issue, any_indexer)
    revisions = changeset.covercharacterboxrevisions.all()
    assert {revision.cover_character_box for revision in revisions} == \
        set(boxes)
    assert box_locks(*boxes).filter(changeset=changeset).count() == 2

    changeset.discard(any_indexer)

    assert not box_locks(*boxes).exists()
    assert not changeset.covercharacterboxrevisions.exclude(
        committed=False).exists()
    second_changeset = issue_changeset(issue, any_indexer)
    assert second_changeset.covercharacterboxrevisions.count() == 2


@pytest.mark.django_db
def test_reservation_needs_the_locks_of_the_boxes(box_world, any_indexer):
    """
    A box locked by another change stops the reservation of its issue,
    which would otherwise edit it twice.
    """
    other = Changeset.objects.create(
        state=states.OPEN, indexer=any_indexer, change_type=CTYPES['issue'])
    _get_revision_lock(box_world['box'], changeset=other)

    with pytest.raises(IntegrityError):
        issue_changeset(box_world['cover'].issue, any_indexer)


@pytest.mark.django_db
def test_approval_commits_cloned_boxes_after_appearances(box_world,
                                                         any_indexer):
    """
    Approving frees the locks of the boxes and commits them after the
    appearances: the box of a removed appearance is deleted, the other
    keeps its values, and the cloned boxes can be reserved again.
    """
    issue = box_world['cover'].issue
    changeset = issue_changeset(issue, any_indexer)
    other_appearance = changeset.storycharacterrevisions.get(
        story_character=box_world['other_box'].story_character)
    other_appearance.deleted = True
    other_appearance.save()
    approver = User.objects.create_user('box_approver',
                                        password='box_approver')
    Indexer.objects.create(user=approver,
                           country=any_indexer.indexer.country)
    changeset.approver = approver
    changeset.state = states.REVIEWING
    changeset.save()

    changeset.approve(notes='')

    box = CoverCharacterBox.objects.get()
    assert box == box_world['box']
    assert box.top_left_y == 6500
    assert not box_locks(box).exists()
    assert set(changeset.covercharacterboxrevisions.values_list(
        'committed', 'deleted')) == {(True, False), (True, True)}
    assert issue_changeset(issue, any_indexer)\
        .covercharacterboxrevisions.get().previous_revision.changeset \
        == changeset


@pytest.mark.django_db
def test_points_of_changeset_with_only_box_changes(box_world):
    """
    A changeset changing only boxes is worth one point for the sequence,
    however many boxes changed, added or removed, as its characters are.
    """
    changeset, story_revision, _, revision = edited_box(box_world)
    changeset.calculate_imps()
    assert changeset.imps == 0

    revision.top_left_x = 1100
    revision.save()
    other_appearance = StoryCharacterRevision.clone(
        box_world['other_box'].story_character,
        changeset=changeset,
        story_revision=story_revision)
    removed = CoverCharacterBoxRevision.clone(
        box_world['other_box'],
        changeset=changeset,
        story_character_revision=other_appearance)
    removed.deleted = True
    removed.save()

    changeset.calculate_imps()
    assert changeset.imps == 1

    # Only the removed box left: still one point, so the change can be
    # submitted.
    revision.top_left_x = box_world['box'].top_left_x
    revision.save()
    changeset.calculate_imps()
    assert changeset.imps == 1

    # A removed box is no deletion of the whole change: the other changes
    # of the sequence count as well.
    imps = story_revision.calculate_imps()
    story_revision.title = 'Another title'
    story_revision.save()
    changeset.calculate_imps()
    assert changeset.imps > imps


@pytest.mark.django_db
def test_compare_changes_detects_box_change(box_world):
    """
    The comparison of the sequence notes a changed box and lists the
    boxes for the table; a box added and removed is left out.
    """
    changeset, story_revision, character_revision, revision = \
        edited_box(box_world)
    story_revision.compare_changes()
    assert story_revision.changed['cover_boxes'] is False
    assert [box_revision.id for box_revision
            in story_revision.cover_box_revisions] == [revision.id]

    move_box(revision)
    CoverCharacterBoxRevision.objects.create(
        changeset=changeset,
        story_character_revision=character_revision,
        cover=Cover.objects.create(issue=box_world['cover'].issue),
        deleted=True,
        **BOX_VALUES)
    story_revision.compare_changes()

    assert story_revision.changed['cover_boxes'] is True
    assert story_revision.is_changed is True
    box_revision, = story_revision.cover_box_revisions
    assert box_revision.id == revision.id
    assert box_revision.is_changed is True
    assert box_revision.changed['top_left_x'] is True
    assert box_revision.is_removed is False


@pytest.mark.django_db
def test_compare_changes_shows_box_going_with_appearance(box_world):
    """A box of a removed appearance is shown as removed."""
    _, story_revision, character_revision, revision = \
        edited_box(box_world)
    character_revision.deleted = True
    character_revision.save()

    story_revision.compare_changes()

    box_revision, = story_revision.cover_box_revisions
    assert box_revision.is_removed is True
    assert box_revision.is_changed is True
    assert story_revision.changed['cover_boxes'] is True


@pytest.mark.django_db
def test_compare_changes_shows_box_of_sequence_leaving_its_cover(box_world):
    """
    A cover sequence moved to a variant leaves the cover of the base issue:
    the approver sees that the box goes on approval.
    """
    _, story_revision, _, revision = edited_box(box_world)
    story_revision.issue = make_variant(story_revision.issue, 2)
    story_revision.save()

    story_revision.compare_changes()

    box_revision, = story_revision.cover_box_revisions
    assert box_revision.is_removed is True
    assert box_revision.is_changed is True
    assert story_revision.changed['cover_boxes'] is True


@pytest.mark.django_db
def test_compare_of_sequence_shows_box_table(box_world):
    """
    The comparison of the sequence shows the boxes with their cut-outs,
    the changed one highlighted.
    """
    changeset, story_revision, _, revision = edited_box(box_world)
    move_box(revision)
    request = RequestFactory().get('/')
    request.user = AnonymousUser()

    html = render_to_string('oi/bits/compare_story.html', {
        'story_revision': story_revision,
        'changeset': changeset,
        'states': states,
        'CTYPES': CTYPES,
        'user': request.user,
    }, request=request)

    assert 'Cut-out before' in html
    assert 'Cut-out after' in html
    assert 'comparison_highlight' in html
    # The cut-outs before and after the change, at the large size.
    assert html.count('aria-label="Alpha on the cover of %s"'
                      % box_world['cover'].issue.full_name()) == 2
    assert html.count('<svg class="max-w-full" width="200" ') == 2
    # The cover with the box numbered as in the table.
    assert html.count('with the marked characters"') == 1
    assert html.count('paint-order="stroke">1</text>') == 1


@pytest.mark.django_db
@pytest.mark.parametrize('change_type', sorted(CTYPES.items()))
def test_changesets_with_appearances_commit_their_boxes(
      change_type, any_indexer, any_added_issue):
    """
    Every kind of change holding revisions of appearances also commits
    their boxes, else a cloned box would stay locked for ever.  An issue
    being added holds no boxes: its sequences have no issue yet, and
    boxes can only be marked on the cover of an existing issue.
    """
    name, value = change_type
    changeset = Changeset.objects.create(
        state=states.OPEN, indexer=any_indexer, change_type=value)
    if name in ('issue_add', 'issue_bulk'):
        # The kind holding appearances: one variant added.
        IssueRevision.objects.create(
            changeset=changeset, series=any_added_issue.series, number='1v',
            variant_of=any_added_issue)

    # The unknown kind has no revisions.
    models = {queryset.model
              for queryset in changeset._revision_sets() or ()}

    if name in ('issue_add', 'issue_bulk'):
        assert StoryCharacterRevision in models
        assert CoverCharacterBoxRevision not in models
    elif StoryCharacterRevision in models:
        assert CoverCharacterBoxRevision in models


def issue_in_change(issue, changeset):
    """
    The revision of the issue in the change, cloned from its approved
    revision as reserving does, so that only what the change edits counts
    as edited.  An issue made by a test gets an approved revision first.
    """
    if not issue.revisions.filter(committed=True).exists():
        IssueRevision.objects.create(
            changeset=Changeset.objects.create(
                state=states.APPROVED, indexer=changeset.indexer,
                change_type=CTYPES['issue']),
            committed=True, issue=issue, series=issue.series,
            number=issue.number, variant_of=issue.variant_of,
            variant_name=issue.variant_name,
            variant_cover_status=issue.variant_cover_status)
    return IssueRevision.clone(issue, changeset)


def moving_change(box_world, any_indexer, change_type='two_issues'):
    """
    An open change of two issues, or adding a variant, holding the issue of
    the cover and its cover sequence, with the first box cloned; returns
    the change, the sequence and the box revision.
    """
    changeset = Changeset.objects.create(
        state=states.OPEN, indexer=any_indexer,
        change_type=CTYPES[change_type])
    issue_in_change(box_world['cover'].issue, changeset)
    story_revision = StoryRevision.clone(box_world['appearance'].story,
                                         changeset)
    revision = CoverCharacterBoxRevision.clone(
        box_world['box'], changeset=changeset,
        story_character_revision=StoryCharacterRevision.clone(
          box_world['appearance'], changeset=changeset,
          story_revision=story_revision))
    return changeset, story_revision, revision


def other_issue(changeset, issue, status=None):
    """
    The other issue of the change: a new issue of the series, or a variant
    of the issue with the variant cover status, and its revision.
    """
    other = Issue.objects.create(
        number='9', series=issue.series, sort_code=issue.sort_code + 50,
        variant_of=issue if status else None,
        variant_name='Variant' if status else '',
        variant_cover_status=status or 0)
    issue_in_change(other, changeset)
    return other


def preview_and_result(revision, approve):
    """
    Whether the comparison shows the box as removed, and whether the
    approval removes it, after approve has committed the covers, issues
    and sequences of the change as Changeset.approve does before boxes.
    """
    box_id = revision.cover_character_box_id
    revision.refresh_from_db()
    revision.compare_changes()
    preview = revision.is_removed
    approve()
    commit_again(revision)
    return preview, not CoverCharacterBox.objects.filter(id=box_id).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('target, removed', [
    ('other issue', True), ('variant 1', True), ('variant 2', False),
    ('variant 3', True)])
def test_cover_moved_in_the_change(box_world, any_indexer, target, removed):
    """
    A cover moved to the other issue of the change keeps its boxes only on
    a variant of their issue with only a scan difference.  The comparison
    shows what the approval does.
    """
    changeset, _, revision = moving_change(box_world, any_indexer)
    cover = box_world['cover']
    status = int(target[-1]) if target.startswith('variant') else None
    other = other_issue(changeset, cover.issue, status)
    CoverRevision.objects.create(changeset=changeset, cover=cover,
                                 issue=cover.issue)

    def approve():
        """The cover goes to the other issue."""
        cover.issue = other
        cover.save()

    assert preview_and_result(revision, approve) == (removed, removed)


@pytest.mark.django_db
@pytest.mark.parametrize('status, removed', [(2, False), (3, True)])
def test_variant_changed_in_the_change(box_world, any_indexer, status,
                                       removed):
    """
    A box on the cover of a scan variant goes when the change makes the
    variant one with other art, and the comparison says so.
    """
    issue = box_world['cover'].issue
    variant = Issue.objects.create(
        number='9', series=issue.series, sort_code=issue.sort_code + 50,
        variant_of=issue, variant_name='Variant', variant_cover_status=2)
    box = make_box(box_world['appearance'], Cover.objects.create(
        issue=variant), box_world['appearance'].revisions.get().changeset)
    changeset, _, _ = moving_change(box_world, any_indexer)
    variant_revision = issue_in_change(variant, changeset)
    variant_revision.variant_cover_status = status
    variant_revision.save()
    revision = CoverCharacterBoxRevision.clone(
        box, changeset=changeset,
        story_character_revision=changeset.storycharacterrevisions.get())

    def approve():
        """The variant gets its new status."""
        variant.variant_cover_status = status
        variant.save()

    assert preview_and_result(revision, approve) == (removed, removed)


@pytest.mark.django_db
@pytest.mark.parametrize('with_cover, issue_status', [
    (False, 3), (True, 3), (False, 2)])
def test_sequence_moved_to_a_variant_added_in_the_change(
      box_world, any_indexer, with_cover, issue_status):
    """
    A cover sequence moved to a variant added in the change leaves the
    cover of its issue, unless that cover moves with it.  The variant has
    no issue before approval, and the comparison says the same, also when
    the issue, not a variant, has the variant cover status of a scan
    variant, as imported data can.
    """
    cover = box_world['cover']
    issue = cover.issue
    issue.variant_cover_status = issue_status
    issue.save()
    changeset, story_revision, revision = moving_change(
        box_world, any_indexer, 'variant_add')
    added = IssueRevision.objects.create(
        changeset=changeset, series=issue.series, number=issue.number,
        variant_of=issue, variant_name='Added',
        variant_cover_status=2)
    story_revision.issue = None
    story_revision.save()
    if with_cover:
        CoverRevision.objects.create(changeset=changeset, cover=cover,
                                     issue=issue)

    def approve():
        """The variant is added, the sequence and the cover go to it."""
        variant = Issue.objects.create(
            number=issue.number, series=issue.series,
            sort_code=issue.sort_code + 60, variant_of=issue,
            variant_name='Added', variant_cover_status=2)
        added.issue = variant
        added.committed = True
        added.save()
        story = story_revision.story
        story.issue = variant
        story.save()
        story_revision.committed = True
        story_revision.save()
        if with_cover:
            cover.issue = variant
            cover.save()

    assert preview_and_result(revision, approve) == (not with_cover,
                                                     not with_cover)


@pytest.mark.django_db
def test_box_hidden_by_another_change_stays(box_world, any_indexer):
    """
    A cover moved away by another change hides its boxes; editing the
    issue later neither removes them nor counts them as changes, and they
    are shown again once the cover is back.
    """
    cover = box_world['cover']
    issue = cover.issue
    cover.issue = Issue.objects.create(
        number='99', series=issue.series, sort_code=issue.sort_code + 99)
    cover.save()
    changeset = issue_changeset(issue, any_indexer)
    story_revision = changeset.storyrevisions.get()
    story_revision.compare_changes()
    assert story_revision.changed['cover_boxes'] is False
    changeset.calculate_imps()
    assert changeset.imps == 0
    approver = User.objects.create_user('move_approver',
                                        password='move_approver')
    Indexer.objects.create(user=approver,
                           country=any_indexer.indexer.country)
    changeset.approver = approver
    changeset.state = states.REVIEWING
    changeset.save()

    changeset.approve(notes='')

    assert CoverCharacterBox.objects.count() == 2
    assert not box_locks(box_world['box'], box_world['other_box']).exists()
    assert not CoverCharacterBox.objects.filter(VALID_BOX_COVER).exists()
    cover.issue = issue
    cover.save()
    assert CoverCharacterBox.objects.filter(VALID_BOX_COVER).count() == 2


@pytest.mark.django_db
def test_box_drawn_on_a_cover_taken_away_before_approval(box_world,
                                                         any_indexer):
    """
    A box drawn in the change on the cover of a scan variant, which another
    change makes a variant with other art before the approval, would start
    hidden: it is not written and, as a box added and removed in the same
    change, it is left out of the comparison and counts no point.  Nothing
    in the change itself moves the sequence or the cover.
    """
    issue = box_world['cover'].issue
    variant = make_variant(issue, 2)
    changeset = issue_changeset(issue, any_indexer)
    revision = CoverCharacterBoxRevision.objects.create(
        changeset=changeset,
        story_character_revision=changeset.storycharacterrevisions.get(
          story_character=box_world['appearance']),
        cover=Cover.objects.create(issue=variant), **BOX_VALUES)
    variant.variant_cover_status = 3
    variant.save()

    revision.compare_changes()
    assert revision.is_removed is True
    story_revision = changeset.storyrevisions.get()
    story_revision.compare_changes()
    assert revision.id not in [box_revision.id for box_revision
                               in story_revision.cover_box_revisions]
    assert story_revision.changed['cover_boxes'] is False
    commit_again(revision)

    assert revision.cover_character_box is None
    assert not CoverCharacterBox.objects.filter(cover__issue=variant).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('change', ['variant added', 'other issue edited'])
def test_box_hidden_by_another_change_stays_in_a_change_of_two_issues(
      box_world, any_indexer, change):
    """
    A box hidden by another change, here on a scan variant made one with
    other art, stays as it is in a change adding a variant to its issue or
    changing the variant fields of another issue: only a change of the
    issue of its cover can take it off.  It counts as no change.
    """
    issue = box_world['cover'].issue
    variant = make_variant(issue, 2)
    box = make_box(box_world['appearance'],
                   Cover.objects.create(issue=variant),
                   box_world['appearance'].revisions.get().changeset)
    variant.variant_cover_status = 3
    variant.save()
    changeset, story_revision, _ = moving_change(
        box_world, any_indexer,
        'variant_add' if change == 'variant added' else 'two_issues')
    if change == 'variant added':
        IssueRevision.objects.create(
            changeset=changeset, series=issue.series, number=issue.number,
            variant_of=issue, variant_name='Added', variant_cover_status=2)
    else:
        other_revision = changeset.issuerevisions.get(
            issue=other_issue(changeset, issue, 2))
        other_revision.variant_cover_status = 3
        other_revision.save()
    revision = CoverCharacterBoxRevision.clone(
        box, changeset=changeset,
        story_character_revision=changeset.storycharacterrevisions.get())

    story_revision.compare_changes()
    assert story_revision.changed['cover_boxes'] is False
    assert preview_and_result(revision, lambda: None) == (False, False)


@pytest.mark.django_db
def test_box_on_deleted_cover_stays_when_its_sequence_moves(box_world,
                                                            any_indexer):
    """
    A deleted cover only hides its boxes, also when a change of two issues
    moves their sequence to the other issue: the box stays as it is, and
    the comparison does not show it as removed.
    """
    cover = box_world['cover']
    cover.deleted = True
    cover.save()
    changeset, story_revision, revision = moving_change(box_world,
                                                        any_indexer)
    other = other_issue(changeset, cover.issue)
    story_revision.issue = other
    story_revision.save()

    def approve():
        """The sequence goes to the other issue."""
        story = story_revision.story
        story.issue = other
        story.save()
        story_revision.committed = True
        story_revision.save()

    assert preview_and_result(revision, approve) == (False, False)


@pytest.mark.django_db
def test_history_shows_box_as_approved_after_later_cover_move(
      box_world, any_indexer, any_added_story_rev, any_added_story,
      any_language):
    """
    The comparison of an approved change shows its boxes as they were
    approved, a changed one and an added one, also after a later change
    moved the cover to another issue.
    """
    issue = box_world['cover'].issue
    beta = make_appearance(make_name('Beta', any_language),
                           any_added_story_rev, any_added_story)
    changeset = issue_changeset(issue, any_indexer)
    revision = changeset.covercharacterboxrevisions.get(
        cover_character_box=box_world['box'])
    move_box(revision)
    added = CoverCharacterBoxRevision.objects.create(
        changeset=changeset, cover=box_world['cover'],
        story_character_revision=changeset.storycharacterrevisions.get(
          story_character=beta), **BOX_VALUES)
    approver = User.objects.create_user('history_approver',
                                        password='history_approver')
    Indexer.objects.create(user=approver,
                           country=any_indexer.indexer.country)
    changeset.approver = approver
    changeset.state = states.REVIEWING
    changeset.save()
    changeset.approve(notes='')
    cover = box_world['cover']
    cover.issue = Issue.objects.create(
        number='99', series=issue.series, sort_code=issue.sort_code + 99)
    cover.save()

    story_revision = changeset.storyrevisions.get()
    story_revision.compare_changes()

    shown = {box_revision.id: box_revision
             for box_revision in story_revision.cover_box_revisions}
    for box_revision in (revision, added):
        assert shown[box_revision.id].is_removed is False
        assert shown[box_revision.id].is_changed is True


@pytest.mark.django_db
def test_compare_numbers_boxes_on_two_covers(box_world):
    """
    Boxes on the issue cover and on a scan variant are drawn on their own
    covers, numbered as in the table of the comparison.
    """
    changeset, story_revision, character_revision, revision = \
        edited_box(box_world)
    variant_cover = Cover.objects.create(
        issue=make_variant(box_world['cover'].issue, 2))
    CoverCharacterBoxRevision.objects.create(
        changeset=changeset, story_character_revision=character_revision,
        cover=variant_cover, **BOX_VALUES)
    move_box(revision)

    story_revision.compare_changes()
    tags = story_revision.cover_box_tags()

    assert [box.cover for box in story_revision.cover_box_revisions] == \
        [box_world['cover'], variant_cover]
    assert len(tags) == 2
    assert 'paint-order="stroke">1</text>' in tags[0]
    assert 'paint-order="stroke">2</text>' in tags[1]


def _compare_rows(story_revision, changeset):
    """
    The rows of the table of boxes in the comparison of the sequence, each
    as its class and the contents of its cells.
    """
    html = render_to_string('oi/bits/compare_story.html', {
        'story_revision': story_revision,
        'changeset': changeset,
        'states': states,
        'CTYPES': CTYPES,
        'user': AnonymousUser(),
    }, request=RequestFactory().get('/'))
    if 'Cut-out after' not in html:
        return None
    table = html.split('Cut-out after')[1]\
        .split('</table>')[0]
    rows = []
    for row in table.split('<tr')[1:]:
        row_class = ' '.join(row.split('class="')[1].split('"')[0].split())
        cells = [cell.split('</td>')[0].strip()
                 for cell in row.split('<td>')[1:]]
        rows.append((row_class, cells))
    return rows


@pytest.mark.django_db
def test_compare_table_shows_each_change(box_world, any_added_story_rev,
                                         any_added_story, any_language):
    """
    The table is left out without a changed box.  A removed box shows its
    cut-out before only, an added one after only, each in its colour.
    """
    changeset, story_revision, _, revision = edited_box(box_world)
    story_revision.compare_changes()
    assert _compare_rows(story_revision, changeset) is None

    revision.deleted = True
    revision.save()
    other = make_appearance(make_name('Beta', any_language),
                            any_added_story_rev, any_added_story)
    CoverCharacterBoxRevision.objects.create(
        changeset=changeset, cover=box_world['cover'],
        story_character_revision=StoryCharacterRevision.clone(
          other, changeset=changeset, story_revision=story_revision),
        **BOX_VALUES)
    story_revision.compare_changes()

    removed, added = _compare_rows(story_revision, changeset)
    # Only the box kept after the change is drawn on the cover.
    tag, = story_revision.cover_box_tags()
    assert 'paint-order="stroke">2</text>' in tag
    assert 'paint-order="stroke">1</text>' not in tag
    assert removed[0].endswith('deleted')
    assert '<svg' in removed[1][2] and removed[1][3] == ''
    assert added[0].endswith('added')
    assert added[1][2] == '' and '<svg' in added[1][3]


@pytest.mark.django_db
def test_reservation_reads_boxes_only_of_cover_sequences(box_world,
                                                         any_indexer):
    """
    Reserving an issue reads the boxes of the characters of its cover
    sequence only, not those of other sequences, which have none.
    """
    story = box_world['appearance'].story
    story.type = StoryType.objects.get(id=STORY_TYPES['comic story'])
    story.save()

    with CaptureQueriesContext(connection) as queries:
        changeset = issue_changeset(box_world['cover'].issue, any_indexer)

    assert not [query for query in queries.captured_queries
                if 'gcd_cover_character_box' in query['sql']]
    assert changeset.storycharacterrevisions.count() == 2
    assert not changeset.covercharacterboxrevisions.exists()


@pytest.mark.django_db
def test_change_lists_name_the_changed_boxes(box_world):
    """
    The list of changes of a sequence names the boxes when only they
    changed, as the queues and the history show it.
    """
    changeset, story_revision, _, revision = edited_box(box_world)
    IssueRevision.objects.create(changeset=changeset,
                                 issue=story_revision.issue,
                                 series=story_revision.issue.series)
    assert 'Characters marked on cover' not in changed_story_list(changeset)

    move_box(revision)

    assert 'Characters marked on cover' in changed_story_list(changeset)


@pytest.mark.django_db
def test_compare_flags_cut_outs_on_an_older_scan(box_world):
    """
    A cut-out drawn on a scan replaced since is drawn on the current scan,
    so the comparison says that it was drawn on an older scan.
    """
    cover = box_world['cover']
    cover.last_upload = timezone.now()
    cover.save()
    changeset, story_revision, _, revision = edited_box(box_world)
    move_box(revision)
    story_revision.compare_changes()

    row, = _compare_rows(story_revision, changeset)

    assert 'Drawn on an older scan' in row[1][2]
    assert 'Drawn on an older scan' in row[1][3]

    revision.scan_date = cover.last_upload
    revision.save()
    story_revision.compare_changes()
    row, = _compare_rows(story_revision, changeset)
    assert 'Drawn on an older scan' in row[1][2]
    assert 'Drawn on an older scan' not in row[1][3]


@pytest.mark.django_db
def test_compare_queries_do_not_grow_with_the_boxes(box_world):
    """
    The comparison reads the boxes with their covers and characters at
    once, not again for each box: boxes of the same appearance on more
    covers add no queries.
    """
    changeset, story_revision, character_revision, revision = \
        edited_box(box_world)
    move_box(revision)

    def queries():
        """The queries of the comparison of the sequence."""
        with CaptureQueriesContext(connection) as captured:
            story_revision.compare_changes()
            _compare_rows(story_revision, changeset)
        return len(captured.captured_queries)

    one = queries()
    issue = box_world['cover'].issue
    for number in (1, 2):
        variant = Issue.objects.create(
            number=issue.number, series=issue.series,
            sort_code=issue.sort_code + 10 + number, variant_of=issue,
            variant_name='Scan %d' % number, variant_cover_status=2)
        CoverCharacterBoxRevision.objects.create(
            changeset=changeset, story_character_revision=character_revision,
            cover=Cover.objects.create(issue=variant), **BOX_VALUES)
    three = queries()

    assert len(story_revision.cover_box_revisions) == 3
    assert three <= one


@pytest.mark.django_db
def test_returned_change_keeps_boxes_and_locks(box_world, any_indexer):
    """
    A change sent back to the indexer keeps its boxes and their locks.
    """
    boxes = (box_world['box'], box_world['other_box'])
    changeset = issue_changeset(box_world['cover'].issue, any_indexer)
    approver = User.objects.create_user('return_approver',
                                        password='return_approver')
    Indexer.objects.create(user=approver,
                           country=any_indexer.indexer.country)
    changeset.approver = approver
    changeset.state = states.REVIEWING
    changeset.save()

    changeset.disapprove(notes='')

    assert changeset.state == states.OPEN
    assert changeset.covercharacterboxrevisions.count() == 2
    assert box_locks(*boxes).filter(changeset=changeset).count() == 2
