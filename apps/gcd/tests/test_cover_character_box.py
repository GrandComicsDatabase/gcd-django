# -*- coding: utf-8 -*-
import pytest

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.stddata.models import Country, Language
from apps.gcd.models import (
    Publisher, Series, Issue, Story, StoryType, StoryCharacter, Character,
    CharacterNameDetail, Cover, CoverCharacterBox,
)
from apps.gcd.models.cover import box_covers, VALID_BOX_COVER

# An upright rectangle 3000 wide and 4500 high in affine coordinates of the
# front (x in 1/10000 of its width, y in 1/10000 of its height), drawn on a
# scan of 400 x 615 pixels.
UPRIGHT = {
    'top_left_x': 1000, 'top_left_y': 2000,
    'top_right_x': 4000, 'top_right_y': 2000,
    'bottom_left_x': 1000, 'bottom_left_y': 6500,
    'scan_aspect': 15375,
}


def make_character(name, language):
    """A character with its official name."""
    character = Character.objects.create(
        name=name, sort_name=name, disambiguation='', language=language,
        description='', notes='')
    name_detail = CharacterNameDetail.objects.create(
        name=name, sort_name=name, character=character,
        is_official_name=True)
    return character, name_detail


@pytest.fixture
def box_world(db):
    """
    A cover sequence with one character appearance and the issue cover.
    """
    country = Country.objects.get_or_create(
        code='XZZ', defaults={'name': 'Test Country'})[0]
    language = Language.objects.get_or_create(
        code='XZZ', defaults={'name': 'Test Language'})[0]
    publisher = Publisher.objects.create(
        name='Test Publisher', country=country, year_began=1965)
    series = Series.objects.create(
        name='Test Series', sort_name='Test Series',
        year_began=1965, country=country, language=language,
        publisher=publisher, is_comics_publication=True, has_gallery=True,
        publication_dates='1965')
    issue = Issue.objects.create(
        number='1', series=series, sort_code=0,
        publication_date='1965', key_date='1965-01-00')
    story_type = StoryType.objects.get_or_create(
        name='cover', defaults={'sort_code': 99011})[0]
    story = Story.objects.create(
        issue=issue, type=story_type, sequence_number=0)
    name_detail = make_character('Superman', language)[1]
    appearance = StoryCharacter.objects.create(
        character=name_detail, story=story, notes='')
    cover = Cover.objects.create(issue=issue)
    box = CoverCharacterBox.objects.create(
        story_character=appearance, cover=cover, scan_date=timezone.now(),
        **UPRIGHT)
    return {
        'appearance': appearance,
        'cover': cover,
        'box': box,
    }


def test_box_corners_can_be_outside_the_front(box_world):
    """A character near the edge gives corners beyond 0 and 10000."""
    box = box_world['box']
    box.top_left_x = -1200
    box.top_left_y = -300
    box.top_right_x = 10400
    box.full_clean()
    box.save()
    box.refresh_from_db()
    assert (box.top_left_x, box.top_left_y, box.top_right_x) == (
        -1200, -300, 10400)


def test_box_needs_scan_aspect(box_world):
    """A box without scan_aspect is not valid."""
    box = box_world['box']
    box.scan_aspect = None
    with pytest.raises(ValidationError) as error:
        box.full_clean()
    assert 'scan_aspect' in error.value.message_dict


def test_box_unique_per_appearance_and_cover(box_world):
    """An appearance has one box on a cover."""
    with pytest.raises(IntegrityError), transaction.atomic():
        CoverCharacterBox.objects.create(
            story_character=box_world['appearance'],
            cover=box_world['cover'], **UPRIGHT)


@pytest.fixture
def variant_covers(box_world):
    """
    A cover of a variant for each variant cover status, and a deleted
    cover of the issue.
    """
    issue = box_world['cover'].issue
    covers = {}
    for status in (1, 2, 3):
        variant = Issue.objects.create(
            number='1', series=issue.series, sort_code=status,
            publication_date='1965', key_date='1965-01-00',
            variant_of=issue, variant_name='Variant %d' % status,
            variant_cover_status=status)
        covers[status] = Cover.objects.create(issue=variant)
    covers['deleted'] = Cover.objects.create(issue=issue, deleted=True)
    return covers


def test_box_covers_are_of_the_issue_and_scan_variants(box_world,
                                                       variant_covers):
    """Boxes go on covers of the issue and of its scan variants."""
    issue = box_world['cover'].issue
    allowed = {box_world['cover'], variant_covers[2]}

    assert set(box_covers(issue)) == allowed


def test_valid_box_cover_filters_boxes(box_world, variant_covers):
    """VALID_BOX_COVER keeps only the boxes on those covers."""
    for key in variant_covers:
        CoverCharacterBox.objects.create(
            story_character=box_world['appearance'],
            cover=variant_covers[key], **UPRIGHT)

    valid = CoverCharacterBox.objects.filter(VALID_BOX_COVER)

    assert {box.cover for box in valid} == {
        box_world['cover'], variant_covers[2]}
