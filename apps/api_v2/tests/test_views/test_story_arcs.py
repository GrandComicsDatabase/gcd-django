# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the story-arc v2 endpoints."""

from decimal import Decimal

from django.urls import reverse

from apps.gcd.models import Story, StoryArc, StoryType


def _create_story_arc(
    language,
    *,
    name='Crisis on Infinite Earths',
    year_first_published=1986,
    deleted=False,
):
    """Create a story arc row for view tests."""
    return StoryArc.objects.create(
        name=name,
        sort_name=name,
        disambiguation='',
        language=language,
        year_first_published=year_first_published,
        description='Story arc description',
        notes='Story arc notes',
        deleted=deleted,
    )


def _create_story_type(name='Comic Story', sort_code=19):
    """Create or return a story type row for story-arc tests."""
    story_type, _ = StoryType.objects.get_or_create(
        name=name,
        defaults={'sort_code': sort_code},
    )
    return story_type


def _create_story(issue, *, title, sequence_number):
    """Create a story row for view tests."""
    return Story.objects.create(
        title=title,
        feature='Feature Text',
        sequence_number=sequence_number,
        page_count=Decimal('10.000'),
        script='',
        pencils='',
        inks='',
        colors='',
        letters='',
        editing='',
        job_number='',
        genre='',
        characters='',
        synopsis='',
        reprint_notes='',
        notes='',
        issue=issue,
        type=_create_story_type(),
    )


def test_story_arc_list_returns_paginated_results(api_client, language):
    """The list endpoint is anon-readable and paginated."""
    story_arc = _create_story_arc(language)

    response = api_client.get(reverse('story-arc-list'))

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['next'] is None
    assert response.data['previous'] is None
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['id'] == story_arc.pk
    assert response.data['results'][0]['name'] == 'Crisis on Infinite Earths'
    assert 'stories' not in response.data['results'][0]


def test_story_arc_detail_returns_expected_payload(
    api_client,
    issue,
    language,
):
    """The detail endpoint returns the story-arc detail payload."""
    story_arc = _create_story_arc(language)
    story = _create_story(issue, title='First Story', sequence_number=1)
    story.story_arc.add(story_arc)

    response = api_client.get(
        reverse('story-arc-detail', kwargs={'pk': story_arc.pk}),
    )

    assert response.status_code == 200
    assert response.data['id'] == story_arc.pk
    assert response.data['name'] == 'Crisis on Infinite Earths'
    assert response.data['notes'] == 'Story arc notes'
    assert response.data['stories'] == [
        {
            'id': story.pk,
            'title': 'First Story',
            'issue': {
                'id': issue.pk,
                'descriptor': issue.issue_descriptor,
            },
            'sequence_number': 1,
        },
    ]
    assert response.data['keywords'] == []


def test_story_arc_list_applies_filter_query_params(
    api_client,
    language,
):
    """The list endpoint applies django-filter query params."""
    matching = _create_story_arc(language, name='Crisis on Infinite Earths')
    _create_story_arc(language, name='Secret Wars')

    response = api_client.get(
        reverse('story-arc-list'),
        {'name': 'crisis'},
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == matching.pk


def test_story_arc_endpoints_hide_soft_deleted_records(
    api_client,
    language,
):
    """Soft-deleted story arcs disappear from list and detail responses."""
    visible = _create_story_arc(language, name='Visible Arc')
    deleted = _create_story_arc(
        language,
        name='Deleted Arc',
        deleted=True,
    )

    list_response = api_client.get(reverse('story-arc-list'))
    detail_response = api_client.get(
        reverse('story-arc-detail', kwargs={'pk': deleted.pk}),
    )

    assert list_response.status_code == 200
    assert list_response.data['count'] == 1
    assert list_response.data['results'][0]['id'] == visible.pk
    assert detail_response.status_code == 404


def test_story_arc_list_returns_304_for_if_modified_since(
    authenticated_client,
    language,
):
    """List responses support Last-Modified cache validation."""
    _create_story_arc(language)

    response = authenticated_client.get(reverse('story-arc-list'))

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('story-arc-list'),
        HTTP_IF_MODIFIED_SINCE=response['Last-Modified'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''


def test_story_arc_detail_returns_304_for_if_none_match(
    authenticated_client,
    language,
):
    """Detail responses support ETag cache validation."""
    story_arc = _create_story_arc(language)

    response = authenticated_client.get(
        reverse('story-arc-detail', kwargs={'pk': story_arc.pk}),
    )

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('story-arc-detail', kwargs={'pk': story_arc.pk}),
        HTTP_IF_NONE_MATCH=response['ETag'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''
