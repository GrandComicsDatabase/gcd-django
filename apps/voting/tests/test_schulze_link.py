"""Tests of the explanation of the ranks on an open ranked ballot."""

import datetime
import re

import pytest

from django.contrib.auth.models import Permission, User
from django.urls import reverse
from django.utils import timezone

from apps.indexer.models import Indexer
from apps.stddata.models import Country
from apps.voting.models import Agenda, Topic, VoteType

ARTICLE = 'https://en.wikipedia.org/wiki/Schulze_method'
LINK = re.compile(r'<a href="([^"]*)">Schulze\s+Method</a>')


def _permission(codename):
    """Return the indexer permission with the given code name."""
    return Permission.objects.get(content_type__app_label='indexer',
                                  codename=codename)


def _user(username, *codenames):
    """Return a user with an indexer record and these permissions."""
    user = User.objects.create_user(username)
    country = Country.objects.get_or_create(code='XZZ',
                                            name='Test Country')[0]
    Indexer.objects.create(user=user, country=country)
    for codename in codenames:
        user.user_permissions.add(_permission(codename))
    return user


def _ranked_ballot():
    """Return an open ranked ballot with two options and no votes."""
    agenda = Agenda.objects.create(name='Test Agenda',
                                   permission=_permission('can_vote'))
    vote_type = VoteType.objects.get_or_create(
      name='Ranked Choice', defaults={'max_votes': None, 'max_winners': 1})[0]
    topic = Topic.objects.create(
      name='Test Election', agenda=agenda, vote_type=vote_type,
      author=_user('author'), open=True,
      deadline=timezone.now() + datetime.timedelta(days=7))
    topic.options.create(name='Option A', ballot_position=0)
    topic.options.create(name='Option B', ballot_position=1)
    return topic


@pytest.mark.django_db
def test_schulze_method_link_leads_to_its_description(client):
    """
    The explanation above the ranks of an open ranked ballot links the
    Schulze Method to an article on it, not back to the ballot page.
    """
    topic = _ranked_ballot()
    client.force_login(_user('voter', 'can_vote'))

    response = client.get(reverse('ballot', kwargs={'id': topic.id}))

    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="option_%d"' % topic.options.get(name='Option A').id \
        in content
    links = LINK.findall(content)
    assert links == [ARTICLE]
