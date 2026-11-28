import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.urls import reverse

from apps.indexer.models import Indexer
from apps.oi import states
from apps.oi.models import Changeset

ROLES = ('indexer', 'approver')
COMMENT_REQUIRED = 'A comment is required to put a change into discussion.'


@pytest.fixture
def approver(any_country):
    user = User.objects.create_user('approver',
                                    email='approver@comics.org',
                                    password='approver',
                                    is_superuser=True)
    Indexer.objects.create(user=user, country=any_country)
    return user


def _reserve(client, indexer, model_name, data_object):
    indexer.is_superuser = True
    indexer.save()
    indexer.indexer.max_reservations = 10
    indexer.indexer.save()
    client.force_login(indexer)
    client.post(reverse('reserve_revision',
                        kwargs={'model_name': model_name,
                                'id': data_object.id}))


@pytest.fixture
def reviewing_changeset(client, any_indexer, any_added_publisher, approver):
    _reserve(client, any_indexer, 'publisher', any_added_publisher)
    changeset = Changeset.objects.get(
      publisherrevisions__publisher=any_added_publisher, state=states.OPEN)
    changeset.state = states.REVIEWING
    changeset.approver = approver
    changeset.save()
    client.logout()
    mail.outbox.clear()
    return changeset


def _user(changeset, role):
    return changeset.indexer if role == 'indexer' else changeset.approver


def _discuss(client, user, changeset, data):
    client.force_login(user)
    return client.post(reverse('process', kwargs={'id': changeset.id}),
                       {'discuss': '', **data})


@pytest.mark.django_db
@pytest.mark.parametrize('role', ROLES)
@pytest.mark.parametrize('data', [{'comments': ''}, {'comments': ' \n '}, {}],
                         ids=['empty', 'blank', 'missing'])
def test_discuss_is_refused_without_a_comment(client, reviewing_changeset,
                                              role, data):
    changeset = reviewing_changeset

    response = _discuss(client, _user(changeset, role), changeset, data)

    changeset.refresh_from_db()
    assert changeset.state == states.REVIEWING
    assert not changeset.comments.filter(new_state=states.DISCUSSED).exists()
    assert mail.outbox == []
    assert response.url.startswith(reverse('error'))
    assert COMMENT_REQUIRED in client.get(response.url).content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize('role, queue', [('indexer', 'editing'),
                                         ('approver', 'pending')])
def test_discuss_with_a_comment(client, reviewing_changeset, role, queue):
    changeset = reviewing_changeset
    other = changeset.approver if role == 'indexer' else changeset.indexer

    response = _discuss(client, _user(changeset, role), changeset,
                        {'comments': '  Is the date right?  '})

    changeset.refresh_from_db()
    assert changeset.state == states.DISCUSSED
    comment = changeset.comments.get(new_state=states.DISCUSSED)
    assert comment.text == 'Is the date right?'
    message = [m for m in mail.outbox if other.email in m.to][0]
    assert message.subject == 'GCD change put into discussion with a comment'
    assert 'Is the date right?' in message.body
    assert response.url == reverse(queue)
