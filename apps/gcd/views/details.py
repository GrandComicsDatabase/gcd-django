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
                            Country, Language, Indexer, IndexCredit
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
    country = Country.objects.get(code__iexact = series.country_code)
    image_tag = get_image_tag(series_id = int(series_id),
                              issue_id = series.issue_set.all()[0].id,
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
      'image_tag' : image_tag,
      'country' : country.name or series.country_code,
      'language' : language,
      'table_width': table_width,
      'style' : style,
      'media_url' : settings.MEDIA_URL })

def status(request, series_id):
    """Display the index status matrix for a series."""

    series = get_object_or_404(Series, id = series_id)
    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = 12
    style = get_style(request)

    return render_to_response('gcd/status.html', {
      'series' : series,
      'table_width' : table_width,
      'style' : style,
      'media_url' : settings.MEDIA_URL })

def scans(request, series_id):
    """Display the cover scan status matrix for a series."""

    series = get_object_or_404(Series, id = series_id)
    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = 12
    style = get_style(request)

    return render_to_response('gcd/scans.html', {
      'series' : series,
      'table_width' : table_width,
      'style' : style,
      'media_url' : settings.MEDIA_URL })

def cover(request, issue_id, size):
    """Display the cover for a single issue on its own page."""

    issue = get_object_or_404(Issue, id = issue_id)
    [prev_issue, next_issue] = get_prev_next_issue(issue.series, issue)

    cover_tag = get_image_tag(issue.series_id, issue_id,
                              "Cover Image", int(size))
    style = get_style(request)

    extra = '/cover/' + size + '/' # TODO: remove abstraction-breaking hack.

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
    p = QuerySetPaginator(series.cover_set.all(), 50)
    page_num = 1
    if (request.GET.has_key('page')):
        page_num = int(request.GET['page'])
    page = p.page(page_num)

    for cover in page.object_list:
        issue = cover.issue
        alt_string = series.name + ' #' + issue.number
        cover_tags.append([cover, issue, get_image_tag(series.id,
                                                       issue.id,
                                                       alt_string,
                                                       ZOOM_SMALL,
                                                       cover)])


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

def get_prev_next_issue(series, issue):
    prev_issue = None
    next_issue = None
    if issue.key_date:
        # Get sorted issue_set for series and find previous and next issue
        # TODO:  It would be more efficient to store next/prev issue ids
        # in the the issue DB record and avoid these queries.
        issue_list = series.issue_set.all().order_by('key_date')
    
        earlier_issues = \
          series.issue_set.filter(key_date__lt = issue.key_date)
        earlier_issues = earlier_issues.order_by('-key_date')
        
        later_issues = series.issue_set.filter(key_date__gt = issue.key_date)
        later_issues = later_issues.order_by('key_date')
        
        try:
            prev_issue = earlier_issues[0]
        except IndexError:
            prev_issue = None
        try:
            next_issue = later_issues[0]
        except IndexError:
            next_issue = None

    return [prev_issue, next_issue]

def issue(request, issue_id):
    """Display the issue details page, including story details."""
    issue = get_object_or_404(Issue, id = issue_id)
    image_tag = get_image_tag(series_id = issue.series.id,
                              issue_id = int(issue_id),
                              zoom_level = ZOOM_SMALL,
                              alt_text = 'Cover Thumbnail')
    style = get_style(request)

    # prev_issue = None
    # next_issue = None
    series = issue.series
    [prev_issue, next_issue] = get_prev_next_issue(series, issue)

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

