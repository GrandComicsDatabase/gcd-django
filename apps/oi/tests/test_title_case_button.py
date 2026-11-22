# -*- coding: utf-8 -*-
"""A button puts the title of a sequence or an issue in title case."""

import re

import pytest

from django.urls import reverse

from apps.oi.models import CTYPES
from apps.stddata.models import Language


@pytest.fixture
def indexer_client(client, any_indexer):
    """A logged in indexer with superuser rights."""
    any_indexer.is_superuser = True
    any_indexer.save()
    client.force_login(any_indexer)
    return client


def _edit_page(client, story_revision, model_name):
    """Return the edit page and the label of its title field."""
    # the edit page of a sequence is that of a change to its issue
    changeset = story_revision.changeset
    changeset.change_type = CTYPES['issue']
    changeset.save()
    revision = {'story': story_revision,
                'issue': changeset.issuerevisions.get()}[model_name]
    url = reverse('edit_revision', kwargs={'model_name': model_name,
                                           'id': revision.id})
    response = client.get(url)

    assert response.status_code == 200
    page = response.content.decode()
    label = re.search(r'<label for="id_title"[^>]*>(.*?)</label>', page,
                      re.S)
    assert label
    return page, label.group(1)


@pytest.mark.django_db
@pytest.mark.parametrize('model_name', ['story', 'issue'])
def test_title_has_title_case_button(indexer_client, any_edit_story_rev,
                                     model_name):
    """The title of a series in English has the button."""
    series = any_edit_story_rev.issue.series
    series.language = Language.objects.get_or_create(
      code='en', defaults={'name': 'English'})[0]
    series.save()
    # both forms read the language from this series
    assert any_edit_story_rev.changeset.issuerevisions.get().series == series

    page, label = _edit_page(indexer_client, any_edit_story_rev, model_name)

    # the button sits in the label and changes the field of the label
    assert re.search(
      r'<button type="button" [^>]*onclick="[^"]*'
      r'this\.parentElement\.control[^"]*toTitleCase\(', label)
    # the rule of the button comes from a static script
    assert 'src="/static/js/oi/title_case.js"' in page


@pytest.mark.django_db
@pytest.mark.parametrize('model_name', ['story', 'issue'])
def test_title_has_no_button_in_another_language(
        indexer_client, any_edit_story_rev, model_name):
    """The button knows only the English rules."""
    assert any_edit_story_rev.issue.series.language.code != 'en'

    _, label = _edit_page(indexer_client, any_edit_story_rev, model_name)

    assert '<button' not in label
    assert label.strip().startswith('Title')
