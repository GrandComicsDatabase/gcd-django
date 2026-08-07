# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the Feature v2 endpoints."""

from django.urls import reverse

from apps.gcd.models import (
    Feature,
    FeatureLogo,
    FeatureRelation,
    FeatureRelationType,
    FeatureType,
)
from apps.stddata.models import Language


def _create_feature(
    *,
    language,
    feature_type,
    name='Test Feature',
    genre='superhero',
    year_first_published=1960,
    deleted=False,
):
    """Create a minimal Feature row for view tests."""
    return Feature.objects.create(
        name=name,
        sort_name=name,
        disambiguation='',
        genre=genre,
        language=language,
        feature_type=feature_type,
        year_first_published=year_first_published,
        notes='',
        deleted=deleted,
    )


def _create_logo(feature, *, name, deleted=False):
    """Create a Feature Logo attached to ``feature``."""
    logo = FeatureLogo.objects.create(
        name=name,
        sort_name=name,
        generic=False,
        year_began=1970,
        notes='',
        deleted=deleted,
    )
    logo.feature.add(feature)
    return logo


def test_feature_list_returns_paginated_results(api_client, language):
    """The list endpoint is anonymous, paginated, and trimmed."""
    feature_type = FeatureType.objects.create(name='Character')
    feature = _create_feature(
        language=language,
        feature_type=feature_type,
    )

    response = api_client.get(reverse('feature-list'))

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['next'] is None
    assert response.data['previous'] is None
    assert len(response.data['results']) == 1
    result = response.data['results'][0]
    assert result['id'] == feature.pk
    assert result['feature_type'] == {
        'id': feature_type.pk,
        'name': 'Character',
    }
    assert result['language'] == language.code
    assert 'notes' not in result
    assert 'keywords' not in result
    assert 'logos' not in result
    assert 'relations' not in result


def test_feature_detail_returns_normalized_relationships(
    authenticated_client,
    language,
):
    """The detail endpoint merges active relation directions explicitly."""
    character_type = FeatureType.objects.create(name='Character')
    relation_type = FeatureRelationType.objects.create(
        name='translation',
        description='is translated to',
        reverse_description='is translated from',
    )
    feature = _create_feature(
        language=language,
        feature_type=character_type,
    )
    feature.year_first_published_uncertain = True
    feature.notes = 'Detail notes'
    feature.save()
    feature.keywords.add('alpha', 'beta')
    logo = _create_logo(feature, name='Active Logo')
    _create_logo(feature, name='Deleted Logo', deleted=True)
    outgoing_target = _create_feature(
        language=language,
        feature_type=character_type,
        name='Outgoing Target',
    )
    incoming_source = _create_feature(
        language=language,
        feature_type=character_type,
        name='Incoming Source',
    )
    outgoing = FeatureRelation.objects.create(
        from_feature=feature,
        to_feature=outgoing_target,
        relation_type=relation_type,
        notes='Outgoing notes',
    )
    incoming = FeatureRelation.objects.create(
        from_feature=incoming_source,
        to_feature=feature,
        relation_type=relation_type,
        notes='Incoming notes',
    )

    response = authenticated_client.get(
        reverse('feature-detail', kwargs={'pk': feature.pk}),
    )

    assert response.status_code == 200
    assert response.data['id'] == feature.pk
    assert response.data['year_first_published_uncertain'] is True
    assert response.data['notes'] == 'Detail notes'
    assert set(response.data['keywords']) == {'alpha', 'beta'}
    assert [item['id'] for item in response.data['logos']] == [logo.pk]
    assert [item['id'] for item in response.data['relations']] == [
        outgoing.pk,
        incoming.pk,
    ]
    assert [item['direction'] for item in response.data['relations']] == [
        'outgoing',
        'incoming',
    ]
    assert [
        item['relation_type']['description']
        for item in response.data['relations']
    ] == [
        'is translated to',
        'is translated from',
    ]


def test_feature_list_applies_filter_query_params(
    authenticated_client,
    language,
):
    """The list endpoint applies the complete Feature filter contract."""
    character_type = FeatureType.objects.create(name='Character')
    location_type = FeatureType.objects.create(name='Location')
    other_language = Language.objects.create(
        code='yy',
        name='Other Language',
    )
    matching = _create_feature(
        language=language,
        feature_type=character_type,
        name='Amazing Spider-Man',
        genre='Science Fiction; Superhero',
        year_first_published=1960,
    )
    _create_feature(
        language=other_language,
        feature_type=location_type,
        name='Different Feature',
        genre='Western',
        year_first_published=1940,
    )

    response = authenticated_client.get(
        reverse('feature-list'),
        {
            'name': 'spider',
            'feature_type': str(character_type.pk),
            'language': language.code,
            'genre': 'science fiction',
            'year_first_published': '1960',
        },
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == matching.pk


def test_feature_endpoints_hide_soft_deleted_records(
    api_client,
    language,
):
    """Soft-deleted rows disappear from list and detail responses."""
    feature_type = FeatureType.objects.create(name='Character')
    visible = _create_feature(
        language=language,
        feature_type=feature_type,
        name='Visible Feature',
    )
    deleted = _create_feature(
        language=language,
        feature_type=feature_type,
        name='Deleted Feature',
        deleted=True,
    )

    list_response = api_client.get(reverse('feature-list'))
    detail_response = api_client.get(
        reverse('feature-detail', kwargs={'pk': deleted.pk}),
    )

    assert list_response.status_code == 200
    assert list_response.data['count'] == 1
    assert list_response.data['results'][0]['id'] == visible.pk
    assert detail_response.status_code == 404


def test_feature_list_returns_304_for_if_modified_since(
    authenticated_client,
    language,
):
    """List responses support Last-Modified cache validation."""
    feature_type = FeatureType.objects.create(name='Character')
    _create_feature(language=language, feature_type=feature_type)

    response = authenticated_client.get(reverse('feature-list'))

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('feature-list'),
        HTTP_IF_MODIFIED_SINCE=response['Last-Modified'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''


def test_feature_detail_returns_304_for_if_none_match(
    authenticated_client,
    language,
):
    """Detail responses support ETag cache validation."""
    feature_type = FeatureType.objects.create(name='Character')
    feature = _create_feature(
        language=language,
        feature_type=feature_type,
    )

    response = authenticated_client.get(
        reverse('feature-detail', kwargs={'pk': feature.pk}),
    )

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('feature-detail', kwargs={'pk': feature.pk}),
        HTTP_IF_NONE_MATCH=response['ETag'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''
