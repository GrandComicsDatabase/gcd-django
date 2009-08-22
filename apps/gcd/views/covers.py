import re
from urllib import urlopen

from django.conf import settings
from django.shortcuts import get_list_or_404, \
                             get_object_or_404

from apps.gcd.models import Cover, Series

ZOOM_SMALL = 1
ZOOM_MEDIUM = 2
ZOOM_LARGE = 4

# Entries in this tuple match the server_version column of the covers table.
# Note that there is no sever version 0 recorded.
_server_prefixes = ['',
                    'http://www.comics.org/graphics/covers/',
                    'http://www.gcdcovers.com/graphics/covers/']

def get_image_tag(series_id, cover, alt_text, zoom_level):
    if cover is None:
        return '<img class="no_cover" src="' + _server_prefixes[2] + \
               'nocover.gif" alt="No image yet" class="cover_img"/>'

    if settings.FAKE_COVER_IMAGES:
        if zoom_level == ZOOM_SMALL:
            return '<img src="' +settings.MEDIA_URL + \
                   'img/placeholder_small.jpg" width="100" class="cover_img"/>'
        if zoom_level == ZOOM_MEDIUM:
            return '<img src="' + settings.MEDIA_URL + \
                   'img/placeholder_medium.jpg" width="200" class="cover_img"/>'
        if zoom_level == ZOOM_LARGE:
            return '<img src="' + settings.MEDIA_URL + \
                   'img/placeholder_large.jpg" width="400" class="cover_img"/>'

    width = ''
    if zoom_level == ZOOM_SMALL:
        width = 'width="100"'
    elif zoom_level == ZOOM_MEDIUM:
        width = 'width="200"'
    elif zoom_level == ZOOM_LARGE:
        width = 'width="400"'

    img_url = ('<img src="" alt="' +
               alt_text +
               '" ' +
               width +
               ' class="cover_img"/>')

    if (zoom_level == ZOOM_SMALL):
        if not (cover.has_image):
            return '<img class="no_cover" src="' + _server_prefixes[2] + \
                   'nocover.gif" alt="No image yet" class="cover_img"/>'
        suffix = "%d/%d_%s.jpg" % (series_id, series_id, cover.code)
    else:
        suffix = "%d/" % series_id
        suffix = suffix + "%d00/" % zoom_level
        suffix = suffix + "%d_%d_%s.jpg" % (series_id, zoom_level, cover.code)

    # For now trust the DB on the graphics server.  This will sometimes
    # be wrong but is *MUCH* faster.
    img_url = _server_prefixes[cover.server_version] + suffix
    # try:
        # img_url = _server_prefixes[cover.server_version] + suffix
        # img = urlopen(img_url)
    # except:
        # TODO: Figure out specific recoverable error.
        # TODO: Don't hardcode the number 2.
        # cover.server_version = 2
        # cover.save()
        # img_url = _server_prefixes[cover.server_version] + suffix

    return '<img src="' + img_url + '" alt="' + alt_text + \
           '" ' + width + ' class="cover_img"/>'

def get_image_tags_per_page(page, series=None):
    """
    Produces a list of cover tags for the covers in a page.
    Intended for use as a callback with paginate_response().
    """

    cover_tags = []
    cover_series=series
    for cover in page.object_list:
        if series is None:
            cover_series = cover.series
        issue = cover.issue
        alt_string = cover_series.name + ' #' + issue.number
        cover_tags.append([cover, issue, get_image_tag(cover_series.id,
                                                       cover,
                                                       alt_string,
                                                       ZOOM_SMALL)])
    return cover_tags

