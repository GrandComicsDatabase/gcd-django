"""
A save that exists to change one column must leave the others alone.  The
row was read earlier, so writing all of it would put back the older values
over what another request committed in the meantime.
"""
from datetime import datetime, timezone
from unittest import mock

import pytest

from apps.gcd.models import Issue, Series
from apps.mycomics.models import ReadingOrderItem
from apps.oi.models import IssueRevision, set_series_first_last
from apps.oi.views import _reorder_children

OLD = datetime(2000, 1, 1, tzinfo=timezone.utc)
THEIR_PRICE = '2.00 USD'


@pytest.fixture
def issues(any_added_series):
    """Three issues of a series, with room for their sort codes."""
    return [Issue.objects.create(series=any_added_series, number=str(code),
                                 sort_code=code, price='1.00 USD')
            for code in (10, 20, 30)]


def _read_early(issue):
    """
    Return issue as read before another request changed its price, and
    mark its row as not modified for a long time.
    """
    early = Issue.objects.get(id=issue.id)
    Issue.objects.filter(id=issue.id).update(price=THEIR_PRICE, modified=OLD)
    return early


def _assert_only_its_column(issue, name, value):
    """Check that issue has value in name and kept the other's price."""
    stored = Issue.objects.get(id=issue.id)
    assert getattr(stored, name) == value
    assert stored.price == THEIR_PRICE
    assert stored.modified != OLD


@pytest.mark.django_db
def test_sort_code_space_keeps_other_columns(issues, any_added_series):
    """Making room for new issues writes only the sort code of the later."""
    early = _read_early(issues[2])
    later = mock.MagicMock()
    later.exists.return_value = True
    later.last.return_value = early
    later.__iter__.return_value = iter([early])
    revision = IssueRevision(series=any_added_series)
    target = 'apps.oi.models.Issue.objects.filter'
    same = mock.Mock()
    same.count.return_value = 40
    with mock.patch(target) as issues_filter, \
         mock.patch.object(IssueRevision, '_same_series_open_with_after'
                           ) as open_with_after, \
         mock.patch.object(IssueRevision, '_same_series_revisions',
                           return_value=same):
        issues_filter.return_value.order_by.return_value = later
        open_with_after.return_value.first.return_value = None
        revision._ensure_sort_code_space()

    _assert_only_its_column(issues[2], 'sort_code', 70)


@pytest.mark.django_db
def test_reorder_keeps_other_columns(issues, any_added_series):
    """A reorder writes only the sort code of the children and the extras."""
    early, extra = _read_early(issues[0]), _read_early(issues[1])
    child_set = Issue.objects.filter(series=any_added_series)

    _reorder_children(None, any_added_series, [early], 'sort_code', child_set,
                      True, extras=[extra])

    _assert_only_its_column(issues[0], 'sort_code', 1)
    _assert_only_its_column(issues[1], 'sort_code', 2)


def test_reorder_of_a_child_without_a_modified_column():
    """A reading order item keeps no time of change, and still saves."""
    item = ReadingOrderItem(sequence_number=5)

    with mock.patch.object(ReadingOrderItem, 'save') as save:
        _reorder_children(None, None, [item], 'sequence_number', None,
                          commit=True, unique=False)

    assert item.sequence_number == 0
    save.assert_called_once_with(update_fields=['sequence_number'])


def test_reorder_by_a_name_that_is_no_column_is_an_error():
    """
    A sort field that is no column is an error, not a save that is
    skipped.
    """
    item = ReadingOrderItem(sequence_number=5)

    with pytest.raises(ValueError):
        _reorder_children(None, None, [item], 'no_such_column', None,
                          commit=True, unique=False)


@pytest.mark.django_db
def test_indexed_status_keeps_other_columns(issues):
    """The indexed status writes only that column, of a variant too."""
    issues[0].is_indexed = 1
    issues[0].save()
    variant = issues[2]
    variant.variant_of = issues[0]
    variant.is_indexed = 1
    variant.save()
    early, early_variant = _read_early(issues[0]), _read_early(variant)

    with mock.patch.object(Issue, 'active_variants',
                           return_value=[early_variant]), \
         mock.patch.object(Issue, 'active_stories') as stories, \
         mock.patch.object(Issue, 'has_reprints', return_value=False):
        stories.return_value.exclude.return_value.count.return_value = 0
        stories.return_value.filter.return_value.exists.return_value = False
        stories.return_value.exists.return_value = False
        early.set_indexed_status()

    _assert_only_its_column(issues[0], 'is_indexed', 0)
    _assert_only_its_column(variant, 'is_indexed', 0)


@pytest.mark.django_db
@pytest.mark.parametrize('set_first_last', [Series.set_first_last_issues,
                                            set_series_first_last],
                         ids=['method', 'function'])
def test_first_last_issues_keeps_other_columns(issues, any_added_series,
                                               set_first_last):
    """Setting the first and last issue writes only those columns."""
    early = Series.objects.get(id=any_added_series.id)
    Series.objects.filter(id=early.id).update(notes='Their note',
                                              modified=OLD)

    set_first_last(early)

    stored = Series.objects.get(id=early.id)
    assert stored.first_issue_id == issues[0].id
    assert stored.last_issue_id == issues[2].id
    assert stored.notes == 'Their note'
    assert stored.modified != OLD
