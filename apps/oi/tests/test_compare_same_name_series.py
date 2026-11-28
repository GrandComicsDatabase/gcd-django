"""The series with the same name on the compare page of a new series."""
import pytest

from django.urls import reverse

from apps.gcd.models import Series
from apps.oi import states
from apps.oi.models import Changeset, CTYPES, SeriesRevision

BOX = 'Series with the same name at this publisher'


def _changeset(indexer, state=states.PENDING):
    """A series changeset of the indexer in the given state."""
    return Changeset.objects.create(indexer=indexer, state=state,
                                    change_type=CTYPES['series'])


def _add_series(indexer, values, state=states.PENDING, **fields):
    """A new series in a changeset of its own."""
    return SeriesRevision.objects.create(changeset=_changeset(indexer, state),
                                         **dict(values, **fields))


def _compare(client, changeset):
    """The compare page of the changeset, as its indexer sees it."""
    client.force_login(changeset.indexer)
    response = client.get(reverse('compare', kwargs={'id': changeset.id}))
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
def test_lists_series_and_queued_series_with_the_same_name(
        client, any_indexer, any_added_series, series_add_values):
    # 'The Test Series' has a leading article: it sorts as 'Test Series'
    queued = _add_series(any_indexer, series_add_values, year_began=1995,
                         name='The test series', leading_article=True)
    edit = _changeset(any_indexer)
    SeriesRevision.clone(data_object=any_added_series, changeset=edit)
    revision = _add_series(any_indexer, series_add_values,
                           name='Test Series')

    content = _compare(client, revision.changeset)

    assert BOX in content
    assert '<a href="%s">The Test Series (1990 series)</a>' % (
      any_added_series.get_absolute_url()) in content
    assert '<a href="%s">The test series (1995 series), Pending Review</a>' % (
      reverse('compare', kwargs={'id': queued.changeset_id})) in content
    # an edit is not a new series: not listed, and no list on its page
    assert '(1990 series), Pending Review' not in content
    assert BOX not in _compare(client, edit)
    # once approved, the list is gone
    Changeset.objects.filter(id=revision.changeset_id).update(
      state=states.APPROVED)
    assert BOX not in _compare(client, revision.changeset)


@pytest.mark.django_db
def test_leaves_out_deleted_discarded_other_names_and_itself(
        client, any_indexer, any_added_series, series_add_values):
    Series.objects.filter(id=any_added_series.id).update(deleted=True)
    _add_series(any_indexer, series_add_values, state=states.DISCARDED,
                leading_article=True)
    _add_series(any_indexer, series_add_values, name='Other Series')
    revision = _add_series(any_indexer, series_add_values,
                           name='Test Series')

    assert BOX not in _compare(client, revision.changeset)
