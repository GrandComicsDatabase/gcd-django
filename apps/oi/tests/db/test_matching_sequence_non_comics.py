# -*- coding: utf-8 -*-
"""Which sequence types a reprint link may add to a non-comics issue."""

import pytest
from django.contrib.auth.models import Permission
from django.utils.html import escape

from apps.gcd.models import INDEXED, Issue, Series, StoryType
from apps.oi.models import ReprintRevision
from apps.oi.tests.db.test_matching_sequence_variant import (
    ROUTES, add_approved_cover, added_sequences, assert_refused,
    confirm_new_link, link_to_issue, request_sequence, reserve)

REFUSED = ('Sequences of type "%s" cannot be added to this issue of a '
           'non-comics publication.')


@pytest.fixture
def non_comics(client, any_indexer, any_added_story, any_added_variant):
    """
    Log the indexer in and return an issue of a non-comics series; the
    sequence any_added_story is moved to another issue to link it.
    """
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)
    issue = Issue.objects.get(pk=any_added_variant.variant_of_id)
    Series.objects.filter(pk=issue.series_id).update(
      is_comics_publication=False)
    any_added_story.issue = any_added_variant
    any_added_story.save()
    return issue


def ask_for_copy(client, indexer, story, issue, type_name, route='create'):
    """Give the story the type, link it to the issue and ask for a copy."""
    story.type = StoryType.objects.get(name=type_name)
    story.save()
    changeset = reserve(issue, indexer)
    reprint = link_to_issue(story, issue, changeset)
    response = request_sequence(client, route, reprint, story, issue)
    return response, changeset, reprint


def set_about_comics(issue, has_about_comics, indexed):
    """Set the about comics flag of the series and the index status."""
    Series.objects.filter(pk=issue.series_id).update(
      has_about_comics=has_about_comics)
    Issue.objects.filter(pk=issue.pk).update(is_indexed=INDEXED[indexed])


@pytest.mark.django_db
@pytest.mark.parametrize('route', ROUTES)
def test_non_comics_issue_refuses_a_type_its_form_does_not_offer(
      client, any_indexer, any_added_story, non_comics, route):
    response, changeset, reprint = ask_for_copy(
      client, any_indexer, any_added_story, non_comics, 'text story', route)

    assert_refused(response, escape(REFUSED % 'text story'), changeset,
                   reprint, True)


@pytest.mark.django_db
@pytest.mark.parametrize('about_comics, indexed, type_name', [
    (False, 'full', 'cover'),
    (True, 'partial', 'cover'),
    (True, 'ten_percent', 'illustration')])
def test_non_comics_issue_refuses_a_type_offered_elsewhere(
      client, any_indexer, any_added_story, non_comics, about_comics,
      indexed, type_name):
    set_about_comics(non_comics, about_comics, indexed)

    response, changeset, reprint = ask_for_copy(
      client, any_indexer, any_added_story, non_comics, type_name)

    assert_refused(response, escape(REFUSED % type_name), changeset,
                   reprint, True)


@pytest.mark.django_db
@pytest.mark.parametrize('about_comics, indexed, type_name', [
    (False, 'skeleton', 'comic story'),
    (True, 'ten_percent', 'cover'),
    (True, 'full', 'illustration')])
def test_non_comics_issue_takes_a_type_its_form_offers(
      client, any_indexer, any_added_story, non_comics, about_comics,
      indexed, type_name):
    set_about_comics(non_comics, about_comics, indexed)

    response, changeset, _ = ask_for_copy(
      client, any_indexer, any_added_story, non_comics, type_name)

    assert response.status_code == 302
    assert added_sequences(changeset).get().type.name == type_name


@pytest.mark.django_db
def test_cover_for_a_non_comics_issue_with_a_cover_comes_as_a_reprint(
      client, any_indexer, any_added_story, story_add_values, non_comics):
    add_approved_cover(non_comics, any_indexer, story_add_values)

    response, changeset, _ = ask_for_copy(
      client, any_indexer, any_added_story, non_comics, 'cover')

    assert response.status_code == 302
    assert added_sequences(changeset).get().type.name == \
        'cover reprint (on interior page)'


@pytest.mark.django_db
def test_refused_type_leaves_a_new_link_unsaved(
      client, any_indexer, any_added_story, non_comics):
    any_added_story.type = StoryType.objects.get(name='text story')
    any_added_story.save()
    changeset = reserve(non_comics, any_indexer)

    response = confirm_new_link(client, 'matching_sequence', changeset,
                                any_added_story, non_comics)

    assert response.status_code == 200
    assert escape(REFUSED % 'text story') in response.content.decode()
    assert not ReprintRevision.objects.filter(changeset=changeset).exists()
