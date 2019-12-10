# -*- coding: utf-8 -*-
from urllib.parse import quote

from django.conf import settings
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from apps.gcd.models import Issue
from apps.gcd.models.cover import ZOOM_SMALL, ZOOM_MEDIUM, ZOOM_LARGE
from apps.oi import states

def get_generic_image_tag(image, alt_text):
    img_class = 'cover_img'
    try:
        width = min(image.image_file.width, 400)
    except IOError:
        width = 0
    return mark_safe('<img src="' + image.scaled_image.url + '?' + \
                     str(hash(image.modified)) + '" alt="' + esc(alt_text) \
                     + '" ' + ' class="' + img_class + '" width="' + str(width) + '"/>')

def get_image_tag(cover, alt_text, zoom_level, can_have_cover=True):
    img_class = 'cover_img'
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

    if not can_have_cover:
        return mark_safe('<img class="no_cover" src="' + settings.STATIC_URL + \
            'img/noupload_' + size +'.png" alt="No image"' + \
            'class="cover_img">')

    if cover is None:
        return mark_safe('<img class="no_cover" src="' + settings.STATIC_URL + \
            'img/nocover_' + size +'.png" alt="No image yet"' + \
            'class="cover_img">')

    if cover.limit_display and zoom_level != ZOOM_SMALL:
        # TODO: Make 'cannot display due to...' image and use here
        return mark_safe('<img class="no_cover" src="' + settings.STATIC_URL + \
               'img/nocover_' + size +'.png" alt="No image yet"' + \
               'class="cover_img">')

    if settings.FAKE_IMAGES:
        return mark_safe('<img src="' +settings.STATIC_URL + \
               'img/placeholder_' + size + '.jpg"' + \
               'class="cover_img">')

    img_url = cover.get_base_url()+("/w%d/%d.jpg" % (width, cover.id))

    # For replacement and variant cover uploads we should make sure that no
    # cached cover is displayed. Adding a changing query string seems the
    # prefered solution found on the net.
    img_url = img_url + '?' + str(hash(cover.last_upload))

    return mark_safe('<img src="' + img_url + '" alt="' + esc(alt_text) + \
           '" ' + ' class="' + img_class + '"/>')


def get_image_tags_per_issue(issue, alt_text, zoom_level, as_list=False,
                             variants=False, exclude_ids=None):
    if issue.has_covers() or (variants and issue.variant_covers().count()):
        covers = issue.active_covers()
        if variants:
            covers = covers | issue.variant_covers()
    else:
        return mark_safe(get_image_tag(cover=None, zoom_level=zoom_level,
                    alt_text=alt_text,
                    can_have_cover=issue.can_have_cover()))

    if exclude_ids:
        covers = covers.exclude(id__in=exclude_ids)
    if as_list:
        cover_tags = []
        alt_string = 'Cover for %s' % issue.full_name()
    else:
        tag = ''

    for cover in covers:
        if as_list:
            active = cover.revisions.filter(changeset__state__in=states.ACTIVE)
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
    cover_series=series
    for cover in page.object_list.select_related('issue__series__publisher'):
        if series is None:
            cover_series = cover.issue.series
        issue = cover.issue
        alt_string = 'Cover for %s' % issue.full_name()
        cover_tags.append([cover, issue, get_image_tag(cover,
                                                       alt_string,
                                                       ZOOM_SMALL)])
    return cover_tags

