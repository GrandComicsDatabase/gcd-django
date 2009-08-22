"""View methods for pages displaying entity details."""

import re
from urllib import urlopen
from datetime import date, timedelta

from django.db.models import Q
from django.conf import settings
from django.core import urlresolvers
from django.core.paginator import QuerySetPaginator
from django.shortcuts import render_to_response, \
                             get_object_or_404, \
                             get_list_or_404
from django.http import HttpResponseRedirect
from django.template import RequestContext

from apps.gcd.models import Publisher, Series, Issue, Story, \
                            Country, Language, Indexer, IndexCredit, Cover
from apps.gcd.views import paginate_response, ORDER_ALPHA, ORDER_CHRONO
from apps.gcd.views.covers import get_image_tag, \
                                  get_image_tags_per_page, \
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
    pub = get_object_or_404(Publisher, id = publisher_id)

    vars = { 'publisher' : pub,
             'style' : style,
             'media_url' : settings.MEDIA_URL }
    return paginate_response(request, pub.series_set.order_by('name'),
                             'gcd/details/publisher.html', vars)

def imprint(request, imprint_id):
    """
    Display the details page for an Imprint.
    """

    style = get_style(request)
    imprint = get_object_or_404(Publisher, id = imprint_id)
    imprint_series = imprint.imprint_series_set.order_by('name')

    vars = { 'publisher' : imprint, 'style' : style }
    return paginate_response(request,
                             imprint_series,
                             'gcd/details/publisher.html',
                             vars)

def imprints(request, publisher_id):
    """
    Finds imprints of a publisher.  Imprints are defined as those
    publishers whose parent_id matches the given publisher.
    """

    publisher = get_object_or_404(Publisher, id = publisher_id)
    imps = publisher.imprint_set.all()

    sort = ORDER_ALPHA
    if 'sort' in request.GET:
        sort = request.GET['sort']

    if (sort == ORDER_CHRONO):
        imps = imps.order_by('year_began', 'name')
    else:
        imps = imps.order_by('name', 'year_began')

    style = get_style(request)
    return paginate_response(request, imps, 'gcd/details/imprints.html', {
      'publisher' : publisher,
      'imprints' : imps,
      'style' : style })

def series(request, series_id):
    """
    Display the details page for a series.
    """
    
    series = get_object_or_404(Series, id = series_id)
    covers = series.cover_set.select_related('issue')
    
    try:
        cover = covers.filter(has_image = '1')[0]
    except IndexError:
        try:
            cover = covers[0]
        except IndexError:
            cover = None
        
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

    return render_to_response(
      'gcd/details/series.html',
      {
        'series' : series,
        'covers' : covers,
        'image_tag' : image_tag,
        'country' : country,
        'language' : language,
        'table_width': table_width,
        'style' : style
      },
      context_instance=RequestContext(request))

def status(request, series_id):
    """Display the index status matrix for a series."""

    series = get_object_or_404(Series, id = series_id)
    # Cover sort codes are more reliable than issue key dates,
    # and the 'select_related' optimization only works in this direction.
    covers = series.cover_set.select_related('issue')

    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = 12
    style = get_style(request)

    return render_to_response('gcd/status/status.html', {
      'series' : series,
      'covers' : covers,
      'table_width' : table_width,
      'style' : style },
      context_instance=RequestContext(request))

def scans(request, series_id):
    """
    Display the cover scan status matrix for a series.
    """

    series = get_object_or_404(Series, id = series_id)
    covers = series.cover_set.select_related('issue')

    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = 12
    style = get_style(request)

    return render_to_response('gcd/status/scans.html', {
      'series' : series,
      'covers' : covers,
      'table_width' : table_width,
      'style' : style },
      context_instance=RequestContext(request))

def covers_to_replace(request, starts_with=None, style="default"):
    """
    Display the covers that are marked for replacement.
    """

    covers = Cover.objects.filter(marked = True)
    if starts_with:
        covers = covers.filter(issue__series__name__startswith = starts_with)
    covers = covers.order_by("issue__series__name",
                             "issue__series__year_began",
                             "issue__key_date")

    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = 5
    style = get_style(request)

    return paginate_response(
      request,
      covers,
      'gcd/status/covers_to_replace.html',
      {
        'table_width' : table_width,
        'style' : style,
        'starts_with' : starts_with
      },
      page_size=50,
      callback_key='tags',
      callback=get_image_tags_per_page)


def daily_covers(request, show_date=None):
    """
    Produce a page displaying the covers uploaded on a given day.
    """

    requested_date = None
    try:
        if 'day' in request.GET:
            year = int(request.GET['year'])
            month = int(request.GET['month'])
            day = int(request.GET['day'])

        elif show_date:
            year = int(show_date[0:4])
            month = int(show_date[5:7])
            day = int(show_date[8:10])

        else:
            # Don't redirect, as this is a proper default.
            requested_date = date.today()

        if requested_date is None:
            requested_date = date(year, month, day)

    except (TypeError, ValueError):
        # Redirect so the user sees the date in the URL that matches
        # the output, instead of seeing the erroneous date.
        return HttpResponseRedirect(
          urlresolvers.reverse(
            issue,
            kwargs={ 'show_date': date.today().strftime('%Y-%m-%d') }))

    date_before = requested_date + timedelta(-1)
    if requested_date <= date.today():
        date_after = requested_date + timedelta(1)
    else:
        date_after = None

    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = 5
    style = get_style(request)
    covers = Cover.objects.filter(modified=requested_date)
    covers = covers.order_by("issue__series__publisher__name",
                             "issue__series__name",
                             "issue__series__year_began",
                             "issue__number")

    return paginate_response(
      request,
      covers,
      'gcd/status/daily_covers.html',
      {
        'date' : show_date,
        'date_after' : date_after,
        'date_before' : date_before,
        'table_width' : table_width,
        'style' : style,
      },
      page_size=50,
      callback_key='tags',
      callback=get_image_tags_per_page)
    
    
def cover(request, issue_id, size):
    """
    Display the cover for a single issue on its own page.
    """

    issue = get_object_or_404(Issue, id = issue_id)
    cover = issue.cover
    [prev_issue, next_issue] = get_prev_next_issue(issue.series, cover)

    cover_tag = get_image_tag(issue.series_id, cover,
                              "Cover Image", int(size))
    style = get_style(request)

    extra = 'cover/' + size + '/' # TODO: remove abstraction-breaking hack.

    return render_to_response(
      'gcd/details/cover.html',
      {
        'issue' : issue,
        'prev_issue' : prev_issue,
        'next_issue' : next_issue,
        'cover_tag' : cover_tag,
        'extra' : extra,
        'style' : style
      },
      context_instance=RequestContext(request)
    )

def covers(request, series_id, style="default"):
    """
    Display the index status matrix for a series.
    """

    series = get_object_or_404(Series, id = series_id)
    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = 5

    covers =series.cover_set.select_related('issue').filter(has_image = '1')
    style = get_style(request)
    vars = {
      'series' : series,
      'table_width' : table_width,
      'style' : style,
    }

    return paginate_response(request, covers, 'gcd/details/covers.html', vars,
      page_size=50,
      callback_key='tags',
      callback=lambda page: get_image_tags_per_page(page, series))

def issue_form(request):
    """
    Redirect form-style URL used by the drop-down menu on the series
    details page into a standard issue details URL.  There is probably
    a better way to propagate the 'style' parameter.
    """
    params = request.GET.copy()
    id = params['id']
    del params['id']
    return HttpResponseRedirect(
      urlresolvers.reverse(issue, kwargs={ 'issue_id': id }) +
      '?' + params.urlencode())

def get_prev_next_issue(series, cover):
    """
    Find the issues immediately before and after the issue with the given cover.
    """

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
    """
    Display the issue details page, including story details.
    """
    issue = get_object_or_404(Issue, id = issue_id)
    cover = issue.cover
    image_tag = get_image_tag(series_id=issue.series.id,
                              cover=cover,
                              zoom_level=ZOOM_SMALL,
                              alt_text='Cover Thumbnail')
    style = get_style(request)

    series = issue.series
    [prev_issue, next_issue] = get_prev_next_issue(series, cover)

    if issue.index_status <= 1: # only skeleton
        # TODO: create a special empty page (with the cover if existing)
        # TODO: could vary accord. to (un)reserved/part.indexed/submitted
        pass
    
    # TODO: Since the number of stories per issue is typically fairly small,
    # it seems more efficient to grab the whole list and only do one database
    # query rather than separately select the cover story and the interior
    # stories.  But we should measure this.  Note that we definitely want
    # to send the cover and interior stories to the UI separately, as the
    # UI should not be concerned with the designation of story 0 as the cover.
    stories = list(issue.story_set.order_by('sequence_number'))

    cover_story = None
    if (len(stories) > 0):
        cover_stories = stories.pop(0)
    return render_to_response(
      'gcd/details/issue.html',
      {
        'issue' : issue,
        'prev_issue' : prev_issue,
        'next_issue' : next_issue,
        'cover_story' : cover_story,
        'stories' : stories,
        'image_tag' : image_tag,
        'style' : style,
      },
      context_instance=RequestContext(request))


def last_updated(request, number = 5):
    """
    Display the <number> last updated indexes
    """
    
    i = Issue.objects.latest('modified')
    issues = Issue.objects.order_by('-modified','-modification_time')
    last_update = issues[:number]
    for i in last_updated:
        print i.series.name,i.id,i.number,i.modified,i.modification_time

