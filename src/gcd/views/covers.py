import re
from urllib import urlopen

from django.conf import settings


def get_issue_image_tag(series_id, issue_id):
    """Either return a placeholder for the issue page's cover image, or
    find and link to the real image from the production GCD site.  At last
    resort, fake it all with an iframe that loads whole cover page.
    Ginormous hack until the method of mapping image locations is made
    available."""
    if (settings.FAKE_COVER_IMAGES):
        return "<img src=\"" + settings.MEDIA_URL + \
               "/img/placeholder_small.jpg\"/>"

    gcd_page = urlopen("http://www.comics.org/details.lasso?id=%s" % issue_id)

    match = None
    image_source = None
    image_number = None
    image_tag = None
    for line in gcd_page:
        match = re.search(\
          "http://www.comics.org/graphics/covers/%s/%s_\d+.jpg" %
          (series_id, series_id), line)
        if (match):
            image_source = match.group(0)
            image_tag = "<img src=\"%s\"/>" % image_source
            break

    gcd_page.close()
    if (not image_tag):
        # TODO: No standalone page for the smallest size, so this
        # TODO: returns an iframe that is too big.  For now.
        # TODO: Hopefully we never get here anyway.
        image_tag = "<iframe src=\"http://www.comics.org/coverview.lasso?" \
                    "id=%s&zoom=4\" height=346 frameborder=0 scrolling=no>" \
                    "</iframe>" % issue_id
    return image_tag


def get_series_image_tag(series_id):
    """Either return a placeholder for the series page's cover image, or
    find and link to the real image from the production GCD site.  At last
    resort, fake it all with an iframe that loads whole cover page.
    Ginormous hack until the method of mapping image locations is made
    available."""

    if (settings.FAKE_COVER_IMAGES):
        return "<img src=\"" + settings.MEDIA_URL + \
               "/img/placeholder_medium.jpg\"/>"

    gcd_page = urlopen("http://www.comics.org/series.lasso?SeriesID=%s" % \
                       series_id)

    match = None
    image_source = None
    image_number = None
    image_tag = None
    for line in gcd_page:
        match = re.search("http://www.comics.org/graphics/covers/%s/200/" \
                          "%s_2_\d+.jpg" % (series_id, series_id), line)
        if (match):
            image_source = match.group(0)
            image_tag = "<img src=\"%s\"/>" % image_source
            break

    gcd_page.close()
    if (not image_tag):
        image_tag = "<iframe src=\"http://www.comics.org/coverview.lasso?" \
                    "id=%s&zoom=2\" height=346 frameborder=0 scrolling=no>" \
                    "</iframe>" % series_id
    return image_tag

