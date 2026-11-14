# -*- coding: utf-8 -*-
"""
Tests of the cover images of a character: the cut-outs on the character
page, chosen at random among its marked boxes.
"""
import re
from datetime import timedelta
from types import SimpleNamespace

import pytest

from django.contrib.auth.models import Permission, User
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from apps.indexer.models import Indexer
from apps.stddata.models import Country, Language
from apps.gcd.models import (
    Publisher, Series, Issue, Story, StoryType, StoryCharacter, Character,
    CharacterNameDetail, CharacterRelation, CharacterRelationType, Cover,
    CoverCharacterBox, Universe,
)
from apps.gcd.models.issue import VCS_Codes
from apps.gcd.tests.page_ids import assert_valid_ids
from apps.gcd.views import details
from apps.gcd.views.details import _current_boxes, _character_page_images
from apps.oi import states
from apps.oi.models import (Changeset, CharacterNameDetailRevision,
                            CharacterRevision, CTYPES)

# Scan of 400 x 615 pixels.
SCAN_ASPECT = 15375

# Shown width of the boxes of add_box, 3000 x 6918.75 units: alone in the
# largest 200 x 304 (304 / 6918.75 * 3000), and in the smaller 98 x 149
# when shown with others of the same proportion.
ALONE_WIDTH = '131.8'
TOGETHER_WIDTH = '64.61'


def make_character(name, language, **values):
    """A character with its official name."""
    character = Character.objects.create(
        name=name, sort_name=name, disambiguation='', language=language,
        description='', notes='', **values)
    name_detail = CharacterNameDetail.objects.create(
        name=name, sort_name=name, character=character,
        is_official_name=True)
    return character, name_detail


def make_user(name, country):
    """A user with an indexer profile, allowed to reserve."""
    user = User.objects.create_user(name, password=name)
    Indexer.objects.create(user=user, country=country)
    user.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    return user


@pytest.fixture
def page(db):
    """
    The page of a character without covers yet, and an indexer.
    """
    country = Country.objects.get_or_create(
        code='XZZ', defaults={'name': 'Test Country'})[0]
    language = Language.objects.get_or_create(
        code='XZZ', defaults={'name': 'Test Language'})[0]
    publisher = Publisher.objects.create(
        name='Test Publisher', country=country, year_began=1960)
    series = Series.objects.create(
        name='Test Series', sort_name='Test Series',
        year_began=1960, country=country, language=language,
        publisher=publisher, is_comics_publication=True, has_gallery=True,
        publication_dates='1960')
    character, name_detail = make_character('Superman', language)
    return SimpleNamespace(
        language=language, series=series, character=character,
        name_detail=name_detail, issues=0,
        indexer=make_user('images_indexer', country))


def box_values(width):
    """
    The corners and scan of a box width units wide and 4500 high, in
    1/10000 of the front.
    """
    return {'top_left_x': 1000, 'top_left_y': 2000,
            'top_right_x': 1000 + width, 'top_right_y': 2000,
            'bottom_left_x': 1000, 'bottom_left_y': 6500,
            'scan_aspect': SCAN_ASPECT}


def add_box(page, width=3000, name_detail=None, universe=None,
            replaced=False, deleted_appearance=False):
    """
    A box of a character appearance in the cover sequence of a new issue,
    a year after the previous one, with its cover, drawn on the current
    scan unless replaced.
    """
    page.issues += 1
    year = 1960 + page.issues
    issue = Issue.objects.create(
        number=str(page.issues), series=page.series, sort_code=page.issues,
        publication_date=str(year), key_date='%d-01-00' % year)
    story = Story.objects.create(
        issue=issue, type=StoryType.objects.get(id=6), sequence_number=0)
    appearance = StoryCharacter.objects.create(
        character=name_detail or page.name_detail, story=story,
        universe=universe, deleted=deleted_appearance, notes='')
    upload = timezone.now()
    cover = Cover.objects.create(issue=issue, last_upload=upload)
    return CoverCharacterBox.objects.create(
        story_character=appearance, cover=cover,
        scan_date=upload - timedelta(days=1) if replaced else upload,
        **box_values(width))


def add_scan_variant_box(page, box):
    """
    The box of the same appearance on the cover of a variant of its issue
    with only a scan difference, which shows the same art.
    """
    issue = box.cover.issue
    page.issues += 1
    variant = Issue.objects.create(
        number=issue.number, series=page.series, sort_code=page.issues,
        publication_date=issue.publication_date, key_date=issue.key_date,
        variant_of=issue, variant_name='Scan Variant',
        variant_cover_status=VCS_Codes.ONLY_SCAN_DIFFERENCE)
    upload = timezone.now()
    cover = Cover.objects.create(issue=variant, last_upload=upload)
    return CoverCharacterBox.objects.create(
        story_character=box.story_character, cover=cover, scan_date=upload,
        **box_values(3000))


def svg_widths(content):
    """The widths set on the cut-outs of a page."""
    return re.findall(r'<svg class="max-w-full" width="([\d.]+)"', content)


def shown_issues(images):
    """The issues of the cut-outs of the character page, in their order."""
    return [issue for issue, tag in images]


def character_url(page):
    """The character page."""
    return reverse('show_character',
                   kwargs={'character_id': page.character.id})


def test_character_page_shows_three_used_images_in_random_order(
      client, page, monkeypatch):
    """
    Three of the boxes drawn on the current scan replace the random cover,
    in the order of the shuffle, each in the small frame with a link to its
    cover.
    """
    used = [add_box(page) for _ in range(5)]
    add_box(page, replaced=True)
    monkeypatch.setattr(details, 'shuffle',
                        lambda pairs: pairs.sort(reverse=True))

    response = client.get(character_url(page))

    assert shown_issues(response.context['box_images']) == [
        box.cover.issue for box in used[:1:-1]]
    assert response.context['image_issue'] is None
    content = response.content.decode()
    assert svg_widths(content) == [TOGETHER_WIDTH] * 3
    assert 'Random Cover from Character' not in content
    assert 'href="%scover/4/"' % used[4].cover.issue.get_absolute_url() \
        in content
    assert 'aria-label="Superman on the cover of %s"' % escape(
        used[4].cover.issue.full_name()) in content


@pytest.mark.parametrize('used, shown, width', [
    (0, 0, None), (1, 1, ALONE_WIDTH), (2, 2, TOGETHER_WIDTH),
    (3, 3, TOGETHER_WIDTH), (50, 3, TOGETHER_WIDTH)])
def test_character_page_shows_as_many_used_images_as_there_are_up_to_three(
      client, page, used, shown, width):
    """
    One used image gives one, two give two, three or more give three; with
    none the random cover of the character stays as it was.
    """
    add_box(page, replaced=True)
    for _ in range(used):
        add_box(page)

    response = client.get(character_url(page))

    assert len(response.context['box_images']) == shown
    content = response.content.decode()
    assert svg_widths(content) == [width] * shown
    assert ('Random Cover from Character' in content) == (shown == 0)


def test_images_shown_together_share_one_proportion(client, page):
    """
    A tall box, 6918.75 / 3000 = 2.30625, and a wide one, 6918.75 / 9000
    = 0.76875, share the proportion halfway between them, 1.3315, at the
    same size; each is widened only on its shorter side.
    """
    add_box(page, width=3000)
    add_box(page, width=9000)

    content = client.get(character_url(page)).content.decode()

    frames = re.findall(r'<svg class="max-w-full" width="([\d.]+)" '
                        r'viewBox="(\S+) (\S+) (\S+) (\S+)"', content)
    assert sorted(frame[3] for frame in frames) == ['5196.15', '9000']
    for width, left, top, frame_width, frame_height in frames:
        assert width == '98'
        assert float(frame_height) / float(frame_width) == \
            pytest.approx(1.3315, abs=0.0005)


def test_character_page_chooses_again_at_each_view(page):
    """
    Every view shows three different used images, and in many views each
    of them shows up.
    """
    used = {add_box(page).cover.issue for _ in range(5)}
    add_box(page, replaced=True)

    seen = set()
    for _ in range(30):
        issues = shown_issues(_character_page_images(page.character))
        assert len(set(issues)) == 3 and set(issues) <= used
        seen.update(issues)

    assert seen == used


def test_character_page_shows_one_image_of_an_appearance(page):
    """
    The boxes of an appearance on a cover and on its scan variant show the
    same art, so one of them at most is shown.
    """
    box = add_box(page)
    variant_box = add_scan_variant_box(page, box)
    other = add_box(page)

    for _ in range(10):
        issues = shown_issues(_character_page_images(page.character))
        assert len(issues) == 2 and other.cover.issue in issues
        assert (box.cover.issue in issues) != (
            variant_box.cover.issue in issues)


def test_character_page_shows_one_image_at_the_size_of_a_cover(client,
                                                               page):
    """
    A single image takes the large frame and the caption of the random
    cover: the issue and its publication date.
    """
    box = add_box(page)
    issue = box.cover.issue

    content = client.get(character_url(page)).content.decode()

    assert svg_widths(content) == [ALONE_WIDTH]
    assert 'viewBox="0 0 3000 6918.75"' in content
    assert 'href="%scover/4/"' % issue.get_absolute_url() in content
    assert '%s<br>' % escape(issue.full_name()) in content
    assert issue.publication_date in content


def test_character_page_keeps_the_random_cover_without_used_images(
      client, page):
    """
    Without a box on the current scan the random cover stays.
    """
    first = add_box(page, replaced=True)
    second = add_box(page, replaced=True)

    response = client.get(character_url(page))

    assert response.context['box_images'] == []
    assert response.context['image_issue'] in {first.cover.issue,
                                               second.cover.issue}
    content = response.content.decode()
    assert 'Random Cover from Character' in content


def test_box_on_a_hidden_cover_leaves_the_character_pages(client, page):
    """
    A cover of limited display hides its boxes from the character page.
    """
    hidden = add_box(page)
    shown = add_box(page)
    hidden.cover.limit_display = True
    hidden.cover.save()

    assert set(_current_boxes(page.character)) == {shown}
    response = client.get(character_url(page))
    assert shown_issues(response.context['box_images']) == [
        shown.cover.issue]


def test_box_on_a_cover_without_upload_date(page):
    """
    A box drawn on a cover with no last upload is on its current scan,
    but one with a scan date is not.
    """
    without_date = add_box(page)
    with_date = add_box(page)
    Cover.objects.filter(id__in=[without_date.cover_id, with_date.cover_id])\
        .update(last_upload=None)
    CoverCharacterBox.objects.filter(id=without_date.id).update(scan_date=None)

    assert set(_current_boxes(page.character)) == {without_date}


def test_universe_version_shows_only_its_universe(page):
    """
    The page of a universe version shows the appearances of its general
    character in that universe, as show_character does.
    """
    universe = Universe.objects.create(
        multiverse='Test', name='Earth-Two', designation='Two',
        description='', notes='')
    version = make_character('Superman Two', page.language,
                             universe=universe)[0]
    generalisation = CharacterRelationType.objects.get_or_create(
        id=6, defaults={'type': 'generalisation',
                        'reverse_type': 'specification'})[0]
    CharacterRelation.objects.create(
        to_character=version, from_character=page.character,
        relation_type=generalisation, notes='')
    in_universe = add_box(page, universe=universe)
    elsewhere = add_box(page)

    assert set(_current_boxes(version)) == {in_universe}
    assert set(_current_boxes(page.character)) == {in_universe, elsewhere}


@pytest.mark.parametrize('cover', ['no appearance', 'no scan inserted',
                                   'deleted scan'])
def test_character_page_without_any_cover(client, page, cover):
    """
    A character without an appearance on a cover, on one with no scan
    inserted or only a deleted one, shows no image and no caption.
    """
    if cover != 'no appearance':
        box = add_box(page)
        if cover == 'deleted scan':
            Cover.objects.filter(id=box.cover_id).update(deleted=True)
        else:
            box.cover.delete()

    response = client.get(character_url(page))

    assert response.status_code == 200
    assert response.context['box_images'] == []
    assert response.context['image_issue'] is None
    content = response.content.decode()
    assert '<svg class="max-w-full"' not in content
    assert 'Random Cover from Character' not in content
    assert_valid_ids(content)


def test_box_on_a_deleted_cover_leaves_the_character_pages(page):
    """
    A deleted cover hides its boxes from the character page.
    """
    deleted = add_box(page)
    shown = add_box(page)
    Cover.objects.filter(id=deleted.cover_id).update(deleted=True)

    assert set(_current_boxes(page.character)) == {shown}


def test_box_of_a_deleted_appearance_or_sequence_is_left_out(page):
    """
    A deleted appearance, or one in a deleted sequence, has no image on
    the character page.
    """
    add_box(page, deleted_appearance=True)
    in_deleted_sequence = add_box(page)
    in_deleted_sequence.story_character.story.deleted = True
    in_deleted_sequence.story_character.story.save()
    shown = add_box(page)

    assert set(_current_boxes(page.character)) == {shown}


def test_box_of_a_sequence_no_longer_on_the_cover_is_left_out(page):
    """
    A box of a sequence that is no longer a cover sequence has no image on
    the character page.
    """
    other_type = add_box(page)
    story = other_type.story_character.story
    story.type = StoryType.objects.get_or_create(
        id=19, defaults={'name': 'comic story', 'sort_code': 19})[0]
    story.save()
    shown = add_box(page)

    assert set(_current_boxes(page.character)) == {shown}


def test_box_on_a_scan_variant_links_to_the_variant(client, page):
    """
    A cut-out of the cover of a variant with only a scan difference links
    to that cover and names that issue.
    """
    box = add_box(page)
    variant_box = add_scan_variant_box(page, box)
    box.delete()
    variant = variant_box.cover.issue

    content = client.get(character_url(page)).content.decode()

    assert 'href="%scover/4/"' % variant.get_absolute_url() in content
    assert 'aria-label="Superman on the cover of %s"' % escape(
        variant.full_name()) in content


def test_character_page_preview_of_a_revision(client, page):
    """
    The preview of a character change in the queue shows the cover images
    of the character, and none for a character being added.
    """
    add_box(page)
    changeset = Changeset.objects.create(
        state=states.OPEN, indexer=page.indexer,
        change_type=CTYPES['character'])
    previews = []
    for source in (page.character, None):
        revision = CharacterRevision.objects.create(
            changeset=changeset, character=source, name='Superman',
            sort_name='Superman', disambiguation='', language=page.language,
            description='', notes='')
        CharacterNameDetailRevision.objects.create(
            changeset=changeset, character_revision=revision,
            name='Superman', sort_name='Superman', is_official_name=True)
        previews.append(reverse('preview_revision', kwargs={
          'model_name': 'character', 'id': revision.id}))
    client.force_login(page.indexer)

    existing = client.get(previews[0])
    added = client.get(previews[1])

    assert existing.status_code == 200
    assert svg_widths(existing.content.decode()) == [ALONE_WIDTH]
    assert added.status_code == 200
    assert added.context['box_images'] == []
