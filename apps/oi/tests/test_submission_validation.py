import pytest

from django.contrib.auth.models import Permission, User
from django.http import HttpResponse
from django.test import RequestFactory

from apps.gcd.models import CreditType, Feature, FeatureType, StoryType, \
                            CREDIT_TYPES, STORY_TYPES
from apps.indexer.models import Indexer
from apps.oi import states
from apps.oi.models import Changeset, CTYPES, IssueRevision, RevisionLock
from apps.oi.views import (APPROVE, SEND_BACK_TO_INDEXER, approve, disapprove,
                           submit, validate_changeset_revisions)


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def required_story_type():
    """Supply reference data when this module runs with --no-migrations."""
    StoryType.objects.get_or_create(
      id=STORY_TYPES['comic story'],
      defaults={'name': 'comic story', 'sort_code': 19})
    CreditType.objects.get_or_create(
      id=CREDIT_TYPES['editing'],
      defaults={'name': 'editing', 'sort_code': CREDIT_TYPES['editing']})


@pytest.fixture
def any_editor(any_country):
    user = User.objects.create_user('editor', password='editor')
    Indexer.objects.create(user=user, country=any_country)
    user.user_permissions.add(Permission.objects.get(
      codename='can_approve', content_type__app_label='indexer'))
    return user


def _request_for(user):
    request = RequestFactory().post('/submit/', {'comments': ''})
    request.user = user
    return request


def _add_feature_object(story_revision, language):
    feature_type, _ = FeatureType.objects.get_or_create(
      id=1, defaults={'name': 'feature'})
    feature = Feature.objects.create(
      name='Migrated Feature',
      sort_name='Migrated Feature',
      genre='',
      language=language,
      feature_type=feature_type,
      notes='')
    story_revision.feature_object.add(feature)


def _put_in_review(changeset, editor, *locked_objects):
    # Active edit revisions hold this lock until approval commits them.
    for locked_object in locked_objects:
        RevisionLock.objects.create(
          locked_object=locked_object, changeset=changeset)
    changeset.approver = editor
    changeset.state = states.REVIEWING
    changeset.save()


def test_submission_validation_finds_mixed_feature_data(
        any_edit_story_rev, any_indexer):
    changeset = any_edit_story_rev.changeset
    changeset.change_type = CTYPES['issue']
    changeset.save()
    _add_feature_object(any_edit_story_rev,
                        any_edit_story_rev.issue.series.language)

    invalid = validate_changeset_revisions(
      changeset, _request_for(any_indexer))

    assert len(invalid) == 1
    assert invalid[0][0] == any_edit_story_rev
    assert 'Either use the text feature field or the database objects.' \
           in invalid[0][1]


def test_submission_validation_finds_invalid_issue(any_added_issue,
                                                   any_indexer):
    changeset = Changeset.objects.create(
      change_type=CTYPES['issue'], indexer=any_indexer, state=states.OPEN)
    revision = IssueRevision.clone(any_added_issue, changeset=changeset)
    revision.no_editing = True
    revision.save()

    invalid = validate_changeset_revisions(
      changeset, _request_for(any_indexer))

    assert len(invalid) == 1
    assert invalid[0][0] == revision
    assert 'Editing field and No Editing checkbox cannot both be filled in.' \
           in invalid[0][1]


def test_submission_validation_accepts_empty_multiple_choice(
        any_edit_story_rev, any_indexer):
    any_edit_story_rev.genre = ''
    any_edit_story_rev.save()

    invalid = validate_changeset_revisions(
      any_edit_story_rev.changeset, _request_for(any_indexer))

    assert invalid == []


def test_submit_keeps_invalid_changeset_open(any_edit_story_rev,
                                             any_indexer):
    changeset = any_edit_story_rev.changeset
    changeset.change_type = CTYPES['issue']
    changeset.save()
    _add_feature_object(any_edit_story_rev,
                        any_edit_story_rev.issue.series.language)

    response = submit.__wrapped__(_request_for(any_indexer), changeset.id)

    changeset.refresh_from_db()
    assert response.status_code == 200
    assert changeset.state == states.OPEN
    assert b'invalid issue or sequence data' in response.content


def test_submit_allows_corrected_changeset(any_edit_story_rev,
                                           any_indexer):
    changeset = any_edit_story_rev.changeset
    changeset.change_type = CTYPES['issue']
    changeset.save()

    response = submit.__wrapped__(_request_for(any_indexer), changeset.id)

    changeset.refresh_from_db()
    assert response.status_code == 302
    assert changeset.state == states.PENDING


def test_approve_keeps_invalid_changeset_in_review(any_edit_story_rev,
                                                   any_editor):
    changeset = any_edit_story_rev.changeset
    changeset.change_type = CTYPES['issue']
    issue_revision = IssueRevision.clone(
      any_edit_story_rev.issue, changeset=changeset)
    _put_in_review(changeset, any_editor, any_edit_story_rev.issue,
                   any_edit_story_rev.story)
    _add_feature_object(any_edit_story_rev,
                        any_edit_story_rev.issue.series.language)

    response = approve.__wrapped__(_request_for(any_editor), changeset.id)

    changeset.refresh_from_db()
    issue_revision.refresh_from_db()
    any_edit_story_rev.refresh_from_db()
    assert response.status_code == 200
    assert changeset.state == states.REVIEWING
    assert issue_revision.committed is not True
    assert any_edit_story_rev.committed is not True
    assert b'invalid issue or sequence data' in response.content
    assert str(APPROVE).encode() in response.content
    assert str(SEND_BACK_TO_INDEXER).encode() in response.content


def test_approve_allows_corrected_changeset(any_edit_story_rev, any_editor):
    changeset = any_edit_story_rev.changeset
    changeset.change_type = CTYPES['issue']
    issue_revision = IssueRevision.clone(
      any_edit_story_rev.issue, changeset=changeset)
    _put_in_review(changeset, any_editor, any_edit_story_rev.issue,
                   any_edit_story_rev.story)

    response = approve.__wrapped__(_request_for(any_editor), changeset.id)

    changeset.refresh_from_db()
    issue_revision.refresh_from_db()
    any_edit_story_rev.refresh_from_db()
    assert response.status_code == 302
    assert changeset.state == states.APPROVED
    assert issue_revision.committed is True
    assert any_edit_story_rev.committed is True


def test_send_back_requires_comment_using_button_label(any_edit_story_rev,
                                                       any_editor,
                                                       monkeypatch):
    changeset = any_edit_story_rev.changeset
    _put_in_review(changeset, any_editor, any_edit_story_rev.story)
    monkeypatch.setattr(
      'apps.oi.views.render_error',
      lambda request, message: HttpResponse(message))

    response = disapprove.__wrapped__(
      _request_for(any_editor), changeset.id)

    changeset.refresh_from_db()
    assert response.status_code == 200
    assert changeset.state == states.REVIEWING
    assert str(SEND_BACK_TO_INDEXER).encode() in response.content
