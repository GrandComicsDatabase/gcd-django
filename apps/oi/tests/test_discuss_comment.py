import re

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


def _modal_url(changeset):
    return reverse('discuss_modal', kwargs={'id': changeset.id})


def _user(changeset, role):
    return changeset.indexer if role == 'indexer' else changeset.approver


def _discuss(client, user, changeset, data):
    client.force_login(user)
    return client.post(reverse('process', kwargs={'id': changeset.id}),
                       {'discuss': '', **data})


def _assert_button_opens_modal(html, changeset):
    button = re.search(r'<button[^>]*name="discuss"[^>]*>', html).group(0)
    assert 'hx-post="%s"' % _modal_url(changeset) in button
    assert 'hx-target="body"' in button
    assert 'hx-swap="beforeend"' in button
    assert 'js/htmx.min.js' in html


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


@pytest.mark.django_db
def test_modal_asks_for_the_comment(client, reviewing_changeset):
    changeset = reviewing_changeset
    client.force_login(changeset.approver)

    response = client.post(_modal_url(changeset),
                           {'comments': 'Typed <b>first</b>'})

    html = response.content.decode()
    assert response.status_code == 200
    assert '<div id="modal"' in html
    assert 'action="%s"' % reverse('process', kwargs={'id': changeset.id}) \
        in html
    assert 'csrfmiddlewaretoken' in html
    textarea = re.search(r'<textarea[^>]*>', html).group(0)
    assert 'name="comments"' in textarea
    assert 'required' in textarea
    assert 'Typed &lt;b&gt;first&lt;/b&gt;</textarea>' in html
    assert re.search(r'<button[^>]*name="discuss"', html)
    changeset.refresh_from_db()
    assert changeset.state == states.REVIEWING


@pytest.mark.django_db
def test_modal_cannot_be_fetched_with_get(client, reviewing_changeset):
    client.force_login(reviewing_changeset.approver)

    html = client.get(_modal_url(reviewing_changeset)).content.decode()

    assert 'may only be accessed through the proper form' in html
    assert 'id="modal"' not in html


@pytest.mark.django_db
@pytest.mark.parametrize('role', ROLES)
def test_compare_page_button_opens_modal(client, reviewing_changeset, role):
    changeset = reviewing_changeset
    client.force_login(_user(changeset, role))

    response = client.get(reverse('compare', kwargs={'id': changeset.id}))

    _assert_button_opens_modal(response.content.decode(), changeset)


@pytest.mark.django_db
def test_inline_edit_page_button_opens_modal(client, reviewing_changeset):
    changeset = reviewing_changeset
    changeset.state = states.OPEN
    changeset.save()
    client.force_login(changeset.indexer)

    response = client.get(reverse('edit', kwargs={'id': changeset.id}))

    _assert_button_opens_modal(response.content.decode(), changeset)


@pytest.mark.django_db
def test_issue_changeset_page_button_opens_modal(client, any_indexer,
                                                 any_added_issue, approver):
    _reserve(client, any_indexer, 'issue', any_added_issue)
    changeset = Changeset.objects.get(issuerevisions__issue=any_added_issue,
                                      state=states.OPEN)
    changeset.approver = approver
    changeset.save()

    response = client.get(reverse('edit', kwargs={'id': changeset.id}))

    _assert_button_opens_modal(response.content.decode(), changeset)
