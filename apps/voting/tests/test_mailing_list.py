import datetime

import pytest

from django.contrib.auth.models import Group, Permission, User
from django.test import override_settings
from django.utils import timezone

from apps.indexer.models import Indexer
from apps.stddata.models import Country
from apps.voting.models import Agenda, AgendaMailingList, MailingList, \
                               Topic, Vote, VoteType, TYPE_PASS_FAIL
from apps.voting.views import _calculate_results

LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'
LIST = 'gcd-main@example.org'
MEMBER = 'board.member@example.org'


@pytest.fixture
def board():
    """
    A group with one member who receives the mails of the group.
    """
    group = Group.objects.create(name='Board')
    user = User.objects.create_user('member', email=MEMBER)
    country = Country.objects.get_or_create(code='XZZ',
                                            name='Test Country')[0]
    Indexer.objects.create(user=user, country=country)
    user.groups.add(group)
    return group


def _list_config(group=None):
    return AgendaMailingList(mailing_list=MailingList(address=LIST),
                             group=group)


def _recipients(mailoutbox):
    return sorted(address for mail in mailoutbox for address in mail.to)


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND=LOCMEM, BETA=False)
def test_live_site_sends_to_the_mailing_list_and_the_group(mailoutbox,
                                                           board):
    _list_config(board).send_mail(subject='GCD Vote Result: X',
                                  message='Body')

    assert _recipients(mailoutbox) == [MEMBER, LIST]
    assert {mail.subject for mail in mailoutbox} == {'GCD Vote Result: X'}


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND=LOCMEM, BETA=True)
def test_beta_sends_no_agenda_mails(mailoutbox, board):
    _list_config(board).send_mail(subject='GCD Vote Result: X',
                                  message='Body')

    assert mailoutbox == []


def _closed_vote_with_list():
    """
    A Pass / Fail topic past its deadline, with two votes For, on an agenda
    that mails its results to LIST.
    """
    agenda = Agenda.objects.create(name='Board',
                                   permission=Permission.objects.first())
    AgendaMailingList.objects.create(
      agenda=agenda, on_vote_close=True,
      mailing_list=MailingList.objects.create(address=LIST))
    vote_type = VoteType.objects.get_or_create(
      name=TYPE_PASS_FAIL, defaults={'max_votes': 1, 'max_winners': 1})[0]
    topic = Topic.objects.create(
      name='Motion', agenda=agenda, vote_type=vote_type,
      author=User.objects.create_user('author'),
      deadline=timezone.now() - datetime.timedelta(days=1))
    for name in ('one', 'two'):
        Vote.objects.create(option=topic.options.get(name='For'),
                            voter=User.objects.create_user(name))
    return topic


@pytest.mark.django_db
@pytest.mark.parametrize(('beta', 'recipients'), ((False, [LIST]),
                                                  (True, [])))
def test_result_of_a_closed_vote(mailoutbox, beta, recipients):
    topic = _closed_vote_with_list()

    with override_settings(EMAIL_BACKEND=LOCMEM, BETA=beta):
        _calculate_results([topic])

    assert _recipients(mailoutbox) == recipients
