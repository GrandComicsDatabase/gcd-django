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

def get_image_tag(series_id, issue_id, alt_text, zoom_level):
    img_url = '<img src="" alt="' + alt_text + '"/>'

    cover = get_list_or_404(Cover, issue__id = issue_id)[0]
        
    if (zoom_level == ZOOM_SMALL):
        suffix = "%d/%d_%s.jpg" % (series_id, series_id, cover.code)
    else:

        suffix = "%d/" % series_id
        suffix = suffix + "%d00/" % zoom_level
        suffix = suffix + "%d_%d_%s.jpg" % (series_id, zoom_level, cover.code)
    try:
        img_url = _server_prefixes[cover.server_version] + suffix
        img = urlopen(img_url)
    except:
        # TODO: Figure out specific recoverable error.
        # TODO: Don't hardcode the number 2.
        cover.server_version = 2
        cover.save()
        img_url = _server_prefixes[cover.server_version] + suffix

    return '<img src="' + img_url + '" alt="' + alt_text + '"/>'

