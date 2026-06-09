# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the story v2 endpoints."""

from decimal import Decimal

from django.urls import reverse
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.api_v2.views.stories import StoryViewSet
from apps.gcd.models import (
    CREDIT_TYPES,
    Character,
    CharacterNameDetail,
    CharacterRole,
    Creator,
    CreatorNameDetail,
    CreditType,
    Feature,
    FeatureLogo,
    FeatureType,
    Reprint,
    Story,
    StoryCharacter,
    StoryCredit,
    StoryType,
)
from apps.stddata.models import Script


def _create_script():
    """Return a Latin script row fit for name-detail fixtures."""
    obj, _ = Script.objects.get_or_create(
        id=Script.LATIN_PK,
        defaults={
            'number': 215,
            'name': 'Latin',
        },
    )
    return obj


def _create_story_type(name='Comic Story', sort_code=19):
    """Create or return a story type row for view tests."""
    story_type, _ = StoryType.objects.get_or_create(
        name=name,
        defaults={'sort_code': sort_code},
    )
    return story_type


def _create_issue(series, *, number, sort_code):
    """Create a minimal issue row for story view tests."""
    return series.issue_set.model.objects.create(
        number=number,
        title='',
        volume='',
        isbn='',
        valid_isbn='',
        variant_name='',
        barcode='',
        publication_date='',
        key_date='2024-01-01',
        on_sale_date='2024-01-08',
        sort_code=sort_code,
        indicia_frequency='',
        price='',
        editing='',
        notes='',
        indicia_printer_sourced_by='',
        series=series,
    )


def _create_story(
    issue,
    *,
    title,
    sequence_number,
    story_type=None,
    genre='superhero',
    deleted=False,
):
    """Create a story row for view tests."""
    return Story.objects.create(
        title=title,
        feature='Feature Text',
        sequence_number=sequence_number,
        page_count=Decimal('10.000'),
        script='Legacy Writer',
        pencils='',
        inks='',
        colors='',
        letters='',
        editing='',
        job_number='',
        genre=genre,
        characters='Legacy Character',
        synopsis='Story synopsis',
        first_line='First line',
        reprint_notes='',
        notes='Story notes',
        issue=issue,
        type=story_type or _create_story_type(),
        deleted=deleted,
    )


def _create_creator(name, sort_name):
    """Return a creator plus official name-detail row."""
    creator = Creator.objects.create(
        gcd_official_name=name,
        sort_name=sort_name,
        disambiguation='',
        birth_province='',
        birth_city='',
        death_province='',
        death_city='',
        bio='',
        notes='',
    )
    name_detail = CreatorNameDetail.objects.create(
        creator=creator,
        name=name,
        sort_name=sort_name,
        is_official_name=True,
        given_name='',
        family_name='',
        in_script=_create_script(),
    )
    return creator, name_detail


def _create_credit_type(name, sort_code):
    """Return a credit type with the canonical v2 test id."""
    credit_type, _ = CreditType.objects.update_or_create(
        id=CREDIT_TYPES[name],
        defaults={
            'name': name,
            'sort_code': sort_code,
        },
    )
    return credit_type


def _create_character(name, sort_name, language):
    """Return a character plus official name-detail row."""
    character = Character.objects.create(
        name=name,
        sort_name=sort_name,
        disambiguation='',
        year_first_published=1939,
        language=language,
        description='',
        notes='',
    )
    name_detail = CharacterNameDetail.objects.create(
        character=character,
        name=name,
        sort_name=sort_name,
        is_official_name=True,
    )
    return character, name_detail


def _add_story_detail_relations(story):
    """Attach nested detail rows to ``story`` and return expectations."""
    language = story.issue.series.language
    feature_type = FeatureType.objects.create(name='Character')
    feature = Feature.objects.create(
        name='Batman',
        sort_name='Batman',
        disambiguation='',
        genre='superhero',
        language=language,
        feature_type=feature_type,
        year_first_published=1939,
        notes='',
    )
    logo = FeatureLogo.objects.create(
        name='Bat Logo',
        sort_name='Bat Logo',
        generic=False,
        year_began=1940,
        year_ended=1945,
        notes='',
    )
    logo.feature.add(feature)
    story.feature_object.add(feature)
    story.feature_logo.add(logo)
    creator, creator_name = _create_creator('Writer One', 'Writer, One')
    script_type = _create_credit_type('script', 1)
    StoryCredit.objects.create(
        creator=creator_name,
        credit_type=script_type,
        story=story,
        signed_as='',
        credited_as='',
        sourced_by='',
        credit_name='',
    )
    character, character_name = _create_character(
        'Batman',
        'Batman',
        language,
    )
    role = CharacterRole.objects.create(name='cameo', sort_code=1)
    StoryCharacter.objects.create(
        character=character_name,
        story=story,
        role=role,
        notes='',
    )
    origin = _create_story(
        story.issue,
        title='Original Story',
        sequence_number=2,
    )
    target = _create_story(
        story.issue,
        title='Reprint Story',
        sequence_number=3,
    )
    Reprint.objects.create(
        origin=origin,
        target=story,
        origin_issue=origin.issue,
        target_issue=story.issue,
        notes='',
    )
    Reprint.objects.create(
        origin=story,
        target=target,
        origin_issue=story.issue,
        target_issue=target.issue,
        notes='',
    )
    story.keywords.add('alpha', 'beta')
    return feature, logo, creator, character, origin, target


def test_story_list_returns_paginated_results(api_client, issue):
    """The list endpoint is anon-readable and paginated."""
    story = _create_story(issue, title='Lead Story', sequence_number=1)

    response = api_client.get(reverse('story-list'))

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['next'] is None
    assert response.data['previous'] is None
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['id'] == story.pk
    assert response.data['results'][0]['type'] == {
        'id': story.type_id,
        'name': story.type.name,
    }
    assert response.data['results'][0]['issue'] == {
        'id': issue.pk,
        'descriptor': issue.issue_descriptor,
    }
    assert 'credits' not in response.data['results'][0]
    assert 'characters' not in response.data['results'][0]


def test_story_list_queryset_uses_id_based_issue_ordering():
    """The list queryset avoids the costly related-issue default sort."""
    assert StoryViewSet.queryset.query.order_by == (
        'issue_id',
        'sequence_number',
        'id',
    )


def test_story_list_queryset_uses_modified_ordering_for_delta_filters():
    """Modified delta requests switch to an index-friendly ordering."""
    view = StoryViewSet()
    request = APIRequestFactory().get(
        '/api/v2/stories/',
        {'modified__gt': '2025-01-01T00:00:00Z'},
    )
    view.request = Request(request)
    view.action = 'list'

    queryset = view.get_queryset()

    assert queryset.query.order_by == ('modified', 'id')


def test_story_list_skips_exact_count_for_modified_delta_filters():
    """Modified delta requests opt into no-count pagination."""
    view = StoryViewSet()
    request = APIRequestFactory().get(
        '/api/v2/stories/',
        {'modified__gt': '2025-01-01T00:00:00Z'},
    )

    assert view.should_skip_exact_count(Request(request)) is True


def test_story_detail_returns_expected_payload(api_client, issue):
    """The detail endpoint returns the story detail serializer payload."""
    story = _create_story(issue, title='Lead Story', sequence_number=1)
    feature, logo, creator, character, origin, target = (
        _add_story_detail_relations(story)
    )

    response = api_client.get(reverse('story-detail', kwargs={'pk': story.pk}))

    assert response.status_code == 200
    assert response.data['id'] == story.pk
    assert response.data['feature_object'] == [
        {
            'id': feature.pk,
            'name': 'Batman',
            'feature_type': {
                'id': feature.feature_type_id,
                'name': 'Character',
            },
        },
    ]
    assert response.data['feature_logo'] == [
        {
            'id': logo.pk,
            'name': 'Bat Logo',
            'year_began': 1940,
            'year_ended': 1945,
        },
    ]
    assert response.data['credits'] == [
        {
            'creator': {
                'id': creator.pk,
                'name': 'Writer One',
            },
            'role': 'script',
        },
    ]
    assert response.data['characters'] == [
        {
            'character': {
                'id': character.pk,
                'name': 'Batman',
            },
            'role': 'cameo',
        },
    ]
    assert response.data['keywords'] == ['alpha', 'beta']
    assert response.data['reprint_origins'] == [origin.pk]
    assert response.data['reprint_targets'] == [target.pk]


def test_story_list_applies_filter_query_params(api_client, issue, publisher):
    """The list endpoint applies django-filter query params."""
    comic_story = _create_story_type('Comic Story', 19)
    text_story = _create_story_type('Text Story', 7)
    matching = _create_story(
        issue,
        title='Lead Story',
        sequence_number=1,
        story_type=comic_story,
        genre='superhero',
    )
    _create_story(
        issue,
        title='Text Story',
        sequence_number=2,
        story_type=text_story,
        genre='superhero',
    )
    other_series = issue.series.__class__.objects.create(
        name='Other Series',
        sort_name='Other Series',
        year_began=1991,
        publication_dates='1991 - present',
        notes='',
        tracking_notes='',
        country=issue.series.country,
        language=issue.series.language,
        publisher=publisher,
    )
    other_issue = _create_issue(other_series, number='1', sort_code=1)
    _create_story(
        other_issue,
        title='Other Story',
        sequence_number=1,
        story_type=comic_story,
        genre='superhero',
    )

    response = api_client.get(
        reverse('story-list'),
        {
            'title': 'lead',
            'type': str(comic_story.pk),
            'genre': 'superhero',
            'issue': str(issue.pk),
            'issue__series': str(issue.series_id),
        },
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == matching.pk


def test_story_endpoints_hide_soft_deleted_records(api_client, issue):
    """Soft-deleted stories disappear from list and detail responses."""
    visible = _create_story(issue, title='Visible Story', sequence_number=1)
    deleted = _create_story(
        issue,
        title='Deleted Story',
        sequence_number=2,
        deleted=True,
    )

    list_response = api_client.get(reverse('story-list'))
    detail_response = api_client.get(
        reverse('story-detail', kwargs={'pk': deleted.pk}),
    )

    assert list_response.status_code == 200
    assert list_response.data['count'] == 1
    assert list_response.data['results'][0]['id'] == visible.pk
    assert detail_response.status_code == 404


def test_story_list_returns_304_for_if_modified_since(
    authenticated_client,
    issue,
):
    """List responses support Last-Modified cache validation."""
    _create_story(issue, title='Lead Story', sequence_number=1)

    response = authenticated_client.get(reverse('story-list'))

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('story-list'),
        HTTP_IF_MODIFIED_SINCE=response['Last-Modified'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''


def test_story_detail_returns_304_for_if_none_match(
    authenticated_client,
    issue,
):
    """Detail responses support ETag cache validation."""
    story = _create_story(issue, title='Lead Story', sequence_number=1)

    response = authenticated_client.get(
        reverse('story-detail', kwargs={'pk': story.pk}),
    )

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('story-detail', kwargs={'pk': story.pk}),
        HTTP_IF_NONE_MATCH=response['ETag'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''
