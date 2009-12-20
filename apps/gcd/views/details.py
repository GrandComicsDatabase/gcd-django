# -*- coding: utf-8 -*-

"""View methods for pages displaying entity details."""

import re
from urllib import urlopen
from datetime import date, datetime, time, timedelta

from django.db.models import Q
from django.conf import settings
from django.core import urlresolvers
from django.core.paginator import QuerySetPaginator
from django.shortcuts import render_to_response, \
                             get_object_or_404, \
                             get_list_or_404
from django.http import HttpResponseRedirect, Http404
from django.template import RequestContext
from django.utils.safestring import mark_safe

from apps.gcd.models import Publisher, Series, Issue, Story, \
                            IndiciaPublisher, Brand, \
                            Country, Language, Indexer, IndexCredit, Cover
from apps.gcd.views import paginate_response, ORDER_ALPHA, ORDER_CHRONO
from apps.gcd.views.covers import get_image_tag, \
                                  get_image_tags_per_issue, \
                                  get_image_tags_per_page, \
                                  ZOOM_SMALL, \
                                  ZOOM_MEDIUM, \
                                  ZOOM_LARGE
from apps.oi import states
from apps.oi.models import IssueRevision

def get_style(request):
    style = 'default'
    if (request.GET.has_key('style')):
        style = request.GET['style']
    return style


def publisher(request, publisher_id):
    """
    Display the details page for a Publisher.
    """
    style = get_style(request)
    pub = get_object_or_404(Publisher, id = publisher_id)

    vars = { 'publisher': pub, 'error_subject': pub }
    return paginate_response(request, pub.series_set.order_by('name'),
                             'gcd/details/publisher.html', vars)

def indicia_publisher(request, indicia_publisher_id):
    """
    Display the details page for an Indicia Publisher.
    """
    indicia_publisher = get_object_or_404(
      IndiciaPublisher, id = indicia_publisher_id)
    return show_indicia_publisher(request, indicia_publisher)

def show_indicia_publisher(request, indicia_publisher, preview=False):
    indicia_publisher_issues = indicia_publisher.issue_set.order_by(
      'series__name', 'sort_code')

    vars = { 'indicia_publisher' : indicia_publisher,
             'error_subject': '%s' % indicia_publisher,
             'preview': preview }
    return paginate_response(request,
                             indicia_publisher_issues,
                             'gcd/details/indicia_publisher.html',
                             vars)

def brand(request, brand_id):
    """
    Display the details page for a Brand.
    """
    brand = get_object_or_404(Brand, id = brand_id)
    return show_brand(request, brand)

def show_brand(request, brand, preview=False):
    brand_issues = brand.issue_set.order_by('series__name', 'sort_code')

    vars = { 'brand' : brand, 'error_subject': '%s' % brand, 'preview': preview }
    return paginate_response(request,
                             brand_issues,
                             'gcd/details/brand.html',
                             vars)

def imprint(request, imprint_id):
    """
    Display the details page for an Imprint.
    """
    style = get_style(request)
    imprint = get_object_or_404(Publisher, id = imprint_id)
    imprint_series = imprint.imprint_series_set.order_by('name')

    vars = { 'publisher' : imprint, 'error_subject': '%s' % imprint }
    return paginate_response(request,
                             imprint_series,
                             'gcd/details/publisher.html',
                             vars)

def brands(request, publisher_id):
    """
    Finds brands of a publisher.
    """

    publisher = get_object_or_404(Publisher, id = publisher_id)
    brands = publisher.brands.all()

    sort = ORDER_ALPHA
    if 'sort' in request.GET:
        sort = request.GET['sort']

    if (sort == ORDER_CHRONO):
        brands = brands.order_by('year_began', 'name')
    else:
        brands = brands.order_by('name', 'year_began')

    return paginate_response(request, brands, 'gcd/details/brands.html', {
      'publisher' : publisher,
      'error_subject' : '%s brands' % publisher,
    })

def indicia_publishers(request, publisher_id):
    """
    Finds brands of a publisher.
    """

    publisher = get_object_or_404(Publisher, id = publisher_id)
    indicia_publishers = publisher.indicia_publishers.all()

    sort = ORDER_ALPHA
    if 'sort' in request.GET:
        sort = request.GET['sort']

    if (sort == ORDER_CHRONO):
        indicia_publishers = indicia_publishers.order_by('year_began', 'name')
    else:
        indicia_publishers = indicia_publishers.order_by('name', 'year_began')

    return paginate_response(request, indicia_publishers,
      'gcd/details/indicia_publishers.html',
      {
        'publisher' : publisher,
        'error_subject' : '%s brands' % publisher,
      })

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
      'error_subject' : '%s imprints' % publisher,
      })

def series(request, series_id):
    """
    Display the details page for a series.
    """
    
    series = get_object_or_404(Series, id=series_id)
    return show_series(request, series)

def show_series(request, series, preview=False):
    """
    Handle the main work of displaying a series.  Also used by OI previews.
    """
    covers = series.cover_set.select_related('issue')
    issues = series.issue_set.all()
    
    try:
        cover = covers.filter(has_image=True)[0]
        image_tag = get_image_tag(cover=cover,
                                  zoom_level=ZOOM_MEDIUM,
                                  alt_text='First Issue Cover')

    except IndexError:
        image_tag = ''
        
    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = 12

    style = get_style(request)

    return render_to_response(
      'gcd/details/series.html',
      {
        'series': series,
        'issues': issues,
        'covers': covers,
        'image_tag': image_tag,
        'country': series.country,
        'language': series.language,
        'table_width': table_width,
        'error_subject': '%s' % series,
        'style': style,
        'preview': preview,
      },
      context_instance=RequestContext(request))

def status(request, series_id):
    """
    Display the index status matrix for a series.
    """
    series = get_object_or_404(Series, id=series_id)
    issues = series.issue_set.all()

    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = 12
    style = get_style(request)

    return render_to_response('gcd/status/status.html', {
      'series': series,
      'issues': issues,
      'table_width': table_width,
      'style': style },
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

    covers = Cover.objects.filter(marked = True).filter(has_image = True)
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
            # Do a redirect, otherwise pagination links point to today
            requested_date = date(year, month, day)
            show_date = requested_date.strftime('%Y-%m-%d')
            return HttpResponseRedirect(
              urlresolvers.reverse(
                'covers_by_date',
                kwargs={'show_date': show_date} ))

        elif show_date:
            year = int(show_date[0:4])
            month = int(show_date[5:7])
            day = int(show_date[8:10])

        else:
            # Don't redirect, as this is a proper default.
            requested_date = date.today()

        if requested_date is None:
            requested_date = date(year, month, day)

        if show_date is None:
            show_date = requested_date.strftime('%Y-%m-%d')

    except (TypeError, ValueError):
        # Redirect so the user sees the date in the URL that matches
        # the output, instead of seeing the erroneous date.
        return HttpResponseRedirect(
          urlresolvers.reverse(
            'covers_by_date',
            kwargs={'show_date' : date.today().strftime('%Y-%m-%d') }))

    date_before = requested_date + timedelta(-1)
    if requested_date < date.today():
        date_after = requested_date + timedelta(1)
    else:
        date_after = None

    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = 5
    style = get_style(request)

    covers = Cover.objects.filter(modified__range=(\
                                  datetime.combine(requested_date, time.min),
                                  datetime.combine(requested_date, time.max)))

    covers = covers.filter(has_image=True)
    covers = covers.order_by("issue__series__publisher__name",
                             "issue__series__name",
                             "issue__series__year_began",
                             "issue__sort_code")

    # TODO: once we have permissions 'can_mark' should be one
    if request.user.is_authenticated() and \
      request.user.groups.filter(name='editor'):
        can_mark = True
    else:
        can_mark = False

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
        'can_mark' : can_mark
      },
      page_size=50,
      callback_key='tags',
      callback=get_image_tags_per_page)
    
    
def cover(request, issue_id, size):
    """
    Display the cover for a single issue on its own page.
    """

    issue = get_object_or_404(Issue, id = issue_id)
    cover = issue.cover_set.all()[0]
    [prev_issue, next_issue] = issue.get_prev_next_issue()

    cover_tag = get_image_tags_per_issue(issue, "Cover Image", 
                                         int(size))
    style = get_style(request)

    extra = 'cover/' + size + '/' # TODO: remove abstraction-breaking hack.

    return render_to_response(
      'gcd/details/cover.html',
      {
        'issue': issue,
        'prev_issue': prev_issue,
        'next_issue': next_issue,
        'cover_tag': cover_tag,
        'extra': extra,
        'error_subject': '%s cover' % issue,
        'style': style
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

    # TODO: once we get permissions going 'can_mark' should be one
    if request.user.is_authenticated() and \
      request.user.groups.filter(name='editor'):
        can_mark = True
    else:
        can_mark = False

    covers =series.cover_set.select_related('issue').filter(has_image = '1')
    style = get_style(request)
    vars = {
      'series': series,
      'error_subject': '%s covers' % series,
      'table_width': table_width,
      'style': style,
      'can_mark': can_mark
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
    if 'id' not in params:
        raise Http404

    id = params['id']
    del params['id']
    return HttpResponseRedirect(
      urlresolvers.reverse(issue, kwargs={ 'issue_id': id }) +
      '?' + params.urlencode())

def issue(request, issue_id):
    """
    Display the issue details page, including story details.
    """
    issue = get_object_or_404(Issue, id = issue_id)
    return show_issue(request, issue)

def show_issue(request, issue, preview=False):
    """
    Handle the main work of displaying an issue.  Also used by OI previews.
    """
    cover_issue = issue
    if preview:
        cover_issue = issue.issue

    image_tag = get_image_tags_per_issue(issue=cover_issue,
                                         zoom_level=ZOOM_SMALL,
                                         alt_text='Cover Thumbnail')
    style = get_style(request)

    series = issue.series
    [prev_issue, next_issue] = issue.get_prev_next_issue()

    # TODO: Since the number of stories per issue is typically fairly small,
    # it seems more efficient to grab the whole list and only do one database
    # query rather than separately select the cover story and the interior
    # stories.  But we should measure this.  Note that we definitely want
    # to send the cover and interior stories to the UI separately, as the
    # UI should not be concerned with the designation of story 0 as the cover.
    stories = list(issue.story_set.order_by('sequence_number'))

    cover_story = None
    if (len(stories) > 0):
        cover_story = stories.pop(0)

    # get reservations which got approved and make unique for indexers
    res = issue.reservation_set.filter(status=3)
    oi_indexers = []
    for i in res:
        oi_indexers.append(i.indexer)

    if preview:    
        res = IssueRevision.objects.filter(issue=issue.issue)
    else:
        res = IssueRevision.objects.filter(issue=issue)
    res = res.filter(changeset__state=states.APPROVED)
    for i in res:
        oi_indexers.append(i.changeset.indexer.indexer)
    oi_indexers = list(set(oi_indexers))

    return render_to_response(
      'gcd/details/issue.html',
      {
        'issue': issue,
        'prev_issue': prev_issue,
        'next_issue': next_issue,
        'cover_story': cover_story,
        'stories': stories,
        'oi_indexers' : oi_indexers,
        'image_tag': image_tag,
        'error_subject': '%s' % issue,
        'preview': preview,
        'style': style,
      },
      context_instance=RequestContext(request))


# this should later be moved to admin.py or something like that
def countries_in_use(request):
    """
    Show list of countries with name and flag.
    Main use is to find missing names and flags.
    """

    if request.user.is_authenticated() and \
      request.user.groups.filter(name='admin'):
        countries_from_series = list(set(Series.objects.all().
                                         values_list('country', flat=True)))
        countries_from_indexers = list(set(Indexer.objects.filter(user__is_active=True).
                                           values_list('country', flat=True)))
        countries_from_publishers = list(set(Publisher.objects.all().
                                             values_list('country', flat=True)))
        used_ids = list(set(countries_from_indexers + \
                                     countries_from_series + \
                                     countries_from_publishers))
        used_countries = [Country.objects.filter(id=id)[0] for id in used_ids]
        
        return render_to_response('gcd/admin/countries.html',
                                  {'countries' : used_countries },
                                  context_instance=RequestContext(request))
    else:
        return render_to_response('gcd/error.html', {
          'error_text' : 'You are not allowed to access this page.',
          },
          context_instance=RequestContext(request))

