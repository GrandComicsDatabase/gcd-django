# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Performance tests for story endpoints."""

from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

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
    """Create or return a story type row for performance tests."""
    story_type, _ = StoryType.objects.get_or_create(
        name=name,
        defaults={'sort_code': sort_code},
    )
    return story_type


def _create_story(issue, *, title, sequence_number):
    """Create a story row for performance tests."""
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
        genre='superhero',
        characters='Legacy Character',
        synopsis='Story synopsis',
        first_line='First line',
        reprint_notes='',
        notes='Story notes',
        issue=issue,
        type=_create_story_type(),
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
    """Attach nested detail rows to ``story``."""
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
    _creator, creator_name = _create_creator('Writer One', 'Writer, One')
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
    _character, character_name = _create_character(
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


def test_story_list_query_count(api_client, issue):
    """The story list stays on the expected query budget."""
    _create_story(issue, title='Lead Story', sequence_number=1)
    _create_story(issue, title='Backup Story', sequence_number=2)

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(reverse('story-list'))

    assert response.status_code == 200
    assert len(context) == 3


def test_story_detail_query_count(api_client, issue):
    """The story detail endpoint avoids lazy-loading regressions."""
    story = _create_story(issue, title='Lead Story', sequence_number=1)
    _add_story_detail_relations(story)

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(
            reverse('story-detail', kwargs={'pk': story.pk}),
        )

    assert response.status_code == 200
    assert len(context) == 9
