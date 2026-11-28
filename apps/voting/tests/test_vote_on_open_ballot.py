"""Tests that a vote counts only on a ballot that is open."""

import datetime

import pytest

from django.contrib.auth.models import Permission, User
from django.urls import reverse
from django.utils import timezone

from apps.indexer.models import Indexer
from apps.stddata.models import Country
from apps.voting.models import Agenda, Topic, Vote, VoteType, \
                               TYPE_PASS_FAIL

REFUSAL = 'This ballot is not open for votes.'
ONE_BALLOT = 'You can vote on only one ballot at a time.'


def _voter():
    """Return a user with an indexer record who may vote."""
    user = User.objects.create_user('voter')
    country = Country.objects.get_or_create(code='XZZ',
                                            name='Test Country')[0]
    Indexer.objects.create(user=user, country=country)
    user.user_permissions.add(Permission.objects.get(
      content_type__app_label='indexer', codename='can_vote'))
    return user


def _ballot(days, is_open, result_calculated):
    """
    Return a Pass / Fail topic whose deadline is `days` from now, opened
    for votes or not, with or without its result counted.
    """
    agenda = Agenda.objects.create(
      name='Test Agenda',
      permission=Permission.objects.get(content_type__app_label='indexer',
                                        codename='can_vote'))
    vote_type = VoteType.objects.get_or_create(
      name=TYPE_PASS_FAIL, defaults={'max_votes': 1, 'max_winners': 1})[0]
    return Topic.objects.create(
      name='Test Motion', text='A motion.', agenda=agenda,
      vote_type=vote_type,
      author=User.objects.get_or_create(username='author')[0],
      open=is_open, result_calculated=result_calculated,
      deadline=timezone.now() + datetime.timedelta(days=days))


def _vote_for(client, topic):
    """Vote For on `topic` as a member and return the page shown."""
    client.force_login(_voter())
    return client.post(reverse('vote'),
                       {'option': topic.options.get(name='For').id},
                       follow=True)


@pytest.mark.django_db
@pytest.mark.parametrize('days, is_open, result_calculated', [
    (-1, True, False), (1, False, False), (1, True, True)],
    ids=['past_deadline', 'not_opened', 'result_counted'])
def test_vote_on_a_ballot_that_is_not_open_is_refused(
  client, days, is_open, result_calculated):
    """
    The ballot page shows no form once the deadline has passed or the
    result is counted, nor before the ballot is opened; a vote sent
    anyway is refused and not saved.
    """
    topic = _ballot(days, is_open, result_calculated)

    response = _vote_for(client, topic)

    assert REFUSAL in response.content.decode()
    assert not Vote.objects.filter(option__topic=topic).exists()


@pytest.mark.django_db
def test_vote_on_an_open_ballot_is_saved(client):
    """A vote before the deadline on an opened ballot is saved."""
    topic = _ballot(1, True, False)

    response = _vote_for(client, topic)

    assert REFUSAL not in response.content.decode()
    assert Vote.objects.filter(option__topic=topic,
                               option__name='For').count() == 1


@pytest.mark.django_db
def test_vote_on_two_ballots_at_once_is_refused(client):
    """
    A vote with an option of an open ballot that allows two choices and
    one of a ballot that is not open is refused, and nothing is saved.
    """
    closed = _ballot(1, False, False)
    topic = _ballot(1, True, False)
    topic.vote_type = VoteType.objects.create(
      name='Test Two Choices', max_votes=2, max_winners=2)
    topic.save()
    client.force_login(_voter())

    response = client.post(reverse('vote'), {'option': [
      topic.options.get(name='For').id,
      closed.options.get(name='Against').id]}, follow=True)

    assert ONE_BALLOT in response.content.decode()
    assert not Vote.objects.exists()
