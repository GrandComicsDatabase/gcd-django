import re
from django.http import HttpResponsePermanentRedirect


def _find_key(request, key='SeriesID'):
    matches = filter(lambda k: re.match('%s$' %key, k, re.IGNORECASE), request.GET.keys())
    if len(matches) > 0:
        return request.GET[matches[0]]


def publisher(request):
    """
    Redirects the lasso publisher page.
    """

    get_id = _find_key(request,'id')

    if get_id: 
        return HttpResponsePermanentRedirect('/publisher/' + get_id)

    return HttpResponsePermanentRedirect("/")


def series(request):
    """
    Redirects the lasso series page.
    """
    
    get_id = _find_key(request)

    if get_id: 
        return HttpResponsePermanentRedirect('/series/' + get_id)

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
        return HttpResponsePermanentRedirect('/issue/' + get_id)

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
        return HttpResponsePermanentRedirect('/daily_covers/' + request.GET['date'])

    return HttpResponsePermanentRedirect("/daily_covers/")


def search(request):
    """
    Redirects the lasso search result page.
    """

    if 'type' in request.GET and 'query' in request.GET:
        # letters becomes letterer
        if request.GET['type'] == 'letters':
            search_type = '/letterer'
        # colors becomes colorist
        elif request.GET['type'] == 'colors':
            search_type = '/colorist'
        # title becomes series
        elif request.GET['type'] == 'title':
            search_type = '/series'
        # jobno becomes job_number
        elif request.GET['type'] == 'jobno':
            search_type = '/job_number'
        else:
            search_type = '/' + request.GET['type']

        if 'sort' in request.GET:
             return HttpResponsePermanentRedirect(search_type + \
                    "/name/" + request.GET['query'] + '/sort/' + request.GET['sort'])
        else:
             return HttpResponsePermanentRedirect(search_type + \
                    "/name/" + request.GET['query'])

    return HttpResponsePermanentRedirect("/")

