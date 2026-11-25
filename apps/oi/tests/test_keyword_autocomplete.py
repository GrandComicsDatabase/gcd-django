"""Who may add a new keyword from the keyword picker of the story form."""
import pytest

from django.contrib.auth.models import Group, Permission
from django.urls import reverse
from taggit.models import Tag

NEW_KEYWORD = 'Some New Keyword'


@pytest.fixture
def member(any_indexer):
    """An indexer in the member group, which can vote; not a superuser."""
    group = Group.objects.get_or_create(name='member')[0]
    group.permissions.add(Permission.objects.get(
      codename='can_vote', content_type__app_label='indexer'))
    any_indexer.groups.add(group)
    return any_indexer


def _create_offered(client):
    """Say if the picker offers to create the keyword typed in it."""
    answer = client.get(reverse('keyword_autocomplete'), {'q': NEW_KEYWORD})
    return any(result.get('create_id')
               for result in answer.json()['results'])


@pytest.mark.django_db
def test_member_can_add_a_keyword(client, member):
    """The picker offers a member to create the keyword, and creates it."""
    client.force_login(member)

    offered = _create_offered(client)
    answer = client.post(reverse('keyword_autocomplete'),
                         {'text': NEW_KEYWORD})

    assert offered
    assert answer.status_code == 200
    assert Tag.objects.filter(name=NEW_KEYWORD).exists()


@pytest.mark.django_db
def test_indexer_who_is_not_a_member_cannot_add_a_keyword(client,
                                                          any_indexer):
    """The picker neither offers nor creates a keyword for a non-member."""
    client.force_login(any_indexer)

    offered = _create_offered(client)
    answer = client.post(reverse('keyword_autocomplete'),
                         {'text': NEW_KEYWORD})

    assert not offered
    assert answer.status_code == 403
    assert not Tag.objects.filter(name=NEW_KEYWORD).exists()
