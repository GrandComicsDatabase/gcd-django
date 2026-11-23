"""Tests of the count of the votes of a closed ranked ballot."""

import datetime

import pytest

from django.contrib.auth.models import Permission, User
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.voting.models import Agenda, AgendaMailingList, MailingList, \
                               Receipt, Topic, Vote, VoteType
from apps.voting.views import _calculate_results

pytestmark = pytest.mark.django_db

LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'
NO_RESULT = 'This vote failed to produce a valid result'


def _ranked_topic(secret=False):
    """
    Return a closed ranked topic with the options For and Against, on an
    agenda with a quorum of one voter whose results go to a mailing list.
    """
    agenda = Agenda.objects.create(
      name='Test Agenda', secret_ballot=secret, quorum=1,
      permission=Permission.objects.get(content_type__app_label='indexer',
                                        codename='can_vote'))
    AgendaMailingList.objects.create(
      agenda=agenda, on_vote_close=True,
      mailing_list=MailingList.objects.create(address='list@example.org'))
    vote_type = VoteType.objects.get_or_create(
      name='Ranked Choice', defaults={'max_votes': None, 'max_winners': 1})[0]
    topic = Topic.objects.create(
      name='Test Election', agenda=agenda, vote_type=vote_type,
      author=User.objects.create_user('author'), open=True,
      deadline=timezone.now() - datetime.timedelta(days=1))
    topic.options.create(name='For', ballot_position=0)
    topic.options.create(name='Against', ballot_position=1)
    return topic


def _rank(topic, voter):
    """Rank For before Against on `topic`, with `voter` on the votes."""
    for name, rank in (('For', 1), ('Against', 2)):
        Vote.objects.create(option=topic.options.get(name=name), rank=rank,
                            voter=voter)


@override_settings(EMAIL_BACKEND=LOCMEM, BETA=False)
def test_secret_ranked_vote_has_no_valid_result(mailoutbox):
    """
    The rankings of a secret ballot have no voter, so they cannot be put
    together into ballots: the topic has no valid result, as for a tie.
    """
    topic = _ranked_topic(secret=True)
    _rank(topic, None)
    Receipt.objects.create(topic=topic, vote_key='key',
                           voter=User.objects.create_user('voter'))

    _calculate_results([topic])

    topic.refresh_from_db()
    assert topic.result_calculated
    assert topic.invalid
    assert not topic.options.filter(result=True).exists()
    assert len(mailoutbox) == 1
    assert NO_RESULT in mailoutbox[0].body


def test_agenda_page_of_a_secret_ranked_ballot(client):
    """The agenda page lists a closed secret ranked ballot as invalid."""
    topic = _ranked_topic(secret=True)
    _rank(topic, None)
    Receipt.objects.create(topic=topic, vote_key='key',
                           voter=User.objects.create_user('voter'))

    response = client.get(reverse('agenda', kwargs={'id': topic.agenda.id}))

    assert response.status_code == 200
    assert '[no result]' in response.content.decode()


def test_ranked_vote_is_counted():
    """A ranked ballot with its voters is counted as before."""
    topic = _ranked_topic()
    _rank(topic, User.objects.create_user('voter'))

    _calculate_results([topic])

    topic.refresh_from_db()
    assert topic.result_calculated
    assert not topic.invalid
    assert topic.options.get(name='For').result is True
    assert topic.options.get(name='Against').result is False
