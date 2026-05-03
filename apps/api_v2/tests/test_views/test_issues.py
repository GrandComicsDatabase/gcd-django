"""Tests for the issue v2 endpoints."""

from decimal import Decimal

from django.urls import reverse

from apps.gcd.models import Brand, Cover, IndiciaPublisher, Story, StoryType


def _create_issue(
    series,
    *,
    number,
    key_date,
    on_sale_date,
    sort_code,
    isbn='',
    barcode='',
    deleted=False,
):
    """Create a minimal issue row for view tests."""
    return series.issue_set.model.objects.create(
        number=number,
        title='',
        volume='',
        isbn=isbn,
        valid_isbn='',
        variant_name='',
        barcode=barcode,
        publication_date='',
        key_date=key_date,
        on_sale_date=on_sale_date,
        sort_code=sort_code,
        indicia_frequency='',
        price='',
        editing='',
        notes='',
        indicia_printer_sourced_by='',
        series=series,
        deleted=deleted,
    )


def test_issue_list_returns_paginated_results(
    api_client, issue, publisher, country
):
    """The list endpoint is anon-readable and paginated."""
    issue.series.is_comics_publication = True
    issue.series.save()
    indicia_publisher = IndiciaPublisher.objects.create(
        name='Test Indicia',
        year_began=1960,
        notes='',
        parent=publisher,
        country=country,
    )
    brand = Brand.objects.create(
        name='Test Brand',
        year_began=1960,
        notes='',
    )
    issue.title = 'Issue Title'
    issue.key_date = '2024-01-01'
    issue.on_sale_date = '2024-01-08'
    issue.editing = 'Editor One; Editor Two'
    issue.indicia_publisher = indicia_publisher
    issue.save()
    issue.brand_emblem.add(brand)
    issue.keywords.add('alpha')
    cover = Cover.objects.create(issue=issue)

    response = api_client.get(reverse('issue-list'))

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['next'] is None
    assert response.data['previous'] is None
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['id'] == issue.pk
    assert response.data['results'][0]['series'] == {
        'id': issue.series_id,
        'name': issue.series.name,
    }
    assert response.data['results'][0]['editing_credits'] == [
        'Editor One',
        'Editor Two',
    ]
    assert response.data['results'][0]['cover_url'] == (
        f'{cover.get_base_url()}/w400/{cover.id}.jpg'
    )
    assert 'stories' not in response.data['results'][0]


def test_issue_detail_returns_expected_payload(
    api_client, issue, publisher, country
):
    """The detail endpoint returns the issue serializer payload."""
    issue.series.is_comics_publication = True
    issue.series.save()
    indicia_publisher = IndiciaPublisher.objects.create(
        name='Test Indicia',
        year_began=1960,
        notes='',
        parent=publisher,
        country=country,
    )
    brand = Brand.objects.create(
        name='Test Brand',
        year_began=1960,
        notes='',
    )
    story_type, _ = StoryType.objects.get_or_create(
        name='Comic Story',
        defaults={'sort_code': 19},
    )
    issue.title = 'Issue Title'
    issue.volume = '2'
    issue.variant_name = 'Direct Market'
    issue.publication_date = 'January 2024'
    issue.key_date = '2024-01-01'
    issue.on_sale_date = '2024-01-08'
    issue.price = '$4.99'
    issue.page_count = Decimal('32.000')
    issue.editing = 'Editor One; Editor Two'
    issue.indicia_publisher = indicia_publisher
    issue.isbn = '1111111111111'
    issue.barcode = '12345'
    issue.rating = 'Teen'
    issue.indicia_frequency = 'Monthly'
    issue.notes = 'Issue notes'
    issue.save()
    issue.brand_emblem.add(brand)
    issue.keywords.add('alpha', 'beta')
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

    response = api_client.get(
        reverse('issue-detail', kwargs={'pk': issue.pk}),
    )

    assert response.status_code == 200
    assert response.data['id'] == issue.pk
    assert response.data['series'] == {
        'id': issue.series_id,
        'name': issue.series.name,
    }
    assert response.data['editing_credits'] == ['Editor One', 'Editor Two']
    assert response.data['brand_emblems'] == [
        {'id': brand.pk, 'name': brand.name},
    ]
    assert len(response.data['stories']) == 1
    assert response.data['stories'][0]['id'] == story.pk
    assert response.data['stories'][0]['type'] == {
        'id': story_type.pk,
        'name': story_type.name,
    }


def test_issue_list_applies_filter_query_params(api_client, issue, publisher):
    """The list endpoint applies django-filter query params."""
    issue.key_date = '2024-01-01'
    issue.on_sale_date = '2024-01-08'
    issue.isbn = '1111111111111'
    issue.barcode = '12345'
    issue.save()
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
    _create_issue(
        other_series,
        number='1',
        key_date='2024-01-01',
        on_sale_date='2024-01-08',
        sort_code=1,
        isbn='1111111111111',
        barcode='12345',
    )

    response = api_client.get(
        reverse('issue-list'),
        {
            'series': str(issue.series.pk),
            'number': '1',
            'isbn': '1111111111111',
            'barcode': '12345',
        },
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == issue.pk


def test_issue_endpoints_hide_soft_deleted_records(api_client, issue):
    """Soft-deleted issues disappear from list and detail responses."""
    visible = issue
    visible.key_date = '2024-01-01'
    visible.on_sale_date = '2024-01-08'
    visible.save()
    deleted = _create_issue(
        issue.series,
        number='2',
        key_date='2024-01-02',
        on_sale_date='2024-01-09',
        sort_code=2,
        deleted=True,
    )

    list_response = api_client.get(reverse('issue-list'))
    detail_response = api_client.get(
        reverse('issue-detail', kwargs={'pk': deleted.pk}),
    )

    assert list_response.status_code == 200
    assert list_response.data['count'] == 1
    assert list_response.data['results'][0]['id'] == visible.pk
    assert detail_response.status_code == 404


def test_issue_list_returns_304_for_if_modified_since(
    authenticated_client,
    issue,
):
    """List responses support Last-Modified cache validation."""
    response = authenticated_client.get(reverse('issue-list'))

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('issue-list'),
        HTTP_IF_MODIFIED_SINCE=response['Last-Modified'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''


def test_issue_detail_returns_304_for_if_none_match(
    authenticated_client,
    issue,
):
    """Detail responses support ETag cache validation."""
    response = authenticated_client.get(
        reverse('issue-detail', kwargs={'pk': issue.pk}),
    )

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('issue-detail', kwargs={'pk': issue.pk}),
        HTTP_IF_NONE_MATCH=response['ETag'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''
