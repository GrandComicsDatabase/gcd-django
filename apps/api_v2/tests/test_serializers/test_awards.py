# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for Award and received-award serializers."""

import pytest
from django.contrib.contenttypes.models import ContentType

from apps.api_v2.serializers.awards import (
    AwardListSerializer,
    AwardRecipientSerializer,
    AwardSerializer,
)
from apps.gcd.models import Award, Creator, ReceivedAward, Story, StoryType

pytestmark = pytest.mark.django_db


def _create_creator(name):
    """Create a minimal Creator recipient."""
    return Creator.objects.create(
        gcd_official_name=name,
        sort_name=f'{name}, Sort',
        disambiguation='Test identity',
        birth_province='',
        birth_city='',
        death_province='',
        death_city='',
        bio='',
        notes='',
    )


def _create_story(issue):
    """Create a minimal Story recipient."""
    story_type, _ = StoryType.objects.get_or_create(
        name='comic story',
        defaults={'sort_code': 19},
    )
    return Story.objects.create(
        title='Award-Winning Story',
        feature='The Feature',
        sequence_number=1,
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
        first_line='',
        reprint_notes='',
        notes='',
        issue=issue,
        type=story_type,
    )


def _create_received_award(
    *,
    award,
    recipient,
    name,
    year,
    uncertain=False,
):
    """Create a received Award for a generic recipient."""
    return ReceivedAward.objects.create(
        content_type=ContentType.objects.get_for_model(recipient),
        object_id=recipient.pk,
        award=award,
        award_name=name,
        award_year=year,
        award_year_uncertain=uncertain,
        notes=f'{name} notes',
    )


def test_award_serializers_expose_trimmed_list_and_full_detail_contracts():
    """Award list rows stay trimmed while detail adds notes."""
    award = Award.objects.create(
        name='Eisner Awards',
        notes='Award notes',
    )

    list_data = AwardListSerializer(award).data
    detail_data = AwardSerializer(award).data

    assert set(list_data) == {
        'id',
        'name',
        'created',
        'modified',
    }
    assert list_data['name'] == 'Eisner Awards'
    assert set(detail_data) == set(list_data) | {'notes'}
    assert detail_data['notes'] == 'Award notes'


def test_award_recipient_serializer_emits_typed_recipient_objects(
    issue,
    series,
):
    """Each supported generic recipient has a useful stable shape."""
    award = Award.objects.create(name='Eisner Awards', notes='')
    creator = _create_creator('Jane Doe')
    story = _create_story(issue)
    rows = [
        _create_received_award(
            award=award,
            recipient=creator,
            name='Best Creator',
            year=1989,
        ),
        _create_received_award(
            award=award,
            recipient=issue,
            name='Best Issue',
            year=1990,
        ),
        _create_received_award(
            award=award,
            recipient=series,
            name='Best Series',
            year=1991,
        ),
        _create_received_award(
            award=award,
            recipient=story,
            name='Best Story',
            year=1992,
            uncertain=True,
        ),
    ]

    data = AwardRecipientSerializer(rows, many=True).data

    assert set(data[0]) == {
        'id',
        'recipient_type',
        'recipient',
        'name',
        'year',
        'year_uncertain',
        'notes',
        'created',
        'modified',
    }
    assert data[0]['recipient_type'] == 'creator'
    assert data[0]['recipient'] == {
        'id': creator.pk,
        'name': 'Jane Doe',
        'sort_name': 'Jane Doe, Sort',
        'disambiguation': 'Test identity',
    }
    assert data[1]['recipient_type'] == 'issue'
    assert data[1]['recipient'] == {
        'id': issue.pk,
        'number': '1',
        'volume': '',
        'title': '',
        'series': {
            'id': series.pk,
            'name': 'Test Series',
        },
    }
    assert data[2]['recipient_type'] == 'series'
    assert data[2]['recipient'] == {
        'id': series.pk,
        'name': 'Test Series',
        'sort_name': 'Test Series',
        'year_began': 1990,
    }
    assert data[3]['recipient_type'] == 'story'
    assert data[3]['recipient'] == {
        'id': story.pk,
        'title': 'Award-Winning Story',
        'feature': 'The Feature',
        'sequence_number': 1,
        'issue': {
            'id': issue.pk,
            'number': '1',
            'series': {
                'id': series.pk,
                'name': 'Test Series',
            },
        },
    }
    assert data[3]['name'] == 'Best Story'
    assert data[3]['year'] == 1992
    assert data[3]['year_uncertain'] is True
    assert data[3]['notes'] == 'Best Story notes'
