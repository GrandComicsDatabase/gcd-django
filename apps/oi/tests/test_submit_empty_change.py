import pytest
from django.urls import reverse

from apps.gcd.models import StoryType
from apps.oi import states
from apps.oi.models import Changeset, StoryRevision, CTYPES

EMPTY_CHANGE_ERROR = ('A submission needs to consists of at least one '
                      'change to the data or have a comment.')


def _add_story(issue, indexer, sequence_number):
    changeset = Changeset.objects.create(state=states.OPEN, indexer=indexer,
                                         change_type=CTYPES['issue'])
    revision = StoryRevision.objects.create(
      changeset=changeset, issue=issue, sequence_number=sequence_number,
      type=StoryType.objects.get(name='comic story'), title='Story',
      page_count=8, script='Writer', pencils='Penciller', inks='Inker',
      no_colors=True, letters='Letterer', no_editing=True)
    revision.commit_to_display()
    changeset.state = states.APPROVED
    changeset.save()
    return revision.story


@pytest.mark.django_db
@pytest.mark.parametrize('swap', [True, False])
def test_submit_without_comment_needs_a_change(client, any_indexer,
                                               any_added_issue, swap):
    first = _add_story(any_added_issue, any_indexer, 0)
    second = _add_story(any_added_issue, any_indexer, 1)
    any_indexer.is_superuser = True
    any_indexer.save()
    any_indexer.indexer.max_reservations = 10
    any_indexer.indexer.save()
    client.force_login(any_indexer)
    client.post(reverse('reserve_revision',
                        kwargs={'model_name': 'issue',
                                'id': any_added_issue.id}))
    changeset = Changeset.objects.get(issuerevisions__issue=any_added_issue,
                                      state=states.OPEN)
    if swap:
        # a new order of the sequences gives no IMPs
        client.post(
          reverse('reorder_stories', kwargs={'issue_id': any_added_issue.id,
                                             'changeset_id': changeset.id}),
          {'sequence_number_%d' % changeset.storyrevisions.get(
             story=first).id: '2',
           'sequence_number_%d' % changeset.storyrevisions.get(
             story=second).id: '1'})

    response = client.post(reverse('submit', kwargs={'id': changeset.id}),
                           {'comments': ''},
                           HTTP_REFERER=reverse('edit',
                                                kwargs={'id': changeset.id}))

    assert (EMPTY_CHANGE_ERROR in response.content.decode()) is not swap
    changeset = Changeset.objects.get(id=changeset.id)
    assert changeset.state == (states.PENDING if swap else states.OPEN)


@pytest.mark.django_db
@pytest.mark.parametrize('headers, link', [
    ({}, None), ({'HTTP_REFERER': '/from/here/'}, '/from/here/')])
def test_the_empty_change_message_links_back(client, any_indexer,
                                             any_added_issue, headers, link):
    """The link goes to the referrer, or else to the edit page of the change."""
    _add_story(any_added_issue, any_indexer, 0)
    any_indexer.is_superuser = True
    any_indexer.save()
    any_indexer.indexer.max_reservations = 10
    any_indexer.indexer.save()
    client.force_login(any_indexer)
    client.post(reverse('reserve_revision',
                        kwargs={'model_name': 'issue',
                                'id': any_added_issue.id}))
    changeset = Changeset.objects.get(issuerevisions__issue=any_added_issue,
                                      state=states.OPEN)

    response = client.post(reverse('submit', kwargs={'id': changeset.id}),
                           {'comments': ''}, **headers)

    edit_url = reverse('edit', kwargs={'id': changeset.id})
    content = response.content.decode()
    assert EMPTY_CHANGE_ERROR in content
    assert 'href="%s"' % (link or edit_url) in content
