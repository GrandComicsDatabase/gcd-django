# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Performance tests for Feature endpoints."""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import (
    Feature,
    FeatureLogo,
    FeatureNameDetail,
    FeatureRelation,
    FeatureRelationType,
    FeatureType,
)


def _create_feature(*, language, feature_type, name):
    """Create a minimal Feature row for performance tests."""
    return Feature.objects.create(
        name=name,
        sort_name=name,
        disambiguation='',
        genre='superhero',
        language=language,
        feature_type=feature_type,
        year_first_published=1950,
        notes='',
    )


def _create_relationships(feature, *, language, feature_type, count):
    """Attach logos plus incoming and outgoing relations to ``feature``."""
    feature_name = FeatureNameDetail.objects.create(
        feature=feature,
        name=feature.name,
        sort_name=feature.sort_name,
        is_official_name=True,
    )
    relation_type = FeatureRelationType.objects.create(
        name='alternate_version',
        description='is an alternate version of',
        reverse_description='has alternate version',
    )
    for number in range(count):
        logo = FeatureLogo.objects.create(
            name=f'Logo {number:03d}',
            sort_name=f'Logo {number:03d}',
            notes='',
        )
        logo.feature_name.add(feature_name)
        outgoing_target = _create_feature(
            language=language,
            feature_type=feature_type,
            name=f'Outgoing {number:03d}',
        )
        incoming_source = _create_feature(
            language=language,
            feature_type=feature_type,
            name=f'Incoming {number:03d}',
        )
        FeatureRelation.objects.create(
            from_feature=feature,
            to_feature=outgoing_target,
            relation_type=relation_type,
            notes='',
        )
        FeatureRelation.objects.create(
            from_feature=incoming_source,
            to_feature=feature,
            relation_type=relation_type,
            notes='',
        )


def test_feature_list_query_count(api_client, language):
    """The Feature list stays on its query budget."""
    feature_type = FeatureType.objects.create(name='Character')
    _create_feature(
        language=language,
        feature_type=feature_type,
        name='Alpha Feature',
    )
    _create_feature(
        language=language,
        feature_type=feature_type,
        name='Beta Feature',
    )

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(reverse('feature-list'))

    assert response.status_code == 200
    assert len(context) == 3


def test_feature_detail_query_count_is_relationship_count_independent(
    api_client,
    language,
):
    """Detail serialization uses bounded logo and relation prefetches."""
    feature_type = FeatureType.objects.create(name='Character')
    feature = _create_feature(
        language=language,
        feature_type=feature_type,
        name='Detail Feature',
    )
    feature.keywords.add('detail')
    _create_relationships(
        feature,
        language=language,
        feature_type=feature_type,
        count=8,
    )

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(
            reverse('feature-detail', kwargs={'pk': feature.pk}),
        )

    assert response.status_code == 200
    assert len(response.data['logos']) == 8
    assert len(response.data['relations']) == 16
    assert len(context) == 7
