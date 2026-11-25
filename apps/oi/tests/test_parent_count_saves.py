"""
The count update of an approval writes only the count columns of a parent
and the time of the change.  The approval read the parent rows at its
start, so writing all of a row would put back the older values over what
another request committed in the meantime.
"""
from datetime import datetime, timezone
from unittest import mock

import pytest

from apps.gcd.models import Printer
from apps.oi.models import IssueRevision

OLD = datetime(2000, 1, 1, tzinfo=timezone.utc)
THEIRS = 'Their value'

PARENTS = [
    pytest.param(lambda revision: revision.series, 'binding', id='series'),
    pytest.param(lambda revision: revision.series.publisher, 'notes',
                 id='publisher'),
]


def _approve_meanwhile(revision, parent, column, owner=IssueRevision,
                       name='_adjust_stats'):
    """
    Commit revision as read again by the approval, while another request
    writes THEIRS to column of the row of parent just before each call of
    the method name of owner.  Return that row as stored at the end.
    """
    model = type(parent)
    method = getattr(owner, name)

    def another_request_first(instance, *args, **kwargs):
        model.objects.filter(id=parent.id).update(modified=OLD,
                                                  **{column: THEIRS})
        return method(instance, *args, **kwargs)

    with mock.patch.object(owner, name, autospec=True,
                           side_effect=another_request_first):
        IssueRevision.objects.get(id=revision.id).commit_to_display()
    return model.objects.get(id=parent.id)


@pytest.mark.django_db
@pytest.mark.parametrize('parent_of, column', PARENTS)
def test_added_issue_writes_only_the_count(any_added_issue_rev, parent_of,
                                           column):
    """An added issue moves the count of a parent and keeps its values."""
    parent = parent_of(any_added_issue_rev)
    count = type(parent).objects.get(id=parent.id).issue_count

    stored = _approve_meanwhile(any_added_issue_rev, parent, column)

    assert getattr(stored, column) == THEIRS
    assert stored.issue_count == count + 1
    assert stored.modified != OLD


@pytest.mark.django_db
@pytest.mark.parametrize('parent_of, column', PARENTS)
def test_added_variant_writes_only_the_time(any_added_variant_rev, parent_of,
                                            column):
    """
    A variant moves no count of these parents, so only the time of the
    change is written.
    """
    parent = parent_of(any_added_variant_rev)
    count = type(parent).objects.get(id=parent.id).issue_count

    stored = _approve_meanwhile(any_added_variant_rev, parent, column)

    assert getattr(stored, column) == THEIRS
    assert stored.issue_count == count
    assert stored.modified != OLD


@pytest.mark.django_db
def test_added_issue_writes_only_the_count_of_a_printer(any_added_issue_rev):
    """
    An added issue moves the count of the printer of its indicia printer
    and keeps its values.
    """
    printer = any_added_issue_rev.indicia_printer.get().parent
    count = Printer.objects.get(id=printer.id).issue_count

    stored = _approve_meanwhile(any_added_issue_rev, printer, 'notes',
                                owner=Printer, name='save')

    assert stored.notes == THEIRS
    assert stored.issue_count == count + 1
    assert stored.modified != OLD
