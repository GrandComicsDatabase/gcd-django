"""The issues with the same number on the compare page of new issues."""
import pytest

from django.urls import reverse

from apps.gcd.models import Issue
from apps.oi import states
from apps.oi.models import Changeset, CTYPES, IssueRevision

BOX = 'Issues of this series with the same number'


def _add_issues(indexer, series, numbers, state=states.PENDING, **fields):
    """New issues of the series in a changeset of their own."""
    changeset = Changeset.objects.create(indexer=indexer, state=state,
                                         change_type=CTYPES['issue_add'])
    for number in numbers:
        IssueRevision.objects.create(changeset=changeset, series=series,
                                     number=number, **fields)
    return changeset


def _compare(client, changeset):
    """The compare page of the changeset, as its indexer sees it."""
    client.force_login(changeset.indexer)
    response = client.get(reverse('compare', kwargs={'id': changeset.id}))
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
def test_lists_issues_and_queued_issues_with_the_same_number(
        client, any_indexer, any_added_issue):
    series = any_added_issue.series
    queued = _add_issues(any_indexer, series, ['43'])
    IssueRevision.clone(data_object=any_added_issue,
                        changeset=_add_issues(any_indexer, series, []))
    changeset = _add_issues(any_indexer, series, ['42', '43', '44'])

    content = _compare(client, changeset)

    assert BOX in content
    assert '<a href="%s">%s #42</a>' % (
      any_added_issue.get_absolute_url(), series) in content
    assert '<a href="%s">%s #43, Pending Review</a>' % (
      reverse('compare', kwargs={'id': queued.id}), series) in content
    # an edit in the queue is not a new issue
    assert '#42, Pending Review' not in content
    # once approved, the list is gone
    Changeset.objects.filter(id=changeset.id).update(state=states.APPROVED)
    assert BOX not in _compare(client, changeset)


@pytest.mark.django_db
def test_leaves_out_deleted_variants_nn_discarded_and_itself(
        client, any_indexer, any_added_issue, any_added_variant):
    series = any_added_issue.series
    Issue.objects.filter(id=any_added_issue.id).update(number='43',
                                                       deleted=True)
    Issue.objects.filter(id=any_added_variant.id).update(number='43')
    _add_issues(any_indexer, series, ['43'], variant_of=any_added_issue)
    _add_issues(any_indexer, series, ['43'], state=states.DISCARDED)
    _add_issues(any_indexer, series, ['[nn]'])
    changeset = _add_issues(any_indexer, series, ['[nn]', '43'])

    assert BOX not in _compare(client, changeset)
