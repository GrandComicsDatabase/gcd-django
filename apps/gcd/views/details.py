# -*- coding: utf-8 -*-

"""View methods for pages displaying entity details."""

import re
from urllib.parse import urlencode, quote
from urllib.request import urlopen
from urllib.error import HTTPError
from datetime import date, datetime, time, timedelta
from calendar import monthrange
from operator import attrgetter
from random import randint

from django.db.models import Q
from django.conf import settings
from django.core import urlresolvers
from django.shortcuts import get_object_or_404, \
                             render
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.utils.safestring import mark_safe
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from django_tables2 import RequestConfig

from apps.indexer.views import ViewTerminationError

from apps.stddata.models import Country, Language
from apps.stats.models import CountStats

from apps.indexer.models import Indexer
from apps.gcd.models import Publisher, Series, Issue, Story, StoryType, Image,\
                            IndiciaPublisher, Brand, BrandGroup, Cover,\
                            SeriesBond, Award, Creator, CreatorMembership,\
                            ReceivedAward, CreatorDegree, CreatorArtInfluence,\
                            CreatorNonComicWork, CreatorSchool, CreatorRelation,\
                            Feature, FeatureLogo
from apps.gcd.models.story import CORE_TYPES, AD_TYPES
from apps.gcd.views import paginate_response, ORDER_ALPHA, ORDER_CHRONO
from apps.gcd.views.covers import get_image_tag, get_generic_image_tag, \
                                  get_image_tags_per_issue, \
                                  get_image_tags_per_page
from apps.gcd.models.cover import ZOOM_SMALL, ZOOM_MEDIUM, ZOOM_LARGE
from apps.gcd.forms import get_generic_select_form
from apps.oi import states
from apps.oi.models import IssueRevision, SeriesRevision, PublisherRevision, \
                           BrandGroupRevision, BrandRevision, CoverRevision, \
                           IndiciaPublisherRevision, ImageRevision, Changeset, \
                           SeriesBondRevision, CreatorRevision, CTYPES
from apps.gcd.models.series import SeriesTable
from apps.gcd.views import ResponsePaginator

KEY_DATE_REGEXP = \
  re.compile(r'^(?P<year>\d{4})\-(?P<month>\d{2})\-(?P<day>\d{2})$')

# TODO: Pull this from the DB somehow, but not on every page load.
MIN_GCD_YEAR = 1800

COVER_TABLE_WIDTH = 5
COVERS_PER_GALLERY_PAGE = 50

IS_EMPTY = '[IS_EMPTY]'
IS_NONE = '[IS_NONE]'

# For ad purposes, we need to be able to identify adult cover images,
# right now we do it by publisher.
PUB_WITH_ADULT_IMAGES = [
  3729,  # Amryl Entertainment
  1052,  # Avatar Press
  4810,  # Dolmen Editorial
  4117,  # Ediciones La Cúpula
  1078,  # Edifumetto
  8484,  # Editorial Toukan
  4562,  # Ediperiodici
  445,   # Fantagraphics
  8415,  # Hustler Magazine, Inc.
  351,   # Last Gasp
  3287,  # Penthouse
  4829,  # Weissblech Comics
  3197,  # Zenescope Entertainment
]


# to set flag for choice of ad providers
def _publisher_image_content(publisher_id):
    if publisher_id in PUB_WITH_ADULT_IMAGES:
        return 2

    return 1


def get_gcd_object(model, object_id, model_name=None):
    object = get_object_or_404(model, id=object_id)
    if object.deleted:
        if not model_name:
            model_name = model._meta.model_name
        raise ViewTerminationError(
          response = HttpResponseRedirect(urlresolvers.reverse(
                                          'change_history',
                                          kwargs={'model_name': model_name,
                                                  'id': object_id})))
    return object


def creator(request, creator_id):
    creator = get_gcd_object(Creator, creator_id)
    return show_creator(request, creator)


def show_creator(request, creator, preview=False):
    vars = {'creator': creator,
            'error_subject': creator,
            'preview': preview}
    return render(request, 'gcd/details/creator.html', vars)


def creator_membership(request, creator_membership_id):
    creator_membership = get_gcd_object(CreatorMembership, 
                                        creator_membership_id,
                                        model_name='creator_membership')
    return show_creator_membership(request, creator_membership)


def show_creator_membership(request, creator_membership, preview=False):
    vars = {'creator_membership': creator_membership,
            'error_subject': creator_membership,
            'preview': preview}
    return render(request, 'gcd/details/creator_membership.html', vars)


def creator_art_influence(request, creator_art_influence_id):
    creator_art_influence = get_gcd_object(CreatorArtInfluence,
                                           creator_art_influence_id,
                                           model_name='creator_art_influence')
    return show_creator_art_influence(request, creator_art_influence)


def show_creator_art_influence(request, creator_art_influence, preview=False):
    vars = {'creator_art_influence': creator_art_influence,
            'error_subject': creator_art_influence,
            'preview': preview}
    return render(request, 'gcd/details/creator_art_influence.html', vars)


def received_award(request, received_award_id):
    received_award = get_gcd_object(ReceivedAward, received_award_id,
                                    model_name='received_award')
    return show_received_award(request, received_award)


def show_received_award(request, received_award, preview=False):
    vars = {'received_award': received_award,
            'error_subject': received_award,
            'preview': preview}
    return render(request, 'gcd/details/received_award.html', vars)


def creator_degree(request, creator_degree_id):
    creator_degree = get_gcd_object(CreatorDegree, creator_degree_id,
                                    model_name='creator_degree')
    return show_creator_degree(request, creator_degree)


def show_creator_degree(request, creator_degree, preview=False):
    vars = {'creator': creator_degree.creator,
            'creator_degree': creator_degree,
            'error_subject': creator_degree,
            'preview': preview}
    return render(request, 'gcd/details/creator_degree.html', vars)


def creator_non_comic_work(request, creator_non_comic_work_id):
    creator_non_comic_work = get_gcd_object(CreatorNonComicWork,
                                            creator_non_comic_work_id,
                                            model_name='creator_non_comic_work')
    return show_creator_non_comic_work(request, creator_non_comic_work)


def show_creator_non_comic_work(request, creator_non_comic_work, preview=False):
    vars = {'creator_non_comic_work': creator_non_comic_work,
            'error_subject': creator_non_comic_work,
            'preview': preview}
    return render(request, 'gcd/details/creator_non_comic_work.html', vars)


def creator_relation(request, creator_relation_id):
    creator_relation = get_gcd_object(CreatorRelation,
                                      creator_relation_id,
                                      model_name='creator_relation')
    return show_creator_relation(request, creator_relation)


def show_creator_relation(request, creator_relation, preview=False):
    vars = {'creator_relation': creator_relation,
            'error_subject': creator_relation,
            'preview': preview}
    return render(request, 'gcd/details/creator_relation.html', vars)


def creator_school(request, creator_school_id):
    creator_school = get_gcd_object(CreatorSchool, creator_school_id,
                                    model_name='creator_school')
    return show_creator_school(request, creator_school)


def show_creator_school(request, creator_school, preview=False):
    vars = {'creator': creator_school.creator,
            'creator_school': creator_school,
            'error_subject': creator_school,
            'preview': preview}
    return render(request, 'gcd/details/creator_school.html', vars)


def award(request, award_id):
    """
    Display the details page for an Award.
    """
    award = get_object_or_404(Award, id = award_id)
    if award.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'award', 'id': award_id}))

    return show_award(request, award)


def show_award(request, award, preview=False):
    awards = award.active_awards().order_by(
      'award_year', 'award_name')

    vars = { 'award' : award,
             'error_subject': '%s' % award,
             'preview': preview }
    return paginate_response(request,
                             awards,
                             'gcd/details/award.html',
                             vars)


def publisher(request, publisher_id):
    """
    Display the details page for a Publisher.
    """
    publisher = get_object_or_404(Publisher, id = publisher_id)
    if publisher.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'publisher', 'id': publisher_id}))

    return show_publisher(request, publisher)


def show_publisher(request, publisher, preview=False):
    publisher_series = publisher.active_series()

    vars = { 'publisher': publisher,
             'current': publisher.series_set.filter(deleted=False,
                                                    is_current=True),
             'error_subject': publisher,
             'preview': preview}
    paginator = ResponsePaginator(publisher_series, per_page=100, vars=vars,
                                  alpha=True)
    page_number = paginator.paginate(request).number
    # doing select_related above looks like a more costly query for
    # ResponsePaginator
    publisher_series = publisher.active_series().select_related('first_issue',
                                                                'last_issue')
    if 'sort' in request.GET:
        extra_string = 'sort=%s' % (request.GET['sort'])
        if request.GET['sort'] != 'name' and \
          paginator.vars['pagination_type'] == 'alpha':
            args = request.GET.copy()
            args['page'] = 1
            return HttpResponseRedirect(quote(request.path.encode('UTF-8')) +
                                        '?' + args.urlencode())
    else:
        extra_string = ''

    table = SeriesTable(publisher_series, attrs={'class': 'listing'},
                        template_name='gcd/bits/sortable_table.html',
                        order_by=('name'))
    RequestConfig(request, paginate={'per_page': 100,
                                     'page': page_number}).configure(table)
    vars['table'] = table
    vars['extra_string'] = extra_string

    return render(request, 'gcd/details/publisher.html', vars)


def publisher_monthly_covers(request,
                             publisher_id,
                             year=None,
                             month=None,
                             use_on_sale=True):
    """
    Display the covers for the monthly publications of a publisher.
    """
    publisher = get_gcd_object(Publisher, publisher_id)

    if use_on_sale:
        date_type = 'publisher_monthly_covers_on_sale'
    else:
        date_type = 'publisher_monthly_covers_pub_date'

    # parts are generic and should be re-factored if we ever need it elsewhere
    try:
        if 'month' in request.GET:
            year = int(request.GET['year'])
            month = int(request.GET['month'])
            # do a redirect, otherwise pagination links point to current month
            return HttpResponseRedirect(
              urlresolvers.reverse(date_type,
                                   kwargs={'publisher_id': publisher_id,
                                           'year': year,
                                           'month': month} ))
        if year:
            year = int(year)
        if month:
            month = int(month)
    except ValueError:
        year = None

    if year is None:
        year = date.today().year
        month = date.today().month

    table_width = COVER_TABLE_WIDTH

    covers = Cover.objects.filter(issue__series__publisher=publisher,
                                  deleted=False).select_related('issue')
    if use_on_sale:
        covers = \
          covers.filter(issue__on_sale_date__gte='%d-%02d-00' % (year, month),
                        issue__on_sale_date__lte='%d-%02d-32' % (year, month))\
                .order_by('issue__on_sale_date', 'issue__series')
    else:
        covers = \
          covers.filter(issue__key_date__gte='%d-%02d-00' % (year, month),
                        issue__key_date__lte='%d-%02d-32' % (year, month))\
                .order_by('issue__key_date', 'issue__series')

    start_date = datetime(year, month, 1)
    date_before = start_date + timedelta(-1)
    date_after = start_date + timedelta(31)
    choose_url = urlresolvers.reverse(date_type,
                                      kwargs={'publisher_id': publisher_id,
                                              'year': year,
                                              'month': month})
    choose_url_before = urlresolvers.reverse(date_type,
                                             kwargs={
                                               'publisher_id': publisher_id,
                                               'year': date_before.year,
                                               'month': date_before.month})
    choose_url_after = urlresolvers.reverse(date_type,
                                            kwargs={
                                              'publisher_id': publisher_id,
                                              'year': date_after.year,
                                              'month': date_after.month})

    vars = {
      'publisher': publisher,
      'date': start_date,
      'choose_url': choose_url,
      'choose_url_after': choose_url_after,
      'choose_url_before': choose_url_before,
      'use_on_sale': use_on_sale,
      'table_width': table_width,
      'RANDOM_IMAGE': _publisher_image_content(publisher.id)
    }

    return paginate_response(request, covers,
      'gcd/details/publisher_monthly_covers.html', vars,
      per_page=COVERS_PER_GALLERY_PAGE,
      callback_key='tags', callback=get_image_tags_per_page)

    
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
      'series__sort_name', 'sort_code').prefetch_related('series',
                                                         'brand')

    vars = { 'indicia_publisher' : indicia_publisher,
             'error_subject': '%s' % indicia_publisher,
             'preview': preview }
    return paginate_response(request,
                             indicia_publisher_issues,
                             'gcd/details/indicia_publisher.html',
                             vars,
                             alpha=False)

def brand_group(request, brand_group_id):
    """
    Display the details page for a BrandGroup.
    """
    brand_group = get_object_or_404(BrandGroup, id = brand_group_id)
    if brand_group.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'brand_group', 'id': brand_group_id}))

    return show_brand_group(request, brand_group)

def show_brand_group(request, brand_group, preview=False):
    brand_issues = brand_group.active_issues().order_by(
      'series__sort_name', 'sort_code').prefetch_related('series',
                                                         'indicia_publisher')
    brand_emblems = brand_group.active_emblems()

    vars = {
        'brand' : brand_group,
        'brand_emblems': brand_emblems,
        'error_subject': '%s' % brand_group,
        'preview': preview
    }
    return paginate_response(request,
                             brand_issues,
                             'gcd/details/brand_group.html',
                             vars,
                             alpha=False)

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
    brand_issues = brand.active_issues().order_by(
      'series__sort_name', 'sort_code').prefetch_related('series',
                                                         'indicia_publisher')

    uses = brand.in_use.all()
    vars = {
        'brand' : brand,
        'uses' : uses,
        'error_subject': '%s' % brand,
        'preview': preview
    }
    return paginate_response(request,
                             brand_issues,
                             'gcd/details/brand.html',
                             vars,
                             alpha=False)


def imprint(request, imprint_id):
    """
    Redirect to the change history page for an Imprint, which all are deleted.
    """
    imprint = get_object_or_404(Publisher, id = imprint_id, deleted=True)

    return HttpResponseRedirect(urlresolvers.reverse('change_history',
      kwargs={'model_name': 'imprint', 'id': imprint_id}))


def brands(request, publisher_id):
    """
    Finds brands of a publisher and presents them as a paginated list.
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

def brand_uses(request, publisher_id):
    """
    Finds brand emblems used at a publisher and presents them as a paginated list.
    """

    publisher = get_object_or_404(Publisher, id = publisher_id)
    if publisher.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'publisher', 'id': publisher_id}))

    brand_uses = publisher.branduse_set.all()

    sort = ORDER_ALPHA
    if 'sort' in request.GET:
        sort = request.GET['sort']

    if (sort == ORDER_CHRONO):
        brand_uses = brand_uses.order_by('year_began', 'emblem__name')
    else:
        brand_uses = brand_uses.order_by('emblem__name', 'year_began')

    return paginate_response(request, brand_uses,
      'gcd/details/brand_uses.html', {
        'publisher' : publisher,
        'error_subject' : '%s brands' % publisher,
      })

def indicia_publishers(request, publisher_id):
    """
    Finds indicia publishers of a publisher and presents them as
    a paginated list.
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

def series(request, series_id):
    """
    Display the details page for a series.
    """

    series = get_object_or_404(Series.objects.select_related('publisher'),
                               id=series_id)
    if series.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'series', 'id': series_id}))
    if series.is_singleton and series.issue_count:
        return HttpResponseRedirect(
          urlresolvers.reverse(issue, kwargs={ 'issue_id': int(series.active_issues()[0].id) }))

    return show_series(request, series)

def show_series(request, series, preview=False):
    """
    Helper function to handle the main work of displaying a series.
    Also used by OI previews.
    """
    covers = []

    scans, image_tag, issue = _get_scan_table(series)

    if series.has_issue_title:
        issue_status_width = "status_wide";
    else:
        issue_status_width = "status_small";

    if series.has_issue_title:
        cover_status_width = "status_wide";
    elif series.active_issues().exclude(variant_name='').count():
        cover_status_width = "status_medium";
    else:
        cover_status_width = "status_small";

    return render(request, 'gcd/details/series.html',
      {
        'series': series,
        'scans': scans,
        'image_tag': image_tag,
        'image_issue': issue,
        'country': series.country,
        'language': series.language,
        'issue_status_width': issue_status_width,
        'cover_status_width': cover_status_width,
        'error_subject': '%s' % series,
        'preview': preview,
        'is_empty': IS_EMPTY,
        'is_none': IS_NONE,
        'RANDOM_IMAGE': _publisher_image_content(series.publisher_id)
      })

def series_details(request, series_id, by_date=False):
    """
    Displays a non-paginated list of all issues in a series along with
    certain issue-level data fields.

    Works in two forms- one which is a straight ordered listing, and the
    other which attempts to graphically represent the issues in a timeline,
    with special handling for issues whose date cannot be resolved.
    """
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
            except ValueError as ve:
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

    volume_present = (series.has_volume and
        series.active_issues().filter(no_volume=False)
              .exclude(volume='').exists())
    brand_present = (series.active_issues().filter(no_brand=False)
                           .exclude(brand__isnull=True).exists())
    frequency_present = (series.has_indicia_frequency and
        series.active_issues().filter(no_indicia_frequency=False)
              .exclude(indicia_frequency='').exists())
    isbn_present = (series.has_isbn and
        series.active_issues().filter(no_isbn=False)
              .exclude(isbn='').exists())
    barcode_present = (series.has_barcode and
        series.active_issues().filter(no_barcode=False)
              .exclude(barcode='').exists())
    title_present = (series.has_issue_title and
        series.active_issues().filter(no_title=False)
              .exclude(title='').exists())
    on_sale_date_present = (series.active_issues()
                                  .exclude(on_sale_date='').exists())
    rating_present = (series.has_rating and
        series.active_issues().filter(no_rating=False)
              .exclude(rating='').exists())

    return render(request, 'gcd/details/series_details.html',
      {
        'series': series,
        'by_date': by_date,
        'rows': issues_by_date,
        'no_date_rows': issues_left_over,
        'volume_present': volume_present,
        'brand_present': brand_present,
        'frequency_present': frequency_present,
        'isbn_present': isbn_present,
        'barcode_present': barcode_present,
        'title_present': title_present,
        'on_sale_date_present': on_sale_date_present,
        'rating_present': rating_present,
        'bad_dates': len(bad_key_dates),
      })

def change_history(request, model_name, id):
    """
    Displays the change history of the given object of the type
    specified by model_name.
    """
    from apps.oi.views import DISPLAY_CLASSES, REVISION_CLASSES
    if model_name not in ['publisher', 'brand_group', 'brand',
                          'indicia_publisher', 'series', 'issue', 'cover',
                          'image', 'series_bond', 'award', 'creator_degree',
                          'creator', 'creator_membership', 'received_award',
                          'creator_art_influence', 'creator_non_comic_work',
                          'creator_relation', 'feature', 'feature_logo']:
        if not (model_name == 'imprint' and
          get_object_or_404(Publisher, id=id).deleted):
            return render(
              request, 'indexer/error.html',
              {'error_text':
               'There is no change history for this type of object.'})
    if model_name == 'cover' and not request.user.has_perm('indexer.can_vote'):
        return render(
          request, 'indexer/error.html',
          {'error_text':
           'Only members can access the change history for covers.'})

    template = 'gcd/details/change_history.html'
    prev_issue = None
    next_issue = None

    if model_name == 'imprint':
        object = get_object_or_404(Publisher, id=id)
        filter_string = 'publisherrevisions__publisher'

    else:
        object = get_object_or_404(DISPLAY_CLASSES[model_name], id=id)

        # filter is publisherrevisions__publisher, seriesrevisions__series, etc.
        filter_string = '%ss__%s' % (REVISION_CLASSES[model_name].__name__.lower(),
                                     model_name)

    kwargs = { str(filter_string): object, 'state': states.APPROVED }
    changesets = Changeset.objects.filter(**kwargs).order_by('-modified', '-id')

    if model_name == 'issue':
        [prev_issue, next_issue] = object.get_prev_next_issue()

    return render(request, template,
      {
        'description': model_name.replace('_', ' ').title(),
        'object': object,
        'changesets': changesets,
        'prev_issue': prev_issue,
        'next_issue': next_issue,
      })

def _handle_key_date(issue, grid_date, prev_year, prev_month, issues_by_date):
    """
    Helper function for building timelines of issues by key_date.
    """
    if prev_year == None:
        issues_by_date.append({'date': grid_date, 'issues': [issue]})

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
    return HttpResponseRedirect(urlresolvers.reverse('show_series',
      kwargs={'series_id': series_id}) + '#index_status')


def _get_scan_table(series, show_cover=True):
    # freshly added series have no scans on preview page
    if series is None:
        return None, None, None

    if not series.is_comics_publication:
        return Cover.objects.none(), get_image_tag(cover=None, 
          zoom_level=ZOOM_MEDIUM, alt_text='First Issue Cover', 
          can_have_cover=series.is_comics_publication), None
    # all a series' covers + all issues with no covers
    covers = Cover.objects.filter(issue__series=series, deleted=False) \
                          .select_related()
    issues = series.issues_without_covers()

    list_covers = list(covers)
    scans = list(issues)
    scans.extend(list_covers)
    scans.sort(key=attrgetter('sort_code'))

    if covers and show_cover:
        selected_cover = covers[randint(0, covers.count()-1)]
        image_tag = get_image_tag(cover=selected_cover,
                                  zoom_level=ZOOM_MEDIUM,
                                  alt_text='Random Cover from Series')
        issue = selected_cover.issue
    else:
        image_tag = None
        issue = None

    return scans, image_tag, issue


def scans(request, series_id):
    """
    Display the cover scan status matrix for a series.
    """
    return HttpResponseRedirect(urlresolvers.reverse('show_series',
      kwargs={'series_id': series_id}) + '#cover_status')


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
        'starts_with' : starts_with,
        'RANDOM_IMAGE': 2,
      },
      per_page=COVERS_PER_GALLERY_PAGE,
      callback_key='tags',
      callback=get_image_tags_per_page)


def daily_covers(request, show_date=None, user=False):
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
                '%scovers_by_date' % ('my_' if user else ''),
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
            '%scovers_by_date' % ('my_' if user else ''),
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
    if user and request.user.is_authenticated:
        revisions = CoverRevision.objects.filter(
          changeset__comments__created__range=(datetime.combine(requested_date,
                                                                time.min),
                                               datetime.combine(requested_date,
                                                                time.max)),
          changeset__indexer=request.user, changeset__comments__new_state=5)
        covers = covers.filter(revisions__in=revisions)

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
        'RANDOM_IMAGE': 2,
        'choose_url_before': urlresolvers.reverse(
          '%scovers_by_date' % ('my_' if user else ''),
          kwargs={'show_date': date_before}),
        'choose_url_after': urlresolvers.reverse(
          '%scovers_by_date' % ('my_' if user else ''),
          kwargs={'show_date': date_after}),
        'other_url': urlresolvers.reverse(
          '%scovers_by_date' % ('my_' if user is False else ''),
          kwargs={'show_date': requested_date}),
      },
      per_page=COVERS_PER_GALLERY_PAGE,
      callback_key='tags',
      callback=get_image_tags_per_page)


def _get_daily_revisions(model, args, model_name, change_type=None,
                         user=None):
    anon = User.objects.get(username=settings.ANON_USER_NAME)
    if change_type is None:
        change_type = model_name
    revisions = model.objects.filter(
      changeset__change_type=CTYPES[change_type], **args)\
      .exclude(changeset__indexer=anon).values_list(model_name,
                                                    flat=True)
    if user is None:
        return revisions
    else:
        return revisions.filter(changeset__indexer=user)


def daily_changes(request, show_date=None, user=False):
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
                '%schanges_by_date' % ('my_' if user is not None else ''),
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
            '%schanges_by_date' % ('my_' if user is not None else ''),
            kwargs={'show_date' : date.today().strftime('%Y-%m-%d') }))

    date_before = requested_date + timedelta(-1)
    if requested_date < date.today():
        date_after = requested_date + timedelta(1)
    else:
        date_after = None

    args = {'changeset__modified__range' : \
                (datetime.combine(requested_date, time.min),
                 datetime.combine(requested_date, time.max)),
            'deleted':False,
            'changeset__state': states.APPROVED }

    if user and request.user.is_authenticated:
        user = request.user
    else:
        user = None

    # TODO what aboud awards, memberships, etc. Display separately,
    # or display the affected creator for such changes as well.
    creator_revisions = list(_get_daily_revisions(CreatorRevision, args,
                                                  'creator', user=user))
    creators = Creator.objects.filter(id__in=creator_revisions).distinct()

    publisher_revisions = list(_get_daily_revisions(PublisherRevision, args,
                                                    'publisher', user=user))
    publishers = Publisher.objects.filter(id__in=publisher_revisions)\
                                  .distinct().select_related('country')

    brand_group_revisions = list(_get_daily_revisions(BrandGroupRevision,
                                                      args, 'brand_group',
                                                      user=user))
    brand_groups = BrandGroup.objects.filter(id__in=brand_group_revisions)\
      .distinct().select_related('parent__country')

    brand_revisions = list(_get_daily_revisions(BrandRevision, args, 'brand',
                                                user=user))
    brands = Brand.objects.filter(id__in=brand_revisions).distinct()\
      .prefetch_related('group__parent__country')

    ind_pub_revisions = list(_get_daily_revisions(IndiciaPublisherRevision,
                                                  args, 'indicia_publisher',
                                                  user=user))
    indicia_publishers = IndiciaPublisher.objects.filter(
      id__in=ind_pub_revisions).distinct()\
      .select_related('parent__country')

    series_revisions = list(_get_daily_revisions(SeriesRevision, args,
                                                 'series', user=user))
    series = Series.objects.filter(id__in=series_revisions).distinct()\
      .select_related('publisher','country', 'first_issue','last_issue')

    series_bond_revisions = list(_get_daily_revisions(SeriesBondRevision,
                                                      args, 'series_bond',
                                                      user=user))
    series_bonds = SeriesBond.objects.filter(id__in=series_bond_revisions)\
      .distinct().select_related('origin','target')

    issue_revisions = list(_get_daily_revisions(IssueRevision, args, 'issue',
                                                user=user))
    issue_revisions.extend(list(_get_daily_revisions(IssueRevision, args,
                                                     'issue', 'variant_add',
                                                     user=user)))
    issues = Issue.objects.filter(id__in=issue_revisions).distinct()\
      .select_related('series__publisher', 'series__country')

    images = []
    image_revisions = _get_daily_revisions(ImageRevision, args, 'image',
                                           user=user)

    brand_revisions = list(image_revisions.filter(type__name='BrandScan'))
    brand_images = Brand.objects.filter(image_resources__id__in=brand_revisions).distinct()
    if brand_images:
      images.append((brand_images, '', 'Brand emblem', 'brand'))

    indicia_revisions = list(image_revisions.filter(type__name='IndiciaScan'))
    indicia_issues = Issue.objects.filter(image_resources__id__in=indicia_revisions)
    if indicia_issues:
      images.append((indicia_issues, 'image/', 'Indicia Scan', 'issue'))

    soo_revisions = list(image_revisions.filter(type__name='SoOScan'))
    soo_issues = Issue.objects.filter(image_resources__id__in=soo_revisions)
    if soo_issues:
      images.append((soo_issues, 'image/', 'Statement of ownership', 'issue'))

    return render(request, 'gcd/status/daily_changes.html',
      {
        'date' : show_date,
        'choose_url_before': urlresolvers.reverse(
          '%schanges_by_date' % ('my_' if user is not None else ''),
          kwargs={'show_date': date_before}),
        'choose_url_after': urlresolvers.reverse(
          '%schanges_by_date' % ('my_' if user is not None else ''),
          kwargs={'show_date': date_after}),
        'other_url': urlresolvers.reverse(
          '%schanges_by_date' % ('my_' if user is None else ''),
          kwargs={'show_date': requested_date}),
        'creators' : creators,
        'publishers' : publishers,
        'brand_groups' : brand_groups,
        'brands' : brands,
        'indicia_publishers' : indicia_publishers,
        'series' : series,
        'series_bonds' : series_bonds,
        'issues' : issues,
        'all_images' : images
      })

def do_on_sale_weekly(request, year=None, week=None):
    """
    Produce a page displaying the comics on-sale in a given week.
    """
    try:
        if 'week' in request.GET:
            year = int(request.GET['year'])
            week = int(request.GET['week'])
            # Do a redirect, otherwise pagination links point to today
            return HttpResponseRedirect(
                urlresolvers.reverse(
                'on_sale_weekly',
                kwargs={'year': year, 'week': week} )), None
        if year:
            year = int(year)
        if week:
            week = int(week)
    except ValueError:
        year = None
    if year == None:
        year, week = date.today().isocalendar()[0:2]
    # gregorian calendar date of the first day of the given ISO year
    fourth_jan = date(int(year), 1, 4)
    delta = timedelta(fourth_jan.isoweekday()-1)
    year_start = fourth_jan - delta
    monday = year_start + timedelta(weeks=int(week)-1)
    sunday = monday + timedelta(days=6)
    # we need this to filter out incomplete on-sale dates
    if monday.month != sunday.month:
        endday = monday.replace(day=monthrange(monday.year,monday.month)[1])
        issues_on_sale = \
          Issue.objects.filter(on_sale_date__gte=monday.isoformat(),
                               on_sale_date__lte=endday.isoformat())
        startday = sunday.replace(day=1)
        issues_on_sale = issues_on_sale | \
          Issue.objects.filter(on_sale_date__gte=startday.isoformat(),
                               on_sale_date__lte=sunday.isoformat())

    else:
        issues_on_sale = Issue.objects\
                              .filter(on_sale_date__gte=monday.isoformat(),
                                      on_sale_date__lte=sunday.isoformat())
    previous_week = (monday - timedelta(weeks=1)).isocalendar()[0:2]
    if monday + timedelta(weeks=1) <= date.today():
        next_week = (monday + timedelta(weeks=1)).isocalendar()[0:2]
    else:
        next_week = None
    heading = "Issues on-sale in week %s/%s" % (week, year)
    dates = "from %s to %s" % (monday.isoformat(), sunday.isoformat())
    query_val = {'target': 'issue', 
                 'method': 'icontains'}
    query_val['start_date'] = monday.isoformat()
    query_val['end_date'] = sunday.isoformat()
    query_val['use_on_sale_date'] = True
    issues_on_sale = issues_on_sale.filter(deleted=False)
    vars = { 
        'items': issues_on_sale,
        'heading': heading,
        'dates': dates,
        'previous_week': previous_week,
        'next_week': next_week,
        'query_string': urlencode(query_val),
    }
    return issues_on_sale, vars


def on_sale_weekly(request, year=None, week=None):
    issues_on_sale, vars = do_on_sale_weekly(request, year, week)
    if vars == None:
        return issues_on_sale
    return paginate_response(request, issues_on_sale,
                             'gcd/status/issues_on_sale.html', vars)


def int_stats_language(request):
    """
    Display the international stats by language
    """
    choices = [("series", "series"),
               ("issues", "issues"),
               ("variant issues", "variant issues"),
               ("issue indexes", "issues indexed"),
               ("covers", "covers"),
               ("stories", "stories")]
    return int_stats(request, Language, choices)

def int_stats_country(request):
    """
    Display the international stats by country
    """
    choices = [("publishers", "publishers"),
               ("indicia publishers", "indicia publishers"),
               ("series", "series"),
               ("issues", "issues"),
               ("variant issues", "variant issues"),
               ("issue indexes", "issues indexed"),
               ("covers", "covers"),
               ("stories", "stories")]
    return int_stats(request, Country, choices)

def int_stats(request, object_type, choices):
    """
    Display the international stats
    """
    f = get_generic_select_form(choices)
    if 'submit' in request.GET:
        form = f(request.GET)
        order_by = form.data['object_choice']
    else:
        form = f(initial={'object_choice': 'issue indexes'})
        order_by = 'issue indexes'

    objects = object_type.objects.filter(countstats__name=order_by) \
                            .order_by('-countstats__count', 'name')
    object_name = (object_type.__name__).lower()
    stats=[]
    for obj in objects:
        kwargs = {object_name: obj}
        stats.append((obj, CountStats.objects.filter(**kwargs)))

    return render(request, 'gcd/status/international_stats.html',
      {
        'stats' : stats,
        'type' : object_name,
        'form': form
      })


def feature(request, feature_id):
    """
    Display the details page for a Feature.
    """
    feature = get_object_or_404(Feature, id = feature_id)
    if feature.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'feature', 'id': feature_id}))

    return show_feature(request, feature)


def show_feature(request, feature, preview=False):
    logos = feature.active_logos().order_by(
      'year_began', 'name')

    vars = { 'feature' : feature,
             'error_subject': '%s' % feature,
             'preview': preview }
    return paginate_response(request,
                             logos,
                             'gcd/details/feature.html',
                             vars)


def feature_logo(request, feature_logo_id):
    """
    Display the details page for a Feature.
    """
    feature_logo = get_object_or_404(FeatureLogo, id = feature_logo_id)
    if feature_logo.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'feature_logo', 'id': feature_logo_id}))

    return show_feature_logo(request, feature_logo)


def show_feature_logo(request, feature_logo, preview=False):
    vars = { 'feature_logo' : feature_logo,
             'error_subject': '%s' % feature_logo,
             'preview': preview }
    return render(request, 'gcd/details/feature_logo.html', vars)


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

    cover_tag = get_image_tags_per_issue(issue, "Cover for %s" % \
                                                str(issue.full_name()), 
                                         size, variants=True, as_list=True)
    extra = 'cover/%d/' % size  # TODO: remove abstraction-breaking hack.

    covers = Cover.objects.filter(issue__series=issue.series,
                                  issue__sort_code__lt=issue.sort_code,
                                  deleted=False)
    cover_page = covers.count()/COVERS_PER_GALLERY_PAGE + 1

    return render(request, 'gcd/details/cover.html',
      {
        'issue': issue,
        'prev_issue': prev_issue,
        'next_issue': next_issue,
        'cover_tag': cover_tag,
        'cover_page': cover_page,
        'extra': extra,
        'error_subject': '%s cover' % issue,
        'RANDOM_IMAGE': _publisher_image_content(issue.series.publisher_id)
      })

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
    if request.user.is_authenticated and \
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
      'can_mark': can_mark,
      'RANDOM_IMAGE': _publisher_image_content(series.publisher_id)
    }

    return paginate_response(request, covers, 'gcd/details/covers.html', vars,
      per_page=COVERS_PER_GALLERY_PAGE,
      callback_key='tags',
      callback=lambda page: get_image_tags_per_page(page, series))

def issue_images(request, issue_id):
    """
    Display the images for a single issue on its own page.
    """

    issue = get_object_or_404(Issue, id = issue_id)

    if issue.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'issue', 'id': issue_id}))

    [prev_issue, next_issue] = issue.get_prev_next_issue()

    indicia_image = issue.indicia_image
    if indicia_image:
        indicia_tag = get_generic_image_tag(indicia_image, 'indicia scan')
    else:
        indicia_tag = None

    soo_image = issue.soo_image
    if soo_image:
        soo_tag = get_generic_image_tag(soo_image, 'statement of ownership scan')
    else:
        soo_tag = None

    return render(request, 'gcd/details/issue_images.html',
      {
        'issue': issue,
        'prev_issue': prev_issue,
        'next_issue': next_issue,
        'indicia_tag': indicia_tag,
        'indicia_image': indicia_image,
        'soo_tag': soo_tag,
        'soo_image': soo_image,
        'extra': 'image/'
      })

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
    issue = get_object_or_404(
              Issue.objects.select_related('series__publisher'),
              id=issue_id)

    if issue.deleted:
        return HttpResponseRedirect(urlresolvers.reverse('change_history',
          kwargs={'model_name': 'issue', 'id': issue_id}))

    return show_issue(request, issue)


def show_issue(request, issue, preview=False):
    """
    Helper function to handle the main work of displaying an issue.
    Also used by OI previews.
    """
    alt_text = 'Cover Thumbnail for %s' % issue.full_name()
    zoom_level = ZOOM_MEDIUM

    if 'issue_detail' in request.GET:
        try:
            issue_detail = int(request.GET['issue_detail'])
        except ValueError:
            issue_detail = 1
    elif request.user.is_authenticated:
        issue_detail = request.user.indexer.issue_detail
    else:
        issue_detail = 1
    if issue_detail == 0:
        not_shown_types = StoryType.objects.exclude(id__in=CORE_TYPES)\
                            .values_list('id', flat=True)
    elif issue_detail == 1:
        not_shown_types = AD_TYPES
    else:
        not_shown_types = []
    image_tag = get_image_tags_per_issue(issue=issue,
                                          zoom_level=zoom_level,
                                          alt_text=alt_text)
    images_count = Image.objects.filter(object_id=issue.id, deleted=False,
      content_type = ContentType.objects.get_for_model(issue)).count()

    if preview:
        cover_page = 0
    else:
        covers = Cover.objects.filter(issue__series=issue.series,
                                      issue__sort_code__lt=issue.sort_code,
                                      deleted=False)
        cover_page = covers.count()/COVERS_PER_GALLERY_PAGE + 1

    variant_image_tags = []
    for variant_cover in issue.variant_covers():
        variant_image_tags.append([variant_cover.issue,
          get_image_tag(variant_cover, zoom_level=ZOOM_SMALL,
          alt_text='Cover Thumbnail for %s' % str(variant_cover.issue))])

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
    oi_indexers = []
    if not preview:
        res = issue.reservation_set.filter(status=3)
        for i in res:
            oi_indexers.append(i.indexer)

    res = IssueRevision.objects.filter(issue=issue)
    res = res.filter(changeset__state=states.APPROVED)\
             .exclude(changeset__indexer__username=settings.ANON_USER_NAME)
    for i in res:
        oi_indexers.append(i.changeset.indexer.indexer)
    oi_indexers = list(set(oi_indexers))

    if series.is_singleton:
        country = series.country
        language = series.language
    else:
        country = None
        language = None

    return render(request, 'gcd/details/issue.html',
      {
        'issue': issue,
        'prev_issue': prev_issue,
        'next_issue': next_issue,
        'cover_story': cover_story,
        'stories': stories,
        'oi_indexers' : oi_indexers,
        'image_tag': image_tag,
        'variant_image_tags': variant_image_tags,
        'images_count': images_count,
        'cover_page': cover_page,
        'country': country,
        'language': language,
        'error_subject': '%s' % issue,
        'preview': preview,
        'not_shown_types': not_shown_types,
        'RANDOM_IMAGE': _publisher_image_content(issue.series.publisher_id)
      })


# this should later be moved to admin.py or something like that
def countries_in_use(request):
    """
    Show list of countries with name and flag.
    Main use is to find missing names and flags.
    """

    if request.user.is_authenticated and \
       request.user.groups.filter(name='admin'):
        countries_from_series = set(
                Series.objects.exclude(deleted=True).
                values_list('country', flat=True))
        countries_from_indexers = set(
                Indexer.objects.filter(user__is_active=True).
                values_list('country', flat=True))
        countries_from_publishers = set(
                Publisher.objects.exclude(deleted=True).
                values_list('country', flat=True))
        countries_from_creators = set(
                country for tuple in
                Creator.objects.exclude(deleted=True).
                values_list('birth_country', 'death_country')
                for country in tuple)
        used_ids = list(countries_from_indexers |
                        countries_from_series |
                        countries_from_publishers |
                        countries_from_creators)
        used_countries = Country.objects.filter(id__in=used_ids)

        return render(request, 'gcd/admin/countries.html',
                      {'countries': used_countries})
    else:
        return render(request, 'indexer/error.html',
                      {'error_text':
                       'You are not allowed to access this page.'})


def agenda(request, language):
    """
    TODO: Why is this called agenda?  It sounds like a voting app thing but isn't.
    """
    try:
        f = urlopen("https://www.google.com/calendar/embed?src=comics.org_v62prlv9"
          "dp79hbjt4du2unqmks%%40group.calendar.google.com&showTitle=0&showNav=0&"
          "showDate=0&showPrint=0&showTabs=0&showCalendars=0&showTz=0&mode=AGENDA"
          "&height=600&wkst=1&bgcolor=%%23FFFFFF&color=%%238C500B"
          "&ctz=GMT&hl=%s" % language)
    except HTTPError:
        raise Http404

    a = f.read().decode(encoding='UTF-8')
    # two possibilites here
    # a) use an absolute url to the calendar, but than not all works,
    #    i.e. images don't show
    # b) replace by our own copy of the javascript with some edits,
    #    used to work, but not currently. If we want to use that again,
    #    need to replace the google link between js_pos and js_pos_end
    #    with one pointing to our own edited version, one per language
    #js_pos = a.find('<script type="text/javascript" src="') + \
    #         len('<script type="text/javascript" src="')
    # js_pos_end = a[js_pos:].find('"></script>') + js_pos
    #a = a[:js_pos] + 'http://www.google.com/calendar/' + a[js_pos:]

    css_text = '<link type="text/css" rel="stylesheet" href="'
    css_pos = a.find(css_text) + len(css_text)
    css_pos_end = a[css_pos:].find('">') + css_pos
    a = a[:css_pos]  + settings.STATIC_URL + \
      'calendar/css/c9ff6efaf72bf95e3e2b53938d3fbacaembedcompiled_fastui.css' \
      + a[css_pos_end:]
    javascript_text = '<script type="text/javascript" src="'
    javascript_pos = a.find(javascript_text) + len(javascript_text)
    a = a[:javascript_pos] + '//www.google.com' + a[javascript_pos:]

    return HttpResponse(a.encode(encoding='UTF-8'))
