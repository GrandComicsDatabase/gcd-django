"""Tests of the Text column of a voter's ranks on an open ranked ballot."""

import datetime
import re

import pytest

from django.contrib.auth.models import Permission, User
from django.urls import reverse
from django.utils import timezone

from apps.indexer.models import Indexer
from apps.stddata.models import Country
from apps.voting.models import Agenda, Topic, Vote, VoteType

OPTION_TEXT = 'Keep the current list.'
ROW = r'<td> %s </td>\s*<td> %d </td>\s*<td>(.*?)</td>'


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


def _ranked_ballot(voter):
    """
    Return an open ranked ballot on an agenda that allows abstentions,
    with the option A, whose text is OPTION_TEXT, and the option Abstain
    that the topic gets by itself; `voter` ranked them 1 and 2.
    """
    agenda = Agenda.objects.create(name='Test Agenda',
                                   permission=_permission('can_vote'),
                                   allows_abstentions=True)
    vote_type = VoteType.objects.get_or_create(
      name='Ranked Choice', defaults={'max_votes': None, 'max_winners': 1})[0]
    topic = Topic.objects.create(
      name='Test Election', agenda=agenda, vote_type=vote_type,
      author=_user('author'), open=True,
      deadline=timezone.now() + datetime.timedelta(days=7))
    with_text = topic.options.create(name='Option A', text=OPTION_TEXT,
                                     ballot_position=0)
    Vote.objects.create(option=with_text, rank=1, voter=voter)
    Vote.objects.create(option=topic.options.get(name='Abstain'), rank=2,
                        voter=voter)
    return topic


@pytest.mark.django_db
def test_ranked_vote_text_is_empty_for_an_option_without_text(client):
    """
    In a voter's ranks the Text cell of an option without text, such as
    the Abstain that a topic gets by itself, is empty, and an option with
    a text shows it.
    """
    voter = _user('voter', 'can_vote')
    topic = _ranked_ballot(voter)
    assert topic.options.get(name='Abstain').text is None
    client.force_login(voter)

    response = client.get(reverse('ballot', kwargs={'id': topic.id}))

    assert response.status_code == 200
    content = response.content.decode()
    with_text = re.search(ROW % ('Option A', 1), content, re.S)
    without_text = re.search(ROW % ('Abstain', 2), content, re.S)
    assert with_text and without_text
    assert with_text.group(1).strip() == OPTION_TEXT
    assert without_text.group(1).strip() == ''
