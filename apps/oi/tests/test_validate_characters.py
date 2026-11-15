# -*- coding: utf-8 -*-
"""The "Validate Characters" button of the sequence form and its view."""

import re

import pytest

from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from apps.oi.models import CTYPES, Changeset, StoryRevision

BUTTON = re.compile(r'<button type="button" class="mx-0 btn-blue-editing '
                    r'inline" hx-post="([^"]+)" hx-params="([^"]+)" '
                    r'hx-target="#characters-check">Validate Characters'
                    r'</button><div id="characters-check"></div>')


@pytest.fixture
def story_revision(any_edit_story_rev):
    """A sequence on the edit page of a change to its issue."""
    changeset = any_edit_story_rev.changeset
    changeset.change_type = CTYPES['issue']
    changeset.save()
    changeset.indexer.user_permissions.add(Permission.objects.get(
      content_type__app_label='indexer', codename='can_reserve'))
    return any_edit_story_rev


def _edit_url(revision):
    """The edit page of the sequence."""
    return reverse('edit_revision', kwargs={'model_name': 'story',
                                            'id': revision.id})


def _add_url(revision):
    """The page that adds a sequence to the issue of the change."""
    changeset = revision.changeset
    return reverse('add_story', kwargs={
      'issue_revision_id': changeset.issuerevisions.get().id,
      'changeset_id': changeset.id}) + '?added_sequence_number=2'


def _form_value(html, name):
    """The value the page gives to the field name."""
    textarea = re.search(r'<textarea name="%s"[^>]*>\n?(.*?)</textarea>'
                         % name, html, re.S)
    if textarea:
        return textarea.group(1)
    return re.search(r'name="%s" value="([^"]*)"' % name, html).group(1)


@pytest.mark.django_db
@pytest.mark.parametrize('use_tabs', [True, False])
@pytest.mark.parametrize('page', [_edit_url, _add_url])
def test_the_button_sends_the_text_of_the_page(story_revision, use_tabs,
                                               page):
    """The button posts the field and the token to its view."""
    indexer = story_revision.changeset.indexer
    indexer.indexer.use_tabs = use_tabs
    indexer.indexer.save()
    client = Client(enforce_csrf_checks=True)
    client.force_login(indexer)
    html = client.get(page(story_revision)).content.decode()

    buttons = BUTTON.findall(html)
    assert len(buttons) == 1
    url, params = buttons[0]
    assert html.index('name="characters"') < html.index(url)
    data = {name: _form_value(html, name) for name in params.split(',')}
    assert set(data) == {'characters', 'csrfmiddlewaretoken'}
    data['characters'] = 'Ann[Bob]'
    response = client.post(url, data)

    assert response.status_code == 200
    html = ' '.join(response.content.decode().split())
    assert '1 item: 0 well-formed, 1 warning, 0 errors.' in html


@pytest.mark.django_db
def test_the_check_shows_the_findings(client, story_revision):
    """The view renders the counts, findings and "Read as", escaped."""
    client.force_login(story_revision.changeset.indexer)

    response = client.post(reverse('validate_characters'), {
      'characters': 'Ann; Batman[Bruce Wayne] (cameo); <b>Bob</b> (x'})

    html = response.content.decode()
    assert [template.name for template in response.templates] == \
        ['oi/bits/characters_check.html']
    assert ' '.join(html.split()) == (
      '<div class="w-full lg:w-4/5 border border-gray-400 rounded px-1 '
      'max-h-60 overflow-y-auto"> <div> 3 items: 1 well-formed, 1 warning, '
      '1 error. '
      '</div> <div class="my-1 bg-amber-50"> <div> <span class="font-bold">'
      '2</span> Batman[Bruce Wayne] (cameo) </div> <div> Warning, column 7: '
      'No space before &quot;[&quot;. </div> <div>Read as: Batman [Bruce '
      'Wayne] (cameo)</div> </div> <div class="my-1 bg-red-50"> <div> '
      '<span class="font-bold">3</span> &lt;b&gt;Bob&lt;/b&gt; (x </div> '
      '<div class="text-red-600"> Error, column 12: &quot;(&quot; is never '
      'closed. The text from here to the end is not read. </div> </div> '
      '</div>')


@pytest.mark.django_db
def test_an_empty_text(client, any_indexer):
    """An empty field gets a short message."""
    client.force_login(any_indexer)

    response = client.post(reverse('validate_characters'), {})

    assert 'No characters in the text.' in response.content.decode()


@pytest.mark.django_db
def test_nothing_is_saved(client, story_revision):
    """The check creates and changes nothing."""
    client.force_login(story_revision.changeset.indexer)
    counts = (Changeset.objects.count(), StoryRevision.objects.count())
    text = story_revision.characters

    client.post(reverse('validate_characters'),
                {'characters': 'Ann [Bob]', 'id': story_revision.id})

    assert (Changeset.objects.count(),
            StoryRevision.objects.count()) == counts
    story_revision.refresh_from_db()
    assert story_revision.characters == text


@pytest.mark.django_db
def test_only_through_the_form(client, any_indexer):
    """A GET is refused."""
    client.force_login(any_indexer)

    response = client.get(reverse('validate_characters'),
                          {'characters': 'Ann'})

    html = response.content.decode()
    assert 'This page may only be accessed through the proper form.' in html
    assert 'well-formed' not in html


@pytest.mark.django_db
def test_only_for_users_logged_in(client):
    """Without a login the box asks to log in again."""
    response = client.post(reverse('validate_characters'),
                           {'characters': 'Ann'})

    html = response.content.decode()
    assert response.status_code == 200
    assert 'Log in again to check the characters.' in html
    assert 'well-formed' not in html


@pytest.mark.django_db
@pytest.mark.parametrize('length, shown', [
  (20000, 'well-formed'),
  (20001, 'The text has 20001 characters; the check reads at most 20000.'),
])
def test_long_texts(client, any_indexer, length, shown):
    """Texts past the limit get a message instead of the check."""
    client.force_login(any_indexer)
    text = ('a; ' * length)[:length]

    response = client.post(reverse('validate_characters'),
                           {'characters': text})

    assert shown in ' '.join(response.content.decode().split())
