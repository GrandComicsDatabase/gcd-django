# -*- coding: utf-8 -*-
"""Tests of the selector page of reprint links and series bonds."""

import re

import pytest

from django.contrib.auth.models import Permission
from django.urls import resolve, reverse

pytestmark = pytest.mark.django_db


def log_in(client, changeset):
    """Log in the indexer of the changeset, with the right to edit."""
    indexer = changeset.indexer
    indexer.user_permissions.add(Permission.objects.get(
      content_type__app_label='indexer', codename='can_reserve'))
    client.force_login(indexer)


def selector_page(client, response):
    """Follow the redirect to the selector and return the html of its page."""
    select_key = resolve(response.url).kwargs['select_key']
    return client.get(reverse('select_object',
                              kwargs={'select_key': select_key})
                      ).content.decode()


def note_page(client, revision, note):
    """Follow Add Reprint from a reprint note and return the page."""
    log_in(client, revision.changeset)
    return selector_page(client, client.get(reverse(
      'add_story_reprint',
      kwargs={'story_id': revision.id, 'changeset_id': revision.changeset_id,
              'reprint_note': note})))


def test_reprint_note_is_shown_after_the_heading(client, any_edit_story_rev):
    """A paragraph inside the h2 is no valid html, and it reads as a title."""
    note = 'from Tom & Jerry (Dell, 1948 series) #1'
    html = note_page(client, any_edit_story_rev, note)
    heading = re.search(r'<h2>(.*?)</h2>', html, re.DOTALL).group(1)
    assert 'Reprint note' not in heading
    assert html.count('Reprint note:') == 1
    assert re.search(r'</h2>\s*<p>Reprint note: from Tom &amp; Jerry '
                     r'\(Dell, 1948 series\) #1</p>', html)
