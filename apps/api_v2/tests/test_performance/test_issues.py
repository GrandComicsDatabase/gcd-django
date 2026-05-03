"""Performance tests for issue endpoints."""

from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import Brand, Cover, Story, StoryType


def _create_issue(series, *, number, sort_code):
    """Create a minimal issue row for performance tests."""
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
        editing='Editor One; Editor Two',
        notes='',
        indicia_printer_sourced_by='',
        series=series,
    )


def test_issue_list_query_count(api_client, series):
    """The issue list stays on the expected query budget."""
    brand = Brand.objects.create(
        name='Test Brand',
        year_began=1960,
        notes='',
    )
    series.is_comics_publication = True
    series.save()
    first = _create_issue(series, number='1', sort_code=1)
    second = _create_issue(series, number='2', sort_code=2)
    first.brand_emblem.add(brand)
    second.brand_emblem.add(brand)
    first.keywords.add('alpha')
    second.keywords.add('beta')
    Cover.objects.create(issue=first)
    Cover.objects.create(issue=second)

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(reverse('issue-list'))

    assert response.status_code == 200
    assert len(context) == 9


def test_issue_detail_query_count(api_client, issue):
    """The issue detail endpoint avoids lazy-loading regressions."""
    story_type, _ = StoryType.objects.get_or_create(
        name='Comic Story',
        defaults={'sort_code': 19},
    )
    issue.series.is_comics_publication = True
    issue.series.save()
    issue.keywords.add('detail')
    Cover.objects.create(issue=issue)
    story = Story.objects.create(
        title='Lead Story',
        feature='Feature Text',
        sequence_number=1,
        page_count=Decimal('10.000'),
        script='Writer One; Writer Two',
        pencils='Penciler One',
        inks='Inker One',
        colors='Colorist One',
        letters='Letterer One',
        editing='Story Editor',
        job_number='JOB-1',
        genre='superhero',
        characters='Batman',
        synopsis='Story synopsis',
        reprint_notes='',
        notes='Story notes',
        issue=issue,
        type=story_type,
    )
    story.keywords.add('story-alpha')

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(
            reverse('issue-detail', kwargs={'pk': issue.pk}),
        )

    assert response.status_code == 200
    assert len(context) == 10
