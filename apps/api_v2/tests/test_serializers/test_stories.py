# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the story serializers."""

from decimal import Decimal

from apps.api_v2.serializers.stories import (
    StoryListSerializer,
    StorySerializer,
)
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
    """Create or return a story type row for story tests."""
    story_type, _ = StoryType.objects.get_or_create(
        name=name,
        defaults={'sort_code': sort_code},
    )
    return story_type


def _create_story(issue, *, title, sequence_number):
    """Create a story row for serializer tests."""
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


def _create_feature(language):
    """Return a feature row with feature type."""
    feature_type = FeatureType.objects.create(name='Character')
    return Feature.objects.create(
        name='Batman',
        sort_name='Batman',
        disambiguation='',
        genre='superhero',
        language=language,
        feature_type=feature_type,
        year_first_published=1939,
        notes='',
    )


def test_story_list_serializer_exposes_list_contract(issue):
    """The story list serializer emits the trimmed Sprint 3 list contract."""
    story = _create_story(issue, title='Lead Story', sequence_number=1)

    data = StoryListSerializer(story).data

    assert set(data) == {
        'id',
        'title',
        'type',
        'feature',
        'sequence_number',
        'page_count',
        'issue',
        'created',
        'modified',
    }
    assert data['id'] == story.pk
    assert data['title'] == 'Lead Story'
    assert data['type'] == {
        'id': story.type_id,
        'name': story.type.name,
    }
    assert data['feature'] == 'Feature Text'
    assert data['sequence_number'] == 1
    assert data['page_count'] == '10.000'
    assert data['issue'] == {
        'id': issue.pk,
        'descriptor': issue.issue_descriptor,
    }


def test_story_detail_serializer_exposes_detail_contract(issue):
    """The story detail serializer emits structured Sprint 3 fields."""
    story = _create_story(issue, title='Lead Story', sequence_number=1)
    story.keywords.add('alpha', 'beta')
    feature = _create_feature(issue.series.language)
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
        issue.series.language,
    )
    role = CharacterRole.objects.create(name='cameo', sort_code=1)
    StoryCharacter.objects.create(
        character=character_name,
        story=story,
        role=role,
        notes='',
    )
    origin = _create_story(issue, title='Original Story', sequence_number=2)
    target = _create_story(issue, title='Reprint Story', sequence_number=3)
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

    data = StorySerializer(story).data

    assert set(data) == {
        'id',
        'title',
        'type',
        'feature',
        'sequence_number',
        'page_count',
        'issue',
        'created',
        'modified',
        'feature_object',
        'feature_logo',
        'credits',
        'characters',
        'synopsis',
        'genre',
        'first_line',
        'notes',
        'keywords',
        'reprint_origins',
        'reprint_targets',
    }
    assert data['feature_object'] == [
        {
            'id': feature.pk,
            'name': 'Batman',
            'feature_type': {
                'id': feature.feature_type_id,
                'name': 'Character',
            },
        },
    ]
    assert data['feature_logo'] == [
        {
            'id': logo.pk,
            'name': 'Bat Logo',
            'year_began': 1940,
            'year_ended': 1945,
        },
    ]
    assert data['credits'] == [
        {
            'creator': {
                'id': creator.pk,
                'name': 'Writer One',
            },
            'role': 'script',
        },
    ]
    assert data['characters'] == [
        {
            'character': {
                'id': character.pk,
                'name': 'Batman',
            },
            'role': 'cameo',
        },
    ]
    assert data['synopsis'] == 'Story synopsis'
    assert data['genre'] == 'superhero'
    assert data['first_line'] == 'First line'
    assert data['notes'] == 'Story notes'
    assert data['keywords'] == ['alpha', 'beta']
    assert data['reprint_origins'] == [origin.pk]
    assert data['reprint_targets'] == [target.pk]
