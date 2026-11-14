import pytest

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.html import escape

from apps.gcd.models import Issue
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


BARCODE_WARNING = ('The new series does not show the <span class="comparison_'
                   'highlight">barcode</span> of this issue.')


def _moved_header(number, old_series, new_series):
    return ('Issue %s moved from <span class="comparison_highlight">%s</span>'
            ' to <span class="comparison_highlight">%s</span>'
            % (number, escape(old_series), escape(new_series)))


@pytest.fixture
def logged_in_indexer(client, any_indexer):
    # superuser passes the permission checks of the OI views and can approve
    # its own changes, enough reservations for the two issues
    any_indexer.is_superuser = True
    any_indexer.save()
    any_indexer.indexer.max_reservations = 10
    any_indexer.indexer.save()
    client.force_login(any_indexer)
    return any_indexer


def _add_issue(series, indexer, indicia_publisher, number):
    changeset = Changeset.objects.create(
      indexer=indexer, state=states.OPEN, change_type=CTYPES['issue_add'])
    revision = IssueRevision.objects.create(
      changeset=changeset, number=number, series=series,
      indicia_publisher=indicia_publisher, barcode='012345678905',
      no_title=True, no_volume=True, no_isbn=True, no_rating=True,
      no_brand=True, no_indicia_frequency=True,
      publication_date='February 1947', key_date='1947-02-00', page_count=32)
    revision.commit_to_display()
    changeset.state = states.APPROVED
    changeset.save()
    return Issue.objects.get(id=revision.issue.id)


def _move(client, revision, series):
    response = client.post(reverse('move_issue',
                                   kwargs={'issue_revision_id': revision.id,
                                           'series_id': series.id}))
    assert response.status_code == 302


def _approve(changeset, approver):
    changeset = Changeset.objects.get(id=changeset.id)
    changeset.submit(notes='')
    changeset = Changeset.objects.get(id=changeset.id)
    changeset.assign(approver=User.objects.get(id=approver.id), notes='')
    changeset = Changeset.objects.get(id=changeset.id)
    changeset.approve(notes='')


def _compare(client, changeset):
    response = client.get(reverse('compare', kwargs={'id': changeset.id}))
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
def test_compare_of_approved_move_still_warns(
        client, logged_in_indexer, any_added_issue, any_added_series):
    any_added_issue.barcode = '012345678905'
    any_added_issue.no_barcode = False
    any_added_issue.save()
    old_series = any_added_issue.series
    target = any_added_series
    target.has_barcode = False
    target.save()
    response = client.post(reverse(
      'reserve_revision', kwargs={'model_name': 'issue',
                                  'id': any_added_issue.id}))
    assert response.status_code == 302
    changeset = Changeset.objects.get(state=states.OPEN,
                                      change_type=CTYPES['issue'])
    _move(client, changeset.issuerevisions.get(), target)

    _approve(changeset, logged_in_indexer)
    assert Issue.objects.get(id=any_added_issue.id).series == target

    # the issue is now in the new series, the warning names the old one
    content = _compare(client, changeset)
    assert BARCODE_WARNING in content
    assert _moved_header('#42', old_series, target) in content


@pytest.mark.django_db
def test_compare_warns_about_second_issue_of_two_issues(
        client, logged_in_indexer, any_added_issue, any_added_series):
    second_issue = _add_issue(any_added_series, logged_in_indexer,
                              any_added_issue.indicia_publisher, '1')
    target = any_added_issue.series
    target.has_barcode = False
    target.save()
    response = client.post(reverse(
      'reserve_two_issues', kwargs={'issue_one_id': any_added_issue.id,
                                    'issue_two_id': second_issue.id}))
    assert response.status_code == 302
    changeset = Changeset.objects.get(state=states.OPEN,
                                      change_type=CTYPES['two_issues'])
    # the second issue revision shown on the compare page
    revision = changeset.issuerevisions.all()[1]
    assert revision.issue == second_issue
    _move(client, revision, target)

    content = _compare(client, changeset)
    assert BARCODE_WARNING in content
    assert _moved_header('#1', any_added_series, target) in content
