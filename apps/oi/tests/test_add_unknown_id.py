# -*- coding: utf-8 -*-
"""Tests of the error pages for an id that does not exist."""

import pytest
from django.urls import reverse


@pytest.fixture
def logged_in(client, any_indexer):
    """A client logged in as an indexer who can reserve."""
    any_indexer.is_superuser = True
    any_indexer.save()
    any_indexer.indexer.max_reservations = 10
    any_indexer.indexer.save()
    client.force_login(any_indexer)
    return client


@pytest.mark.django_db
def test_add_series_to_an_unknown_publisher(logged_in):
    """Adding a series to a publisher that does not exist shows an error."""
    response = logged_in.get(reverse('add_series',
                                     kwargs={'publisher_id': 999999}),
                             follow=True)

    assert 'Could not find publisher for id 999999' in \
        response.content.decode()


@pytest.mark.django_db
def test_add_sequence_to_an_unknown_issue_revision(logged_in,
                                                   any_editing_changeset):
    """Adding a sequence to a revision not in the change shows an error."""
    response = logged_in.get(
      reverse('add_story', kwargs={'issue_revision_id': 999999,
                                   'changeset_id': any_editing_changeset.id}),
      follow=True)

    assert 'Could not find issue revision for id 999999' in \
        response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize('button', ['copy', 'copy_cover'])
def test_copy_sequence_to_an_unknown_issue_revision(logged_in,
                                                    any_editing_changeset,
                                                    button):
    """The copy buttons with a revision not in the change find nothing."""
    response = logged_in.get(
      reverse('add_story', kwargs={'issue_revision_id': 999999,
                                   'changeset_id': any_editing_changeset.id}),
      {button: '1', 'added_sequence_number': '1'})

    assert response.status_code == 404
