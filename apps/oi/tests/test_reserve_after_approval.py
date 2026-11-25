"""
Reserving an object right after a change to it was approved.

The view reads the object before it takes the object's lock, and an
approval frees that lock before it writes the object.  These tests run
the competing write exactly between the read and the lock.
"""
from urllib.parse import urlencode

import pytest

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse

from apps.gcd.models import Cover, CreditType, Issue, Reprint, SeriesBond, \
                            StoryType, CREDIT_TYPES, STORY_TYPES
from apps.indexer.models import Indexer
from apps.mycomics.models import Collector, ConditionGradeScale
from apps.oi import states
from apps.oi import views
from apps.oi.models import Changeset, CoverRevision, CTYPES, IssueRevision, \
                           ReprintRevision, RevisionLock


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


def _user(name, country, permission=None):
    """Return a new user with an indexer and, if given, a permission."""
    user = User.objects.create_user(name, password=name)
    Indexer.objects.create(user=user, country=country)
    if permission:
        user.user_permissions.add(Permission.objects.get(
          codename=permission, content_type__app_label='indexer'))
    return user


def _change_in_review(issue, country):
    """
    Return the revision of a change of the issue's price, in review.

    The change belongs to a second indexer and holds the issue's lock,
    as an edit does until its approval.
    """
    changeset = Changeset.objects.create(
      change_type=CTYPES['issue'], state=states.OPEN,
      indexer=_user('other', country))
    revision = IssueRevision.clone(issue, changeset=changeset)
    revision.price = '2.61 USD'
    revision.save()
    RevisionLock.objects.create(locked_object=issue, changeset=changeset)
    changeset.approver = _user('editor', country, 'can_approve')
    changeset.state = states.REVIEWING
    changeset.save()
    return revision


def _write_before_lock(monkeypatch, write):
    """Run write once, right before the view takes the object's lock."""
    real_get_revision_lock = views._get_revision_lock
    pending = [write]

    def get_revision_lock(*args, **kwargs):
        """Take the lock after the competing write."""
        while pending:
            pending.pop()()
        return real_get_revision_lock(*args, **kwargs)

    monkeypatch.setattr('apps.oi.views._get_revision_lock',
                        get_revision_lock)


def _reserve(user, display_obj, model_name='issue'):
    """Call the reserve view for the object as the user."""
    request = RequestFactory().post('/reserve/')
    request.user = user
    return views.reserve.__wrapped__(request, display_obj.id, model_name)


def _show_errors(monkeypatch):
    """Make the error page show only its message."""
    monkeypatch.setattr(
      'apps.oi.views.render_error',
      lambda request, message: HttpResponse(message))


def _open_revisions(issue):
    """Return the revisions of the issue in an open change."""
    return IssueRevision.objects.filter(issue=issue,
                                        changeset__state=states.OPEN)


def _lock_rows(display_obj):
    """Return the lock rows of the object."""
    return RevisionLock.objects.filter(
      object_id=display_obj.id,
      content_type=ContentType.objects.get_for_model(display_obj))


def _bulk_edit(client, user, language, issue):
    """Post the legacy bulk edit of the issue's series with its values."""
    Collector.objects.create_collector(
      user, grade_system=ConditionGradeScale.objects.create(name='Scale'),
      default_language=language)
    user.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(user)
    url = '%s?%s' % (reverse('edit_issues_in_bulk'), urlencode({
      'target': 'issue', 'method': 'icontains', 'logic': 'False',
      'series': issue.series.name}))
    page = client.get(url)
    data = {'comments': 'Same values.'}
    for field in page.context['form']:
        value = field.value()
        if value is True:
            data[field.html_name] = 'on'
        elif value is not None and value is not False:
            data[field.html_name] = value
    credits = page.context['credits_formset']
    if credits:
        # No editing credits are added.
        for name in ('TOTAL_FORMS', 'INITIAL_FORMS'):
            data[credits.management_form[name].html_name] = 0
    return client.post(url, data)


def _approved_cover(issue, indexer):
    """Return a cover of the issue with its approved upload."""
    cover = Cover.objects.create(issue=issue)
    upload = Changeset.objects.create(
      indexer=indexer, state=states.APPROVED, change_type=CTYPES['cover'])
    CoverRevision.objects.create(changeset=upload, cover=cover, issue=issue,
                                 committed=True)
    return cover


def test_reserve_after_an_approval_starts_from_the_approved_values(
        any_added_issue, any_indexer, any_country, monkeypatch):
    """A reserve clones the issue as the approval just left it."""
    approved = _change_in_review(any_added_issue, any_country)
    _write_before_lock(
      monkeypatch, lambda: approved.changeset.approve(notes=''))

    response = _reserve(any_indexer, any_added_issue)

    assert response.status_code == 302
    revision = _open_revisions(any_added_issue).get(
      changeset__indexer=any_indexer)
    assert revision.price == '2.61 USD'
    assert revision.previous_revision == approved
    revision.compare_changes()
    assert revision.is_changed is False
    assert _lock_rows(any_added_issue).get().changeset == \
        revision.changeset


def test_reserve_after_a_deletion_creates_no_change(
        any_added_issue, any_indexer, monkeypatch):
    """A reserve of an issue deleted meanwhile keeps no change or lock."""
    changesets = any_indexer.changesets.count()
    issue_row = Issue.objects.filter(id=any_added_issue.id)
    _write_before_lock(monkeypatch, lambda: issue_row.update(deleted=True))
    _show_errors(monkeypatch)

    response = _reserve(any_indexer, any_added_issue)

    assert response.status_code == 200
    assert b'Cannot edit' in response.content
    assert not _lock_rows(any_added_issue).exists()
    assert not _open_revisions(any_added_issue).exists()
    assert any_indexer.changesets.count() == changesets


def test_reserve_of_an_object_removed_meanwhile_creates_no_change(
        any_added_series_bond, any_indexer, monkeypatch):
    """A reserve of a series bond removed meanwhile keeps no lock."""
    bond_row = SeriesBond.objects.filter(id=any_added_series_bond.id)
    _write_before_lock(monkeypatch, lambda: bond_row.delete())
    _show_errors(monkeypatch)

    response = _reserve(any_indexer, any_added_series_bond, 'series_bond')

    assert response.status_code == 200
    assert b'Cannot edit' in response.content
    assert not _lock_rows(any_added_series_bond).exists()


def test_bulk_edit_after_an_approval_starts_from_the_approved_values(
        client, any_added_issue, any_indexer, any_language, monkeypatch):
    """A legacy bulk edit clones the issue as the approval just left it."""
    issue_row = Issue.objects.filter(id=any_added_issue.id)
    _write_before_lock(
      monkeypatch, lambda: issue_row.update(notes='Approved notes'))

    _bulk_edit(client, any_indexer, any_language, any_added_issue)

    revision = IssueRevision.objects.get(
      issue=any_added_issue, changeset__change_type=CTYPES['issue_bulk'])
    assert revision.notes == 'Approved notes'


def test_reprint_reserve_after_an_approval_starts_from_the_approved_values(
        any_added_story, any_added_variant, any_indexer, monkeypatch):
    """A reprint edit clones the link as the approval just left it."""
    values = dict(origin=any_added_story, origin_issue=any_added_story.issue,
                  target_issue=any_added_variant, notes='Old notes')
    reprint = Reprint.objects.create(**values)
    ReprintRevision.objects.create(
      changeset=Changeset.objects.create(
        indexer=any_indexer, state=states.APPROVED,
        change_type=CTYPES['reprint']),
      reprint=reprint, **values)
    changeset = Changeset.objects.create(
      indexer=any_indexer, state=states.OPEN, change_type=CTYPES['issue'])
    reprint_row = Reprint.objects.filter(id=reprint.id)
    _write_before_lock(
      monkeypatch, lambda: reprint_row.update(notes='Approved notes'))
    request = RequestFactory().post('/', {'edit_origin': ''})
    request.user = any_indexer

    views.reserve_reprint.__wrapped__(request, changeset.id, reprint.id)

    revision = ReprintRevision.objects.get(changeset=changeset)
    assert revision.notes == 'Approved notes'


def test_cover_move_after_an_approval_starts_from_the_approved_values(
        any_added_issue, any_added_variant, any_indexer, monkeypatch):
    """A cover move clones the cover as the approval just left it."""
    cover = _approved_cover(any_added_issue, any_indexer)
    changeset = Changeset.objects.create(
      indexer=any_indexer, state=states.OPEN,
      change_type=CTYPES['two_issues'])
    IssueRevision.clone(any_added_variant, changeset=changeset)
    IssueRevision.clone(any_added_issue, changeset=changeset)
    cover_row = Cover.objects.filter(id=cover.id)
    _write_before_lock(
      monkeypatch, lambda: cover_row.update(issue=any_added_variant))
    request = RequestFactory().post('/')
    request.user = any_indexer

    views.move_cover.__wrapped__(request, changeset.id, cover.id)

    revision = CoverRevision.objects.get(changeset=changeset)
    assert revision.issue == any_added_variant
