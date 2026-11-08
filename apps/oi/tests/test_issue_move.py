import pytest

from django.urls import reverse
from django.utils.html import escape

from apps.oi import states
from apps.oi.models import Changeset, CTYPES, IssueRevision


@pytest.mark.django_db
@pytest.mark.parametrize('field, value, flag, label', [
    ('barcode', '012345678905', 'has_barcode', 'barcode'),
    ('isbn', '9780306406157', 'has_isbn', 'ISBN'),
    ('rating', 'Teen Plus', 'has_rating', "publisher's age guidelines")])
def test_move_issue_warns_about_fields_the_new_series_hides(
        client, any_indexer, any_added_issue, any_added_series,
        field, value, flag, label):
    setattr(any_added_issue, field, value)
    setattr(any_added_issue, 'no_%s' % field, False)
    any_added_issue.save()
    target = any_added_series
    setattr(target, flag, False)
    target.save()
    changeset = Changeset.objects.create(
      indexer=any_indexer, state=states.OPEN, change_type=CTYPES['issue'])
    revision = IssueRevision.clone(data_object=any_added_issue,
                                   changeset=changeset)
    any_indexer.is_superuser = True
    any_indexer.save()
    client.force_login(any_indexer)
    url = reverse('move_issue', kwargs={'issue_revision_id': revision.id,
                                        'series_id': target.id})

    # The indexer is warned before confirming the move ...
    confirm = client.get(url)
    assert escape('The series %s does not show the %s of this issue.'
                  % (target, label)) in confirm.content.decode()

    # ... and the approver on the compare page.
    client.post(url)
    compare = client.get(reverse('compare', kwargs={'id': changeset.id}))
    assert ('The new series does not show the <span class="comparison_'
            'highlight">%s</span> of this issue.' % escape(label)) in (
      compare.content.decode())
