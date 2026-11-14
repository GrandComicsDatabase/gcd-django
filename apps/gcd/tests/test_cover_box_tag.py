# -*- coding: utf-8 -*-
import math
import re
from datetime import datetime, timezone

import pytest

from apps.gcd.models import Cover, CoverCharacterBox
from apps.gcd.models.cover import BOX_SIZE_SMALL
from apps.gcd.views.covers import (get_box_tag, get_boxes_cover_tag,
                                   get_box_scan_url, common_proportion)

# Scan of 400 x 615 pixels: a y unit is 1.5375 x units long.
ASPECT = 15375


def make_box(corners, **cover_values):
    """An unsaved box on an unsaved cover, enough to draw the tag."""
    cover = Cover(id=1234567, **cover_values)
    names = ('top_left_x', 'top_left_y', 'top_right_x', 'top_right_y',
             'bottom_left_x', 'bottom_left_y')
    return CoverCharacterBox(cover=cover, scan_aspect=ASPECT,
                             **dict(zip(names, corners)))


def frame(tag):
    """The left, top, width and height of the viewBox, the frame."""
    return [float(value) for value in
            re.search(r'viewBox="(\S+) (\S+) (\S+) (\S+)"', tag).groups()]


def parse(tag):
    """
    The sides of the box, around which the frame is centred, and the six
    numbers of the matrix.
    """
    left, top, width, height = frame(tag)
    matrix = re.search(r'matrix\(([^)]*)\)', tag).group(1).split()
    return ([width + 2 * left, height + 2 * top],
            [float(value) for value in matrix])


def assert_corners_fill_the_box(box, tag):
    """
    The matrix takes the top left, top right and bottom left corners of the
    box, laid out in units of the same length on both axes, to the
    corners of the box in the cut-out, from 0 to its sides.
    """
    _, (a, b, c, d, e, f) = parse(tag)
    aspect = box.scan_aspect / 10000
    corners = [(box.top_left_x, box.top_left_y),
               (box.top_right_x, box.top_right_y),
               (box.bottom_left_x, box.bottom_left_y)]
    width = math.hypot(corners[1][0] - corners[0][0],
                       (corners[1][1] - corners[0][1]) * aspect)
    height = math.hypot(corners[2][0] - corners[0][0],
                        (corners[2][1] - corners[0][1]) * aspect)
    for (x, y), expected in zip(corners,
                                [(0, 0), (width, 0), (0, height)]):
        y = y * aspect
        assert a * x + c * y + e == pytest.approx(expected[0], abs=0.05)
        assert b * x + d * y + f == pytest.approx(expected[1], abs=0.05)


def test_upright_box(settings):
    """An upright box has its sides in pixel units and a plain shift."""
    settings.FAKE_IMAGES = False
    box = make_box((1000, 2000, 4000, 2000, 1000, 6500))

    tag = get_box_tag(box, 'Superman')

    (width, height), matrix = parse(tag)
    assert (width, height) == pytest.approx((3000, 4500 * 1.5375))
    assert matrix == pytest.approx([1, 0, 0, 1, -1000, -2000 * 1.5375])
    assert '/w400/1234567.jpg?' in tag
    assert 'width="10000" height="15375"' in tag


@pytest.mark.parametrize('corners, shown_width', [
    # 3000 x 6918.75 units: the height is the limit, 304 / 6918.75 * 3000.
    ((1000, 2000, 4000, 2000, 1000, 6500), '131.8'),
    # 6000 x 1537.5 units: the width is the limit.
    ((1000, 2000, 7000, 2000, 1000, 3000), '200'),
])
def test_cut_out_shows_the_box_as_drawn(corners, shown_width):
    """
    On its own a cut-out is the box as drawn, in the largest width and
    height; only the width is set.
    """
    box = make_box(corners)

    tag = get_box_tag(box, 'Superman', (200, 304))

    (width, height), _ = parse(tag)
    assert frame(tag) == pytest.approx([0, 0, width, height])
    assert '<svg class="max-w-full" width="%s" viewBox=' % shown_width in tag
    assert 'height' not in tag.split('viewBox')[0]
    assert_corners_fill_the_box(box, tag)


@pytest.mark.parametrize('corners, expected', [
    # 3000 x 6918.75 units, narrower than the proportion 1.52: 6918.75 /
    # 1.52 = 4551.81 wide, 775.9 more on each side.
    ((1000, 2000, 4000, 2000, 1000, 6500), (-775.905, 0, 4551.81, 6918.75)),
    # 6000 x 1537.5 units at 3075 from the top, wider: 6000 * 1.52 = 9120
    # high, 3791.25 more above and below, moved down by 716.25 so that the
    # top of the frame is the top of the cover.
    ((1000, 2000, 7000, 2000, 1000, 3000), (0, -3075, 6000, 9120)),
    # 2000 x 3040 units, already of that proportion: nothing more.
    ((1000, 2000, 3000, 2000, 1000, 3977.24), (0, 0, 2000, 3040)),
])
def test_cut_outs_shown_together_share_a_proportion(corners, expected):
    """
    With a proportion the box is widened on its shorter side around its
    centre, moved inside the cover when it would leave it, and the whole
    box is still shown.
    """
    box = make_box(corners)

    tag = get_box_tag(box, 'Superman', (200, 304), proportion=1.52)

    assert frame(tag) == pytest.approx(expected, abs=0.05)
    assert '<svg class="max-w-full" width="200" viewBox=' in tag
    assert_corners_fill_the_box(box, tag)


def test_frame_stays_centred_when_it_cannot_fit_the_cover():
    """
    A box 9000 x 1537.5 units at the top widened to the proportion 2 is
    18000 units high, more than the cover: it stays centred.
    """
    box = make_box((500, 0, 9500, 0, 500, 1000))

    tag = get_box_tag(box, 'Superman', (200, 304), proportion=2)

    assert frame(tag) == pytest.approx((0, -8231.25, 9000, 18000), abs=0.05)


def test_common_proportion_is_halfway_between_the_extremes():
    """
    Height over width: 6918.75 / 3000 = 2.30625 and 1537.5 / 6000 =
    0.25625 give their geometric mean 0.76875; a box in between changes
    nothing, a single box gives its own.
    """
    tall = make_box((1000, 2000, 4000, 2000, 1000, 6500))
    wide = make_box((1000, 2000, 7000, 2000, 1000, 3000))
    middle = make_box((1000, 2000, 3000, 2000, 1000, 3977.24))

    assert common_proportion([tall, wide]) == pytest.approx(0.76875)
    assert common_proportion([tall, middle, wide]) == pytest.approx(0.76875)
    assert common_proportion([tall]) == pytest.approx(2.30625)


def test_quarter_turned_box():
    """Art printed sideways, head to the left: the top side goes up."""
    box = make_box((1000, 6500, 1000, 2000, 4000, 6500))

    tag = get_box_tag(box, 'Superman')

    (width, height), matrix = parse(tag)
    assert (width, height) == pytest.approx((4500 * 1.5375, 3000))
    assert matrix[:4] == pytest.approx([0, 1, -1, 0])
    assert_corners_fill_the_box(box, tag)


def test_box_turned_by_any_angle():
    """
    A box of 2000 x 3000 pixel units turned by 37 degrees clockwise around
    the centre of the scan, corners rounded as the page stores them.
    """
    turn = math.radians(37)
    centre = (5000, 5000 * 1.5375)

    def corner(across, down):
        """A corner of the box, rounded as the page stores it."""
        x = centre[0] + across * math.cos(turn) - down * math.sin(turn)
        y = centre[1] + across * math.sin(turn) + down * math.cos(turn)
        return [round(x), round(y / 1.5375)]

    box = make_box(corner(-1000, -1500) + corner(1000, -1500)
                   + corner(-1000, 1500))

    tag = get_box_tag(box, 'Superman')

    (width, height), _ = parse(tag)
    assert (width, height) == pytest.approx((2000, 3000), abs=2)
    assert_corners_fill_the_box(box, tag)


def test_wraparound_box_uses_the_front_scan(settings):
    """A wraparound cover uses the w200 scan, only of the front."""
    settings.FAKE_IMAGES = False
    box = make_box((1000, 2000, 4000, 2000, 1000, 6500),
                   is_wraparound=True)

    assert '/w200/1234567.jpg?' in get_box_tag(box, 'Superman')


def test_box_with_fake_images(settings):
    """With FAKE_IMAGES the placeholder takes the place of the scan."""
    settings.FAKE_IMAGES = True
    box = make_box((1000, 2000, 4000, 2000, 1000, 6500))

    tag = get_box_tag(box, 'Superman')

    assert 'img/placeholder_large.jpg' in tag
    assert '1234567.jpg' not in tag


def test_box_of_limited_display_cover(settings):
    """A cover of limited display shows the no-cover image."""
    settings.FAKE_IMAGES = False
    box = make_box((1000, 2000, 4000, 2000, 1000, 6500),
                   limit_display=True)

    tag = get_box_tag(box, 'Superman', BOX_SIZE_SMALL)

    assert tag.startswith('<img class="border-2 max-w-full" width="98"')
    assert 'img/nocover_large.png' in tag
    assert '<svg' not in tag


def test_box_alt_text_is_escaped():
    """The alternative text is escaped in the attribute."""
    box = make_box((1000, 2000, 4000, 2000, 1000, 6500))

    tag = get_box_tag(box, 'Superman & "Lois"')

    assert 'aria-label="Superman &amp; &quot;Lois&quot;"' in tag


def test_cover_with_numbered_boxes(settings):
    """
    The four corners of each box on the whole scan, y in pixel units,
    and its number at its centre.
    """
    settings.FAKE_IMAGES = False
    upright = make_box((1000, 2000, 4000, 2000, 1000, 6500))
    sideways = make_box((1000, 6500, 1000, 2000, 4000, 6500))

    tag = get_boxes_cover_tag(upright.cover, [(1, upright), (2, sideways)],
                              'Cover', 'w-[200px]')

    assert re.search(r'viewBox="0 0 10000 15375"', tag)
    assert '/w400/1234567.jpg?' in tag
    points = re.findall(r'points="([^"]*)"', tag)
    assert points == ['1000,3075 4000,3075 4000,9993.75 1000,9993.75',
                      '1000,9993.75 1000,3075 4000,3075 4000,9993.75']
    numbers = re.findall(r'<text x="(\S+)" y="(\S+)"[^>]*>(\d+)</text>', tag)
    assert numbers == [('2500', '6534.38', '1'), ('2500', '6534.38', '2')]
    # The red of the site's colours, not a colour of its own.
    assert tag.count('class="text-red-600" fill="none" '
                     'stroke="currentColor"') == 2


def test_frame_stays_centred_when_a_corner_cannot_reach_the_cover():
    """
    A box with its top above the cover is widened sideways; no sideways
    move brings its top onto the cover, so the frame stays centred.
    """
    box = make_box((100, -500, 1100, -500, 100, 4000))

    tag = get_box_tag(box, 'Cut-out', BOX_SIZE_SMALL, 0.8)

    assert frame(tag)[0] == pytest.approx((1000 - 6918.75 / 0.8) / 2,
                                          abs=0.01)


def test_scan_address_is_escaped(settings):
    """The address of the scan is escaped in both tags."""
    settings.FAKE_IMAGES = True
    settings.STATIC_URL = '/static&files/'
    box = make_box((1000, 2000, 4000, 2000, 1000, 6500))

    assert 'href="/static&amp;files/img/placeholder_large.jpg"' in \
        get_box_tag(box, 'Cut-out')
    assert 'href="/static&amp;files/img/placeholder_large.jpg"' in \
        get_boxes_cover_tag(box.cover, [(1, box)], 'Cover')


def test_scan_url_changes_with_a_new_scan(settings):
    """
    The scan of a cover replaced since has another address, so a browser
    does not show the old one from its cache.
    """
    settings.FAKE_IMAGES = False
    first = make_box((1000, 2000, 4000, 2000, 1000, 6500),
                     last_upload=datetime(2020, 1, 1, tzinfo=timezone.utc))
    second = make_box((1000, 2000, 4000, 2000, 1000, 6500),
                      last_upload=datetime(2021, 1, 1, tzinfo=timezone.utc))

    assert get_box_scan_url(first.cover) != get_box_scan_url(second.cover)
    assert get_box_scan_url(first.cover).split('?')[0] == \
        get_box_scan_url(second.cover).split('?')[0]


def test_cover_without_boxes_or_of_limited_display():
    """
    There is no tag without boxes, for limited display or for a deleted
    cover, and its cut-outs are the image of a missing cover.
    """
    box = make_box((1000, 2000, 4000, 2000, 1000, 6500),
                   limit_display=True)
    deleted = make_box((1000, 2000, 4000, 2000, 1000, 6500), deleted=True)

    assert get_boxes_cover_tag(box.cover, [(1, box)], 'Cover') == ''
    assert get_boxes_cover_tag(box.cover, [], 'Cover') == ''
    assert get_boxes_cover_tag(deleted.cover, [(1, deleted)], 'Cover') == ''
    assert 'img/nocover_large.png' in get_box_tag(deleted, 'Cut-out')


def test_cover_with_boxes_takes_the_proportions_of_the_current_scan():
    """
    A cover is laid out as high as the current scan, from a box drawn on
    it, though the first box was drawn on an older scan.
    """
    upload = datetime(2021, 1, 1, tzinfo=timezone.utc)
    older = make_box((1000, 2000, 4000, 2000, 1000, 6500),
                     last_upload=upload)
    older.scan_aspect = 14000
    older.scan_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    current = make_box((1000, 2000, 4000, 2000, 1000, 6500))
    current.cover = older.cover
    current.scan_date = upload

    tag = get_boxes_cover_tag(older.cover, [(1, older), (2, current)],
                              'Cover')

    assert 'viewBox="0 0 10000 15375"' in tag
