# -*- coding: utf-8 -*-
import math

from django.conf import settings
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from apps.gcd.models.cover import ZOOM_SMALL, ZOOM_MEDIUM, ZOOM_LARGE, \
                                  BOX_SIZE_LARGE
from apps.oi import states


def get_generic_image_tag(image, alt_text):
    img_class = 'cover_img'
    try:
        width = min(image.image_file.width, 400)
    except IOError:
        width = 0
    return mark_safe('<img src="' + image.scaled_image.url + '?' +
                     str(hash(image.modified)) + '" alt="' + esc(alt_text)
                     + '" ' + ' class="' + img_class +
                     '" width="' + str(width) + '"/>')


def get_image_tag(cover, alt_text, zoom_level, can_have_cover=True,
                  img_class='cover_img', title=''):
    css_width = ''

    if zoom_level == ZOOM_SMALL:
        width = 100
        size = 'small'
        if cover and cover.is_wraparound:
            img_class = 'wraparound_cover_img'
    elif zoom_level == ZOOM_MEDIUM:
        width = 200
        size = 'medium'
        if cover and cover.is_wraparound:
            img_class = 'wraparound_cover_img'
    elif zoom_level == ZOOM_LARGE:
        width = 400
        size = 'large'
    elif zoom_level == 1.5:
        width = 200
        css_width = 150
        size = 'medium'

    if css_width:
        img_class += ' w-[%spx]' % css_width
    else:
        img_class += ' w-[%spx]' % width

    if zoom_level in [1.5, ZOOM_MEDIUM]:
        img_class += ' min-w-[100px] sm:min-w-[150px]'

    no_cover_url = '<img class="border-2" src="' + settings.STATIC_URL
    if cover is None:
        if not can_have_cover:
            return mark_safe(no_cover_url + 'img/noupload_' + size + '.png" '
                             + 'alt="No image"' + 'class="' + img_class + '">')
        return mark_safe(no_cover_url + 'img/nocover_' + size + '.png" '
                         + 'alt="No image yet"' + 'class="' + img_class + '">')

    if cover.limit_display and zoom_level != ZOOM_SMALL:
        # TODO: Make 'cannot display due to...' image and use here
        return mark_safe(no_cover_url + 'img/nocover_' + size + '.png" '
                         + 'alt="No image yet"' + 'class="' + img_class + '">')

    if title:
        add_info = ' title="%s" alt="%s" ' % (esc(title), esc(alt_text))
    else:
        add_info = ' alt="%s" ' % esc(alt_text)

    if settings.FAKE_IMAGES:
        return mark_safe('<img src="' + settings.STATIC_URL +
                         'img/placeholder_' + size + '.jpg"' + add_info +
                         'class="' + img_class + '">')

    img_url = cover.get_base_url()+("/w%d/%d.jpg" % (width, cover.id))

    # For replacement and variant cover uploads we should make sure that no
    # cached cover is displayed. Adding a changing query string seems the
    # preferred solution found on the net.
    img_url = img_url + '?' + str(hash(cover.last_upload))

    return mark_safe('<img src="' + img_url + '"' + add_info +
                     'class="' + img_class + '">')


def get_box_scan_url(cover):
    """
    The URL of the scan the character boxes of a cover are drawn on and
    cut out of: the w400 scan, or the w200 one of a wraparound cover, which
    holds only the front.
    """
    if settings.FAKE_IMAGES:
        return settings.STATIC_URL + 'img/placeholder_large.jpg'
    return '%s/w%d/%d.jpg?%s' % (
      cover.get_base_url(), 200 if cover.is_wraparound else 400, cover.id,
      hash(cover.last_upload))


def box_alt_text(character, issue):
    """
    The alternative text of a cut-out: the character, or the name it has in
    the appearance, on the cover of the issue.
    """
    return '%s on the cover of %s' % (character.name, issue.full_name())


def _box_sides(box):
    """
    The top left corner of a box and its top and left sides as vectors, on
    the scan laid out 10000 units wide and scan_aspect units high, so that a
    unit has the same length on both axes.
    """
    aspect = box.scan_aspect / 10000
    corner = (box.top_left_x, box.top_left_y * aspect)
    across = (box.top_right_x - corner[0],
              box.top_right_y * aspect - corner[1])
    down = (box.bottom_left_x - corner[0],
            box.bottom_left_y * aspect - corner[1])
    return corner, across, down


def common_proportion(boxes):
    """
    The proportion, height over width, shared by cut-outs shown together:
    halfway in ratio between the tallest and the widest box, so that each
    of them is widened as little as possible.
    """
    proportions = []
    for box in boxes:
        _, across, down = _box_sides(box)
        proportions.append(math.hypot(*down) / math.hypot(*across))
    return math.sqrt(min(proportions) * max(proportions))


def _shift_inside(box, corner, units, frame, axis, limit):
    """
    How far to move the frame of a widened box along its widened axis, at
    most limit either way so that the box stays in it, for its four corners
    to be on the cover: the shift nearest to none, or none if no shift
    does it.  units are the unit vectors of the top and left sides, and the
    frame is left, top, width and height in units along them.
    """
    left, top, width, height = frame
    low, high = -limit, limit
    for along in (left, left + width):
        for down in (top, top + height):
            for i, edge in ((0, 10000), (1, box.scan_aspect)):
                point = corner[i] + along * units[0][i] + down * units[1][i]
                step = units[axis][i]
                if abs(step) < 1e-9:
                    if not -1e-6 <= point <= edge + 1e-6:
                        return 0
                    continue
                ends = sorted((-point / step, (edge - point) / step))
                low, high = max(low, ends[0]), min(high, ends[1])
    if low > high + 1e-9:
        return 0
    return min(max(0, low), high)


def get_box_tag(box, alt_text, size=BOX_SIZE_LARGE, proportion=None):
    """
    Show a character box of a cover as an upright cut-out, without
    JavaScript.

    The box is drawn on the scan of get_box_scan_url, laid out as in
    _box_sides, and one matrix, the inverse of the affine map of the cut-out
    onto the scan, brings the scan into the box of the cut-out.

    The cut-out shows the box as drawn and fits in size, its largest width
    and height in pixels.  Cut-outs shown together pass their
    common_proportion: each box is then widened on its shorter side to that
    proportion around its centre, and moved inside the cover when it can
    be, so they look alike side by side and show a little more of the
    cover.  Only the width is set and the height follows from the viewBox,
    so the cut-out also shrinks to the width of its parent.  A cover not
    shown on the site, or deleted, gives the image of a missing cover.
    """
    cover = box.cover
    if cover.limit_display or cover.deleted:
        return mark_safe('<img class="border-2 max-w-full" width="%d" src="%s'
                         'img/nocover_large.png" alt="No image yet">'
                         % (size[0], settings.STATIC_URL))
    img_url = get_box_scan_url(cover)

    (left, top), across, down = _box_sides(box)
    width = math.hypot(*across)
    height = math.hypot(*down)
    cross = across[0] * down[1] - across[1] * down[0]
    a = width * down[1] / cross
    b = -height * across[1] / cross
    c = -width * down[0] / cross
    d = height * across[0] / cross
    e = -(a * left + c * top)
    f = -(b * left + d * top)
    matrix = ' '.join('%.6g' % value for value in (a, b, c, d, e, f))

    frame = [0, 0, width, height]
    if proportion is not None:
        frame[3] = max(height, width * proportion)
        frame[2] = frame[3] / proportion
        frame[0] = (width - frame[2]) / 2
        frame[1] = (height - frame[3]) / 2
        axis = 0 if frame[2] > width else 1
        units = ((across[0] / width, across[1] / width),
                 (down[0] / height, down[1] / height))
        frame[axis] += _shift_inside(box, (left, top), units, frame, axis,
                                     -frame[axis])
    scale = min(size[0] / frame[2], size[1] / frame[3])
    return mark_safe(
      '<svg class="max-w-full" width="%.4g" viewBox="%.6g %.6g %.6g %.6g" '
      'role="img" aria-label="%s"><image href="%s" width="10000" height="%d" '
      'preserveAspectRatio="none" transform="matrix(%s)"/></svg>'
      % (frame[2] * scale, frame[0], frame[1], frame[2], frame[3],
         esc(alt_text), esc(img_url), box.scan_aspect, matrix))


def get_boxes_cover_tag(cover, numbered_boxes, alt_text, img_class=''):
    """
    Show a cover with character boxes drawn on it, each with its number,
    without JavaScript; numbered_boxes are pairs of number and box.

    The scan of get_box_scan_url is laid out 10000 units wide and as
    high as the current scan, in units of the same length on both axes as
    in get_box_tag: its proportions are those of a box drawn on it, else
    of the first box.  The width comes from img_class.  A deleted cover or
    one not shown on the site has no tag.
    """
    if cover.limit_display or cover.deleted or not numbered_boxes:
        return ''
    current = [box for _, box in numbered_boxes
               if box.scan_date == cover.last_upload]
    height = (current or [numbered_boxes[0][1]])[0].scan_aspect
    shapes = []
    for number, box in numbered_boxes:
        corners = (
          (box.top_left_x, box.top_left_y),
          (box.top_right_x, box.top_right_y),
          (box.top_right_x + box.bottom_left_x - box.top_left_x,
           box.top_right_y + box.bottom_left_y - box.top_left_y),
          (box.bottom_left_x, box.bottom_left_y))
        points = ' '.join('%d,%.6g' % (x, y * height / 10000)
                          for x, y in corners)
        centre_x = (box.top_right_x + box.bottom_left_x) / 2
        centre_y = (box.top_right_y + box.bottom_left_y) / 2 \
            * height / 10000
        shapes.append(
          '<polygon points="%s" class="text-red-600" fill="none" '
          'stroke="currentColor" stroke-width="2" '
          'vector-effect="non-scaling-stroke"/><text x="%.6g" y="%.6g" '
          'font-size="800" text-anchor="middle" dominant-baseline="middle" '
          'fill="white" stroke="black" stroke-width="60" '
          'paint-order="stroke">%d</text>'
          % (points, centre_x, centre_y, number))
    return mark_safe(
      '<svg class="%s" viewBox="0 0 10000 %d" role="img" aria-label="%s">'
      '<image href="%s" width="10000" height="%d" '
      'preserveAspectRatio="none"/>%s</svg>'
      % (esc(img_class), height, esc(alt_text),
         esc(get_box_scan_url(cover)), height, ''.join(shapes)))


def get_image_tags_per_issue(issue, alt_text, zoom_level, as_list=False,
                             variants=False, exclude_ids=None):
    if issue.has_covers() or (variants and issue.variant_covers().count()) \
      or (issue.variant_of and issue.variant_cover_status == 1):
        covers = issue.active_covers()
        if variants:
            covers = covers | issue.variant_covers()
    else:
        if as_list:
            return []
        else:
            return mark_safe(get_image_tag(cover=None, zoom_level=zoom_level,
                             alt_text=alt_text,
                             can_have_cover=issue.can_have_cover()))

    if exclude_ids:
        covers = covers.exclude(id__in=exclude_ids)
    if as_list:
        cover_tags = []
    else:
        tag = ''

    for cover in covers:
        if as_list:
            active = cover.revisions.filter(changeset__state__in=states.ACTIVE)
            alt_string = 'Cover for %s' % cover.issue.full_name()
            cover_tags.append([cover, issue,
                               get_image_tag(cover, alt_string, zoom_level),
                               active.count()])
        else:
            tag += get_image_tag(cover=cover, zoom_level=zoom_level,
                                 alt_text=alt_text)
    if as_list:
        return cover_tags
    else:
        return mark_safe(tag)


def get_image_tags_per_page(page, series=None):
    """
    Produces a list of cover tags for the covers in a page.
    Intended for use as a callback with paginate_response().
    """

    cover_tags = []
    for cover in page.object_list.select_related('issue__series__publisher'):
        issue = cover.issue
        alt_string = 'Cover for %s' % issue.full_name()
        cover_tags.append([cover, issue, get_image_tag(cover,
                                                       alt_string,
                                                       ZOOM_SMALL)])
    return cover_tags
