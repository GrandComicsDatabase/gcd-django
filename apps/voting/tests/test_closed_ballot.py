"""Tests of who can read a ballot page and who sees the voters' names."""

import datetime

import pytest

from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.urls import reverse
from django.utils import timezone

from apps.indexer.models import Indexer
from apps.stddata.models import Country
from apps.voting.models import Agenda, Receipt, Topic, Vote, VoteType, \
                               TYPE_PASS_FAIL

TEXT = 'Abbreviations in job descriptions follow the list.'
VOTER_NAME = 'Some Voter'
VOTERS_COLUMN = '<th> Voters </th>'
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


def _ballot(codename='can_vote', secret=False, days=-1, is_open=True):
    """
    Return a Pass / Fail topic on an agenda for the permission `codename`,
    with its deadline `days` from now and one vote For.
    """
    agenda = Agenda.objects.create(name='Test Agenda',
                                   permission=_permission(codename),
                                   secret_ballot=secret)
    vote_type = VoteType.objects.get_or_create(
      name=TYPE_PASS_FAIL, defaults={'max_votes': 1, 'max_winners': 1})[0]
    topic = Topic.objects.create(
      name='Test Motion', text=TEXT, agenda=agenda, vote_type=vote_type,
      author=_user('author'), open=is_open,
      deadline=timezone.now() + datetime.timedelta(days=days))
    voter = _user('voter', 'can_vote', codename,
                  first_name='Some', last_name='Voter')
    option = topic.options.get(name='For')
    if secret:
        Vote.objects.create(option=option, voter=None)
        Receipt.objects.create(topic=topic, voter=voter, vote_key='key')
    else:
        Vote.objects.create(option=option, voter=voter)
    return topic


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
@pytest.mark.parametrize('viewer', ['anonymous', 'reader'])
def test_board_ballot_shows_the_names_to_everyone(client, viewer):
    """On a Board agenda everyone sees the names of the voters."""
    response = _view(client, _ballot(codename='on_board'), viewer)

    assert response.status_code == 200
    content = response.content.decode()
    assert VOTERS_COLUMN in content
    assert VOTER_NAME in content


@pytest.mark.django_db
@pytest.mark.parametrize('viewer', ['anonymous', 'reader', 'member'])
def test_secret_ballot_never_shows_the_names(client, viewer):
    """A secret ballot shows no names, not even on a Board agenda."""
    topic = _ballot(codename='on_board', secret=True)

    response = _view(client, topic, viewer)

    assert response.status_code == 200
    content = response.content.decode()
    assert 'Total number of voters: 1' in content
    assert VOTERS_COLUMN not in content
    assert VOTER_NAME not in content


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
