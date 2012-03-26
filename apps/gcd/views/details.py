# -*- coding: utf-8 -*-

"""View methods for pages displaying entity details."""

import re
from urllib2 import urlopen, HTTPError
from datetime import date, datetime, time, timedelta
from operator import attrgetter

from django.db.models import Q
from django.conf import settings
from django.core import urlresolvers
from django.shortcuts import render_to_response, \
                             get_object_or_404, \
                             get_list_or_404
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.template import RequestContext
from django.utils.safestring import mark_safe
from django.contrib.auth.models import User

from apps.gcd.models import Publisher, Series, Issue, Story, \
                            IndiciaPublisher, Brand, CountStats, \
                            Country, Language, Indexer, IndexCredit, Cover
from apps.gcd.views import paginate_response, ORDER_ALPHA, ORDER_CHRONO
from apps.gcd.views.covers import get_image_tag, \
                                  get_image_tags_per_issue, \
                                  get_image_tags_per_page
from apps.gcd.models.cover import ZOOM_SMALL, ZOOM_MEDIUM, ZOOM_LARGE
from apps.oi import states
from apps.oi.models import IssueRevision, SeriesRevision, PublisherRevision, \
                           BrandRevision, IndiciaPublisherRevision, \
                           Changeset, CTYPES

KEY_DATE_REGEXP = \
  re.compile(r'^(?P<year>\d{4})\-(?P<month>\d{2})\-(?P<day>\d{2})$')

# TODO: Pull this from the DB somehow, but not on every page load.
MIN_GCD_YEAR = 1800

COVER_TABLE_WIDTH = 5

IS_EMPTY = '[IS_EMPTY]'
IS_NONE = '[IS_NONE]'

def publisher(request, publisher_id):
    """
    Display the details page for a Publisher.
    """
    pub = get_object_or_404(Publisher, id = publisher_id)
    if pub.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'publisher', 'id': publisher_id}))

    vars = { 'publisher': pub,
             'current': pub.series_set.filter(deleted=False, is_current=True),
             'error_subject': pub }
    return paginate_response(request, pub.active_series().order_by('sort_name'),
                             'gcd/details/publisher.html', vars)

def indicia_publisher(request, indicia_publisher_id):
    """
    Display the details page for an Indicia Publisher.
    """
    indicia_publisher = get_object_or_404(
      IndiciaPublisher, id = indicia_publisher_id)
    if indicia_publisher.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'indicia_publisher', 'id': indicia_publisher_id}))

    return show_indicia_publisher(request, indicia_publisher)

def show_indicia_publisher(request, indicia_publisher, preview=False):
    indicia_publisher_issues = indicia_publisher.active_issues().order_by(
      'series__sort_name', 'sort_code')

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
    if brand.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'brand', 'id': brand_id}))

    return show_brand(request, brand)

def show_brand(request, brand, preview=False):
    brand_issues = brand.active_issues().order_by('series__sort_name',
                                                  'sort_code')

    vars = {
        'brand' : brand,
        'error_subject': '%s' % brand,
        'preview': preview
    }
    return paginate_response(request,
                             brand_issues,
                             'gcd/details/brand.html',
                             vars)

def imprint(request, imprint_id):
    """
    Display the details page for an Imprint.
    """
    imprint = get_object_or_404(Publisher, id = imprint_id, parent__isnull=False)
    if imprint.parent.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'publisher', 'id': imprint.parent_id}))

    if imprint.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'imprint', 'id': imprint_id}))

    imprint_series = imprint.imprint_series_set.exclude(deleted=True) \
      .order_by('sort_name')

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
    if publisher.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'publisher', 'id': publisher_id}))

    brands = publisher.active_brands()

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
    Finds indicia publishers of a publisher.
    """

    publisher = get_object_or_404(Publisher, id = publisher_id)
    if publisher.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'publisher', 'id': publisher_id}))

    indicia_publishers = publisher.active_indicia_publishers()

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
        'error_subject' : '%s indicia publishers' % publisher,
      })

def imprints(request, publisher_id):
    """
    Finds imprints of a publisher.  Imprints are defined as those
    publishers whose parent_id matches the given publisher.
    """

    publisher = get_object_or_404(Publisher, id = publisher_id)
    if publisher.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'publisher', 'id': publisher_id}))

    imps = publisher.active_imprints()

    sort = ORDER_ALPHA
    if 'sort' in request.GET:
        sort = request.GET['sort']

    if (sort == ORDER_CHRONO):
        imps = imps.order_by('year_began', 'name')
    else:
        imps = imps.order_by('name', 'year_began')

    return paginate_response(request, imps, 'gcd/details/imprints.html', {
      'publisher' : publisher,
      'error_subject' : '%s imprints' % publisher,
      })

def series(request, series_id):
    """
    Display the details page for a series.
    """

    series = get_object_or_404(Series, id=series_id)
    if series.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'series', 'id': series_id}))

    return show_series(request, series)

def show_series(request, series, preview=False):
    """
    Handle the main work of displaying a series.  Also used by OI previews.
    """
    covers = []

    if preview and series.series:
        display_series = series.series
    elif preview:
        display_series = None
    else:
        display_series = series

    scans, first_image_tag = _get_scan_table(display_series)

    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = 12

    return render_to_response(
      'gcd/details/series.html',
      {
        'series': series,
        'scans': scans,
        'first_image_tag': first_image_tag,
        'country': series.country,
        'language': series.language,
        'table_width': table_width,
        'error_subject': '%s' % series,
        'preview': preview,
        'is_empty': IS_EMPTY,
        'is_none': IS_NONE,
      },
      context_instance=RequestContext(request))

def series_details(request, series_id, by_date=False):
    series = get_object_or_404(Series, id=series_id)
    if series.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'series', 'id': series_id}))

    issues_by_date = []
    issues_left_over = []
    bad_key_dates = []
    if by_date:
        no_key_date_q = Q(key_date__isnull=True) | Q(key_date='')
        with_key_dates = series.active_issues().exclude(no_key_date_q)

        prev_year = None
        prev_month = None
        for issue in with_key_dates.order_by('key_date', 'sort_code'):
            m = re.search(KEY_DATE_REGEXP, issue.key_date)
            if m is None:
                bad_key_dates.append(issue.id)
                continue

            year, month, day = m.groups()
            month = int(month)
            if month < 1:
                month = 1
            elif month > 12:
                month = 12

            # Note that we ignore the key_date's day field as it rarely
            # indicates an actual day and we are not arranging the grid
            # at the weekly level anyway.
            try:
                grid_date = date(int(year), month, 1)
            except ValueError, ve:
                bad_key_dates.append(issue.id)
                continue

            if (grid_date.year > (date.today().year + 1) or
                grid_date.year < MIN_GCD_YEAR):
                bad_key_dates.append(issue.id)
                continue

            _handle_key_date(issue, grid_date,
                             prev_year, prev_month,
                             issues_by_date)

            prev_year = grid_date.year
            prev_month = grid_date.month

        issues_left_over = series.active_issues().filter(
          no_key_date_q | Q(id__in=bad_key_dates))

    # These need to be numbers not True/False booleans so they work
    # in the template.
    num_issues = series.issue_count
    volume_present = series.has_volume and \
      series.active_issues().filter(no_volume=True, variant_of=None).count() - num_issues
    brand_present = \
      series.active_issues().filter(no_brand=True, variant_of=None).count() - num_issues
    frequency_present = series.has_indicia_frequency and \
      series.active_issues().filter(no_indicia_frequency=True, variant_of=None).count() - num_issues
    barcode_present = series.has_barcode and \
      series.active_issues().filter(no_barcode=True, variant_of=None).count() - num_issues
    title_present = series.has_issue_title and \
      series.active_issues().filter(no_title=True, variant_of=None).count() - num_issues
    on_sale_date_present = series.active_issues().exclude(on_sale_date='').count()
    
    return render_to_response('gcd/details/series_details.html',
      {
        'series': series,
        'by_date': by_date,
        'rows': issues_by_date,
        'no_date_rows': issues_left_over,
        'volume_present': volume_present,
        'brand_present': brand_present,
        'frequency_present': frequency_present,
        'barcode_present': barcode_present,
        'title_present': title_present,
        'on_sale_date_present': on_sale_date_present,
        'bad_dates': len(bad_key_dates),
      },
      context_instance=RequestContext(request))

def change_history(request, model_name, id):
    if model_name not in ['publisher', 'brand', 'indicia_publisher',
                          'series', 'issue', 'cover']:
        if not (model_name == 'imprint' and
          get_object_or_404(Publisher, id=id, is_master=False).deleted):
            return render_to_response('gcd/error.html', {
              'error_text' : 'There is no change history for this type of object.'},
              context_instance=RequestContext(request))
    if model_name == 'cover' and not request.user.has_perm('gcd.can_approve'):
        return render_to_response('gcd/error.html', {
          'error_text' : 'Only editors can access the change history for covers.'},
          context_instance=RequestContext(request))

    template = 'gcd/details/change_history.html'
    prev_issue = None
    next_issue = None

    if model_name == 'imprint':
        object = get_object_or_404(Publisher, id=id, is_master=False)
        filter_string = 'publisherrevisions__publisher'
    else:
        # can't import up top because of circular dependency
        from apps.oi.views import DISPLAY_CLASSES, REVISION_CLASSES
        object = get_object_or_404(DISPLAY_CLASSES[model_name], id=id)

        # filter is publisherrevisions__publisher, seriesrevisions__series, etc.
        filter_string = '%ss__%s' % (REVISION_CLASSES[model_name].__name__.lower(),
                                     model_name)
    kwargs = { str(filter_string): object, 'state': states.APPROVED }
    changesets = Changeset.objects.filter(**kwargs).order_by('-modified', '-id')

    if model_name == 'issue':
        [prev_issue, next_issue] = object.get_prev_next_issue()

    return render_to_response(template,
      {
        'description': model_name.replace('_', ' ').title(),
        'object': object,
        'changesets': changesets,
        'prev_issue': prev_issue,
        'next_issue': next_issue,
      },
      context_instance=RequestContext(request))

def _handle_key_date(issue, grid_date, prev_year, prev_month, issues_by_date):
    if prev_year == None:
        issues_by_date.append({'date': grid_date, 'issues': [issue] })

    elif prev_year == grid_date.year:
        last_date_issues = issues_by_date[len(issues_by_date) - 1]
        if prev_month == grid_date.month:
            if grid_date == last_date_issues['date']:
                # Add the issue to the list for the current date.
                last_date_issues['issues'].append(issue)
            else:
                # Add a new row for the issue.
                issues_by_date.append(
                  {'date': grid_date, 'issues': [issue] })
        else:
            # Add rows for the skipped months.
            for month in range(prev_month + 1, grid_date.month):
                issues_by_date.append({'date': date(prev_year, month, 1),
                                       'issues': []})

            # Add the next issue.
            issues_by_date.append({'date': grid_date, 'issues': [issue]})
    else:
        # Add rows for the rest of the months in the current year.
        for month in range(prev_month + 1, 13):
            issues_by_date.append({'date': date(prev_year, month, 1),
                                   'issues': []})

        # Add twelve rows for each empty year.
        for year in range(prev_year + 1, grid_date.year):
            for month in range(1, 13):
                issues_by_date.append({'date': date(year, month, 1),
                                       'issues': []})

        # Add the skipped months in the year of the next issue.
        for month in range(1, grid_date.month):
            issues_by_date.append({'date': date(grid_date.year, month, 1),
                                   'issues': []})

        # Add the next issue.
        issues_by_date.append({'date': grid_date, 'issues': [issue]})


def status(request, series_id):
    """
    Display the index status matrix for a series.
    """
    series = get_object_or_404(Series, id=series_id)
    if series.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'series', 'id': series_id}))

    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = 12

    return render_to_response('gcd/status/status.html', {
      'series': series,
      'table_width': table_width },
      context_instance=RequestContext(request))

def _get_scan_table(series):
    # freshly added series have no scans on preview page
    if series is None:
        return None, None

    # all a series' covers + all issues with no covers
    covers = Cover.objects.filter(issue__series=series, deleted=False) \
                          .select_related()
    issues = series.issues_without_covers()

    scans = list(issues)
    scans.extend(list(covers))
    scans.sort(key=attrgetter('sort_code'))

    if covers:
        first_image_tag = get_image_tag(cover=covers[0], zoom_level=ZOOM_MEDIUM,
                                        alt_text='First Issue Cover')
    else:
        first_image_tag = None

    return scans, first_image_tag

def scans(request, series_id):
    """
    Display the cover scan status matrix for a series.
    """

    series = get_object_or_404(Series, id = series_id)
    if series.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'series', 'id': series_id}))

    scans, unused_tag = _get_scan_table(series)

    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = 12

    return render_to_response('gcd/status/scans.html', {
      'series' : series,
      'scans' : scans,
      'table_width' : table_width },
      context_instance=RequestContext(request))

def covers_to_replace(request, starts_with=None):
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
    table_width = COVER_TABLE_WIDTH

    return paginate_response(
      request,
      covers,
      'gcd/status/covers_to_replace.html',
      {
        'table_width' : table_width,
        'starts_with' : starts_with
      },
      page_size=50,
      callback_key='tags',
      callback=get_image_tags_per_page)


def daily_covers(request, show_date=None):
    """
    Produce a page displaying the covers uploaded on a given day.
    """

    # similar to the section in daily_changes. if we need it elsewhere,
    # time to split it out.
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
            requested_date = date(year, month, day)

        else:
            # Don't redirect, as this is a proper default.
            requested_date = date.today()
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
    table_width = COVER_TABLE_WIDTH

    covers = Cover.objects.filter(last_upload__range=(\
                                  datetime.combine(requested_date, time.min),
                                  datetime.combine(requested_date, time.max)),
                                  deleted=False)

    covers = covers.order_by("issue__series__publisher__name",
                             "issue__series__sort_name",
                             "issue__series__year_began",
                             "issue__sort_code")

    return paginate_response(
      request,
      covers,
      'gcd/status/daily_covers.html',
      {
        'date' : show_date,
        'date_after' : date_after,
        'date_before' : date_before,
        'table_width' : table_width,
      },
      page_size=50,
      callback_key='tags',
      callback=get_image_tags_per_page)

def daily_changes(request, show_date=None):
    """
    Produce a page displaying the changes on a given day.
    """

    # similar to the section in daily_covers. if we need it elsewhere,
    # time to split it out.
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
                'changes_by_date',
                kwargs={'show_date': show_date} ))

        elif show_date:
            year = int(show_date[0:4])
            month = int(show_date[5:7])
            day = int(show_date[8:10])
            requested_date = date(year, month, day)

        else:
            # Don't redirect, as this is a proper default.
            requested_date = date.today()
            show_date = requested_date.strftime('%Y-%m-%d')

    except (TypeError, ValueError):
        # Redirect so the user sees the date in the URL that matches
        # the output, instead of seeing the erroneous date.
        return HttpResponseRedirect(
          urlresolvers.reverse(
            'changes_by_date',
            kwargs={'show_date' : date.today().strftime('%Y-%m-%d') }))

    date_before = requested_date + timedelta(-1)
    if requested_date < date.today():
        date_after = requested_date + timedelta(1)
    else:
        date_after = None

    anon = User.objects.get(username=settings.ANON_USER_NAME)

    publisher_revisions = list(PublisherRevision.objects.filter(
      changeset__change_type=CTYPES['publisher'],
      changeset__state=states.APPROVED,
      deleted=False,
      changeset__modified__range=(
        datetime.combine(requested_date, time.min),
        datetime.combine(requested_date, time.max)))\
      .exclude(changeset__indexer=anon).values_list('publisher', flat=True))
    publishers = Publisher.objects.filter(is_master=1,
      id__in=publisher_revisions).distinct().select_related('country')

    brand_revisions = list(BrandRevision.objects.filter(
      changeset__change_type=CTYPES['brand'],
      changeset__state=states.APPROVED,
      deleted=False,
      changeset__modified__range=(
        datetime.combine(requested_date, time.min),
        datetime.combine(requested_date, time.max)))\
        .exclude(changeset__indexer=anon)\
        .values_list('brand', flat=True))
    brands = Brand.objects.filter(id__in=brand_revisions).distinct()\
      .select_related('parent__country')

    indicia_publisher_revisions = list(IndiciaPublisherRevision.objects.filter(
      changeset__change_type=CTYPES['indicia_publisher'],
      changeset__state=states.APPROVED,
      deleted=False,
      changeset__modified__range=(
        datetime.combine(requested_date, time.min),
        datetime.combine(requested_date, time.max)))\
      .exclude(changeset__indexer=anon)\
      .values_list('indicia_publisher', flat=True))
    indicia_publishers = IndiciaPublisher.objects.filter(
      id__in=indicia_publisher_revisions).distinct()\
      .select_related('parent__country')

    series_revisions = list(SeriesRevision.objects.filter(
      changeset__change_type=CTYPES['series'],
      changeset__state=states.APPROVED,
      deleted=False,
      changeset__modified__range=(
        datetime.combine(requested_date, time.min),
        datetime.combine(requested_date, time.max)))\
      .exclude(changeset__indexer=anon).values_list('series', flat=True))
    series = Series.objects.filter(id__in=series_revisions).distinct()\
      .select_related('publisher','country', 'first_issue','last_issue')

    issues_change_types = [CTYPES['issue'], CTYPES['variant_add']]
    issue_revisions = list(IssueRevision.objects.filter(\
      changeset__change_type__in=issues_change_types,
      changeset__state=states.APPROVED,
      deleted=False,
      changeset__modified__range=(
        datetime.combine(requested_date, time.min),
        datetime.combine(requested_date, time.max)))\
      .exclude(changeset__indexer=anon).values_list('issue', flat=True))
    issues = Issue.objects.filter(id__in=issue_revisions).distinct()\
      .select_related('series__publisher', 'series__country')

    return render_to_response('gcd/status/daily_changes.html',
      {
        'date' : show_date,
        'date_after' : date_after,
        'date_before' : date_before,
        'publishers' : publishers,
        'brands' : brands,
        'indicia_publishers' : indicia_publishers,
        'series' : series,
        'issues' : issues
      },
      context_instance=RequestContext(request)
    )

def int_stats(request):
    """
    Display the international stats by language
    """
    languages = Language.objects.filter(countstats__name='issue indexes') \
                                .order_by('-countstats__count', 'name')
    stats=[]
    for lang in languages:
        stats.append((lang, CountStats.objects.filter(language=lang)))
    return render_to_response(
      'gcd/status/international_stats.html',
      {
        'stats' : stats
      },
      context_instance=RequestContext(request)
    )

def cover(request, issue_id, size):
    """
    Display the cover for a single issue on its own page.
    """

    size = int(size)
    if size not in [ZOOM_SMALL, ZOOM_MEDIUM, ZOOM_LARGE]:
        raise Http404

    issue = get_object_or_404(Issue, id = issue_id)

    if issue.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'issue', 'id': issue_id}))

    [prev_issue, next_issue] = issue.get_prev_next_issue()

    cover_tag = get_image_tags_per_issue(issue, "Cover Image", size, variants=True)

    extra = 'cover/%d/' % size  # TODO: remove abstraction-breaking hack.

    return render_to_response(
      'gcd/details/cover.html',
      {
        'issue': issue,
        'prev_issue': prev_issue,
        'next_issue': next_issue,
        'cover_tag': cover_tag,
        'extra': extra,
        'error_subject': '%s cover' % issue,
      },
      context_instance=RequestContext(request)
    )

def covers(request, series_id):
    """
    Display the cover gallery for a series.
    """

    series = get_object_or_404(Series, id = series_id)
    if series.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'series', 'id': series_id}))

    # TODO: Figure out optimal table width and/or make it user controllable.
    table_width = COVER_TABLE_WIDTH

    # TODO: once we get permissions going 'can_mark' should be one
    if request.user.is_authenticated() and \
      request.user.groups.filter(name='editor'):
        can_mark = True
    else:
        can_mark = False

    covers = Cover.objects.filter(issue__series=series, deleted=False) \
                          .select_related('issue')

    vars = {
      'series': series,
      'error_subject': '%s covers' % series,
      'table_width': table_width,
      'can_mark': can_mark
    }

    return paginate_response(request, covers, 'gcd/details/covers.html', vars,
      page_size=50,
      callback_key='tags',
      callback=lambda page: get_image_tags_per_page(page, series))

def issue_form(request):
    """
    Redirect form-style URL used by the drop-down menu on the series
    details page into a standard issue details URL.
    """
    params = request.GET.copy()
    if 'id' not in params:
        raise Http404

    id = params['id']
    del params['id']
    if 'extra' in params:
        extra = params['extra']
        del params['extra']
    else:
        extra = ''
    try:
        return HttpResponseRedirect(
          urlresolvers.reverse(issue, kwargs={ 'issue_id': int(id) }) + extra +
          '?' + params.urlencode())
    except ValueError:
        raise Http404

def issue(request, issue_id):
    """
    Display the issue details page, including story details.
    """
    issue = get_object_or_404(Issue, id = issue_id)

    if issue.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'issue', 'id': issue_id}))

    return show_issue(request, issue)

def show_issue(request, issue, preview=False):
    """
    Handle the main work of displaying an issue.  Also used by OI previews.
    """
    alt_text = 'Cover Thumbnail'
    zoom_level = ZOOM_MEDIUM
    if preview:
        # excludes are currently only relevant for variant_add, maybe later
        # other cover moves will be possible
        if issue.changeset.change_type in [CTYPES['variant_add'],
                                           CTYPES['two_issues']] and \
          issue.changeset.coverrevisions.count():
            # need to exclude the moved one
            image_tag = mark_safe('')
            if issue.issue and issue.issue.active_covers().count():
                exclude_ids = issue.changeset.coverrevisions\
                .filter(issue=issue.issue).values_list('cover__id', flat=True)
                if len(exclude_ids) < issue.issue.active_covers().count():
                    image_tag = get_image_tags_per_issue(issue=issue.issue,
                                  zoom_level=zoom_level,
                                  alt_text=alt_text,
                                  exclude_ids=exclude_ids)
            # add moved cover(s)
            for cover in issue.changeset.coverrevisions\
                                        .exclude(issue=issue.issue):
                image_tag += get_image_tag(cover.cover,
                                           alt_text=alt_text,
                                           zoom_level=zoom_level)
            if image_tag == '':
                image_tag = mark_safe(get_image_tag(cover=None,
                                                    zoom_level=zoom_level,
                                                    alt_text=alt_text))
        elif issue.issue:
            image_tag = get_image_tags_per_issue(issue=issue.issue,
                                                 zoom_level=zoom_level,
                                                 alt_text=alt_text)
        else:
            image_tag = mark_safe(get_image_tag(cover=None,
                                                zoom_level=zoom_level,
                                                alt_text=alt_text))
    else:
        image_tag = get_image_tags_per_issue(issue=issue,
                                             zoom_level=zoom_level,
                                             alt_text=alt_text)

    variant_image_tags = []
    for variant_cover in issue.variant_covers():
        variant_image_tags.append([variant_cover.issue,
                                   get_image_tag(variant_cover,
                                                 zoom_level=ZOOM_SMALL,
                                                 alt_text='Cover Thumbnail')])

    series = issue.series
    [prev_issue, next_issue] = issue.get_prev_next_issue()

    # TODO: Since the number of stories per issue is typically fairly small,
    # it seems more efficient to grab the whole list and only do one database
    # query rather than separately select the cover story and the interior
    # stories.  But we should measure this.  Note that we definitely want
    # to send the cover and interior stories to the UI separately, as the
    # UI should not be concerned with the designation of story 0 as the cover.
    cover_story, stories = issue.shown_stories()

    # get reservations which got approved and make unique for indexers
    res = issue.reservation_set.filter(status=3)
    oi_indexers = []
    for i in res:
        oi_indexers.append(i.indexer)

    if preview:
        if issue.issue:
            res = IssueRevision.objects.filter(issue=issue.issue)
        else:
            res = IssueRevision.objects.none()
    else:
        res = IssueRevision.objects.filter(issue=issue)
    res = res.filter(changeset__state=states.APPROVED)\
             .exclude(changeset__indexer__username=settings.ANON_USER_NAME)
    for i in res:
        oi_indexers.append(i.changeset.indexer.indexer)
    oi_indexers = list(set(oi_indexers))

    show_original = False
    if (request.GET.has_key('original_reprint_notes')):
        if request.GET['original_reprint_notes'] == 'True':
            show_original = True

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
        'variant_image_tags': variant_image_tags,
        'show_original': show_original,
        'error_subject': '%s' % issue,
        'preview': preview,
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
        countries_from_series = list(set(Series.objects.exclude(deleted=True).
                                         values_list('country', flat=True)))
        countries_from_indexers = list(set(Indexer.objects.
                                           filter(user__is_active=True).
                                           values_list('country', flat=True)))
        countries_from_publishers = list(set(Publisher.objects.exclude(deleted=True).
                                             values_list('country', flat=True)))
        used_ids = list(set(countries_from_indexers +
                            countries_from_series +
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

def agenda(request, language):
    try:
        f = urlopen("https://www.google.com/calendar/embed?src=comics.org_v62prlv9"
          "dp79hbjt4du2unqmks%40group.calendar.google.com&showTitle=0&showNav=0&"
          "showDate=0&showPrint=0&showTabs=0&showCalendars=0&showTz=0&mode=AGENDA"
          "&height=600&wkst=1&bgcolor=%23FFFFFF&color=%238C500B"
          "&ctz=America%2FLos_Angeles&hl=de")
    except HTTPError:
        raise Http404

    a = f.read()
    js_pos = a.find('<script type="text/javascript" src="') + \
      len('<script type="text/javascript" src="')
    js_pos_end = a[js_pos:].find('"></script>') + js_pos
    if language not in ['en', 'de']:
        language = 'en'
    a = a[:js_pos] + settings.MEDIA_URL + 'calendar/js/d55029fd56f3be5e874d2c'\
      '1680fee739embedcompiled__%s.js' % str(language) + a[js_pos_end:]

    #js_pos = a.find('<script type="text/javascript" src="') + len('<script type="text/javascript" src="')
    #js_pos_end = a[js_pos:].find('"></script>') + js_pos
    #a = a[:js_pos] + 'http://www.google.com/calendar/' + a[js_pos:]

    css_pos = a.find('<link type="text/css" rel="stylesheet" href="') + \
      len('<link type="text/css" rel="stylesheet" href="')
    css_pos_end = a[css_pos:].find('">') + css_pos
    a = a[:css_pos]  + settings.MEDIA_URL + 'calendar/css/d55029fd56f3be5e87' \
      '4d2c1680fee739embedcompiled_fastui.css' + a[css_pos_end:]
    return HttpResponse(a)
