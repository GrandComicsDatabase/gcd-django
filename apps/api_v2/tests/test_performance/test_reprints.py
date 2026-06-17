# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Performance tests for reprint endpoints."""

from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import Reprint, Story, StoryType


def _create_story_type(name='Comic Story', sort_code=19):
    """Create or return a story type row for performance tests."""
    story_type, _ = StoryType.objects.get_or_create(
        name=name,
        defaults={'sort_code': sort_code},
    )
    return story_type


def _create_issue(series, *, number, sort_code):
    """Create a minimal issue row for reprint performance tests."""
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


def _create_story(issue, *, title, sequence_number):
    """Create a story row for performance tests."""
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
        genre='',
        characters='',
        synopsis='',
        reprint_notes='',
        notes='',
        issue=issue,
        type=_create_story_type(),
    )


def _create_reprint(origin, target):
    """Create a reprint row for performance tests."""
    return Reprint.objects.create(
        origin=origin,
        target=target,
        origin_issue=origin.issue,
        target_issue=target.issue,
        notes='Translated and recolored.',
    )


def test_reprint_list_query_count(api_client, issue):
    """The reprint list stays on the expected query budget."""
    target_issue = _create_issue(issue.series, number='2', sort_code=2)
    origin = _create_story(issue, title='Original Story', sequence_number=1)
    first_target = _create_story(
        target_issue,
        title='First Target Story',
        sequence_number=1,
    )
    second_target = _create_story(
        target_issue,
        title='Second Target Story',
        sequence_number=2,
    )
    _create_reprint(origin, first_target)
    _create_reprint(origin, second_target)

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(reverse('reprint-list'))

    assert response.status_code == 200
    assert len(context) == 3


def test_reprint_detail_query_count(api_client, issue):
    """The reprint detail endpoint avoids lazy-loading regressions."""
    target_issue = _create_issue(issue.series, number='2', sort_code=2)
    origin = _create_story(issue, title='Original Story', sequence_number=1)
    target = _create_story(
        target_issue,
        title='Target Story',
        sequence_number=1,
    )
    reprint = _create_reprint(origin, target)

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(
            reverse('reprint-detail', kwargs={'pk': reprint.pk}),
        )

    assert response.status_code == 200
    assert len(context) == 2
