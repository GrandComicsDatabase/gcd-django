# -*- coding: utf-8 -*-
"""Tests of the groups in the form to add a sequence, through the view."""

import pytest

from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.gcd.models import Group, GroupNameDetail, StoryType

GROUPS = 'story_group_revisions'


@pytest.fixture
def add_url(client, any_edit_story_rev):
    """Log in the holder of the reservation and return the URL of the form."""
    changeset = any_edit_story_rev.changeset
    changeset.indexer.user_permissions.add(Permission.objects.get(
      content_type__app_label='indexer', codename='can_reserve'))
    client.force_login(changeset.indexer)
    return reverse('add_story',
                   kwargs={'issue_revision_id':
                           changeset.issuerevisions.get().id,
                           'changeset_id': changeset.id})


def post_data(**group):
    """Return a valid sequence with one row of groups holding the values."""
    data = {'sequence_number': '2',
            'language_code': 'XZZ',
            'type': StoryType.objects.get(name='comic story').id,
            'title': 'New Sequence',
            'page_count': '8',
            'script': 'Writer',
            'pencils': 'Penciller',
            'inks': 'Inker',
            'no_colors': 'on',
            'letters': 'Letterer',
            'no_editing': 'on',
            GROUPS + '-TOTAL_FORMS': '1',
            GROUPS + '-INITIAL_FORMS': '0'}
    for prefix in ('story_credit_revisions', 'story_character_revisions'):
        data[prefix + '-TOTAL_FORMS'] = '0'
        data[prefix + '-INITIAL_FORMS'] = '0'
    data.update({'%s-0-%s' % (GROUPS, k): v for k, v in group.items()})
    return data


@pytest.mark.django_db
@pytest.mark.parametrize('group, error', [
  ({'notes': 'A note without a group'}, 'This field is required.'),
  ({'group_name': '999999'}, 'Select a valid choice.'),
])
def test_invalid_group_shows_the_form_again(client, add_url,
                                            any_edit_story_rev, group, error):
    response = client.post(add_url, post_data(**group))

    assert response.status_code == 200
    assert 'group_name' in response.context['groups_formset'].errors[0]
    html = response.content.decode()
    assert error in html
    assert 'Changes needed on the Characters tab.' in html
    assert any_edit_story_rev.changeset.storyrevisions.count() == 1


@pytest.mark.django_db
def test_empty_row_of_groups_is_ignored(client, add_url, any_edit_story_rev):
    response = client.post(add_url, post_data())

    assert response.status_code == 302
    added = any_edit_story_rev.changeset.storyrevisions.get(
      title='New Sequence')
    assert not added.story_group_revisions.exists()


@pytest.mark.django_db
def test_valid_group_is_saved(client, add_url, any_edit_story_rev,
                              any_language):
    group_name = GroupNameDetail.objects.create(
      name='Test Group', is_official_name=True,
      group=Group.objects.create(name='Test Group', disambiguation='',
                                 language=any_language, description='',
                                 notes=''))

    response = client.post(add_url, post_data(group_name=group_name.id))

    assert response.status_code == 302
    added = any_edit_story_rev.changeset.storyrevisions.get(
      title='New Sequence')
    assert added.story_group_revisions.get().group_name == group_name
