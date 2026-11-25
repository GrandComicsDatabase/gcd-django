# -*- coding: utf-8 -*-
"""The tabbed sequence form opens on the first tab with an error."""

import re

import pytest

from django.urls import reverse

from apps.oi.forms.story import get_story_revision_form
from apps.oi.models import CTYPES
from apps.oi.tests.test_trailing_semicolons import _post_data

FORMSETS = ('story_credit_revisions', 'story_character_revisions',
            'story_group_revisions')
BAD_ID = '999999'
BAD_CREDIT = {'story_credit_revisions-0-creator': BAD_ID}
BAD_CHARACTER = {'story_character_revisions-0-character': BAD_ID}
BAD_GROUP = {'story_group_revisions-0-group_name': BAD_ID}
# fields of the form itself on the first and the last tab
BAD_FIRST_TAB_FIELD = {'page_count': 'many'}
BAD_LAST_TAB_FIELD = {'universe': BAD_ID}


def _open_tabs(response):
    """The tab panes the server renders as the open ones."""
    return re.findall(
      r'<table id="([\w-]+)"\s+class="editing tab-pane active"',
      response.content.decode())


def _edit_page_data(revision, indexer, values):
    form_class = get_story_revision_form(revision=revision, user=indexer)
    data = _post_data(form_class(instance=revision))
    # the add form does not offer the additional genre of the fixture
    data.pop('genre')
    for prefix in FORMSETS:
        data[prefix + '-TOTAL_FORMS'] = '1'
        data[prefix + '-INITIAL_FORMS'] = '0'
    for name, value in values.items():
        data[name] = value
    data['save'] = 'Save And Continue Editing'
    return dict(data.lists())


@pytest.fixture
def indexer_client(client, any_indexer):
    any_indexer.is_superuser = True
    any_indexer.save()
    client.force_login(any_indexer)
    return client


@pytest.fixture
def story_revision(any_edit_story_rev):
    # the edit page of a sequence is that of a change to its issue
    changeset = any_edit_story_rev.changeset
    changeset.change_type = CTYPES['issue']
    changeset.save()
    return any_edit_story_rev


@pytest.mark.django_db
@pytest.mark.parametrize('bad_values, expected', [
    (BAD_CREDIT, 'creator-credits'),
    (BAD_CHARACTER, 'characters'),
    (BAD_GROUP, 'characters'),
    ({**BAD_CREDIT, **BAD_CHARACTER}, 'creator-credits'),
    ({**BAD_CREDIT, **BAD_LAST_TAB_FIELD}, 'creator-credits'),
    ({**BAD_CREDIT, **BAD_FIRST_TAB_FIELD}, 'sequence-details'),
    (BAD_FIRST_TAB_FIELD, 'sequence-details'),
    (BAD_LAST_TAB_FIELD, 'characters'),
])
def test_save_with_errors_opens_first_tab_with_error(
        indexer_client, any_indexer, story_revision, bad_values, expected):
    url = reverse('process_revision', kwargs={'model_name': 'story',
                                              'id': story_revision.id})
    response = indexer_client.post(
      url, _edit_page_data(story_revision, any_indexer, bad_values))

    assert response.status_code == 200
    assert _open_tabs(response) == [expected]


@pytest.mark.django_db
def test_add_sequence_with_errors_opens_first_tab_with_error(
        indexer_client, any_indexer, story_revision):
    changeset = story_revision.changeset
    url = reverse('add_story', kwargs={
      'issue_revision_id': changeset.issuerevisions.get().id,
      'changeset_id': changeset.id})
    response = indexer_client.post(
      url, _edit_page_data(story_revision, any_indexer, BAD_CREDIT))

    assert response.status_code == 200
    # only the message about the formset, no field of the form has an error
    assert list(response.context['form'].errors) == ['__all__']
    assert _open_tabs(response) == ['creator-credits']


@pytest.mark.django_db
def test_edit_page_without_errors_opens_first_tab(
        indexer_client, story_revision):
    url = reverse('edit_revision', kwargs={'model_name': 'story',
                                           'id': story_revision.id})
    response = indexer_client.get(url)

    assert response.status_code == 200
    assert _open_tabs(response) == ['sequence-details']
