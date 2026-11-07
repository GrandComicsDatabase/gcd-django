import datetime

import pytest

from django.contrib.auth.models import Permission, User
from django.utils import timezone

from apps.voting.models import Agenda, Topic, Vote, VoteType, \
                               TYPE_CHARTER, TYPE_PASS_FAIL
from apps.voting.views import _calculate_results


def _topic(vote_type_name, allows_abstentions=False):
    vote_type, created = VoteType.objects.get_or_create(
      name=vote_type_name, defaults={'max_votes': 1, 'max_winners': 1})
    agenda = Agenda.objects.create(name='Board',
                                   permission=Permission.objects.first(),
                                   allows_abstentions=allows_abstentions)
    author = User.objects.create_user('author')
    # Saving the topic adds its For and Against (and Abstain) options.
    return Topic.objects.create(
      name='Motion', agenda=agenda, vote_type=vote_type, author=author,
      deadline=timezone.now() - datetime.timedelta(days=1))


def _vote(topic, **votes):
    for option_name, count in votes.items():
        option = topic.options.get(name=option_name)
        for i in range(count):
            voter = User.objects.create_user('%s%d' % (option_name, i))
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
))
def test_charter_needs_two_thirds(votes, winner):
    topic = _topic(TYPE_CHARTER)
    _vote(topic, **votes)

    _calculate_results([topic])

    assert _result(topic) == (False, [winner])
