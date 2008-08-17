"""View methods for pages displaying entity details."""

import re
from urllib import urlopen

from django.db.models import Q
from django.conf import settings
from django.core.paginator import QuerySetPaginator
from django.shortcuts import render_to_response, \
                             get_object_or_404, \
                             get_list_or_404
from django.http import HttpResponseRedirect

from apps.gcd.models import Publisher, Series, Issue, Story, \
                            Country, Language, Indexer, IndexCredit, Cover
from apps.gcd.views.covers import get_image_tag, \
                                  ZOOM_SMALL, \
                                  ZOOM_MEDIUM, \
                                  ZOOM_LARGE

def get_style(request):
    style = 'default'
    if (request.GET.has_key('style')):
        style = request.GET['style']
    return style

def publisher(request, publisher_id):
    """Display the details page for a Publisher."""

    style = get_style(request)
    publisher = get_object_or_404(Publisher, id = publisher_id)
    p = QuerySetPaginator(publisher.series_set.order_by('name'), 100)
    page_num = 1
    if (request.GET.has_key('page')):
        page_num = int(request.GET['page'])
    page = p.page(page_num)

    vars = { 'publisher' : publisher,
             'page' : page,
             'paginator' : p,
             'page_number' : page_num,
             'style' : style,
             'media_url' : settings.MEDIA_URL }
    return render_to_response('gcd/publisher.html', vars)

def imprint(request, imprint_id):
    """Display the details page for an Imprint."""

    style = get_style(request)
    imprint = get_object_or_404(Publisher, id = imprint_id)
    p = QuerySetPaginator(imprint.imprint_series_set.order_by('name'), 100)
    page_num = 1
    if (request.GET.has_key('page')):
        page_num = int(request.GET['page'])
    page = p.page(page_num)

    vars = { 'publisher' : imprint,
             'page' : page,
             'paginator' : p,
             'page_number' : page_num,
             'style' : style,
             'media_url' : settings.MEDIA_URL }
    return render_to_response('gcd/publisher.html', vars)

def imprints(request, publisher_id):
    """Finds imprints of a publisher.  Imprints are defined as those
    publishers whose parent_id matches the given publisher."""

    publisher = get_object_or_404(Publisher, id = publisher_id)
    imps = publisher.imprint_set.all()

    # TODO: Re-add sort stuff dropped whem moved here from search.py
    # if (sort == ORDER_ALPHA):
    imps = imps.order_by('name', 'year_began')
    # elif (sort == ORDER_CHRONO):
    #    pubs = pubs.order_by('year_began', 'name')

    style = get_style(request)
    return render_to_response('gcd/imprints.html', {
      'publisher' : publisher,
      'imprints' : imps,
      'style' : style,
      'media_url' : settings.MEDIA_URL })

def series(request, series_id):
    """Display the details page for a series."""
    
    series = get_object_or_404(Series, id = series_id)
    covers = series.cover_set.select_related('issue')
    
    # if just one issue display extended issue page
    if series.issue_count == 1:
        return issue(request,covers[0].issue.id)
    
    try:
        cover = covers.filter(has_image = '1')[0]
    except IndexError:
        cover = covers[0]
        
    try:
        country = Country.objects.get(code__iexact = series.country_code).name
    except:
        country = series.country_code
    image_tag = get_image_tag(series_id = int(series_id),
                              cover = cover,
                              zoom_level = ZOOM_MEDIUM,
                              alt_text = 'First Issue Cover')

    # TODO: Fix language table hookup- why is this not a foreign key?
    # For now if we can't get a match in the table then just use the
    # code as itis.
    language = series.language_code
    try:
        lobj = Language.objects.get(code__iexact = series.language_code)
        language = lobj.name
    except:
        pass

    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = 12

    style = get_style(request)

    return render_to_response('gcd/series.html', {
      'series' : series,
      'covers' : covers,
      'image_tag' : image_tag,
      'country' : country,
      'language' : language,
      'table_width': table_width,
      'style' : style,
      'media_url' : settings.MEDIA_URL })

def status(request, series_id):
    """Display the index status matrix for a series."""

    series = get_object_or_404(Series, id = series_id)
    # Cover sort codes are more reliable than issue key dates,
    # and the 'select_related' optimization only works in this direction.
    covers = series.cover_set.select_related('issue')

    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = 12
    style = get_style(request)

    return render_to_response('gcd/status.html', {
      'series' : series,
      'covers' : covers,
      'table_width' : table_width,
      'style' : style,
      'media_url' : settings.MEDIA_URL })

def scans(request, series_id):
    """Display the cover scan status matrix for a series."""

    series = get_object_or_404(Series, id = series_id)
    covers = series.cover_set.select_related('issue')

    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = 12
    style = get_style(request)

    return render_to_response('gcd/scans.html', {
      'series' : series,
      'covers' : covers,
      'table_width' : table_width,
      'style' : style,
      'media_url' : settings.MEDIA_URL })

def covers_to_replace(request, style="default"):
    """Display the covers to replace."""

    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = 5

    cover_tags = []
    covers = Cover.objects.filter(marked = True)
    covers = covers.order_by("issue__series__name",
                             "issue__series__year_began",
                             "issue__key_date")
    p = QuerySetPaginator(covers, 50)

    page_num = 1
    if (request.GET.has_key('page')):
        page_num = int(request.GET['page'])
    page = p.page(page_num)

    for cover in page.object_list:
        issue = cover.issue
        alt_string = cover.series.name + ' #' + issue.number
        cover_tags.append([cover, issue, get_image_tag(issue.series.id,
                                                       cover,
                                                       alt_string,
                                                       ZOOM_SMALL)])


    style = get_style(request)

    return render_to_response('gcd/covers_to_replace.html', {
      'tags' : cover_tags,
      'table_width' : table_width,
      'page' : page,
      'paginator' : p,
      'page_number' : page_num,
      'style' : style,
      'media_url' : settings.MEDIA_URL })

def cover(request, issue_id, size):
    """Display the cover for a single issue on its own page."""

    issue = get_object_or_404(Issue, id = issue_id)
    cover = issue.cover
    [prev_issue, next_issue] = get_prev_next_issue(issue.series, cover)

    cover_tag = get_image_tag(issue.series_id, cover,
                              "Cover Image", int(size))
    style = get_style(request)

    extra = 'cover/' + size + '/' # TODO: remove abstraction-breaking hack.

    return render_to_response('gcd/cover.html', {
      'issue' : issue,
      'prev_issue' : prev_issue,
      'next_issue' : next_issue,
      'cover_tag' : cover_tag,
      'extra' : extra,
      'style' : style,
      'media_url' : settings.MEDIA_URL })

def covers(request, series_id, style="default"):
    """Display the index status matrix for a series."""

    series = get_object_or_404(Series, id = series_id)
    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = 5

    cover_tags = []
    p = QuerySetPaginator(series.cover_set.select_related('issue') \
        .filter(has_image = '1'), 50)
    page_num = 1
    if (request.GET.has_key('page')):
        page_num = int(request.GET['page'])
    page = p.page(page_num)

    for cover in page.object_list:
        issue = cover.issue
        alt_string = series.name + ' #' + issue.number
        cover_tags.append([cover, issue, get_image_tag(series.id,
                                                       cover,
                                                       alt_string,
                                                       ZOOM_SMALL)])


    style = get_style(request)

    return render_to_response('gcd/covers.html', {
      'series' : series,
      'tags' : cover_tags,
      'table_width' : table_width,
      'page' : page,
      'paginator' : p,
      'page_number' : page_num,
      'style' : style,
      'media_url' : settings.MEDIA_URL })

def issue_form(request):
    """Redirect form-style URL used by the drop-down menu on the series
    details page into a standard issue details URL.  There is probably
    a better way to propagate the 'style' parameter."""
    return HttpResponseRedirect("/gcd/issue/" + request.GET["id"] + \
                                "/?style=" + request.GET["style"])

def get_prev_next_issue(series, cover):
    prev_issue = None
    next_issue = None
    if cover.code != None:
        # Get sorted cover_set for series and find previous and next issue
        # TODO:  It would be more efficient to store next/prev issue ids
        # in the the issue DB record and avoid these queries.
        cover_list = series.cover_set.all()
    
        earlier_covers = \
          series.cover_set.filter(code__lt = cover.code)
        earlier_covers = earlier_covers.order_by('-code')
        
        later_covers = series.cover_set.filter(code__gt = cover.code)
        later_covers = later_covers.order_by('code')
        
        # covers <-> issues is not really one-to-one.  Selecting back
        # along a one-to-one relationship when the other side is not
        # present seems to lead to Django attempting to select the
        # entire table.  Carefully saving off the issue's ID and then
        # filtering (*not* getting) that issue correctly deals with 
        # nonexistant issues.  
        # TODO: Find a less fragile solution.  Or fix the database.
        try:
            earlier_id = earlier_covers[0].issue_id
            earlier_list = Issue.objects.filter(id=earlier_id)
            prev_issue = earlier_list[0]
        except IndexError:
            pass
        try:
            later_id = later_covers[0].issue_id
            later_list = Issue.objects.filter(id=later_id)
            next_issue = later_list[0]
        except IndexError:
            pass

    return [prev_issue, next_issue]

def issue(request, issue_id):
    """Display the issue details page, including story details."""
    issue = get_object_or_404(Issue, id = issue_id)
    cover = issue.cover
    image_tag = get_image_tag(series_id=issue.series.id,
                              cover=cover,
                              zoom_level=ZOOM_SMALL,
                              alt_text='Cover Thumbnail')
    style = get_style(request)

    series = issue.series
    [prev_issue, next_issue] = get_prev_next_issue(series, cover)

    linkify_reprints = None
    if (request.GET.has_key('reprints')):
        linkify_reprints = request.GET['reprints']

    if issue.index_status <= 1: # only skeleton
        # TODO: create a special empty page (with the cover if existing)
        # TODO: could vary accord. to (un)reserved/part.indexed/submitted
        return render_to_response('gcd/issue.html', {
          'issue' : issue,
          'prev_issue' : prev_issue,
          'next_issue' : next_issue,
          'image_tag' : image_tag,
          'style' : style,
          'linkify_reprints' : linkify_reprints,
          'media_url' : settings.MEDIA_URL })
    
    
    # TODO: Since the number of stories per issue is typically fairly small,
    # it seems more efficient to grab the whole list and only do one database
    # query rather than separately select the cover story and the interior
    # stories.  But we should measure this.  Note that we definitely want
    # to send the cover and interior stories to the UI separately, as the
    # UI should not be concerned with the designation of story 0 as the cover.
    stories = list(issue.story_set.order_by('sequence_number'))

    # credits = Indexer.objects.filter(iissue.series.index_credit_set.filter(
    
    return render_to_response('gcd/issue.html', {
      'issue' : issue,
      'prev_issue' : prev_issue,
      'next_issue' : next_issue,
      'cover_story' : stories.pop(0), # cover_story,
      'stories' : stories,
      'image_tag' : image_tag,
      'style' : style,
      'linkify_reprints' : linkify_reprints,
      'media_url' : settings.MEDIA_URL })

