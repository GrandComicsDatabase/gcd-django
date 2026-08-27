# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the Feature serializers."""

import pytest

from apps.api_v2.serializers.features import (
    FeatureListSerializer,
    FeatureSerializer,
)
from apps.gcd.models import (
    Feature,
    FeatureLogo,
    FeatureNameDetail,
    FeatureRelation,
    FeatureRelationType,
    FeatureType,
)

pytestmark = pytest.mark.django_db


def _create_feature(
    *,
    language,
    feature_type,
    name,
    sort_name=None,
    deleted=False,
):
    """Create a Feature with complete root contract data."""
    return Feature.objects.create(
        name=name,
        sort_name=sort_name or name,
        disambiguation='Earth-Prime',
        genre='Science Fiction; Superhero',
        language=language,
        feature_type=feature_type,
        year_first_published=1960,
        year_first_published_uncertain=True,
        description='Feature description',
        notes='Feature notes',
        deleted=deleted,
    )


def _create_logo(
    feature,
    *,
    name,
    sort_name,
    generic=False,
    deleted=False,
):
    """Create a Feature Logo attached to ``feature``."""
    logo = FeatureLogo.objects.create(
        name=name,
        sort_name=sort_name,
        generic=generic,
        year_began=1970,
        year_ended=1980,
        year_began_uncertain=True,
        year_ended_uncertain=False,
        notes='',
        deleted=deleted,
    )
    feature_name, _ = FeatureNameDetail.objects.get_or_create(
        feature=feature,
        name=feature.name,
        defaults={
            'sort_name': feature.sort_name,
            'is_official_name': True,
        },
    )
    logo.feature_name.add(feature_name)
    return logo


def test_feature_list_serializer_exposes_trimmed_contract(language):
    """List rows include identity, classification, and timestamps."""
    feature_type = FeatureType.objects.create(name='Character')
    feature = _create_feature(
        language=language,
        feature_type=feature_type,
        name='Test Feature',
        sort_name='Feature, Test',
    )

    data = FeatureListSerializer(feature).data

    assert set(data) == {
        'id',
        'name',
        'sort_name',
        'disambiguation',
        'feature_type',
        'language',
        'genre',
        'year_first_published',
        'created',
        'modified',
    }
    assert data['id'] == feature.pk
    assert data['name'] == 'Test Feature'
    assert data['sort_name'] == 'Feature, Test'
    assert data['disambiguation'] == 'Earth-Prime'
    assert data['feature_type'] == {
        'id': feature_type.pk,
        'name': 'Character',
    }
    assert data['language'] == language.code
    assert data['genre'] == 'Science Fiction; Superhero'
    assert data['year_first_published'] == 1960
    assert data['created']
    assert data['modified']


def test_feature_detail_serializer_normalizes_active_relationships(language):
    """Detail rows normalize active logos and both relation directions."""
    character_type = FeatureType.objects.create(name='Character')
    location_type = FeatureType.objects.create(name='Location')
    relation_type = FeatureRelationType.objects.create(
        name='alternate_version',
        description='is an alternate version of',
        reverse_description='has alternate version',
    )
    feature = _create_feature(
        language=language,
        feature_type=character_type,
        name='Main Feature',
    )
    feature.keywords.add('alpha', 'beta')
    official_name = FeatureNameDetail.objects.create(
        feature=feature,
        name='Main Feature',
        sort_name='Feature, Main',
        is_official_name=True,
    )
    alternate_name = FeatureNameDetail.objects.create(
        feature=feature,
        name='Alternate Feature',
        sort_name='Feature, Alternate',
        is_official_name=False,
    )
    beta_logo = _create_logo(
        feature,
        name='Beta Logo',
        sort_name='Beta Logo',
        generic=True,
    )
    alpha_logo = _create_logo(
        feature,
        name='Alpha Logo',
        sort_name='Alpha Logo',
    )
    alpha_logo.feature_name.add(official_name)
    beta_logo.feature_name.add(alternate_name)
    _create_logo(
        feature,
        name='Deleted Logo',
        sort_name='Deleted Logo',
        deleted=True,
    )
    outgoing_target = _create_feature(
        language=language,
        feature_type=location_type,
        name='Outgoing Target',
        sort_name='Target, Outgoing',
    )
    incoming_source = _create_feature(
        language=language,
        feature_type=character_type,
        name='Incoming Source',
        sort_name='Source, Incoming',
    )
    deleted_target = _create_feature(
        language=language,
        feature_type=location_type,
        name='Deleted Target',
        deleted=True,
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
    FeatureRelation.objects.create(
        from_feature=feature,
        to_feature=deleted_target,
        relation_type=relation_type,
        notes='Deleted target notes',
    )

    data = FeatureSerializer(feature).data

    assert set(data) == {
        'id',
        'name',
        'sort_name',
        'disambiguation',
        'feature_type',
        'language',
        'genre',
        'year_first_published',
        'created',
        'modified',
        'year_first_published_uncertain',
        'description',
        'notes',
        'name_details',
        'keywords',
        'logos',
        'relations',
    }
    assert data['year_first_published_uncertain'] is True
    assert data['description'] == 'Feature description'
    assert data['notes'] == 'Feature notes'
    assert data['name_details'] == [
        {
            'id': alternate_name.pk,
            'name': 'Alternate Feature',
            'sort_name': 'Feature, Alternate',
            'is_official_name': False,
        },
        {
            'id': official_name.pk,
            'name': 'Main Feature',
            'sort_name': 'Feature, Main',
            'is_official_name': True,
        },
    ]
    assert set(data['keywords']) == {'alpha', 'beta'}
    assert data['logos'] == [
        {
            'id': alpha_logo.pk,
            'name': 'Alpha Logo',
            'generic': False,
            'year_began': 1970,
            'year_ended': 1980,
            'year_began_uncertain': True,
            'year_ended_uncertain': False,
        },
        {
            'id': beta_logo.pk,
            'name': 'Beta Logo',
            'generic': True,
            'year_began': 1970,
            'year_ended': 1980,
            'year_began_uncertain': True,
            'year_ended_uncertain': False,
        },
    ]
    assert data['relations'] == [
        {
            'id': outgoing.pk,
            'direction': 'outgoing',
            'relation_type': {
                'id': relation_type.pk,
                'name': 'alternate_version',
                'description': 'is an alternate version of',
            },
            'feature': {
                'id': outgoing_target.pk,
                'name': 'Outgoing Target',
                'disambiguation': 'Earth-Prime',
                'feature_type': {
                    'id': location_type.pk,
                    'name': 'Location',
                },
            },
            'notes': 'Outgoing notes',
        },
        {
            'id': incoming.pk,
            'direction': 'incoming',
            'relation_type': {
                'id': relation_type.pk,
                'name': 'alternate_version',
                'description': 'has alternate version',
            },
            'feature': {
                'id': incoming_source.pk,
                'name': 'Incoming Source',
                'disambiguation': 'Earth-Prime',
                'feature_type': {
                    'id': character_type.pk,
                    'name': 'Character',
                },
            },
            'notes': 'Incoming notes',
        },
    ]
