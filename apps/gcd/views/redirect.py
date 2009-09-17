from django.http import HttpResponsePermanentRedirect


def publisher(request):
    """
    Redirects the lasso publisher page.
    """

    if 'id' in request.GET:
        return HttpResponsePermanentRedirect('/publisher/' + request.GET['id'])

    return HttpResponsePermanentRedirect("/")


def series(request):
    """
    Redirects the lasso series page.
    """

    if 'SeriesID' in request.GET:
        return HttpResponsePermanentRedirect('/series/' + request.GET['SeriesID'])

    return HttpResponsePermanentRedirect("/")


def series_status(request):
    """
    Redirects the lasso series index status page.
    """

    if 'SeriesID' in request.GET:
        return HttpResponsePermanentRedirect('/series/' + request.GET['SeriesID'] + '/status/')

    return HttpResponsePermanentRedirect("/")


def series_scans(request):
    """
    Redirects the lasso series scan status page.
    """

    if 'SeriesID' in request.GET:
        return HttpResponsePermanentRedirect('/series/' + request.GET['SeriesID'] + '/scans/')

    return HttpResponsePermanentRedirect("/")


def series_covers(request):
    """
    Redirects the lasso series cover page.
    """

    if 'SeriesID' in request.GET:
        return HttpResponsePermanentRedirect('/series/' + request.GET['SeriesID'] + '/covers/')

    return HttpResponsePermanentRedirect("/")


def issue(request):
    """
    Redirects the lasso issue page.
    """

    if 'id' in request.GET:
        return HttpResponsePermanentRedirect('/issue/' + request.GET['id'])

    return HttpResponsePermanentRedirect("/")


def issue_cover(request):
    """
    Redirects the lasso issue cover page.
    """

    # we don't bother about the zoom and show the large scan
    if 'id' in request.GET: 
        return HttpResponsePermanentRedirect('/issue/' + request.GET['id'] + '/cover/4/')

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
            search_type = '/number'
        else:
            search_type = '/' + request.GET['type']

        if 'sort' in request.GET:
             return HttpResponsePermanentRedirect(search_type + \
                    "/name/" + request.GET['query'] + '/sort/' + request.GET['sort'])
        else:
             return HttpResponsePermanentRedirect(search_type + \
                    "/name/" + request.GET['query'])

    return HttpResponsePermanentRedirect("/")

