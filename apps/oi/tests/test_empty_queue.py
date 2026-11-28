import pytest

from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.oi import states
from apps.oi.models import Changeset, PublisherRevision, CTYPES

QUEUES = (
  ('editing', 'You are not editing any records.'),
  ('pending', 'No changes are pending review.'),
  ('reviewing', 'No changes are under your review.'),
)


@pytest.fixture
def editor(any_indexer):
    """An indexer who may open the queues."""
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    return any_indexer


@pytest.mark.django_db
@pytest.mark.parametrize(('url_name', 'sentence'), QUEUES)
def test_empty_queue_says_so(client, editor, url_name, sentence):
    """A queue with no change shows one sentence under its heading."""
    client.force_login(editor)
    response = client.get(reverse(url_name))

    assert sentence in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(('url_name', 'sentence'), QUEUES)
def test_queue_with_a_change_has_no_sentence(client, editor, any_country,
                                             url_name, sentence):
    """A change that the editor reviews is in all three queues."""
    changeset = Changeset.objects.create(
      state=states.REVIEWING, indexer=editor, approver=editor,
      change_type=CTYPES['publisher'])
    PublisherRevision.objects.create(changeset=changeset,
                                     name='Test Publisher',
                                     country=any_country)
    client.force_login(editor)
    response = client.get(reverse(url_name))

    content = response.content.decode()
    assert 'Test Publisher' in content
    assert sentence not in content
