# -*- coding: utf-8 -*-
"""A button puts the title of a sequence or an issue in title case."""

import re

import pytest

from django.urls import reverse

from apps.oi.models import CTYPES


@pytest.fixture
def indexer_client(client, any_indexer):
    any_indexer.is_superuser = True
    any_indexer.save()
    client.force_login(any_indexer)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize('model_name', ['story', 'issue'])
def test_title_has_title_case_button(indexer_client, any_edit_story_rev,
                                     model_name):
    # the edit page of a sequence is that of a change to its issue
    changeset = any_edit_story_rev.changeset
    changeset.change_type = CTYPES['issue']
    changeset.save()
    revision = {'story': any_edit_story_rev,
                'issue': changeset.issuerevisions.get()}[model_name]
    url = reverse('edit_revision', kwargs={'model_name': model_name,
                                           'id': revision.id})
    response = indexer_client.get(url)

    assert response.status_code == 200
    page = response.content.decode()
    label = re.search(r'<label for="id_title"[^>]*>(.*?)</label>', page,
                      re.S)
    # the button sits in the label and changes the field of the label
    assert label and re.search(
      r'<button type="button" [^>]*onclick="[^"]*'
      r'this\.parentElement\.control[^"]*toTitleCase\(', label.group(1))
    # the rule of the button comes from a static script
    assert 'src="/static/js/oi/title_case.js"' in page
