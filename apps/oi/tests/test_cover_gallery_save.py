"""
The approval of a cover writes only the gallery flag of a series and the
time of the change.  The approval read the series row before it saved it,
so writing all of the row would put back the older values over what
another request committed in the meantime.
"""
from datetime import datetime, timezone
from unittest import mock

import pytest

from apps.gcd.models import Cover, Issue, Series
from apps.oi import states
from apps.oi.models import Changeset, CoverRevision, CTYPES, IssueRevision

OLD = datetime(2000, 1, 1, tzinfo=timezone.utc)
THEIRS = 'Their value'


def _changeset(indexer, change_type):
    """An open changeset with the comment that an approval reads."""
    changeset = Changeset.objects.create(indexer=indexer, state=states.OPEN,
                                         change_type=CTYPES[change_type])
    changeset.comments.create(commenter=indexer, text='',
                              old_state=states.OPEN, new_state=states.OPEN)
    return changeset


def _approve_meanwhile(revision, *series):
    """
    Commit revision as read again by the approval, while another request
    writes THEIRS to the notes of a series just before each save of its
    row.  Return the rows of series as stored at the end.
    """
    save = Series.save

    def another_request_first(instance, *args, **kwargs):
        Series.objects.filter(id=instance.id).update(modified=OLD,
                                                     notes=THEIRS)
        return save(instance, *args, **kwargs)

    with mock.patch.object(Series, 'save', autospec=True,
                           side_effect=another_request_first), \
            mock.patch('apps.oi.covers.copy_approved_cover'):
        CoverRevision.objects.get(id=revision.id).commit_to_display()
    return [Series.objects.get(id=one.id) for one in series]


@pytest.mark.django_db
def test_first_cover_writes_only_the_gallery_flag(any_added_issue,
                                                  any_indexer):
    """The first cover of a series sets its flag and keeps its values."""
    series = any_added_issue.series
    revision = CoverRevision.objects.create(
      changeset=_changeset(any_indexer, 'cover'), issue=any_added_issue)

    stored, = _approve_meanwhile(revision, series)

    assert stored.notes == THEIRS
    assert stored.has_gallery is True
    assert stored.modified != OLD


@pytest.mark.django_db
def test_deleted_only_cover_writes_only_the_gallery_flag(any_added_issue,
                                                         any_indexer):
    """The only cover of a series deleted clears its flag, keeps its values."""
    series = any_added_issue.series
    Series.objects.filter(id=series.id).update(has_gallery=True)
    cover = Cover.objects.create(issue=any_added_issue)
    revision = CoverRevision.objects.create(
      changeset=_changeset(any_indexer, 'cover'), issue=any_added_issue,
      cover=cover, deleted=True)

    stored, = _approve_meanwhile(revision, series)

    assert stored.notes == THEIRS
    assert stored.has_gallery is False
    assert stored.modified != OLD


@pytest.mark.django_db
def test_moved_only_cover_writes_only_the_gallery_flags(any_added_issue,
                                                        any_added_series,
                                                        any_indexer):
    """
    The only cover of a series moved, in a change of two issues, to an issue
    of a series without covers sets the flag of the one, clears the flag of
    the other, and keeps the values of both.
    """
    old_series = any_added_issue.series
    Series.objects.filter(id=old_series.id).update(has_gallery=True)
    cover = Cover.objects.create(issue=any_added_issue)
    target = Issue.objects.create(series=any_added_series, number='1',
                                  sort_code=0)
    changeset = _changeset(any_indexer, 'two_issues')
    for issue in (any_added_issue, target):
        IssueRevision.objects.create(changeset=changeset, issue=issue,
                                     series=issue.series, number=issue.number)
    revision = CoverRevision.objects.create(
      changeset=changeset, issue=any_added_issue, cover=cover)

    new, old = _approve_meanwhile(revision, any_added_series, old_series)

    assert new.notes == THEIRS
    assert new.has_gallery is True
    assert new.modified != OLD
    assert old.notes == THEIRS
    assert old.has_gallery is False
    assert old.modified != OLD
