# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the Feature filter set."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.api_v2.filters.features import FeatureFilterSet
from apps.gcd.models import Feature, FeatureNameDetail, FeatureType
from apps.stddata.models import Language

pytestmark = pytest.mark.django_db


def _create_feature(
    *,
    language,
    feature_type,
    name,
    genre='superhero',
    year_first_published=1950,
):
    """Create a minimal Feature row for filter tests."""
    return Feature.objects.create(
        name=name,
        sort_name=name,
        disambiguation='',
        genre=genre,
        language=language,
        feature_type=feature_type,
        year_first_published=year_first_published,
        notes='',
    )


def _set_timestamps(obj, *, created, modified):
    """Persist explicit created/modified timestamps for filter tests."""
    Feature.objects.filter(pk=obj.pk).update(
        created=created,
        modified=modified,
    )
    obj.refresh_from_db()


def test_feature_filter_matches_name_icontains(language):
    """The name filter uses case-insensitive containment."""
    feature_type = FeatureType.objects.create(name='Character')
    matching = _create_feature(
        language=language,
        feature_type=feature_type,
        name='Amazing Spider-Man',
    )
    _create_feature(
        language=language,
        feature_type=feature_type,
        name='Fantastic Four',
    )

    queryset = FeatureFilterSet(
        {'name': 'spider'},
        queryset=Feature.objects.all(),
    ).qs

    assert list(queryset) == [matching]


def test_feature_filter_matches_active_alternate_name(language):
    """The name filter finds active aliases without matching deleted ones."""
    feature_type = FeatureType.objects.create(name='Character')
    matching = _create_feature(
        language=language,
        feature_type=feature_type,
        name='Captain Marvel',
    )
    FeatureNameDetail.objects.create(
        feature=matching,
        name='Shazam',
        sort_name='Shazam',
        is_official_name=False,
    )
    deleted_alias = _create_feature(
        language=language,
        feature_type=feature_type,
        name='Different Feature',
    )
    FeatureNameDetail.objects.create(
        feature=deleted_alias,
        name='Shazam Family',
        sort_name='Shazam Family',
        is_official_name=False,
        deleted=True,
    )

    queryset = FeatureFilterSet(
        {'name': 'shazam'},
        queryset=Feature.objects.all(),
    ).qs

    assert list(queryset) == [matching]


def test_feature_filter_matches_type_language_genre_and_year(language):
    """Type, language, genre, and exact year filters narrow results."""
    character_type = FeatureType.objects.create(name='Character')
    location_type = FeatureType.objects.create(name='Location')
    other_language = Language.objects.create(
        code='yy',
        name='Other Language',
    )
    matching = _create_feature(
        language=language,
        feature_type=character_type,
        name='Matching Feature',
        genre='Science Fiction; Superhero',
        year_first_published=1960,
    )
    _create_feature(
        language=language,
        feature_type=location_type,
        name='Wrong Type',
        genre='Science Fiction; Superhero',
        year_first_published=1960,
    )
    _create_feature(
        language=other_language,
        feature_type=character_type,
        name='Wrong Language',
        genre='Science Fiction; Superhero',
        year_first_published=1960,
    )
    _create_feature(
        language=language,
        feature_type=character_type,
        name='Wrong Genre',
        genre='Western',
        year_first_published=1960,
    )

    queryset = FeatureFilterSet(
        {
            'feature_type': str(character_type.pk),
            'language': language.code,
            'genre': 'science fiction',
            'year_first_published': '1960',
        },
        queryset=Feature.objects.all(),
    ).qs

    assert list(queryset) == [matching]


def test_feature_filter_returns_none_for_unknown_language(language):
    """Unknown public language codes return an empty queryset."""
    feature_type = FeatureType.objects.create(name='Character')
    _create_feature(
        language=language,
        feature_type=feature_type,
        name='Known Language Feature',
    )

    queryset = FeatureFilterSet(
        {'language': 'not-a-code'},
        queryset=Feature.objects.all(),
    ).qs

    assert list(queryset) == []


def test_feature_filter_matches_modified_range(language):
    """Modified range filters support delta-style sync queries."""
    feature_type = FeatureType.objects.create(name='Character')
    older = _create_feature(
        language=language,
        feature_type=feature_type,
        name='Older Feature',
    )
    newer = _create_feature(
        language=language,
        feature_type=feature_type,
        name='Newer Feature',
    )
    now = timezone.now()
    _set_timestamps(
        older,
        created=now - timedelta(days=3),
        modified=now - timedelta(days=2),
    )
    _set_timestamps(
        newer,
        created=now - timedelta(days=1),
        modified=now - timedelta(hours=1),
    )

    queryset = FeatureFilterSet(
        {'modified__gt': (now - timedelta(days=1)).isoformat()},
        queryset=Feature.objects.all(),
    ).qs

    assert list(queryset) == [newer]


def test_feature_filter_matches_created_range(language):
    """Created range filters support bounded Feature queries."""
    feature_type = FeatureType.objects.create(name='Character')
    older = _create_feature(
        language=language,
        feature_type=feature_type,
        name='Older Feature',
    )
    newer = _create_feature(
        language=language,
        feature_type=feature_type,
        name='Newer Feature',
    )
    now = timezone.now()
    older_created = now - timedelta(days=3)
    newer_created = now - timedelta(hours=1)
    _set_timestamps(
        older,
        created=older_created,
        modified=older_created,
    )
    _set_timestamps(
        newer,
        created=newer_created,
        modified=newer_created,
    )

    queryset = FeatureFilterSet(
        {'created__lte': (now - timedelta(days=1)).isoformat()},
        queryset=Feature.objects.all(),
    ).qs

    assert list(queryset) == [older]
