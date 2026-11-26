"""Tests of the table of a voter's ranks on an open ranked ballot."""

import datetime
import re

import pytest

from django.contrib.auth.models import Permission, User
from django.urls import reverse
from django.utils import timezone

from apps.indexer.models import Indexer
from apps.stddata.models import Country
from apps.voting.models import Agenda, Topic, Vote, VoteType

RANKS = {'Option B': 1, 'Option A': 2, 'Option C': 3}
HEADER = re.compile(r'<tr class="([^"]*)">\s*<th> Option </th>\s*'
                    r'<th> Rank </th>')
ROW = r'<tr class="([^"]*)">\s*<td> %s </td>\s*<td> %d </td>'


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
    Return an open ranked ballot with three options, which `voter` ranked
    as in RANKS.
    """
    agenda = Agenda.objects.create(name='Test Agenda',
                                   permission=_permission('can_vote'))
    vote_type = VoteType.objects.get_or_create(
      name='Ranked Choice', defaults={'max_votes': None, 'max_winners': 1})[0]
    topic = Topic.objects.create(
      name='Test Election', agenda=agenda, vote_type=vote_type,
      author=_user('author'), open=True,
      deadline=timezone.now() + datetime.timedelta(days=7))
    for position, name in enumerate(sorted(RANKS)):
        option = topic.options.create(name=name, ballot_position=position)
        Vote.objects.create(option=option, rank=RANKS[name], voter=voter)
    return topic


@pytest.mark.django_db
def test_ranked_votes_show_one_option_per_row(client):
    """
    A voter's ranks show one option per table row, in the order of the
    ranks, with the cells side by side and spaced as in the results table.
    """
    voter = _user('voter', 'can_vote')
    topic = _ranked_ballot(voter)
    client.force_login(voter)

    response = client.get(reverse('ballot', kwargs={'id': topic.id}))

    assert response.status_code == 200
    content = response.content.decode()
    header = HEADER.search(content)
    assert header
    assert '[&_th]:px-2' in header.group(1).split()
    rows = [re.search(ROW % (name, rank), content)
            for name, rank in RANKS.items()]
    assert all(rows)
    assert [row.start() for row in rows] == sorted(
      row.start() for row in rows)
    for row in rows:
        classes = row.group(1).split()
        assert 'flex' not in classes
        assert 'flex-col' not in classes
        assert '[&_td]:px-1' in classes
