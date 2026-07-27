# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Performance tests for Award and recipient endpoints."""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import Award, Creator, ReceivedAward, Story, StoryType

pytestmark = pytest.mark.django_db


def _create_creator(name):
    """Create a minimal Creator recipient."""
    return Creator.objects.create(
        gcd_official_name=name,
        sort_name=name,
        disambiguation='',
        birth_province='',
        birth_city='',
        death_province='',
        death_city='',
        bio='',
        notes='',
    )


def _create_story(issue, number):
    """Create a minimal Story recipient."""
    story_type, _ = StoryType.objects.get_or_create(
        name='comic story',
        defaults={'sort_code': 19},
    )
    return Story.objects.create(
        title=f'Story {number}',
        feature='',
        sequence_number=number,
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


def _create_received_award(*, award, recipient, number):
    """Create a received Award for a generic recipient."""
    return ReceivedAward.objects.create(
        content_type=ContentType.objects.get_for_model(recipient),
        object_id=recipient.pk,
        award=award,
        award_name=f'Best Work {number}',
        award_year=1980 + number,
        notes='',
    )


def test_award_list_and_detail_query_counts(api_client):
    """Award roots stay on fixed list and detail query budgets."""
    award = Award.objects.create(name='Eisner Awards', notes='')

    with CaptureQueriesContext(connection) as list_context:
        list_response = api_client.get(reverse('award-list'))
    with CaptureQueriesContext(connection) as detail_context:
        detail_response = api_client.get(
            reverse('award-detail', kwargs={'pk': award.pk}),
        )

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert len(list_context) == 3
    assert len(detail_context) == 2


def test_award_recipient_query_count_is_row_count_independent(
    api_client,
    issue,
    series,
):
    """Generic recipients use one bounded query per supported model type."""
    award = Award.objects.create(name='Eisner Awards', notes='')
    recipients = []
    for number in range(1, 3):
        recipients.extend(
            (
                _create_creator(f'Creator {number}'),
                issue,
                series,
                _create_story(issue, number),
            ),
        )
    for number, recipient in enumerate(recipients, start=1):
        _create_received_award(
            award=award,
            recipient=recipient,
            number=number,
        )

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(
            reverse('award-recipients', kwargs={'pk': award.pk}),
        )

    assert response.status_code == 200
    assert response.data['count'] == 8
    assert len(response.data['results']) == 8
    assert {row['recipient_type'] for row in response.data['results']} == {
        'creator',
        'issue',
        'series',
        'story',
    }
    assert len(context) == 8
