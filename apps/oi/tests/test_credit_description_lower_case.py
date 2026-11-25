# -*- coding: utf-8 -*-
"""A button puts the description of a credit in lower case."""

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
@pytest.mark.parametrize('model_name, prefix', [
    ('story', 'story_credit_revisions'),
    ('issue', 'issue_credit_revisions'),
])
def test_credit_description_has_lower_case_button(
        indexer_client, any_edit_story_rev, model_name, prefix):
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
    label = re.search(
      r'<label for="id_%s-0-credit_name"[^>]*>(.*?)</label>' % prefix,
      response.content.decode(), re.S)
    # the button sits in the label and changes the field of the label
    assert label and re.search(
      r'<button type="button" [^>]*onclick="[^"]*'
      r'this\.parentElement\.control[^"]*toLowerCase\(\)', label.group(1))
