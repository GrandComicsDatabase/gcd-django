# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the story filter set."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.api_v2.filters.stories import StoryFilterSet
from apps.gcd.models import Feature, FeatureType, Story, StoryType


def _create_story_type(name='Comic Story', sort_code=19):
    """Create or return a story type row for story tests."""
    story_type, _ = StoryType.objects.get_or_create(
        name=name,
        defaults={'sort_code': sort_code},
    )
    return story_type


def _create_issue(series, *, number, sort_code):
    """Create a minimal issue row for story filter tests."""
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
):
    """Create a minimal story row for filter tests."""
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
        genre=genre,
        characters='',
        synopsis='',
        reprint_notes='',
        notes='',
        issue=issue,
        type=story_type or _create_story_type(),
    )


def _create_feature(language, *, name, genre):
    """Create a feature row for linked-genre filter tests."""
    feature_type, _ = FeatureType.objects.get_or_create(name='Character')
    return Feature.objects.create(
        name=name,
        sort_name=name,
        disambiguation='',
        genre=genre,
        language=language,
        feature_type=feature_type,
        year_first_published=1939,
        notes='',
    )


def _set_timestamps(obj, *, created, modified):
    """Persist explicit created/modified timestamps for filter tests."""
    Story.objects.filter(pk=obj.pk).update(
        created=created,
        modified=modified,
    )
    obj.refresh_from_db()


def test_story_filter_matches_title_icontains(issue):
    """The title filter uses case-insensitive containment."""
    matching = _create_story(
        issue,
        title='The Case of the Missing API',
        sequence_number=1,
    )
    _create_story(
        issue,
        title='Backup Feature',
        sequence_number=2,
    )

    qs = StoryFilterSet(
        {'title': 'missing'},
        queryset=Story.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [matching]


def test_story_filter_matches_type_genre_issue_and_series(
    issue,
    publisher,
):
    """Exact story filters narrow list results correctly."""
    comic_story = _create_story_type('Comic Story', 19)
    text_story = _create_story_type('Text Story', 7)
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
    _create_story(
        issue,
        title='Western Story',
        sequence_number=3,
        story_type=comic_story,
        genre='western',
    )
    _create_story(
        other_issue,
        title='Other Series Story',
        sequence_number=1,
        story_type=comic_story,
        genre='superhero',
    )

    qs = StoryFilterSet(
        {
            'type': str(comic_story.pk),
            'genre': 'superhero',
            'issue': str(issue.pk),
            'issue__series': str(issue.series_id),
        },
        queryset=Story.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [matching]


def test_story_filter_matches_story_and_feature_genres(issue):
    """The genre filter checks story text and linked feature genres."""
    story_genre_match = _create_story(
        issue,
        title='Story Genre Match',
        sequence_number=1,
        genre='superhero',
    )
    feature_genre_match = _create_story(
        issue,
        title='Feature Genre Match',
        sequence_number=2,
        genre='',
    )
    feature_genre_match.feature_object.add(
        _create_feature(
            issue.series.language,
            name='Space Feature',
            genre='science fiction; superhero',
        ),
        _create_feature(
            issue.series.language,
            name='Mask Feature',
            genre='superhero',
        ),
    )
    _create_story(
        issue,
        title='Western Story',
        sequence_number=3,
        genre='western',
    )

    qs = StoryFilterSet(
        {'genre': 'superhero'},
        queryset=Story.objects.filter(deleted=False),
    ).qs.order_by('id')

    assert list(qs) == [story_genre_match, feature_genre_match]


def test_story_filter_matches_modified_range(issue):
    """Modified range filters support delta-style story sync queries."""
    older = _create_story(issue, title='Older Story', sequence_number=1)
    newer = _create_story(issue, title='Newer Story', sequence_number=2)
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

    qs = StoryFilterSet(
        {'modified__gt': (now - timedelta(days=1)).isoformat()},
        queryset=Story.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [newer]


def test_story_filter_matches_created_range(issue):
    """Created range filters support bounded story queries."""
    older = _create_story(issue, title='Older Story', sequence_number=1)
    newer = _create_story(issue, title='Newer Story', sequence_number=2)
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

    qs = StoryFilterSet(
        {'created__lte': (now - timedelta(days=1)).isoformat()},
        queryset=Story.objects.filter(deleted=False),
    ).qs

    assert list(qs) == [older]
