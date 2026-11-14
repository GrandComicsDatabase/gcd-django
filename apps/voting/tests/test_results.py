import datetime

import pytest

from django.contrib.auth.models import Permission, User
from django.test import override_settings
from django.utils import timezone

from apps.voting.models import Agenda, AgendaMailingList, MailingList, \
                               Topic, Vote, VoteType, \
                               TYPE_CHARTER, TYPE_PASS_FAIL
from apps.voting.views import _calculate_results

LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'
CHARTER_NOTE = 'Charter Amendments require a 2/3 majority'


def _topic(vote_type_name, allows_abstentions=False, name='Motion'):
    """
    A topic past its deadline, on an agenda that mails its results to a
    mailing list.
    """
    vote_type, created = VoteType.objects.get_or_create(
      name=vote_type_name, defaults={'max_votes': 1, 'max_winners': 1})
    agenda = Agenda.objects.create(name='Board',
                                   permission=Permission.objects.first(),
                                   allows_abstentions=allows_abstentions)
    AgendaMailingList.objects.create(
      agenda=agenda, on_vote_close=True,
      mailing_list=MailingList.objects.create(address='list@example.org'))
    author = User.objects.get_or_create(username='author')[0]
    # Saving the topic adds its For and Against (and Abstain) options.
    return Topic.objects.create(
      name=name, agenda=agenda, vote_type=vote_type, author=author,
      deadline=timezone.now() - datetime.timedelta(days=1))


def _vote(topic, **votes):
    for option_name, count in votes.items():
        option = topic.options.get(name=option_name)
        for i in range(count):
            voter = User.objects.create_user(
              '%s %s %d' % (topic.name, option_name, i))
            Vote.objects.create(option=option, voter=voter)


def _result(topic):
    topic.refresh_from_db()
    return topic.invalid, \
        [option.name for option in topic.options.filter(result=True)]


@pytest.mark.django_db
@pytest.mark.parametrize(('votes', 'winner'), (
    ({'For': 1, 'Against': 1}, 'Against'),
    ({'For': 2, 'Against': 1}, 'For'),
    ({'For': 1, 'Against': 2}, 'Against'),
    ({'For': 2}, 'For'),
    ({'Against': 2}, 'Against'),
))
def test_pass_fail_result(votes, winner):
    topic = _topic(TYPE_PASS_FAIL)
    _vote(topic, **votes)

    _calculate_results([topic])

    assert _result(topic) == (False, [winner])


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND=LOCMEM, BETA=False)
def test_tied_pass_fail_mails_that_the_motion_failed(mailoutbox):
    topic = _topic(TYPE_PASS_FAIL)
    _vote(topic, For=1, Against=1)

    _calculate_results([topic])

    assert len(mailoutbox) == 1
    assert 'The motion FAILED' in mailoutbox[0].body
    assert 'failed to produce a valid result' not in mailoutbox[0].body


@pytest.mark.django_db
def test_pass_fail_abstentions_do_not_decide():
    topic = _topic(TYPE_PASS_FAIL, allows_abstentions=True)
    _vote(topic, For=1, Abstain=2)

    _calculate_results([topic])

    assert _result(topic) == (False, ['For'])


@pytest.mark.django_db
@pytest.mark.parametrize(('votes', 'winner'), (
    ({'For': 2, 'Against': 1}, 'For'),
    ({'For': 1, 'Against': 1}, 'Against'),
    ({'For': 3}, 'For'),
    ({'Against': 3}, 'Against'),
))
def test_charter_needs_two_thirds(votes, winner):
    topic = _topic(TYPE_CHARTER)
    _vote(topic, **votes)

    _calculate_results([topic])

    assert _result(topic) == (False, [winner])


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND=LOCMEM, BETA=False)
def test_charter_note_only_in_the_mail_of_the_charter(mailoutbox):
    charter = _topic(TYPE_CHARTER, name='Charter')
    _vote(charter, For=3, Against=1)
    motion = _topic(TYPE_PASS_FAIL, name='Motion')
    _vote(motion, For=2, Against=1)

    _calculate_results([charter, motion])

    bodies = {mail.subject: mail.body for mail in mailoutbox}
    assert CHARTER_NOTE in bodies['GCD Vote Result: Charter']
    assert CHARTER_NOTE not in bodies['GCD Vote Result: Motion']
