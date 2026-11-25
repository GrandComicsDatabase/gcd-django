# -*- coding: utf-8 -*-
"""The sequence types offered when adding a sequence to an issue."""

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.gcd.models import StoryType
from apps.oi import states
from apps.oi.forms.story import get_story_revision_form
from apps.oi.models import (
    CTYPES, Changeset, IssueRevision, RevisionLock, StoryRevision)


@pytest.fixture
def indexer_client(client, any_indexer):
    """Return a client of the indexer holding the changeset."""
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)
    return client


def reserve(issue, indexer):
    """Return a revision of the issue in a new open changeset."""
    changeset = Changeset(state=states.OPEN, indexer=indexer,
                          change_type=CTYPES['issue'])
    changeset.save()
    RevisionLock.objects.create(locked_object=issue, changeset=changeset)
    revision = IssueRevision.clone(data_object=issue, changeset=changeset)
    revision.save()
    return revision


def add_url(revision):
    """Return the address of the form adding a sequence to the revision."""
    return reverse('add_story',
                   kwargs={'issue_revision_id': revision.id,
                           'changeset_id': revision.changeset_id})


def offered_types(form):
    """Return the names of the sequence types the form offers."""
    return [story_type.name for story_type in form.fields['type'].queryset]


@pytest.mark.django_db
def test_approved_variant_offers_only_the_cover_type(
      indexer_client, any_indexer, any_added_variant):
    revision = reserve(any_added_variant, any_indexer)

    response = indexer_client.get(add_url(revision),
                                  {'added_sequence_number': '0'})

    assert response.status_code == 200
    assert offered_types(response.context['form']) == ['cover']


@pytest.mark.django_db
def test_approved_variant_refuses_another_type(
      indexer_client, any_indexer, any_added_variant):
    revision = reserve(any_added_variant, any_indexer)
    comic_story = StoryType.objects.get(name='comic story')

    response = indexer_client.post(add_url(revision),
                                   {'type': comic_story.id,
                                    'sequence_number': '0'})

    assert 'type' in response.context['form'].errors
    assert not StoryRevision.objects.filter(
      changeset=revision.changeset).exists()


@pytest.mark.django_db
def test_new_variant_offers_only_the_cover_type(
      any_indexer, any_added_variant_rev):
    form_class = get_story_revision_form(
      user=any_indexer, issue_revision=any_added_variant_rev)

    assert offered_types(form_class()) == ['cover']


@pytest.mark.django_db
def test_issue_which_is_no_variant_keeps_the_other_types(
      indexer_client, any_indexer, any_added_issue):
    revision = reserve(any_added_issue, any_indexer)

    response = indexer_client.get(add_url(revision),
                                  {'added_sequence_number': '1'})

    assert response.status_code == 200
    assert 'comic story' in offered_types(response.context['form'])
