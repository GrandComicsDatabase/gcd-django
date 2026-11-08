"""
Reprint links of a sequence moved between the two issues of a two_issues
changeset (move_story_revision) in preview and compare, see #631.
"""

import re

import pytest

from django.contrib.auth.models import User
from django.urls import reverse

from apps.gcd.models import Issue, Reprint, Story, StoryType
from apps.oi import states
from apps.oi.models import (
    Changeset, IssueRevision, ReprintRevision, StoryRevision, CTYPES)


def _approved_change(indexer, revision_class, **values):
    changeset = Changeset(state=states.OPEN, indexer=indexer,
                          change_type=CTYPES['issue'])
    changeset.save()
    revision = revision_class(changeset=changeset, **values)
    revision.save()
    revision.commit_to_display()
    changeset.state = states.APPROVED
    changeset.save()
    return revision


def _add_issue(after, indexer, number):
    revision = _approved_change(
      indexer, IssueRevision, number=number, after=after, series=after.series,
      indicia_publisher=after.indicia_publisher,
      no_title=True, no_volume=True, no_isbn=True, no_barcode=True,
      no_rating=True, no_brand=True, no_indicia_frequency=True,
      publication_date='February 1947', key_date='1947-02-00', page_count=32)
    return Issue.objects.get(id=revision.issue.id)


def _add_story(issue, indexer, sequence_number, title):
    revision = _approved_change(
      indexer, StoryRevision, issue=issue, sequence_number=sequence_number,
      title=title, type=StoryType.objects.get(name='comic story'),
      feature='Test Feature', page_count=8, script='Writer',
      pencils='Penciller', inks='Inker', no_colors=True, letters='Letterer',
      no_editing=True)
    return Story.objects.get(id=revision.story.id)


def _add_reprint(indexer, origin, target):
    _approved_change(indexer, ReprintRevision,
                     origin=origin, origin_issue=origin.issue,
                     target=target, target_issue=target.issue)
    return Reprint.objects.get(origin=origin, target=target)


@pytest.fixture
def logged_in_indexer(client, any_indexer):
    # superuser passes the permission checks of the OI views, enough
    # reservations so that the open changesets of the fixtures don't count
    any_indexer.is_superuser = True
    any_indexer.save()
    any_indexer.indexer.max_reservations = 10
    any_indexer.indexer.save()
    client.force_login(any_indexer)
    return any_indexer


@pytest.fixture
def data(any_added_issue, any_indexer):
    """
    Issues A and B are changed together.  'Moved Story' of A reprints
    'Origin Story' of C and is reprinted in 'Target Story' of C.
    """
    issue_a = any_added_issue
    issue_b = _add_issue(issue_a, any_indexer, '43')
    issue_c = _add_issue(issue_b, any_indexer, '44')
    moved = _add_story(issue_a, any_indexer, 0, 'Moved Story')
    _add_story(issue_a, any_indexer, 1, 'Staying Story')
    _add_story(issue_b, any_indexer, 0, 'Story In B')
    origin = _add_story(issue_c, any_indexer, 0, 'Origin Story')
    target = _add_story(issue_c, any_indexer, 1, 'Target Story')
    from_reprint = _add_reprint(any_indexer, origin, moved)
    to_reprint = _add_reprint(any_indexer, moved, target)
    url = issue_c.get_absolute_url()
    return {
        'issue_a': issue_a, 'issue_b': issue_b, 'moved': moved,
        'from_reprint': from_reprint, 'to_reprint': to_reprint,
        # the links to the two reprints of 'Moved Story' as rendered in
        # the preview and in the compare
        'links': ['%s#%d' % (url, origin.id), '%s#%d' % (url, target.id)],
    }


def _reserve_two_issues(client, data):
    response = client.post(reverse(
      'reserve_two_issues',
      kwargs={'issue_one_id': data['issue_a'].id,
              'issue_two_id': data['issue_b'].id}))
    assert response.status_code == 302
    return Changeset.objects.get(state=states.OPEN,
                                 change_type=CTYPES['two_issues'])


def _move_story(client, changeset, story, to_issue):
    story_revision = changeset.storyrevisions.get(story=story)
    response = client.post(reverse('move_story_revision',
                                   kwargs={'id': story_revision.id}))
    assert response.status_code == 302
    assert StoryRevision.objects.get(id=story_revision.id).issue == to_issue


def _preview(client, changeset, issue):
    issue_revision = changeset.issuerevisions.get(issue=issue)
    response = client.get(reverse('preview_revision',
                                  kwargs={'model_name': 'issue',
                                          'id': issue_revision.id}))
    assert response.status_code == 200
    return response.content.decode()


def _current_reprint_cells(client, changeset):
    """
    The cells of the 'Reprint Links' rows of the compare view
    (oi/bits/compare.html) for the revisions in the changeset, without the
    cells of their previous revisions.
    """
    response = client.get(reverse('compare', kwargs={'id': changeset.id}))
    assert response.status_code == 200
    rows = re.findall(r'Reprint Links </td>(.*?)</tr>',
                      response.content.decode(), re.S)
    assert rows
    return [re.findall(r'<td>(.*?)</td>', row, re.S)[-1] for row in rows]


def _approve(changeset, approver):
    changeset = Changeset.objects.get(id=changeset.id)
    changeset.submit(notes='')
    changeset = Changeset.objects.get(id=changeset.id)
    changeset.assign(approver=User.objects.get(id=approver.id), notes='')
    changeset = Changeset.objects.get(id=changeset.id)
    changeset.approve(notes='')
    return changeset


@pytest.mark.django_db
def test_preview_shows_reprint_links_of_moved_sequence(
        client, logged_in_indexer, data):
    changeset = _reserve_two_issues(client, data)
    _move_story(client, changeset, data['moved'], data['issue_b'])

    content = _preview(client, changeset, data['issue_b'])

    assert 'Moved Story' in content
    for link in data['links']:
        assert content.count(link) == 1


@pytest.mark.django_db
def test_preview_of_other_issue_has_no_reprint_links_of_moved_sequence(
        client, logged_in_indexer, data):
    changeset = _reserve_two_issues(client, data)
    _move_story(client, changeset, data['moved'], data['issue_b'])

    content = _preview(client, changeset, data['issue_a'])

    assert 'Moved Story' not in content
    for link in data['links']:
        assert link not in content


@pytest.mark.django_db
def test_preview_shows_reprint_links_of_sequence_moved_back(
        client, logged_in_indexer, data):
    changeset = _reserve_two_issues(client, data)
    _move_story(client, changeset, data['moved'], data['issue_b'])
    _move_story(client, changeset, data['moved'], data['issue_a'])

    content = _preview(client, changeset, data['issue_a'])

    for link in data['links']:
        assert content.count(link) == 1


@pytest.mark.django_db
def test_compare_shows_reprint_links_of_moved_sequence(
        client, logged_in_indexer, data):
    changeset = _reserve_two_issues(client, data)
    _move_story(client, changeset, data['moved'], data['issue_b'])

    cells = _current_reprint_cells(client, changeset)

    # only the cell of the moved sequence has the links, each one once
    for link in data['links']:
        assert [cell.count(link) for cell in cells if link in cell] == [1]


@pytest.mark.django_db
def test_compare_of_approved_move_shows_reprint_links_once(
        client, logged_in_indexer, data):
    changeset = _reserve_two_issues(client, data)
    _move_story(client, changeset, data['moved'], data['issue_b'])
    changeset = _approve(changeset, logged_in_indexer)
    assert Story.objects.get(id=data['moved'].id).issue == data['issue_b']

    cells = _current_reprint_cells(client, changeset)

    for link in data['links']:
        assert [cell.count(link) for cell in cells if link in cell] == [1]
