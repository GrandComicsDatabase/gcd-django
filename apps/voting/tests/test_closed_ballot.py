"""Tests of who can read a ballot page and who sees the voters' names."""

import datetime
import re

import pytest

from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.urls import reverse
from django.utils import timezone

from apps.indexer.models import Indexer
from apps.stddata.models import Country
from apps.voting.models import Agenda, ExpectedVoter, Receipt, Topic, \
                               Vote, VoteType, TYPE_PASS_FAIL

RANKED = 'Ranked Choice'
TEXT = 'Abbreviations in job descriptions follow the list.'
VOTER_NAME = 'Some Voter'
VOTERS_COLUMN = '<th> Voters </th>'
RANK_COLUMN = '<th> Rank </th>'
ABSENT_ROW = re.compile(r'<td> Absent Voters </td>\s*<td> 1 </td>')
REFUSAL = 'You do not have permission to vote on this topic.'


def _permission(codename):
    """Return the indexer permission with the given code name."""
    return Permission.objects.get(content_type__app_label='indexer',
                                  codename=codename)


def _user(username, *codenames, first_name='', last_name=''):
    """Return a user with an indexer record and these permissions."""
    user = User.objects.create_user(username, first_name=first_name,
                                    last_name=last_name)
    country = Country.objects.get_or_create(code='XZZ',
                                            name='Test Country')[0]
    Indexer.objects.create(user=user, country=country)
    for codename in codenames:
        user.user_permissions.add(_permission(codename))
    return user


def _ballot(codename='can_vote', secret=False, days=-1, is_open=True,
            ranked=False):
    """
    Return a topic with the options For and Against on an agenda for the
    permission `codename`, with its deadline `days` from now and one
    voter, who voted For or, on a ranked vote, ranked For before Against.
    """
    agenda = Agenda.objects.create(name='Test Agenda',
                                   permission=_permission(codename),
                                   secret_ballot=secret)
    if ranked:
        vote_type = VoteType.objects.get_or_create(
          name=RANKED, defaults={'max_votes': None, 'max_winners': 1})[0]
    else:
        vote_type = VoteType.objects.get_or_create(
          name=TYPE_PASS_FAIL, defaults={'max_votes': 1, 'max_winners': 1})[0]
    topic = Topic.objects.create(
      name='Test Motion', text=TEXT, agenda=agenda, vote_type=vote_type,
      author=_user('author'), open=is_open,
      deadline=timezone.now() + datetime.timedelta(days=days))
    if ranked:
        topic.options.create(name='For', ballot_position=0)
        topic.options.create(name='Against', ballot_position=1)
    voter = _user('voter', 'can_vote', codename,
                  first_name='Some', last_name='Voter')
    ranks = {'For': 1, 'Against': 2} if ranked else {'For': None}
    for name, rank in ranks.items():
        Vote.objects.create(option=topic.options.get(name=name), rank=rank,
                            voter=None if secret else voter)
    if secret:
        Receipt.objects.create(topic=topic, voter=voter, vote_key='key')
    return topic


def _expect_voters(topic):
    """
    Make the voter of `topic` and a member who did not vote the expected
    voters of its agenda.
    """
    absent = _user('absent', 'can_vote', first_name='Absent',
                   last_name='Member')
    for user in (User.objects.get(username='voter'), absent):
        ExpectedVoter.objects.create(
          voter=user, agenda=topic.agenda,
          tenure_began=topic.deadline - datetime.timedelta(days=30))


def _view(client, topic, viewer, follow=False):
    """
    Open the ballot page of `topic` as `viewer`: 'anonymous', 'reader'
    (logged in, no vote) or 'member' (a voting member).
    """
    if viewer == 'reader':
        client.force_login(_user('reader'))
    elif viewer == 'member':
        client.force_login(_user('member', 'can_vote'))
    return client.get(reverse('ballot', kwargs={'id': topic.id}),
                      follow=follow)


@pytest.mark.django_db
@pytest.mark.parametrize('viewer', ['anonymous', 'reader'])
def test_everyone_reads_a_closed_ballot(client, viewer):
    """A closed ballot shows its name, period, text and totals to anyone."""
    response = _view(client, _ballot(), viewer)

    assert response.status_code == 200
    content = response.content.decode()
    assert 'Test Motion' in content
    assert 'Voting Period:' in content
    assert TEXT in content
    assert 'Total number of voters: 1' in content
    assert '<td class="align-top"> For </td>' in content
    assert '<td class="align-top"> Against </td>' in content


@pytest.mark.django_db
def test_agenda_results_lead_to_the_closed_ballot(client):
    """The Results of the agenda link to a ballot that anyone can read."""
    topic = _ballot()
    agenda = client.get(topic.agenda.get_absolute_url()).content.decode()
    link = '<a href="%s">Test Motion</a>' % topic.get_absolute_url()
    assert link in agenda

    response = client.get(topic.get_absolute_url())

    assert response.status_code == 200
    assert TEXT in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize('viewer', ['anonymous', 'reader'])
def test_closed_ballot_hides_the_names_from_non_voters(client, viewer):
    """On other agendas the names of the voters stay hidden from non-voters."""
    response = _view(client, _ballot(), viewer)

    assert response.status_code == 200
    content = response.content.decode()
    assert 'Total number of voters: 1' in content
    assert VOTERS_COLUMN not in content
    assert VOTER_NAME not in content


@pytest.mark.django_db
def test_closed_ballot_shows_the_names_to_voters(client):
    """Voting members still see the names of the voters."""
    response = _view(client, _ballot(), 'member')

    assert response.status_code == 200
    content = response.content.decode()
    assert VOTERS_COLUMN in content
    assert VOTER_NAME in content


@pytest.mark.django_db
@pytest.mark.parametrize('viewer', ['anonymous', 'reader', 'member'])
def test_board_ballot_shows_the_names_to_everyone(client, viewer):
    """On a Board agenda everyone sees the names of the voters."""
    response = _view(client, _ballot(codename='on_board'), viewer)

    assert response.status_code == 200
    content = response.content.decode()
    assert VOTERS_COLUMN in content
    assert VOTER_NAME in content


@pytest.mark.django_db
@pytest.mark.parametrize('codename', ['can_vote', 'on_board'])
@pytest.mark.parametrize('viewer', ['anonymous', 'reader', 'member'])
def test_secret_ballot_never_shows_the_names(client, codename, viewer):
    """A secret ballot shows no names, on any agenda, to anyone."""
    topic = _ballot(codename=codename, secret=True)

    response = _view(client, topic, viewer)

    assert response.status_code == 200
    content = response.content.decode()
    assert 'Total number of voters: 1' in content
    assert VOTERS_COLUMN not in content
    assert VOTER_NAME not in content


@pytest.mark.django_db
@pytest.mark.parametrize('viewer, shown', [('reader', False),
                                           ('member', True)])
def test_ranks_go_with_the_names(client, viewer, shown):
    """On a ranked vote the Rank column shows only with the names."""
    response = _view(client, _ballot(ranked=True), viewer)

    assert response.status_code == 200
    content = response.content.decode()
    assert 'Total number of voters: 1' in content
    assert (RANK_COLUMN in content) is shown
    assert (VOTER_NAME in content) is shown


@pytest.mark.django_db
@pytest.mark.parametrize('codename, shown', [('can_vote', False),
                                             ('on_board', True)])
def test_absent_voters_are_counted_and_named_on_board(client, codename,
                                                      shown):
    """Non-voters see how many expected voters did not vote, not who."""
    topic = _ballot(codename=codename)
    _expect_voters(topic)

    response = _view(client, topic, 'reader')

    assert response.status_code == 200
    content = response.content.decode()
    assert ABSENT_ROW.search(content)
    assert ('Absent Member' in content) is shown


@pytest.mark.django_db
def test_ballot_below_quorum_shows_no_votes(client):
    """A ballot just closed below its quorum is counted, and shows none."""
    topic = _ballot(codename='on_board')
    Agenda.objects.filter(id=topic.agenda_id).update(quorum=2)

    response = _view(client, topic, 'anonymous')

    assert response.status_code == 200
    content = response.content.decode()
    assert 'This ballot did not produce a valid result' in content
    assert VOTERS_COLUMN not in content
    assert VOTER_NAME not in content
    topic.refresh_from_db()
    assert topic.result_calculated
    assert topic.invalid


@pytest.mark.django_db
@pytest.mark.parametrize('days, is_open', [(1, True), (-1, False)],
                         ids=['open', 'never_opened'])
def test_ballot_without_result_is_refused_to_anonymous(client, days,
                                                       is_open):
    """An open or never opened ballot still asks anonymous users to log in."""
    topic = _ballot(days=days, is_open=is_open)

    response = _view(client, topic, 'anonymous')

    assert response.status_code == 302
    assert response.url == '%s?next=%s' % (settings.LOGIN_URL,
                                           topic.get_absolute_url())


@pytest.mark.django_db
@pytest.mark.parametrize('days, is_open', [(1, True), (-1, False)],
                         ids=['open', 'never_opened'])
def test_ballot_without_result_is_refused_to_non_voters(client, days,
                                                        is_open):
    """An open or never opened ballot is still refused to non-voters."""
    topic = _ballot(days=days, is_open=is_open)

    response = _view(client, topic, 'reader', follow=True)

    content = response.content.decode()
    assert REFUSAL in content
    assert TEXT not in content
