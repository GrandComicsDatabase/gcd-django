"""
This module implements views which issue permanent redirects for URLs
that were used with the old, Lasso-based site.
"""
import re
from urllib.parse import quote
from django.http import HttpResponsePermanentRedirect


def _find_key(request, key='SeriesID'):
    matches = [k for k in list(request.GET) if re.match('%s$' %key, k, re.IGNORECASE)]
    if len(matches) > 0:
        return request.GET[matches[0]]


def publisher(request):
    """
    Redirects the lasso publisher page.
    """

    get_id = _find_key(request,'id')

    if get_id:
        return HttpResponsePermanentRedirect('/publisher/' + get_id + '/')

    return HttpResponsePermanentRedirect("/")

def series(request):
    """
    Redirects the lasso series page.
    """

    get_id = _find_key(request)

    if get_id:
        return HttpResponsePermanentRedirect('/series/' + get_id + '/')

    return HttpResponsePermanentRedirect("/")


def series_status(request):
    """
    Redirects the lasso series index status page.
    """

    get_id = _find_key(request)

    if get_id:
        return HttpResponsePermanentRedirect('/series/' + get_id + '/status/')

    return HttpResponsePermanentRedirect("/")


def series_scans(request):
    """
    Redirects the lasso series scan status page.
    """

    get_id = _find_key(request)

    if get_id:
        return HttpResponsePermanentRedirect('/series/' + get_id + '/scans/')

    return HttpResponsePermanentRedirect("/")


def series_covers(request):
    """
    Redirects the lasso series cover page.
    """

    get_id = _find_key(request)

    if get_id:
        return HttpResponsePermanentRedirect('/series/' + get_id + '/covers/')

    return HttpResponsePermanentRedirect("/")


def issue(request):
    """
    Redirects the lasso issue page.
    """

    get_id = _find_key(request,'id')

    if get_id:
        return HttpResponsePermanentRedirect('/issue/' + get_id + '/')

    return HttpResponsePermanentRedirect("/")


def issue_cover(request):
    """
    Redirects the lasso issue cover page.
    """

    get_id = _find_key(request,'id')

    # we don't bother about the zoom and show the large scan
    if get_id:
        return HttpResponsePermanentRedirect('/issue/' + get_id + '/cover/4/')

    return HttpResponsePermanentRedirect("/")


def daily_covers(request):
    """
    Redirects the lasso daily cover page.
    """

    if 'date' in request.GET:
        return HttpResponsePermanentRedirect(
          '/daily_covers/' + request.GET['date'] + '/')

    return HttpResponsePermanentRedirect("/daily_covers/")


def adjust_lasso_type(lasso_type):
    # letters becomes letterer
    if lasso_type == 'letters':
        return 'letterer'
    # colors becomes colorist
    elif lasso_type == 'colors':
        return 'colorist'
    # title becomes series
    elif lasso_type == 'title':
        return 'series'
    # jobno becomes job_number
    elif lasso_type == 'jobno':
        return 'job_number'
    else:
        return lasso_type

def search(request):
    """
    Redirects the lasso search result page.
    """

    if 'type' in request.GET and 'query' in request.GET:
        search_type = '/' + adjust_lasso_type(request.GET['type'])

        if 'sort' in request.GET:
             return HttpResponsePermanentRedirect(search_type + \
                    "/name/" + quote(request.GET['query'].encode('utf-8')) + \
                    '/sort/' + request.GET['sort'] + '/')
        else:
             return HttpResponsePermanentRedirect(search_type + \
                    "/name/" + quote(request.GET['query'].encode('utf-8')) + '/')

    return HttpResponsePermanentRedirect("/")

