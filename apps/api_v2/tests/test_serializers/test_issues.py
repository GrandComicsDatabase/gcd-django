"""Tests for the issue serializers."""

from decimal import Decimal

from apps.api_v2.serializers.issues import (
    IssueDetailSerializer,
    IssueListSerializer,
)
from apps.gcd.models import Brand, Cover, IndiciaPublisher, Story, StoryType


def test_issue_serializers_expose_prd_fields(issue, publisher, country):
    """The issue serializers emit the Sprint 1 issue contract."""
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
    variant = issue.__class__.objects.create(
        number='1/A',
        title='',
        volume='',
        isbn='',
        valid_isbn='',
        variant_name='',
        barcode='',
        publication_date='',
        key_date='2024-01-02',
        on_sale_date='2024-01-09',
        sort_code=2,
        indicia_frequency='',
        price='',
        editing='',
        notes='',
        indicia_printer_sourced_by='',
        series=issue.series,
        variant_of=issue,
    )
    issue.variant_of = variant
    issue.save()
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
    cover = Cover.objects.create(issue=issue)

    list_data = IssueListSerializer(issue).data
    detail_data = IssueDetailSerializer(issue).data

    assert set(list_data) == {
        'id',
        'series',
        'number',
        'volume',
        'descriptor',
        'variant_name',
        'title',
        'publication_date',
        'key_date',
        'on_sale_date',
        'price',
        'page_count',
        'editing_credits',
        'indicia_publisher',
        'brand_emblems',
        'isbn',
        'barcode',
        'rating',
        'indicia_frequency',
        'notes',
        'variant_of',
        'keywords',
        'created',
        'modified',
        'cover_url',
    }
    assert list_data['series'] == {
        'id': issue.series_id,
        'name': issue.series.name,
    }
    assert list_data['descriptor'] == issue.full_descriptor
    assert list_data['editing_credits'] == ['Editor One', 'Editor Two']
    assert list_data['indicia_publisher'] == {
        'id': indicia_publisher.pk,
        'name': indicia_publisher.name,
    }
    assert list_data['brand_emblems'] == [
        {'id': brand.pk, 'name': brand.name},
    ]
    assert list_data['variant_of'] == variant.pk
    assert set(list_data['keywords']) == {'alpha', 'beta'}
    assert list_data['cover_url'] == (
        f'{cover.get_base_url()}/w400/{cover.id}.jpg'
    )
    assert 'stories' not in list_data

    assert 'stories' in detail_data
    assert len(detail_data['stories']) == 1
    assert detail_data['stories'][0]['id'] == story.pk
    assert detail_data['stories'][0]['type'] == {
        'id': story_type.pk,
        'name': story_type.name,
    }
    assert detail_data['stories'][0]['script'] == [
        'Writer One',
        'Writer Two',
    ]
    assert detail_data['stories'][0]['editing'] == ['Story Editor']
    assert detail_data['stories'][0]['keywords'] == ['story-alpha']
