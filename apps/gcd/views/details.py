# -*- coding: utf-8 -*-

"""View methods for pages displaying entity details."""

import re
from urllib.parse import urlencode, quote
from datetime import date, datetime, time, timedelta
from calendar import monthrange
from operator import attrgetter
from random import randint

from django.db.models import F, Q, Min, Count, Sum, Case, When, Value, \
                             OuterRef, Subquery
from django.conf import settings
import django.urls as urlresolvers
from django.shortcuts import get_object_or_404, \
                             render
from django.http import HttpResponseRedirect, Http404, JsonResponse, \
                        HttpResponse
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.template.defaultfilters import pluralize
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.utils.safestring import mark_safe

from django_tables2 import RequestConfig
from django_tables2.paginators import LazyPaginator
from django_tables2.export.export import TableExport
import django_tables2 as tables

from djqscsv import render_to_csv_response

from taggit.models import Tag, TaggedItem

from apps.indexer.views import ViewTerminationError
from apps.indexer.models import Indexer

from apps.stddata.models import Country, Language
from apps.stats.models import CountStats

from apps.gcd.models import Publisher, Series, Issue, StoryType, Image, \
                            IndiciaPublisher, Brand, BrandGroup, Cover, \
                            SeriesBond, Award, Creator, CreatorMembership, \
                            ReceivedAward, CreatorDegree, \
                            CreatorArtInfluence, CreatorRelation, \
                            CreatorSchool, CreatorNameDetail, \
                            CreatorNonComicWork, CreatorSignature, \
                            Feature, FeatureLogo, FeatureRelation, \
                            Printer, IndiciaPrinter, School, Story, \
                            Character, CharacterNameDetail, Group, \
                            GroupNameDetail, Universe, Multiverse, \
                            StoryCredit, \
                            CharacterRelation, GroupRelation, GroupMembership
from apps.gcd.models.creator import GenericCreatorTable, \
                                    GenericCreatorNameTable, \
                                    CreatorPortraitTable, \
                                    NAME_TYPES
from apps.gcd.models.character import CharacterTable, CreatorCharacterTable, \
                                      UniverseCharacterTable, \
                                      SeriesCharacterTable, \
                                      FeatureCharacterTable, \
                                      CharacterCharacterTable
from apps.gcd.models.feature import CreatorFeatureTable, \
                                    CharacterFeatureTable, \
                                    GroupFeatureTable, FeatureLogoTable
from apps.gcd.models.issue import IssueTable, BrandGroupIssueTable, \
                                  BrandGroupIssueCoverTable, \
                                  BrandEmblemIssueTable, \
                                  BrandEmblemIssueCoverTable, \
                                  IndiciaPublisherIssueTable, \
                                  IndiciaPublisherIssueCoverTable, \
                                  IssuePublisherTable, PublisherIssueTable, \
                                  SeriesDetailsIssueTable, \
                                  IssueCoverTable, \
                                  IssueCoverPublisherTable, \
                                  PublisherIssueCoverTable
from apps.gcd.models.publisher import BrandEmblemPublisherTable, \
                                      BrandGroupPublisherTable, \
                                      IndiciaPublisherPublisherTable, \
                                      BrandEmblemGroupTable, \
                                      BrandGroupEmblemTable
from apps.gcd.models.series import SeriesTable, CreatorSeriesTable, \
                                   CharacterSeriesTable, GroupSeriesTable
from apps.gcd.models.story import CREDIT_TYPES, CORE_TYPES, AD_TYPES, \
                                  StoryTable
from apps.gcd.views import paginate_response, ORDER_CHRONO, \
                           ResponsePaginator
from apps.gcd.views.covers import get_image_tag, get_generic_image_tag, \
                                  get_image_tags_per_issue, \
                                  get_image_tags_per_page
from apps.gcd.models.cover import CoverIssuePublisherTable, \
                                  CoverIssueStoryTable, \
                                  CoverIssueStoryPublisherTable, \
                                  CoverIssuePublisherEditTable, \
                                  OnSaleCoverIssueTable, \
                                  CoverSeriesTable, \
                                  ZOOM_SMALL, ZOOM_MEDIUM, ZOOM_LARGE
from apps.gcd.forms import get_generic_select_form
from apps.oi import states
from apps.oi.models import IssueRevision, SeriesRevision, PublisherRevision, \
                           BrandGroupRevision, BrandRevision, CoverRevision, \
                           IndiciaPublisherRevision, ImageRevision, \
                           Changeset, SeriesBondRevision, CreatorRevision, \
                           CTYPES
from apps.select.views import KeywordUsedFilter, filter_series, \
                              filter_issues, filter_covers, filter_sequences, \
                              FilterForLanguage

KEY_DATE_REGEXP = \
  re.compile(r'^(?P<year>\d{4})\-(?P<month>\d{2})\-(?P<day>\d{2})$')

# TODO: Pull this from the DB somehow, but not on every page load.
MIN_GCD_YEAR = 1800

COVER_TABLE_WIDTH = 5
COVERS_PER_GALLERY_PAGE = 50

IS_EMPTY = '[IS_EMPTY]'
IS_NONE = '[IS_NONE]'

ISSUE_CHECKLIST_DISCLAIMER = 'Results for stories, covers, '\
                             'and cartoons are shown.'
OVERVIEW_DISCLAIMER = 'In the overview only comic stories are shown.'
COVER_CHECKLIST_DISCLAIMER = 'Results for covers are shown.'
MIGRATE_DISCLAIMER = ' Text credits are currently being migrated to '\
                     'links. Therefore not all credits in our '\
                     'database are shown here.'

SORT_TABLE_TEMPLATE = 'gcd/bits/sortable_table.html'
TW_SORT_TABLE_TEMPLATE = 'gcd/bits/tw_sortable_table.html'
TW_SORT_GRID_TEMPLATE = 'gcd/bits/tw_sortable_grid.html'

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
    if hasattr(object, 'deleted') and object.deleted:
        if not model_name:
            model_name = model._meta.model_name
        raise ViewTerminationError(
          response=HttpResponseRedirect(
            urlresolvers.reverse('change_history',
                                 kwargs={'model_name': model_name,
                                         'id': object_id})))
    return object


def generic_sortable_list(request, items, table, template, context,
                          per_page=100):
    paginator = ResponsePaginator(items, per_page=per_page, vars=context)
    page_number = paginator.paginate(request).number
    request_get = request.GET.copy()
    request_get.pop('page', None)
    query_string = request_get.urlencode()
    RequestConfig(request, paginate={"paginator_class": LazyPaginator,
                                     'per_page': per_page,
                                     'page': page_number}).configure(table)
    export_format = request.GET.get("_export", None)
    if TableExport.is_valid_format(export_format):
        exporter = TableExport(export_format, table)
        return exporter.response("table.{}".format(export_format))
    if export_format and export_format in ['db_csv', 'db_json']:
        fields = [f.name for f in items.model._meta.get_fields()
                  if f.auto_created is False]
        fields = [f for f in fields if f not in {'created', 'modified',
                                                 'deleted', 'keywords',
                                                 'tagged_items', 'awards',
                                                 'portrait', 'sample_scan'}]
        fields.insert(0, 'id')
        if export_format == 'db_csv':
            return render_to_csv_response(items.values(*fields),
                                          append_datestamp=True)
        if export_format == 'db_json':
            data = list(items.values(*fields))
            return JsonResponse(data, safe=False)

    context['table'] = table
    context['query_string'] = query_string
    return render(request, template, context)


def _handle_date_picker(request, url_reverse,
                        show_date=None, monthly=False, kwargs={}):
    try:
        daily = not monthly
        if 'year' in request.GET:
            year = int(request.GET['year'])
            month = int(request.GET['month'])
            if 'sort' in request.GET:
                sort = '?sort=' + request.GET['sort']
            else:
                sort = ''
            if daily:
                day = int(request.GET['day'])
                # Do a redirect, otherwise pagination links point to today
                requested_date = date(year, month, day)
                show_date = requested_date.strftime('%Y-%m-%d')
                return HttpResponseRedirect(
                  urlresolvers.reverse(
                    url_reverse,
                    kwargs={'show_date': show_date})), False
            elif monthly:
                kwargs['year'] = int(year)
                kwargs['month'] = int(month)
                return HttpResponseRedirect(
                    urlresolvers.reverse(
                        url_reverse,
                        kwargs=kwargs) + sort), False
        elif show_date:
            year = int(show_date[0:4])
            month = int(show_date[5:7])
            day = int(show_date[8:10])
            requested_date = date(year, month, day)
        else:
            # Don't redirect, as this is a proper default.
            if daily:
                requested_date = date.today()
                show_date = requested_date.strftime('%Y-%m-%d')
            elif monthly:
                year = date.today().year
                month = date.today().month
    except (TypeError, ValueError):
        if monthly:
            kwargs = {}
            kwargs['year'] = date.today().year
            kwargs['month'] = date.today().month
            return HttpResponseRedirect(
                urlresolvers.reverse(
                    url_reverse,
                    kwargs=kwargs)), False
        else:
            # Redirect so the user sees the date in the URL that matches
            # the output, instead of seeing the erroneous date.
            return HttpResponseRedirect(
              urlresolvers.reverse(
                url_reverse,
                kwargs={'show_date': date.today().strftime('%Y-%m-%d')})), \
              False

    if daily:
        return requested_date, show_date
    elif monthly:
        return (year, month), True


def _get_random_cover_image(request, object, object_filter, object_name):
    page = request.GET.get('page', None)
    image_tag = ''
    selected_issue = None
    if not page or page[-1] == '1':
        covers = Cover.objects.filter(
          **{'issue__%s' % object_filter: object},
          deleted=False)

        if covers.count() > 0:
            selected_cover = covers[randint(0, covers.count()-1)]
            selected_issue = selected_cover.issue
            image_tag = get_image_tag(cover=selected_cover,
                                      zoom_level=ZOOM_MEDIUM,
                                      alt_text='Random Cover from %s'
                                               % object_name)
    return image_tag, selected_issue


def creator(request, creator_id):
    creator = get_gcd_object(Creator, creator_id)
    return show_creator(request, creator)


def show_creator(request, creator, preview=False):
    gcd_name = creator.active_names().get(is_official_name=True)
    other_names = creator.active_names().filter(is_official_name=False)
    vars = {'creator': creator,
            'gcd_name': gcd_name,
            'other_names': other_names,
            'error_subject': creator,
            'preview': preview,
            'studio_types': [2, 3]}
    return render(request, 'gcd/details/tw_creator.html', vars)


def creator_sequences(request, creator_id, series_id=None,
                      country=None, language=None,
                      creator_name=False, signature=False):
    if creator_name:
        creator = get_gcd_object(CreatorNameDetail, creator_id)
        creator_names = CreatorNameDetail.objects.filter(id=creator_id)
    elif signature:
        signature = get_gcd_object(CreatorSignature, creator_id)
        creator = signature.creator
        creator_names = creator.creator_names.filter(deleted=False)
    else:
        creator = get_gcd_object(Creator, creator_id)
        creator_names = _get_creator_names_for_checklist(creator)

    stories = Story.objects.filter(credits__creator__in=creator_names,
                                   credits__deleted=False).distinct()\
                           .select_related('issue__series__publisher')
    if country:
        country = get_object_or_404(Country, code=country)
        stories = stories.filter(issue__series__country=country)
    if language:
        language = get_object_or_404(Language, code=language)
        stories = stories.filter(issue__series__language=language)
    if series_id:
        series = get_gcd_object(Series, series_id)
        stories = stories.filter(issue__series__id=series_id)
        heading = 'for creator %s in series %s' % (creator,
                                                   series)
    elif creator_name:
        heading = 'for Name %s of creator %s' % (creator,
                                                 creator.creator)
    elif signature:
        stories = stories.filter(credits__signature=signature,
                                 credits__deleted=False)
        heading = 'for signature %s of creator %s' % (signature,
                                                      creator)
    else:
        heading = 'for creator %s' % (creator)

    if not series_id:
        filter = filter_sequences(request, stories)
        stories = filter.qs
    else:
        filter = None

    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'sequence',
        'plural_suffix': 's',
        'heading': heading,
        'filter_form': filter.form
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = StoryTable(stories, attrs={'class': 'sortable_listing'},
                       template_name=TW_SORT_TABLE_TEMPLATE,
                       order_by=('issue'))
    return generic_sortable_list(request, stories, table, template, context)


def creator_characters(request, creator_id, country=None):
    creator = get_gcd_object(Creator, creator_id)
    names = _get_creator_names_for_checklist(creator)

    characters = Character.objects.filter(
      character_names__storycharacter__story__credits__creator__in=names,
      character_names__storycharacter__story__type__id__in=CORE_TYPES,
      character_names__storycharacter__story__credits__deleted=False)\
        .distinct()

    characters = characters.annotate(issue_count=Count(
      'character_names__storycharacter__story__issue', distinct=True))
    characters = characters.annotate(first_credit=Min(
      Case(When(character_names__storycharacter__story__issue__key_date='',
                then=Value('9999-99-99'),
                ),
           default=F('character_names__storycharacter__story__issue__key_date')
           )))
    target = 'character_names__storycharacter__story__credits__credit_type__id'
    script = Count('character_names__storycharacter__story__issue',
                   filter=Q(**{target: 1}),
                   distinct=True)
    pencils = Count('character_names__storycharacter__story__issue',
                    filter=Q(**{target: 2}),
                    distinct=True)
    inks = Count('character_names__storycharacter__story__issue',
                 filter=Q(**{target: 3}),
                 distinct=True)
    colors = Count('character_names__storycharacter__story__issue',
                   filter=Q(**{target: 4}),
                   distinct=True)
    letters = Count('character_names__storycharacter__story__issue',
                    filter=Q(**{target: 5}),
                    distinct=True)

    characters = characters.annotate(
      script=script,
      pencils=pencils,
      inks=inks,
      colors=colors,
      letters=letters)

    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'character',
        'plural_suffix': 's',
        'heading': 'for creator %s' % (creator)
    }
    template = 'gcd/search/tw_list_sortable.html'
    filter = FilterForLanguage(request.GET, characters,
                               language='language')
    characters = filter.qs
    context['filter_form'] = filter.form
    table = CreatorCharacterTable(characters,
                                  attrs={'class': 'sortable_listing'},
                                  creator=creator,
                                  template_name=TW_SORT_TABLE_TEMPLATE,
                                  order_by=('character'))
    return generic_sortable_list(request, characters, table, template, context)


def creator_creators(request, creator_id):
    # list of creators the creator creator_id worked with
    creator = get_gcd_object(Creator, creator_id)
    names = _get_creator_names_for_checklist(creator)

    stories = Story.objects.filter(credits__creator__in=names,
                                   credits__credit_type__id__lt=6,
                                   credits__deleted=False).distinct()
    filter = filter_sequences(request, stories)
    stories = filter.qs
    stories_ids = stories.values_list('id', flat=True)

    creators = Creator.objects.filter(
      creator_names__storycredit__story__id__in=stories_ids,
      creator_names__storycredit__story__type__id__in=CORE_TYPES,
      creator_names__storycredit__deleted=False,
      creator_names__storycredit__credit_type__id__lt=6).exclude(id=creator.id)
    creators = creators.annotate(
      issue_count=Count("creator_names__storycredit__story__issue",
                        distinct=True))
    creators = creators.annotate(first_credit=Min(
      Case(When(creator_names__storycredit__story__issue__key_date="",
                then=Value("9999-99-99"),
                ),
           default=F("creator_names__storycredit__story__issue__key_date"),
           )))

    target = 'creator_names__storycredit__credit_type__id'
    script = Count('creator_names__storycredit__story__issue',
                   filter=Q(**{target: 1}),
                   distinct=True)
    pencils = Count('creator_names__storycredit__story__issue',
                    filter=Q(**{target: 2}),
                    distinct=True)
    inks = Count('creator_names__storycredit__story__issue',
                 filter=Q(**{target: 3}),
                 distinct=True)
    colors = Count('creator_names__storycredit__story__issue',
                   filter=Q(**{target: 4}),
                   distinct=True)
    letters = Count('creator_names__storycredit__story__issue',
                    filter=Q(**{target: 5}),
                    distinct=True)

    creators = creators.annotate(
      script=script,
      pencils=pencils,
      inks=inks,
      colors=colors,
      letters=letters)

    context = {
        'result_disclaimer': ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER,
        'item_name': 'creator',
        'plural_suffix': 's',
        'heading': 'that worked with creator %s' % (creator),
        'filter_form': filter.form
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = _table_creators_list_or_grid(request, creators, context,
                                         resolve_name='co_creator',
                                         object=creator)
    return generic_sortable_list(request, creators, table, template, context)


def creator_features(request, creator_id, country=None, language=None):
    # list of features the creator creator_id worked on
    creator = get_gcd_object(Creator, creator_id)
    names = _get_creator_names_for_checklist(creator)

    features = Feature.objects.filter(story__credits__creator__in=names,
                                      story__credits__deleted=False).distinct()
    if language:
        language = get_object_or_404(Language, code=language)
        features = features.filter(language=language)

    features = features.annotate(issue_count=Count('story__issue',
                                                   distinct=True))
    features = features.annotate(first_credit=Min(
                                 Case(When(story__issue__key_date='',
                                           then=Value('9999-99-99'),
                                           ),
                                      default=F('story__issue__key_date'))))
    script = Count('story__issue',
                   filter=Q(story__credits__credit_type__id=1),
                   distinct=True)
    pencils = Count('story__issue',
                    filter=Q(story__credits__credit_type__id=2),
                    distinct=True)
    inks = Count('story__issue',
                 filter=Q(story__credits__credit_type__id=3),
                 distinct=True)
    colors = Count('story__issue',
                   filter=Q(story__credits__credit_type__id=4),
                   distinct=True)
    letters = Count('story__issue',
                    filter=Q(story__credits__credit_type__id=5),
                    distinct=True)

    features = features.annotate(
      script=script,
      pencils=pencils,
      inks=inks,
      colors=colors,
      letters=letters)

    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'feature',
        'plural_suffix': 's',
        'heading': 'for creator %s' % (creator),
    }
    template = 'gcd/search/tw_list_sortable.html'
    filter = FilterForLanguage(request.GET, features,
                               language='language')
    features = filter.qs
    context['filter_form'] = filter.form
    table = CreatorFeatureTable(features, attrs={'class': 'sortable_listing'},
                                creator=creator,
                                template_name=TW_SORT_TABLE_TEMPLATE,
                                order_by=('feature'))
    return generic_sortable_list(request, features, table, template, context)


def creator_overview(request, creator_id):
    creator = get_gcd_object(Creator, creator_id)
    creator_names = _get_creator_names_for_checklist(creator)
    filter = None

    issues = Issue.objects.filter(story__credits__creator__in=creator_names,
                                  story__type__id=19,
                                  story__credits__deleted=False,
                                  story__credits__credit_type__id__lt=6)\
                  .distinct().select_related('series__publisher')
    issues = issues.annotate(
        longest_story_id=Subquery(Story.objects.filter(
                                  credits__creator__in=creator_names,
                                  issue_id=OuterRef('pk'),
                                  type_id=19, deleted=False)
                                  .values('pk')
                                  .order_by('-page_count')[:1]))
    filter = filter_issues(request, issues)
    issues = filter.qs

    context = {
        'item_name': 'issue',
        'plural_suffix': 's',
        'publisher': True,
        'filter_form': filter.form,
        'heading': 'overview for creator %s' % (creator)
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = CoverIssueStoryTable(issues, attrs={'class': 'sortable_listing'},
                                 template_name=TW_SORT_TABLE_TEMPLATE,
                                 order_by=('publication_date'))
    return generic_sortable_list(request, issues, table, template, context, 50)


def creator_issues(request, creator_id, series_id=None, feature_id=None,
                   character_id=None, group_id=None, publisher_id=None,
                   country=None, language=None):
    return checklist_by_id(request, creator_id, series_id=series_id,
                           feature_id=feature_id, character_id=character_id,
                           group_id=group_id, publisher_id=publisher_id,
                           country=country, language=language)


def creator_edited_issues(request, creator_id, series_id=None,
                          country=None, language=None):
    return checklist_by_id(request, creator_id, series_id=series_id,
                           country=country, language=language, edits=True)


def _get_creator_names_for_checklist(creator):
    creator_names = creator.creator_names.filter(deleted=False)
    if creator.official_creator_detail.type_id in [NAME_TYPES['house'],
                                                   NAME_TYPES['joint']]:
        house_names = creator.from_related_creator.filter(
            relation_type_id=4, creator_name__isnull=False)\
            .values_list('creator_name', flat=True)
        creator_names |= CreatorNameDetail.objects.filter(id__in=house_names)
    creator_names = list(creator_names.values_list('id', flat=True))
    if creator.official_creator_detail.type_id == NAME_TYPES['studio']:
        employees = []
        for rel in creator.active_relations()\
                          .filter(relation_type_id__in=[2, 3]):
            if rel.creator_name.all():
                for name in rel.creator_name.all():
                    employees.append(name.id)
        creator_names.extend(employees)
    return creator_names


def creator_series(request, creator_id, country=None, language=None):
    if '_export' in request.GET:
        if request.GET['_export'] in ['db_csv', 'db_json']:
            return render(request, 'indexer/error.html',
                          {'error_text':
                           'There is no raw export for these objects.'})
    creator = get_gcd_object(Creator, creator_id)
    names = _get_creator_names_for_checklist(creator)

    series = Series.objects.filter(
      issue__story__credits__creator__in=names,
      issue__story__type__id__in=CORE_TYPES,
      issue__story__credits__deleted=False,
      issue__story__credits__credit_type__id__lt=6).distinct()
    if country:
        country = get_object_or_404(Country, code=country)
        series = series.filter(country=country)
    if language:
        language = get_object_or_404(Language, code=language)
        series = series.filter(language=language)

    series = series.annotate(issue_credits_count=Count('issue', distinct=True))
    series = series.annotate(first_credit=Min('issue__key_date'))
    script = Count('issue',
                   filter=Q(issue__story__credits__credit_type__id=1),
                   distinct=True)
    pencils = Count('issue',
                    filter=Q(issue__story__credits__credit_type__id=2),
                    distinct=True)
    inks = Count('issue',
                 filter=Q(issue__story__credits__credit_type__id=3),
                 distinct=True)
    colors = Count('issue',
                   filter=Q(issue__story__credits__credit_type__id=4),
                   distinct=True)
    letters = Count('issue',
                    filter=Q(issue__story__credits__credit_type__id=5),
                    distinct=True)
    filter = filter_series(request, series)
    series = filter.qs
    series = series.annotate(
      script=script,
      pencils=pencils,
      inks=inks,
      colors=colors,
      letters=letters)

    context = {
        'result_disclaimer': ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER,
        'item_name': 'series',
        'plural_suffix': '',
        'heading': 'for creator %s' % (creator),
        'filter_form': filter.form
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = CreatorSeriesTable(series, attrs={'class': 'sortable_listing'},
                               creator=creator,
                               template_name=TW_SORT_TABLE_TEMPLATE,
                               order_by=('name'))
    return generic_sortable_list(request, series, table, template, context)


def checklist_by_id(request, creator_id, series_id=None, character_id=None,
                    feature_id=None, co_creator_id=None, group_id=None,
                    publisher_id=None, edits=False, country=None,
                    language=None):
    """
    Provides checklists for a Creator. These include results for all
    CreatorNames and for the overall House Name all uses of that House Name.
    """
    creator = get_gcd_object(Creator, creator_id)
    creator_names = _get_creator_names_for_checklist(creator)
    filter = None

    if edits:
        issues = Issue.objects.filter(credits__creator__in=creator_names,
                                      credits__deleted=False)\
                              .distinct().select_related('series__publisher')
    else:
        issues = Issue.objects.filter(
          story__credits__creator__in=creator_names,
          story__type__id__in=CORE_TYPES,
          story__credits__deleted=False,
          story__credits__credit_type__id__lt=6)\
          .distinct().select_related('series__publisher')
    if country:
        country = get_object_or_404(Country, code=country)
        issues = issues.filter(series__country=country)
    if language:
        language = get_object_or_404(Language, code=language)
        issues = issues.filter(series__language=language)
    if series_id:
        series = get_gcd_object(Series, series_id)
        issues = issues.filter(series__id=series_id)
        heading = 'for creator %s in series %s' % (creator,
                                                   series)
    elif publisher_id:
        publisher = get_gcd_object(Publisher, publisher_id)
        issues = issues.filter(series__publisher__id=publisher_id)
        heading = 'for creator %s for publisher %s' % (creator,
                                                       publisher)
    elif character_id:
        character = get_gcd_object(Character, character_id)
        if character.universe:
            universe_id = character.universe.id
            if character.active_generalisations():
                character = character.active_generalisations().get()\
                                     .from_character
            issues = issues.filter(
              story__credits__creator__creator=creator,
              story__appearing_characters__character__character=character,
              story__appearing_characters__universe_id=universe_id,
              story__type__id__in=CORE_TYPES,
              story__appearing_characters__deleted=False).distinct()
        else:
            issues = issues.filter(
              story__credits__creator__creator=creator,
              story__appearing_characters__character__character=character,
              story__type__id__in=CORE_TYPES,
              story__appearing_characters__deleted=False).distinct()
        heading = 'for creator %s for character %s' % (creator,
                                                       character)
        filter = filter_issues(request, issues)
        filter.filters.pop('language')
        issues = filter.qs
    elif group_id:
        group = get_gcd_object(Group, group_id)
        issues = issues.filter(
          story__credits__creator__creator=creator,
          story__appearing_characters__group_name__group=group,
          story__type__id__in=CORE_TYPES,
          story__appearing_characters__deleted=False).distinct()
        heading = 'for creator %s for group %s' % (creator,
                                                   group)
        filter = filter_issues(request, issues)
        filter.filters.pop('language')
        issues = filter.qs
    elif feature_id:
        feature = get_gcd_object(Feature, feature_id)
        issues = issues.filter(story__credits__creator__creator=creator,
                               story__type__id__in=CORE_TYPES,
                               story__credits__credit_type__id__lt=6,
                               story__feature_object=feature,
                               story__credits__deleted=False,
                               story__deleted=False).distinct()
        filter = filter_issues(request, issues)
        filter.filters.pop('language')
        issues = filter.qs
        heading = 'for creator %s on feature %s' % (creator,
                                                    feature)
    elif edits:
        heading = 'edited by creator %s' % (creator)
        filter = filter_issues(request, issues)
        issues = filter.qs
    elif co_creator_id:
        co_creator = get_gcd_object(Creator, co_creator_id)
        stories = Story.objects.filter(credits__creator__creator=creator,
                                       credits__deleted=False,
                                       credits__credit_type__id__lt=6)\
                               .filter(credits__creator__creator=co_creator,
                                       credits__credit_type__id__lt=6,
                                       credits__deleted=False)\
                               .filter(type__id__in=CORE_TYPES,
                                       deleted=False)
        issue_list = stories.values_list('issue', flat=True)
        issues = Issue.objects.filter(id__in=issue_list,
                                      deleted=False).distinct()
        filter = filter_issues(request, issues)
        issues = filter.qs
        heading = 'for creator %s with creator %s' % (creator,
                                                      co_creator)
    else:
        heading = 'for creator %s' % (creator)
        filter = filter_issues(request, issues)
        issues = filter.qs
    context = {
        'result_disclaimer': ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER,
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': heading,
        'filter_form': filter.form if filter else None
    }
    if edits:
        context['result_disclaimer'] = MIGRATE_DISCLAIMER
    template = 'gcd/search/tw_list_sortable.html'
    table = _table_issues_list_or_grid(request, issues, context)
    return generic_sortable_list(request, issues, table, template, context)


def _table_issues_list_or_grid(request, issues, context, publisher=True):
    context['list_grid'] = True

    if 'display' not in request.GET or request.GET['display'] == 'list':
        if publisher:
            table = IssuePublisherTable(issues,
                                        template_name=TW_SORT_TABLE_TEMPLATE,
                                        order_by=('publication_date'))
        else:
            table = IssueTable(issues,
                               template_name=TW_SORT_TABLE_TEMPLATE,
                               order_by=('publication_date'))
    else:
        if publisher:
            table = IssueCoverPublisherTable(
              issues,
              template_name=TW_SORT_GRID_TEMPLATE,
              order_by=('publication_date'))
        else:
            table = IssueCoverTable(
              issues,
              template_name=TW_SORT_GRID_TEMPLATE,
              order_by=('publication_date'))

    return table


def _table_creators_list_or_grid(request, creators, context, resolve_name,
                                 object):
    context['list_grid'] = True
    if 'display' not in request.GET or request.GET['display'] == 'list':
        table = GenericCreatorTable(creators,
                                    resolve_name=resolve_name,
                                    object=object,
                                    template_name=TW_SORT_TABLE_TEMPLATE,
                                    order_by=('creator'))
    else:
        table = CreatorPortraitTable(creators,
                                     resolve_name=resolve_name,
                                     object=object,
                                     template_name=TW_SORT_GRID_TEMPLATE,
                                     order_by=('creator'))
    return table


def cover_checklist_by_id(request, creator_id, series_id=None,
                          country=None, language=None):
    creator = get_gcd_object(Creator, creator_id)
    creator_names = _get_creator_names_for_checklist(creator)
    issues = Issue.objects.filter(story__credits__creator__in=creator_names,
                                  story__type__id=6,
                                  story__credits__deleted=False,
                                  story__credits__credit_type__id__lt=6)\
                          .distinct().select_related('series__publisher')
    if country:
        country = get_object_or_404(Country, code=country)
        issues = issues.filter(series__country=country)
    if language:
        language = get_object_or_404(Language, code=language)
        issues = issues.filter(series__language=language)
    if series_id:
        series = get_gcd_object(Series, series_id)
        issues = issues.filter(series__id=series_id)
        heading = 'from creator %s in series %s' % (creator,
                                                    series)
    else:
        heading = 'for creator %s' % (creator)
        filter = filter_issues(request, issues)
        issues = filter.qs

    context = {
        'result_disclaimer': COVER_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER,
        'item_name': 'cover',
        'plural_suffix': 's',
        'heading': heading,
        'filter_form': filter.form,
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = CoverIssuePublisherTable(issues,
                                     attrs={'class': 'sortable_listing'},
                                     template_name=TW_SORT_TABLE_TEMPLATE,
                                     order_by=('publication_date'))
    return generic_sortable_list(request, issues, table, template, context)


def checklist_by_name(request, creator, country=None, language=None,
                      to_be_migrated=False):
    creator = creator.replace('+', ' ').title()
    context = {
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'for creator ' + creator,
    }
    prefix = 'story__'
    op = 'icontains'

    q_objs_text = Q()
    for field in ('script', 'pencils', 'inks', 'colors', 'letters', 'editing'):
        if to_be_migrated:
            q_objs_text |= Q(**{'%s%s__%s' % (prefix, field, op): creator,
                                '%sdeleted' % (prefix): False})
        else:
            q_objs_text |= Q(**{'%s%s__%s' % (prefix, field, op): creator,
                                '%stype__id__in' % (prefix): CORE_TYPES,
                                '%sdeleted' % (prefix): False})
    issues = Issue.objects.filter(q_objs_text).distinct()
    creator = Creator.objects.filter(gcd_official_name__iexact=creator)
    if creator and not to_be_migrated:
        q_objs_credits = Q(**{
          '%scredits__creator__creator__in' % (prefix): creator,
          '%stype__id__in' % (prefix): CORE_TYPES})
        items2 = Issue.objects.filter(q_objs_credits).distinct()
    if country:
        country = get_object_or_404(Country, code=country)
        issues = issues.filter(series__country=country)
        if creator and not to_be_migrated:
            items2 = items2.filter(series__country=country)
    if language:
        language = get_object_or_404(Language, code=language)
        issues = issues.filter(series__language=language)
        if creator and not to_be_migrated:
            items2 = items2.filter(series__language=language)
    if creator and not to_be_migrated:
        # an OR query is very expensive, so use IDs and make
        # a separate query after merging both ID-lists
        id1 = list(issues.values_list('id', flat=True))
        id1.extend(items2.values_list('id', flat=True))
        issues = Issue.objects.filter(id__in=id1)
        filter = None
    else:
        filter = filter_issues(request, issues)
        issues = filter.qs
        context['heading'] = 'to be migrated ' + context['heading']

    template = 'gcd/search/tw_list_sortable.html'
    table = _table_issues_list_or_grid(request, issues, context)

    if not to_be_migrated:
        context['result_disclaimer'] = ISSUE_CHECKLIST_DISCLAIMER
    else:
        context['filter_form'] = filter.form

    return generic_sortable_list(request, issues, table, template, context)


def creator_name_issues(request, creator_name_id, character_id=None,
                        group_id=None, feature_id=None, series_id=None,
                        country=None, language=None):
    return creator_name_checklist(request=request,
                                  creator_name_id=creator_name_id,
                                  character_id=character_id,
                                  group_id=group_id,
                                  feature_id=feature_id,
                                  series_id=series_id,
                                  country=country,
                                  language=language
                                  )


def creator_name_checklist(request, creator_name_id, character_id=None,
                           group_id=None, feature_id=None, series_id=None,
                           country=None, language=None):
    """
    Provides checklists for a CreatorNameDetail.
    """
    creator = get_gcd_object(CreatorNameDetail, creator_name_id)
    issues = Issue.objects.filter(story__credits__creator=creator,
                                  story__type__id__in=CORE_TYPES,
                                  story__credits__credit_type__id__lt=6,
                                  story__credits__deleted=False,
                                  story__deleted=False).distinct()\
                          .select_related('series__publisher')
    if character_id:
        character = get_gcd_object(Character, character_id)
        if character.universe:
            universe_id = character.universe.id
            if character.active_generalisations():
                character = character.active_generalisations().get()\
                                     .from_character
            issues = issues.filter(
              story__credits__creator=creator,
              story__appearing_characters__character__character=character,
              story__appearing_characters__universe_id=universe_id,
              story__type__id__in=CORE_TYPES,
              story__appearing_characters__deleted=False).distinct()
        else:
            issues = issues.filter(
              story__credits__creator=creator,
              story__appearing_characters__character__character=character,
              story__type__id__in=CORE_TYPES,
              story__appearing_characters__deleted=False).distinct()
        heading_addon = 'with character %s' % (character)
    if group_id:
        group = get_gcd_object(Group, group_id)
        issues = issues.filter(
          story__credits__creator=creator,
          story__type__id__in=CORE_TYPES,
          story__appearing_characters__group_name__group=group,
          story__appearing_characters__deleted=False)
        heading_addon = 'with group %s' % (group)
    if feature_id:
        feature = get_gcd_object(Feature, feature_id)
        issues = issues.filter(story__credits__creator=creator,
                               story__feature_object=feature)
        heading_addon = 'on feature %s' % (feature)
    if series_id:
        series = get_gcd_object(Series, series_id)
        issues = issues.filter(story__credits__creator=creator,
                               story__issue__series=series)
        heading_addon = 'on series %s' % (series)
    if country:
        country = get_object_or_404(Country, code=country)
        issues = issues.filter(series__country=country)
    if language:
        language = get_object_or_404(Language, code=language)
        issues = issues.filter(series__language=language)

    context = {
        'result_disclaimer': ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER,
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'for creator %s %s' % (creator, heading_addon)
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = _table_issues_list_or_grid(request, issues, context)
    return generic_sortable_list(request, issues, table, template, context)


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
    creator_non_comic_work = get_gcd_object(
      CreatorNonComicWork,
      creator_non_comic_work_id,
      model_name='creator_non_comic_work')
    return show_creator_non_comic_work(request, creator_non_comic_work)


def show_creator_non_comic_work(request, creator_non_comic_work,
                                preview=False):
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


def creator_signature(request, creator_signature_id):
    creator_signature = get_gcd_object(CreatorSignature,
                                       creator_signature_id,
                                       model_name='creator_signature')
    return show_creator_signature(request, creator_signature)


def show_creator_signature(request, creator_signature, preview=False):
    vars = {'creator_signature': creator_signature,
            'error_subject': creator_signature,
            'preview': preview}
    return render(request, 'gcd/details/creator_signature.html', vars)


def award(request, award_id):
    """
    Display the details page for an Award.
    """
    award = get_gcd_object(Award, award_id)
    return show_award(request, award)


def show_award(request, award, preview=False):
    awards = award.active_awards().order_by(
      'award_year', 'award_name')

    vars = {'award': award,
            'error_subject': '%s' % award,
            'preview': preview}
    return paginate_response(request,
                             awards,
                             'gcd/details/tw_award.html',
                             vars)


def received_award(request, received_award_id):
    received_award = get_gcd_object(ReceivedAward, received_award_id,
                                    model_name='received_award')
    return show_received_award(request, received_award)


def show_received_award(request, received_award, preview=False):
    vars = {'received_award': received_award,
            'error_subject': received_award,
            'preview': preview}
    return render(request, 'gcd/details/tw_received_award.html', vars)


def school(request, school_id):
    """
    Display the details page for a School.
    """
    school = get_object_or_404(School, id=school_id)
    return show_school(request, school)


def show_school(request, school, preview=False):
    degrees = school.degree.all()
    students = school.creator.all()

    vars = {'school': school,
            'degrees': degrees,
            'error_subject': '%s' % school,
            'preview': preview}
    return paginate_response(request,
                             students,
                             'gcd/details/school.html',
                             vars)


def publisher(request, publisher_id):
    """
    Display the details page for a Publisher.
    """
    publisher = get_gcd_object(Publisher, publisher_id)
    return show_publisher(request, publisher)


def show_publisher(request, publisher, preview=False):
    publisher_series = publisher.active_series()
    image_tag, selected_issue = _get_random_cover_image(request,
                                                        publisher,
                                                        'series__publisher',
                                                        'Publisher')

    context = {'publisher': publisher,
               'current': publisher.series_set.filter(deleted=False,
                                                      is_current=True),
               'error_subject': publisher,
               'image_tag': image_tag,
               'image_issue': selected_issue,
               'preview': preview}
    paginator = ResponsePaginator(publisher_series, per_page=100, vars=context,
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

    table = SeriesTable(publisher_series, attrs={'class': 'sortable_listing'},
                        template_name=TW_SORT_TABLE_TEMPLATE,
                        order_by=('name'))
    RequestConfig(request, paginate={'per_page': 100,
                                     'page': page_number}).configure(table)
    context['table'] = table
    context['extra_string'] = extra_string

    return generic_sortable_list(request, publisher_series, table,
                                 'gcd/details/tw_publisher.html', context)


def show_publisher_issues(request, publisher_id):
    publisher = get_gcd_object(Publisher, publisher_id)
    issues = Issue.objects.filter(series__publisher=publisher,
                                  deleted=False).order_by(
      'series__sort_name', 'sort_code').prefetch_related('series', 'brand',
                                                         'indicia_publisher')
    context = {'heading': 'of publisher %s' % publisher,
               'item_name': 'issue',
               'plural_suffix': 's',
               'description': 'showing all issues'
               }
    context['list_grid'] = True

    if 'display' not in request.GET or request.GET['display'] == 'list':
        table = PublisherIssueTable(issues,
                                    template_name=TW_SORT_TABLE_TEMPLATE,
                                    order_by=('issue'))
    else:
        table = PublisherIssueCoverTable(
          issues,
          template_name=TW_SORT_GRID_TEMPLATE,
          order_by=('issue'))

    return generic_sortable_list(request, issues, table,
                                 'gcd/search/tw_list_sortable.html', context)


def show_publisher_current_series(request, publisher_id):
    publisher = get_gcd_object(Publisher, publisher_id)
    current_series = publisher.active_series().filter(deleted=False,
                                                      is_current=True)

    context = {'object': publisher,
               'description': 'showing current series',
               'plural_suffix': '',
               'heading': 'of current series for %s' % publisher
               }
    table = SeriesTable(current_series,
                        template_name=TW_SORT_TABLE_TEMPLATE,
                        order_by=('name'))
    return generic_sortable_list(request, current_series, table,
                                 'gcd/search/tw_list_sortable.html', context)


def _filter_issues_year_month(objects, year, month,
                              use_on_sale=False, cover=False, yearly=False):
    day = 99
    if yearly:
        month = 1
    if month == 1:
        # to get issues with month not set, start from end of year before
        year_start = year-1
        month_start = 14
    else:
        # start from month before
        year_start = year
        month_start = month-1

    # key_date can have valid entry of 13, catch these for December
    if month == 12 or yearly:
        month_end = 14
    else:
        month_end = month

    if use_on_sale:
        date_field = 'on_sale_date'
    else:
        date_field = 'key_date'

    if cover:
        date_field = 'issue__' + date_field
        order_series = 'issue__series'
    else:
        order_series = 'series'

    objects = objects.filter(**{date_field + '__gte': '%d-%02d-%d' % (
        year_start, month_start, day),
                            date_field + '__lte': '%d-%02d-32' % (
        year, month_end)}).order_by(date_field, order_series)

    return objects


def publisher_monthly_covers(request,
                             publisher_id,
                             year=None,
                             month=None,
                             use_on_sale=True,
                             overview=False):
    """
    Display the covers for the monthly publications of a publisher.
    """
    publisher = get_gcd_object(Publisher, publisher_id)
    yearly = False

    if overview:
        if use_on_sale:
            date_type = 'publisher_monthly_issues_on_sale'
        else:
            date_type = 'publisher_monthly_issues_pub_date'
    else:
        if use_on_sale:
            date_type = 'publisher_monthly_covers_on_sale'
        else:
            date_type = 'publisher_monthly_covers_pub_date'

    if use_on_sale:
        url_name = date_type[:-7] + 'pub_date'
        ordering = 'on_sale_date'
    else:
        url_name = date_type[:-8] + 'on_sale'
        ordering = 'publication_date'

    if year and 'month' not in request.GET:
        year = int(year)
        month = int(month)
    else:
        return_val, show_date = _handle_date_picker(
          request, date_type, monthly=True, kwargs={'publisher_id':
                                                    publisher_id})
        if show_date is False:
            return return_val
        elif show_date is True:
            year = return_val[0]
            month = return_val[1]

    switch_date_link = "Show %s by <a href='%s'>%s</a>." % (
      'issues' if overview else 'covers',
      urlresolvers.reverse(url_name,
                           kwargs={'publisher_id': publisher_id,
                                   'year': year,
                                   'month': month}),
      'on-sale date' if not use_on_sale else 'publication date')

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
    # TODO remove backward/forward links if overall less then 50

    if overview:
        heading = ''
        issues = Issue.objects.filter(series__publisher=publisher,
                                      variant_of=None, deleted=False)\
                              .select_related('series')\
                              .prefetch_related('cover_set')
        continue_processing = False
        # overall more than 50
        if issues.count() > 50:
            if use_on_sale:
                heading += 'on-sale in '
            else:
                heading += 'with a publication date of '
            issues = _filter_issues_year_month(issues, year, month,
                                               use_on_sale, yearly=True)
            continue_processing = True
        # in this year more than 50
        if issues.count() > 50:
            issues = _filter_issues_year_month(issues, year, month,
                                               use_on_sale)
        # otherwise we have less 50 for this year, modify links, etc.
        elif continue_processing:
            yearly = True
            if month == 1:
                year_before = date_before.year
            else:
                year_before = date_before.year - 1
            if month == 12:
                year_after = date_after.year
            else:
                year_after = date_after.year + 1
            choose_url_before = urlresolvers.reverse(
              date_type, kwargs={'publisher_id': publisher_id,
                                 'year': year_before,
                                 'month': 12})
            choose_url_after = urlresolvers.reverse(
              date_type, kwargs={'publisher_id': publisher_id,
                                 'year': year_after,
                                 'month': 1})
            heading += '%d ' % year
            continue_processing = False
        # there are none in the current month, redirect
        if not issues.exists() and year == date.today().year and \
           month == date.today().month:
            issues = Issue.objects.filter(series__publisher=publisher,
                                          variant_of=None, deleted=False)
            if use_on_sale:
                issues = issues.exclude(on_sale_date__contains='?')
            if issues.exists():
                if use_on_sale:
                    latest_issues_date = issues.latest('on_sale_date')\
                                               .on_sale_date
                else:
                    latest_issues_date = issues.latest('key_date').key_date
                year = latest_issues_date[:4]
                month = latest_issues_date[5:7]
                if not month or month == '00':
                    month = '01'
                if month == '13':
                    month = '12'
                kwargs = {}
                kwargs['publisher_id'] = publisher_id
                kwargs['year'] = year
                kwargs['month'] = month
            else:
                year = None
            if year:
                return HttpResponseRedirect(urlresolvers.reverse(
                    date_type, kwargs=kwargs))
            else:
                issues = Issue.objects.none()
        if continue_processing:
            if month == 1:
                heading += '%d or ' % year
            heading += '%s ' % date(year, month, 1).strftime('%B %Y')
        issues = issues.annotate(
          longest_story_id=Subquery(Story.objects.filter(
                                    issue_id=OuterRef('pk'),
                                    type_id=19, deleted=False)
                                    .values('pk')
                                    .order_by('-page_count')[:1]))
        heading += 'from %s' % publisher

        if 'sort' in request.GET:
            sort = request.GET['sort']
            choose_url_after += '?sort=%s' % request.GET['sort']
            choose_url_before += '?sort=%s' % request.GET['sort']
        else:
            sort = ''

        context = {
          'item_name': 'issue',
          'plural_suffix': 's',
          'heading': heading,
          'years': range(date.today().year,
                         (publisher.year_began or 1900) - 1,
                         -1),
          'sort': sort,
          'yearly': yearly,
          'choose_url': choose_url,
          'choose_url_after': choose_url_after,
          'choose_url_before': choose_url_before,
          'choose_date': True,
          'result_disclaimer': mark_safe(switch_date_link),
        }
        template = 'gcd/search/tw_list_sortable.html'
        context['list_grid'] = True
        if 'display' not in request.GET or request.GET['display'] == 'list':
            table = CoverIssueStoryTable(issues,
                                         template_name=TW_SORT_TABLE_TEMPLATE,
                                         order_by=(ordering))
        else:
            table = IssueCoverPublisherTable(
              issues,
              template_name=TW_SORT_GRID_TEMPLATE,
              order_by=(ordering))

        return generic_sortable_list(request, issues, table, template,
                                     context, 50)
    else:
        heading = 'for comics '
        covers = Cover.objects.filter(issue__series__publisher=publisher,
                                      deleted=False).select_related('issue')
        continue_processing = False
        if covers.count() > 50:
            if use_on_sale:
                heading += 'on-sale in '
            else:
                heading += 'with a publication date of '
            covers = _filter_issues_year_month(covers, year, month,
                                               use_on_sale, cover=True,
                                               yearly=True)
            continue_processing = True
        if covers.count() > 50:
            covers = _filter_issues_year_month(covers, year, month,
                                               use_on_sale, cover=True)
        elif continue_processing:
            yearly = True
            if month == 1:
                year_before = date_before.year
            else:
                year_before = date_before.year - 1
            if month == 12:
                year_after = date_after.year
            else:
                year_after = date_after.year + 1
            choose_url_before = urlresolvers.reverse(
              date_type, kwargs={'publisher_id': publisher_id,
                                 'year': year_before,
                                 'month': 12})
            choose_url_after = urlresolvers.reverse(
              date_type, kwargs={'publisher_id': publisher_id,
                                 'year': year_after,
                                 'month': 1})
            heading += '%d ' % year
            continue_processing = False
        if not covers.exists() and year == date.today().year and \
           month == date.today().month:
            covers = Cover.objects.filter(
                issue__series__publisher=publisher, deleted=False)
            if use_on_sale:
                covers = covers.exclude(issue__on_sale_date__contains='?')
            if covers.exists():
                if use_on_sale:
                    latest_issues_date = covers.latest('issue__on_sale_date')\
                                               .issue.on_sale_date
                else:
                    latest_issues_date = covers.latest('issue__key_date')\
                                               .issue.key_date
                year = latest_issues_date[:4]
                month = latest_issues_date[5:7]
                if not month or month == '00':
                    month = '01'
                if month == '13':
                    month = '12'
                kwargs = {}
                kwargs['publisher_id'] = publisher_id
                kwargs['year'] = year
                kwargs['month'] = month
            else:
                year = None
            if year:
                return HttpResponseRedirect(urlresolvers.reverse(
                  date_type, kwargs=kwargs))
            else:
                covers = Cover.objects.none()
        if continue_processing:
            if month == 1:
                heading += '%d or ' % year
            heading += '%s ' % date(year, month, 1).strftime('%B %Y')
        heading += 'from %s' % publisher
        context = {
          'item_name': 'cover',
          'plural_suffix': 's',
          'publisher': publisher,
          'date': start_date,
          'monthly': True,
          'years': range(date.today().year,
                         (publisher.year_began or 1900) - 1,
                         -1),
          'yearly': yearly,
          'choose_url': choose_url,
          'choose_url_after': choose_url_after,
          'choose_url_before': choose_url_before,
          'choose_date': True,
          'use_on_sale': use_on_sale,
          'heading': heading,
          'result_disclaimer': mark_safe(switch_date_link),
          'RANDOM_IMAGE': _publisher_image_content(publisher.id)
        }

        template = 'gcd/search/tw_list_sortable.html'
        table = OnSaleCoverIssueTable(
          covers,
          template_name=TW_SORT_GRID_TEMPLATE,
          order_by=(ordering))
        return generic_sortable_list(request, covers, table, template,
                                     context, 50)


def indicia_publisher(request, indicia_publisher_id):
    """
    Display the details page for an Indicia Publisher.
    """
    indicia_publisher = get_gcd_object(IndiciaPublisher, indicia_publisher_id,
                                       model_name='indicia_publisher')
    return show_indicia_publisher(request, indicia_publisher)


def show_indicia_publisher(request, indicia_publisher, preview=False):
    indicia_publisher_issues = indicia_publisher.active_issues()\
                                                .prefetch_related('series',
                                                                  'brand')
    image_tag, selected_issue = _get_random_cover_image(request,
                                                        indicia_publisher,
                                                        'indicia_publisher',
                                                        'Indicia Publisher')

    context = {'indicia_publisher': indicia_publisher,
               'error_subject': '%s' % indicia_publisher,
               'image_tag': image_tag,
               'image_issue': selected_issue,
               'preview': preview}
    context['list_grid'] = True

    if 'display' not in request.GET or request.GET['display'] == 'list':
        table = IndiciaPublisherIssueTable(indicia_publisher_issues,
                                           template_name=TW_SORT_TABLE_TEMPLATE,
                                           order_by=('issue'))
    else:
        table = IndiciaPublisherIssueCoverTable(
          indicia_publisher_issues,
          template_name=TW_SORT_GRID_TEMPLATE,
          order_by=('issue'))

    return generic_sortable_list(request, indicia_publisher_issues, table,
                                 'gcd/details/tw_indicia_publisher.html',
                                 context)


def brand_group(request, brand_group_id):
    """
    Display the details page for a BrandGroup.
    """
    brand_group = get_gcd_object(BrandGroup, brand_group_id)
    return show_brand_group(request, brand_group)


def show_brand_group(request, brand_group, preview=False):
    brand_issues = brand_group.active_issues().order_by(
      'series__sort_name', 'sort_code').prefetch_related('series', 'brand',
                                                         'indicia_publisher')
    image_tag, selected_issue = _get_random_cover_image(request,
                                                        brand_group,
                                                        'brand__group',
                                                        'Brand')

    brand_emblems = brand_group.active_emblems()
    brand_emblems_table = BrandEmblemGroupTable(
      brand_emblems,
      template_name=TW_SORT_TABLE_TEMPLATE,
      order_by=('name'))
    brand_emblems_table.no_export = True
    RequestConfig(request,
                  paginate={"paginator_class": LazyPaginator}).configure(
                    brand_emblems_table)

    context = {'brand': brand_group,
               'brand_emblems_table': brand_emblems_table,
               'error_subject': '%s' % brand_group,
               'image_tag': image_tag,
               'image_issue': selected_issue,
               'preview': preview
               }
    context['list_grid'] = True

    if 'display' not in request.GET or request.GET['display'] == 'list':
        table = BrandGroupIssueTable(brand_issues,
                                     brand=brand_group,
                                     template_name=TW_SORT_TABLE_TEMPLATE,
                                     order_by=('issue'))
    else:
        table = BrandGroupIssueCoverTable(
          brand_issues,
          brand=brand_group,
          template_name=TW_SORT_GRID_TEMPLATE,
          order_by=('issue'))

    return generic_sortable_list(request, brand_issues, table,
                                 'gcd/details/tw_brand_group.html', context)


def brand(request, brand_id):
    """
    Display the details page for a Brand.
    """
    brand = get_gcd_object(Brand, brand_id)
    return show_brand(request, brand)


def show_brand(request, brand, preview=False):
    brand_issues = brand.active_issues().order_by(
      'series__sort_name', 'sort_code').prefetch_related('series',
                                                         'indicia_publisher')
    image_tag, selected_issue = _get_random_cover_image(request,
                                                        brand,
                                                        'brand',
                                                        'Brand Emblem')

    groups_table = BrandGroupEmblemTable(brand.group.all(),
                                         template_name=TW_SORT_TABLE_TEMPLATE,
                                         order_by=('name'))
    groups_table.no_export = True
    RequestConfig(request,
                  paginate={"paginator_class": LazyPaginator}).configure(
                    groups_table)

    uses = brand.in_use.all()
    context = {'brand': brand,
               'groups_table': groups_table,
               'uses': uses,
               'error_subject': '%s' % brand,
               'image_tag': image_tag,
               'image_issue': selected_issue,
               'preview': preview
               }
    context['list_grid'] = True
    if 'display' not in request.GET or request.GET['display'] == 'list':
        table = BrandEmblemIssueTable(brand_issues,
                                      template_name=TW_SORT_TABLE_TEMPLATE,
                                      order_by=('issue'))
    else:
        table = BrandEmblemIssueCoverTable(
          brand_issues,
          template_name=TW_SORT_GRID_TEMPLATE,
          order_by=('issue'))
    return generic_sortable_list(request, brand_issues, table,
                                 'gcd/details/tw_brand_emblem.html', context)


def imprint(request, imprint_id):
    """
    Redirect to the change history page for an Imprint, which all are deleted.
    """
    get_object_or_404(Publisher, id=imprint_id, deleted=True)

    return HttpResponseRedirect(
      urlresolvers.reverse('change_history',
                           kwargs={'model_name': 'imprint', 'id': imprint_id}))


def publisher_brands(request, publisher_id):
    """
    Finds brands of a publisher and presents them as a paginated list.
    """

    publisher = get_object_or_404(Publisher, id=publisher_id)
    if publisher.deleted:
        return HttpResponseRedirect(
          urlresolvers.reverse('change_history',
                               kwargs={'model_name': 'publisher',
                                       'id': publisher_id}))

    brands = publisher.active_brands()

    brands = brands.annotate(brand_emblem_count=Count(
      'brand', filter=Q(brand__deleted=False)))

    sort = request.GET.get('sort', None)
    if (sort == ORDER_CHRONO):
        order_by = 'year_began'
    else:
        order_by = 'name'

    context = {'item_name': "publisher's brand group",
               'plural_suffix': 's',
               'heading': mark_safe('used at <a href="%s">%s</a>' % (
                                    publisher.get_absolute_url(), publisher))}

    table = BrandGroupPublisherTable(
        brands,
        template_name='gcd/bits/tw_sortable_table.html',
        order_by=(order_by))
    template = 'gcd/search/tw_list_sortable.html'
    return generic_sortable_list(request, brands, table, template,
                                 context)


def publisher_brand_uses(request, publisher_id):
    """
    Finds brand emblems used at a publisher and presents them as a
    paginated list.
    """

    publisher = get_object_or_404(Publisher, id=publisher_id)
    if publisher.deleted:
        return HttpResponseRedirect(
          urlresolvers.reverse('change_history',
                               kwargs={'model_name': 'publisher',
                                       'id': publisher_id}))

    brand_uses = publisher.branduse_set.all()

    sort = request.GET.get('sort', None)
    if (sort == ORDER_CHRONO):
        order_by = 'year_began'
    else:
        order_by = 'name'

    brand_uses = brand_uses.annotate(issue_count=Count(
      'emblem__issue', filter=Q(emblem__issue__deleted=False,
                                emblem__issue__key_date__gte=F('year_began'),
                                emblem__issue__key_date__lte=F('year_ended'))))

    context = {'item_name': "publisher's brand emblem",
               'plural_suffix': 's',
               'heading': mark_safe('used at <a href="%s">%s</a>' % (
                                    publisher.get_absolute_url(), publisher))}

    table = BrandEmblemPublisherTable(
        brand_uses,
        template_name='gcd/bits/tw_sortable_table.html',
        order_by=(order_by))
    template = 'gcd/search/tw_list_sortable.html'
    return generic_sortable_list(request, brand_uses, table, template,
                                 context)


def publisher_indicia_publishers(request, publisher_id):
    """
    Finds indicia publishers of a publisher and presents them as
    a paginated list.
    """
    publisher = get_object_or_404(Publisher, id=publisher_id)
    if publisher.deleted:
        return HttpResponseRedirect(
          urlresolvers.reverse('change_history',
                               kwargs={'model_name': 'publisher',
                                       'id': publisher_id}))

    indicia_publishers = publisher.active_indicia_publishers()

    sort = request.GET.get('sort', None)
    if (sort == ORDER_CHRONO):
        order_by = 'year_began'
    else:
        order_by = 'name'

    context = {'item_name': "indicia / colophon publisher",
               'plural_suffix': 's',
               'heading': mark_safe('used at <a href="%s">%s</a>' % (
                                    publisher.get_absolute_url(), publisher))}

    table = IndiciaPublisherPublisherTable(
        indicia_publishers,
        template_name='gcd/bits/tw_sortable_table.html',
        order_by=(order_by))
    template = 'gcd/search/tw_list_sortable.html'
    return generic_sortable_list(request, indicia_publishers, table, template,
                                 context)


def printer(request, printer_id):
    """
    Display the details page for a Printer.
    """
    printer = get_gcd_object(Printer, printer_id)
    return show_printer(request, printer)


def show_printer(request, printer, preview=False):
    if preview:
        if hasattr(printer, 'printer'):
            indicia_printers = printer.printer.active_indicia_printers()
        else:
            indicia_printers = None
    else:
        indicia_printers = printer.active_indicia_printers()

    vars = {'printer': printer,
            'indicia_printers': indicia_printers,
            'error_subject': printer,
            'preview': preview}
    return render(request, 'gcd/details/tw_printer.html', vars)


def printer_issues(request, printer_id):
    printer = get_gcd_object(Printer, printer_id)

    issues = Issue.objects.filter(indicia_printer__parent=printer,
                                  deleted=False).distinct()\
                          .select_related('series__publisher')
    filter = filter_issues(request, issues)
    issues = filter.qs

    context = {
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'for printer %s' % (printer),
        'filter_form': filter.form,
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = IssuePublisherTable(issues,
                                template_name=TW_SORT_TABLE_TEMPLATE,
                                order_by=('publication_date'))
    return generic_sortable_list(request, issues, table, template, context)


def indicia_printer(request, indicia_printer_id):
    """
    Display the details page for an Indicia Printer.
    """
    indicia_printer = get_gcd_object(IndiciaPrinter, indicia_printer_id)
    return show_indicia_printer(request, indicia_printer)


def show_indicia_printer(request, indicia_printer, preview=False):
    context = {'indicia_printer': indicia_printer,
               'error_subject': '%s' % indicia_printer,
               'preview': preview}
    return render(request, 'gcd/details/tw_indicia_printer.html', context)


def indicia_printer_issues(request, indicia_printer_id):
    indicia_printer = get_gcd_object(IndiciaPrinter, indicia_printer_id)

    issues = Issue.objects.filter(indicia_printer=indicia_printer,
                                  deleted=False).distinct()\
                          .select_related('series__publisher')
    filter = filter_issues(request, issues)
    issues = filter.qs

    context = {
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'for indicia printer %s' % (indicia_printer),
        'filter_form': filter.form,
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = IssuePublisherTable(issues,
                                attrs={'class': 'sortable_listing'},
                                template_name=TW_SORT_TABLE_TEMPLATE,
                                order_by=('publication_date'))
    return generic_sortable_list(request, issues, table, template, context)


def series(request, series_id):
    """
    Display the details page for a series.
    """

    series = get_object_or_404(Series.objects.select_related('publisher'),
                               id=series_id)
    if series.deleted:
        return HttpResponseRedirect(
          urlresolvers.reverse('change_history',
                               kwargs={'model_name': 'series',
                                       'id': series_id}))
    if series.is_singleton and series.issue_count:
        return HttpResponseRedirect(
          urlresolvers.reverse(issue,
                               kwargs={'issue_id':
                                       int(series.active_issues()[0].id)}))

    return show_series(request, series)


def show_series(request, series, preview=False):
    """
    Helper function to handle the main work of displaying a series.
    Also used by OI previews.
    """
    scans, image_tag, issue = _get_scan_table(series)

    if series.has_issue_title:
        issue_status_width = "basis-96"
    else:
        issue_status_width = "basis-24"

    if series.has_issue_title:
        cover_status_width = "basis-96"
    elif series.active_issues().exclude(variant_name='').count():
        cover_status_width = "basis-48"
    else:
        cover_status_width = "basis-24"

    images = series.active_issues().filter(variant_of=None)\
                   .annotate(sum_scans_code=Sum('image_resources__type__id'))\
                   .order_by('sort_code')

    return render(
      request, 'gcd/details/tw_series.html',
      {
        'series': series,
        'scans': scans,
        'image_resources': images,
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


def series_covers(request, series_id):
    """
    Display the cover gallery for a series.
    """

    series = get_gcd_object(Series, series_id)
    covers = Cover.objects.filter(issue__series=series, deleted=False) \
                          .select_related('issue')
    series_status_info = '<a href="%sstatus"> Index Status</a> / ' \
                         '<a href="%sscans">Cover Scan Status</a>' \
                         ' (%s %s for %s %s available).' % (
                           series.get_absolute_url(),
                           series.get_absolute_url(),
                           series.scan_count,
                           pluralize(series.scan_count, 'cover,covers'),
                           series.issue_count,
                           pluralize(series.issue_count, 'issue,issues'),
                         )

    context = {
        'item_name': 'cover',
        'plural_suffix': 's',
        'publisher': publisher,
        'heading': mark_safe("for %s" %
                             series.full_name_with_link(publisher=True)),
        'result_disclaimer': mark_safe(series_status_info),
    }

    template = 'gcd/search/tw_list_sortable.html'
    table = CoverSeriesTable(
      covers,
      template_name=TW_SORT_GRID_TEMPLATE,
      order_by=('issue'))
    return generic_sortable_list(request, covers, table, template,
                                 context, 50)


def series_overview(request, series_id):
    """
    Display the cover gallery for a series with core sequence info.
    """

    series = get_gcd_object(Series, series_id)

    issues = series.active_issues().filter(variant_of=None)\
                   .annotate(longest_story_id=Subquery(Story.objects.filter(
                                              issue_id=OuterRef('pk'),
                                              type_id=19, deleted=False)
                                              .values('pk')
                                              .order_by('-page_count',
                                                        'sequence_number')[:1])
                             )

    heading = 'with covers and longest comic story for series %s' % (series)

    context = {
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': heading,
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = CoverIssueStoryTable(issues,
                                 attrs={'class': 'sortable_listing'},
                                 template_name=TW_SORT_TABLE_TEMPLATE,
                                 order_by=('issues'))
    return generic_sortable_list(request, issues, table, template, context, 50)


def series_details(request, series_id, by_date=False):
    """
    Displays a non-paginated list of all issues in a series along with
    certain issue-level data fields.

    Works in two forms- one which is a straight ordered listing, and the
    other which attempts to graphically represent the issues in a timeline,
    with special handling for issues whose date cannot be resolved.
    """
    series = get_gcd_object(Series, series_id)
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
            except ValueError:
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
                         series.active_issues()
                               .filter(no_indicia_frequency=False)
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

    if not by_date:
        exclude_columns = []
        if not volume_present:
            exclude_columns.append('volume')
        if not brand_present:
            exclude_columns.append('brand')
        if not frequency_present:
            exclude_columns.append('indicia_frequency')
        if not isbn_present:
            exclude_columns.append('isbn')
        if not barcode_present:
            exclude_columns.append('barcode')
        if not title_present:
            exclude_columns.append('title')
        if not on_sale_date_present:
            exclude_columns.append('on_sale_date')
        if not rating_present:
            exclude_columns.append('rating')

        context = {
            'series': series,
            'by_date': by_date,
        }
        template = 'gcd/details/series_details_sortable.html'
        issues = series.active_issues()
        table = SeriesDetailsIssueTable(issues,
                                        template_name=TW_SORT_TABLE_TEMPLATE,
                                        order_by=('key_date'),
                                        exclude_columns=exclude_columns)
        return generic_sortable_list(request, issues, table, template,
                                     context, 500)

    return render(
      request, 'gcd/details/series_timeline.html',
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


def _annotate_creator_list(creators):
    creators = creators.annotate(
      first_credit=Min(Case(When(
        creator_names__storycredit__story__issue__key_date='',
        then=Value('9999-99-99'),),
                            default=F(
        'creator_names__storycredit__story__issue__key_date'))))
    script = Count('creator_names__storycredit__story__issue',
                   filter=Q(creator_names__storycredit__credit_type__id=1),
                   distinct=True)
    pencils = Count('creator_names__storycredit__story__issue',
                    filter=Q(creator_names__storycredit__credit_type__id=2),
                    distinct=True)
    inks = Count('creator_names__storycredit__story__issue',
                 filter=Q(creator_names__storycredit__credit_type__id=3),
                 distinct=True)
    colors = Count('creator_names__storycredit__story__issue',
                   filter=Q(creator_names__storycredit__credit_type__id=4),
                   distinct=True)
    letters = Count('creator_names__storycredit__story__issue',
                    filter=Q(creator_names__storycredit__credit_type__id=5),
                    distinct=True)
    creators = creators.annotate(
      issue_count=Count('creator_names__storycredit__story__issue',
                        distinct=True),
      script=script,
      pencils=pencils,
      inks=inks,
      colors=colors,
      letters=letters)
    return creators


def _annotate_creator_name_detail_list(creator_names):
    creators = creator_names.annotate(
      first_credit=Min(Case(When(storycredit__story__issue__key_date='',
                       then=Value('9999-99-99'),
                                 ),
                            default=F('storycredit__story__issue__key_date'))))
    script = Count('storycredit__story__issue',
                   filter=Q(storycredit__credit_type__id=1), distinct=True)
    pencils = Count('storycredit__story__issue',
                    filter=Q(storycredit__credit_type__id=2), distinct=True)
    inks = Count('storycredit__story__issue',
                 filter=Q(storycredit__credit_type__id=3), distinct=True)
    colors = Count('storycredit__story__issue',
                   filter=Q(storycredit__credit_type__id=4), distinct=True)
    letters = Count('storycredit__story__issue',
                    filter=Q(storycredit__credit_type__id=5), distinct=True)
    creators = creators.annotate(
      issue_count=Count('storycredit__story__issue', distinct=True),
      script=script,
      pencils=pencils,
      inks=inks,
      colors=colors,
      letters=letters)
    return creators


def publisher_creators(request, publisher_id, creator_names=False):
    publisher = get_gcd_object(Publisher, publisher_id)

    if creator_names:
        creators = CreatorNameDetail.objects.all()
        creators = creators.filter(
          storycredit__story__issue__series__publisher=publisher,
          storycredit__story__type__id__in=CORE_TYPES,
          storycredit__deleted=False).distinct()\
                                     .select_related('creator')
        creators = _annotate_creator_name_detail_list(creators)
    else:
        creators = Creator.objects.all()
        creators = creators.filter(
          creator_names__storycredit__story__issue__series__publisher=publisher,
          creator_names__storycredit__story__type__id__in=CORE_TYPES,
          creator_names__storycredit__deleted=False).distinct()
        creators = _annotate_creator_list(creators)

    context = {
        'result_disclaimer': ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER,
        'item_name': 'creator',
        'plural_suffix': 's',
        'heading': 'working for %s' % (publisher)
    }
    template = 'gcd/search/tw_list_sortable.html'
    if creator_names:
        table = GenericCreatorNameTable(creators,
                                        resolve_name='publisher',
                                        object=publisher,
                                        template_name=TW_SORT_TABLE_TEMPLATE,
                                        order_by=('name'))
    else:
        table = _table_creators_list_or_grid(request, creators, context,
                                             resolve_name='publisher',
                                             object=publisher)
    return generic_sortable_list(request, creators, table, template, context)


def series_creators(request, series_id, creator_names=False):
    series = get_gcd_object(Series, series_id)

    if creator_names:
        creators = CreatorNameDetail.objects.all()
        creators = creators.filter(storycredit__story__issue__series=series,
                                   storycredit__story__type__id__in=CORE_TYPES,
                                   storycredit__deleted=False).distinct()\
                           .select_related('creator')
        creators = _annotate_creator_name_detail_list(creators)
    else:
        creators = Creator.objects.all()
        creators = creators.filter(
          creator_names__storycredit__story__issue__series=series,
          creator_names__storycredit__story__type__id__in=CORE_TYPES,
          creator_names__storycredit__deleted=False).distinct()
        creators = _annotate_creator_list(creators)
    context = {
        'result_disclaimer': ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER,
        'item_name': 'creator',
        'plural_suffix': 's',
        'heading': 'working on %s' % (series)
    }
    template = 'gcd/search/tw_list_sortable.html'
    if creator_names:
        table = GenericCreatorNameTable(creators,
                                        object=series,
                                        resolve_name='series',
                                        template_name=TW_SORT_TABLE_TEMPLATE,
                                        order_by=('creator'))
    else:
        table = _table_creators_list_or_grid(request, creators, context,
                                             resolve_name='series',
                                             object=series)
    return generic_sortable_list(request, creators, table, template, context)


def series_characters(request, series_id):
    series = get_gcd_object(Series, series_id)
    characters = Character.objects.filter(
      character_names__storycharacter__story__issue__series=series,
      character_names__storycharacter__story__type__id__in=CORE_TYPES,
      character_names__storycharacter__deleted=False,
      deleted=False).distinct()

    characters = characters.annotate(issue_count=Count(
      'character_names__storycharacter__story__issue', distinct=True))
    characters = characters.annotate(first_appearance=Min(
      Case(When(character_names__storycharacter__story__issue__key_date='',
                then=Value('9999-99-99'),
                ),
           default=F('character_names__storycharacter__story__issue__key_date')
           )))
    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'character',
        'plural_suffix': 's',
        'heading': 'in series %s' % (series)
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = SeriesCharacterTable(characters,
                                 series=series,
                                 template_name=TW_SORT_TABLE_TEMPLATE,
                                 order_by=('character'))
    return generic_sortable_list(request, characters, table, template, context)


def series_issues_to_migrate(request, series_id):
    series = get_gcd_object(Series, series_id)
    issues = series.issues_to_migrate

    context = {
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'with text credits to migrate for %s' % (series)
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = _table_issues_list_or_grid(request, issues, context,
                                       publisher=False)
    return generic_sortable_list(request, issues, table, template, context)


class KeywordsTable(tables.Table):
    keyword = tables.Column(accessor='name')
    objects_count = tables.Column(verbose_name='# Usages')

    def render_keyword(self, record):
        url = urlresolvers.reverse(
                'show_keyword',
                kwargs={'keyword': record.name})
        return mark_safe('<a href="%s">%s</a>' % (url,
                                                  record.name))


def keywords(request, keyword=''):
    """
    List all keywords
    """
    if keyword:
        keywords = Tag.objects.filter(name__icontains=keyword)
    else:
        keywords = Tag.objects.all()
    keywords = keywords.annotate(
      objects_count=Count(
        'taggit_taggeditem_items',
        filter=~Q(taggit_taggeditem_items__content_type__id__in=[72, 75])))\
        .order_by('-objects_count').filter(objects_count__gt=0)
    template = 'gcd/search/tw_list_sortable.html'
    context = {
        'item_name': 'keyword',
        'plural_suffix': 's',
        'selected': 'keyword',
        'search_term': keyword,
        'heading': 'containing "%s"' % keyword
    }
    if not keyword:
        context['heading'] = ''
    table = KeywordsTable(keywords,
                          attrs={'class': 'sortable_listing'},
                          template_name=TW_SORT_TABLE_TEMPLATE,
                          order_by=('keywords'))
    return generic_sortable_list(request, keywords, table, template, context)


class KeywordTable(tables.Table):
    item = tables.Column(accessor='content_object',
                         verbose_name='Tagged Objects',
                         orderable=False)

    def render_item(self, record):
        url = record.content_object.get_absolute_url()
        return mark_safe('<a href="%s">%s</a>' % (url,
                                                  record.content_object))


def keyword(request, keyword, model_name=''):
    """
    Display the objects associated to a keyword.
    """
    if 'content_type' in request.GET:
        if request.GET['content_type'] == '13':
            model_name = 'story'
        elif request.GET['content_type'] == '12':
            model_name = 'issue'
        elif request.GET['content_type'] == '147':
            model_name = 'character'

    if model_name:
        from apps.oi.views import DISPLAY_CLASSES
        objs = DISPLAY_CLASSES[model_name].objects.filter(
          keywords__name=keyword, deleted=False)
        filter = None

    plural_suffix = 's'
    if model_name == 'story':
        table = StoryTable(objs,
                           template_name=TW_SORT_TABLE_TEMPLATE,
                           order_by=('issue'))
        object_type = 'sequence'
    elif model_name == 'issue':
        table = IssuePublisherTable(objs,
                                    template_name=TW_SORT_TABLE_TEMPLATE,
                                    order_by=('issue'))
        object_type = 'issue'
    elif model_name == 'character':
        table = CharacterTable(objs,
                               template_name=TW_SORT_TABLE_TEMPLATE,
                               order_by=('character'))
        object_type = 'character'
    else:
        objs = TaggedItem.objects.filter(tag__name=keyword).exclude(
          content_type__id__in=[72, 75])
        content_types = set(objs.values_list('content_type', flat=True))
        filter = KeywordUsedFilter(request.GET,
                                   queryset=objs,
                                   content_type=content_types)
        objs = filter.qs
        table = KeywordTable(objs,
                             attrs={'class': 'sortable_listing'},
                             template_name=TW_SORT_TABLE_TEMPLATE,
                             order_by=('name'))
        object_type = 'object'

    description = 'with the keyword "%s" (case insensitive)' % (
      keyword)

    context = {'object': keyword,
               'heading': description,
               'item_name': object_type,
               'plural_suffix': plural_suffix,
               }
    if filter:
        context['filter'] = filter

    return generic_sortable_list(request, objs, table,
                                 'gcd/search/tw_list_sortable.html', context)


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
                          'creator_relation', 'creator_school',
                          'creator_signature', 'feature', 'feature_logo',
                          'character', 'group', 'character_relation',
                          'group_relation', 'group_membership', 'universe']:
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

        # filter is publisherrevisions__publisher, seriesrevisions__series, etc
        filter_string = '%ss__%s' % (
          REVISION_CLASSES[model_name].__name__.lower(), model_name)

    kwargs = {str(filter_string): object, 'state': states.APPROVED}
    changesets = Changeset.objects.filter(**kwargs).order_by('-modified',
                                                             '-id')

    if model_name == 'issue':
        [prev_issue, next_issue] = object.get_prev_next_issue()

    return render(
      request, template,
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
    if prev_year is None:
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
                  {'date': grid_date, 'issues': [issue]})
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
    return HttpResponseRedirect(
      urlresolvers.reverse('show_series',
                           kwargs={'series_id': series_id}) + '#index_status')


def _get_scan_table(series, show_cover=True):
    # freshly added series have no scans on preview page
    if series is None:
        return None, None, None

    if not series.is_comics_publication:
        return Cover.objects.none(), \
          get_image_tag(cover=None, zoom_level=ZOOM_MEDIUM,
                        alt_text='First Issue Cover',
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
    return HttpResponseRedirect(
      urlresolvers.reverse('show_series',
                           kwargs={'series_id': series_id}) + '#cover_status')


def covers_to_replace(request, starts_with=None):
    """
    Display the covers that are marked for replacement.
    """

    covers = Cover.objects.filter(marked=True)
    if starts_with:
        covers = covers.filter(issue__series__name__startswith=starts_with)
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
        'table_width': table_width,
        'starts_with': starts_with,
        'RANDOM_IMAGE': 2,
      },
      per_page=COVERS_PER_GALLERY_PAGE,
      callback_key='tags',
      callback=get_image_tags_per_page)


def daily_covers(request, show_date=None, user=False):
    """
    Produce a page displaying the covers uploaded on a given day.
    """
    url_reverse = '%scovers_by_date' % ('my_' if user else '')
    requested_date, show_date = _handle_date_picker(request,
                                                    url_reverse,
                                                    show_date=show_date)
    if show_date is False:
        return requested_date

    date_before = requested_date + timedelta(-1)
    if requested_date < date.today():
        date_after = requested_date + timedelta(1)
    else:
        date_after = None

    covers = Cover.objects.filter(last_upload__range=(
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

    filter = filter_covers(request, covers)
    covers = filter.qs

    if request.user.is_authenticated and request.user.indexer.imps > 0:
        link_name = 'all uploaded covers' if user else 'my uploaded covers'
        other_url = urlresolvers.reverse(
          '%scovers_by_date' % ('my_' if user is False else ''),
          kwargs={'show_date': requested_date})

        result_disclaimer = mark_safe('Switch to <a href="%s">%s</a>.' % (
          other_url, link_name))
    else:
        result_disclaimer = ''

    context = {
        'item_name': 'cover',
        'plural_suffix': 's',
        'publisher': publisher,
        'heading': 'uploaded on %s' % show_date,
        'years': range(date.today().year, 2003, -1),
        'daily': True,
        'choose_url_before': urlresolvers.reverse(
          '%scovers_by_date' % ('my_' if user else ''),
          kwargs={'show_date': date_before}),
        'choose_url_after': urlresolvers.reverse(
          '%scovers_by_date' % ('my_' if user else ''),
          kwargs={'show_date': date_after}),
        'choose_date': True,
        'result_disclaimer': result_disclaimer,
        'filter_form': filter.form,
    }

    template = 'gcd/search/tw_list_sortable.html'
    table = CoverIssuePublisherEditTable(
      covers,
      template_name=TW_SORT_GRID_TEMPLATE,
      order_by=('publisher'))
    return generic_sortable_list(request, covers, table, template,
                                 context, 50)

    return paginate_response(
      request,
      covers,
      'gcd/status/daily_covers.html',
      {
        'date': show_date,
        'years': range(date.today().year, 2003, -1),
        'daily': True,
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

    url_reverse = '%schanges_by_date' % ('my_' if user else '')
    requested_date, show_date = _handle_date_picker(request,
                                                    url_reverse,
                                                    show_date=show_date)
    if show_date is False:
        return requested_date

    date_before = requested_date + timedelta(-1)
    if requested_date < date.today():
        date_after = requested_date + timedelta(1)
    else:
        date_after = None

    args = {'changeset__modified__range':
            (datetime.combine(requested_date, time.min),
             datetime.combine(requested_date, time.max)),
            'deleted': False,
            'changeset__state': states.APPROVED}

    if user and request.user.is_authenticated:
        user = request.user
    else:
        user = None

    # TODO what about awards, memberships, etc. Display separately,
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
                   .select_related('publisher', 'country',
                                   'first_issue', 'last_issue')

    series_bond_revisions = list(_get_daily_revisions(SeriesBondRevision,
                                                      args, 'series_bond',
                                                      user=user))
    series_bonds = SeriesBond.objects.filter(id__in=series_bond_revisions)\
                             .distinct().select_related('origin', 'target')

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
    brand_images = Brand.objects.filter(
      image_resources__id__in=brand_revisions).distinct()
    if brand_images:
        images.append((brand_images, '', 'Brand emblem', 'brand'))

    indicia_revisions = list(image_revisions.filter(type__name='IndiciaScan'))
    indicia_issues = Issue.objects.filter(
      image_resources__id__in=indicia_revisions)
    if indicia_issues:
        images.append((indicia_issues, 'image/', 'Indicia Scan', 'issue'))

    soo_revisions = list(image_revisions.filter(type__name='SoOScan'))
    soo_issues = Issue.objects.filter(image_resources__id__in=soo_revisions)
    if soo_issues:
        images.append((soo_issues, 'image/', 'Statement of ownership',
                       'issue'))

    return render(
      request, 'gcd/status/daily_changes.html',
      {
        'date': show_date,
        'years': range(date.today().year, 2009, -1),
        'daily': True,
        'choose_url_before': urlresolvers.reverse(
          '%schanges_by_date' % ('my_' if user else ''),
          kwargs={'show_date': date_before}),
        'choose_url_after': urlresolvers.reverse(
          '%schanges_by_date' % ('my_' if user else ''),
          kwargs={'show_date': date_after}),
        'other_url': urlresolvers.reverse(
          '%schanges_by_date' % ('my_' if user is False else ''),
          kwargs={'show_date': requested_date}),
        'creators': creators,
        'publishers': publishers,
        'brand_groups': brand_groups,
        'brands': brands,
        'indicia_publishers': indicia_publishers,
        'series': series,
        'series_bonds': series_bonds,
        'issues': issues,
        'all_images': images
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
              urlresolvers.reverse('on_sale_weekly',
                                   kwargs={'year': year,
                                           'week': week})), None
        if year:
            year = int(year)
        if week:
            week = int(week)
    except ValueError:
        year = None
    if year is None:
        year, week = date.today().isocalendar()[0:2]
    # gregorian calendar date of the first day of the given ISO year
    fourth_jan = date(int(year), 1, 4)
    delta = timedelta(fourth_jan.isoweekday()-1)
    year_start = fourth_jan - delta
    monday = year_start + timedelta(weeks=int(week)-1)
    sunday = monday + timedelta(days=6)
    # we need this to filter out incomplete on-sale dates
    if monday.month != sunday.month:
        endday = monday.replace(day=monthrange(monday.year, monday.month)[1])
        issues_on_sale = Issue.objects.filter(
          on_sale_date__gte=monday.isoformat(),
          on_sale_date__lte=endday.isoformat())
        startday = sunday.replace(day=1)
        issues_on_sale = issues_on_sale | Issue.objects.filter(
          on_sale_date__gte=startday.isoformat(),
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
    choose_url = urlresolvers.reverse("on_sale_this_week")
    choose_url_before = urlresolvers.reverse("on_sale_weekly",
                                             kwargs={
                                               'year': previous_week[0],
                                               'week': previous_week[1]})
    if next_week:
        choose_url_after = urlresolvers.reverse("on_sale_weekly",
                                                kwargs={
                                                  'year': next_week[0],
                                                  'week': next_week[1]})
    else:
        choose_url_after = ""
    vars = {
        'items': issues_on_sale,
        'heading': heading,
        'dates': dates,
        'choose_url': choose_url,
        'choose_url_after': choose_url_after,
        'choose_url_before': choose_url_before,
        'query_string': urlencode(query_val),
    }
    return issues_on_sale, vars


def on_sale_weekly(request, year=None, week=None, variant=True):
    issues_on_sale, vars = do_on_sale_weekly(request, year, week)
    if vars is None:
        # MYCOMICS
        return issues_on_sale

    issues_on_sale = issues_on_sale.annotate(
      longest_story_id=Subquery(Story.objects.filter(
                                issue_id=OuterRef('pk'),
                                type_id=19, deleted=False)
                                .values('pk').order_by('-page_count')[:1]))

    if not variant:
        issues_on_sale = issues_on_sale.filter(variant_of=None)
    filter = filter_issues(request, issues_on_sale)
    issues_on_sale = filter.qs
    table = CoverIssueStoryPublisherTable(issues_on_sale,
                                          attrs={'class': 'sortable_listing'},
                                          template_name=SORT_TABLE_TEMPLATE,
                                          order_by=('issues'))
    vars['filter'] = filter
    vars['variant'] = variant
    if variant:
        if year:
            vars['path'] = urlresolvers.reverse("on_sale_weekly_no_variant",
                                                kwargs={'year': year,
                                                        'week': week})
        else:
            vars['path'] = urlresolvers.reverse("on_sale_this_week_no_variant")
    else:
        if year:
            vars['path'] = urlresolvers.reverse("on_sale_weekly",
                                                kwargs={'year': year,
                                                        'week': week})
        else:
            vars['path'] = urlresolvers.reverse("on_sale_this_week")

    return generic_sortable_list(request, issues_on_sale, table,
                                 'gcd/status/issues_on_sale.html', vars, 50)


def do_on_sale_monthly(request, year=None, month=None):
    """
    Produce a page displaying the comics on-sale in a given month.
    """
    if year and 'month' not in request.GET:
        year = int(year)
        month = int(month)
    else:
        return_val, show_date = _handle_date_picker(request,
                                                    'on_sale_monthly',
                                                    monthly=True)
        if show_date is False:
            return return_val, None
        elif show_date is True:
            year = int(return_val[0])
            month = int(return_val[1])

    issues_on_sale = Issue.objects.filter(
      on_sale_date__gte='%d-%02d-50' % (year, month-1),
      on_sale_date__lte='%d-%02d-32' % (year, month))

    start_date = datetime(year, month, 1)
    heading = "on-sale in %s" % (start_date.strftime('%B %Y'))
    query_val = {'target': 'issue',
                 'method': 'icontains'}
    query_val['use_on_sale_date'] = True
    query_val['start_date'] = '%d-%02d-32' % (year, month-1)
    query_val['end_date'] = '%d-%02d-32' % (year, month)
    issues_on_sale = issues_on_sale.filter(deleted=False)
    date_before = start_date + timedelta(-1)
    date_after = start_date + timedelta(31)
    choose_url = urlresolvers.reverse("on_sale_monthly",
                                      kwargs={'year': year,
                                              'month': month})
    choose_url_before = urlresolvers.reverse("on_sale_monthly",
                                             kwargs={
                                               'year': date_before.year,
                                               'month': date_before.month})
    choose_url_after = urlresolvers.reverse("on_sale_monthly",
                                            kwargs={
                                              'year': date_after.year,
                                              'month': date_after.month})
    oldest = Issue.objects.exclude(on_sale_date='').order_by('on_sale_date')[0]

    vars = {
        'items': issues_on_sale,
        'years': range(date.today().year, int(oldest.on_sale_date[:4]), -1),
        'heading': heading,
        'choose_url': choose_url,
        'choose_url_after': choose_url_after,
        'choose_url_before': choose_url_before,
        'choose_date': True,
        'query_string': urlencode(query_val),
        'date': start_date,
    }
    return issues_on_sale, vars


def on_sale_monthly(request, year=None, month=None, variant=True):
    issues_on_sale, context = do_on_sale_monthly(request, year, month)
    if context is None:
        return issues_on_sale
    issues_on_sale = issues_on_sale.annotate(
      longest_story_id=Subquery(Story.objects.filter(
                                issue_id=OuterRef('pk'),
                                type_id=19, deleted=False)
                                .values('pk')
                                .order_by('-page_count')[:1]))
    if not variant:
        issues_on_sale = issues_on_sale.filter(variant_of=None)
    filter = filter_issues(request, issues_on_sale)
    issues_on_sale = filter.qs

    if variant:
        if year:
            switch_url = urlresolvers.reverse("on_sale_monthly_no_variant",
                                              kwargs={'year': year,
                                                      'month': month})
        else:
            switch_url = urlresolvers.reverse(
              "on_sale_this_month_no_variant")
        switch_name = 'Show Without Variants'
    else:
        if year:
            switch_url = urlresolvers.reverse("on_sale_monthly",
                                              kwargs={'year': year,
                                                      'month': month})
        else:
            switch_url = urlresolvers.reverse("on_sale_this_month")
        switch_name = 'Show With Variants'

    switch_link = '<div class="mt-1"><a href="%s">' \
                  '<button class="btn btn-blue">%s</button></a></div>' % (
                    switch_url, switch_name)
    context['result_disclaimer'] = mark_safe(switch_link)
    context['item_name'] = 'issue'
    context['plural_suffix'] = 's'
    context['filter_form'] = filter.form
    context['variant'] = variant
    table = CoverIssueStoryPublisherTable(issues_on_sale,
                                          attrs={'class': 'sortable_listing'},
                                          template_name=TW_SORT_TABLE_TEMPLATE,
                                          order_by=('issues'))
    return generic_sortable_list(request, issues_on_sale, table,
                                 'gcd/search/tw_list_sortable.html',
                                 context, 50)


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
    stats = []
    for obj in objects:
        kwargs = {object_name: obj}
        stats.append((obj, CountStats.objects.filter(**kwargs)))

    return render(
      request, 'gcd/status/international_stats.html',
      {
        'stats': stats,
        'type': object_name,
        'form': form
      })


def feature(request, feature_id):
    """
    Display the details page for a Feature.
    """
    feature = get_gcd_object(Feature, feature_id)
    return show_feature(request, feature)


def show_feature(request, feature, preview=False):
    logos = feature.active_logos().annotate(
      issue_count=Count('story__issue', distinct=True))

    table = FeatureLogoTable(logos,
                             template_name=TW_SORT_TABLE_TEMPLATE,
                             order_by=('year_began'))
    table.no_export = True
    table.not_sticky = True

    issues = Issue.objects.filter(story__feature_object=feature,
                                  story__type__id=6,
                                  story__credits__deleted=False,
                                  cover__isnull=False,
                                  cover__deleted=False).distinct()

    if issues:
        selected_issue = issues[randint(0, issues.count()-1)]
        image_tag = get_image_tag(cover=selected_issue.cover_set.first(),
                                  zoom_level=ZOOM_MEDIUM,
                                  alt_text='Random Cover from Feature')
    else:
        image_tag = ''
        selected_issue = None

    context = {'feature': feature,
               'table': table,
               'image_tag': image_tag,
               'image_issue': selected_issue,
               'error_subject': '%s' % feature,
               'preview': preview}
    return generic_sortable_list(request, logos, table,
                                 'gcd/details/tw_feature.html', context)


def feature_sequences(request, feature_id, country=None):
    feature = get_gcd_object(Feature, feature_id)
    stories = Story.objects.filter(feature_object=feature,
                                   deleted=False).distinct()\
                           .select_related('issue__series__publisher')
    if country:
        country = get_object_or_404(Country, code=country)
        stories = stories.filter(issue__series__country=country)
    heading = 'for feature %s' % (feature)

    filter = filter_sequences(request, stories)
    filter.filters.pop('language')
    stories = filter.qs

    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'sequence',
        'plural_suffix': 's',
        'heading': heading,
        'filter_form': filter.form
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = StoryTable(stories,
                       template_name=TW_SORT_TABLE_TEMPLATE,
                       order_by=('issue'))
    return generic_sortable_list(request, stories, table, template, context)


def feature_issuelist_by_id(request, feature_id):
    feature = get_gcd_object(Feature, feature_id)

    if feature.feature_type.id == 1:
        issues = Issue.objects.filter(story__feature_object=feature,
                                      story__type__id__in=CORE_TYPES,
                                      story__deleted=False).distinct()\
                              .select_related('series__publisher')
        result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER
    else:
        issues = Issue.objects.filter(story__feature_object=feature,
                                      story__deleted=False).distinct()\
                              .select_related('series__publisher')
        result_disclaimer = MIGRATE_DISCLAIMER

    filter = filter_issues(request, issues)
    filter.filters.pop('language')
    issues = filter.qs

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'for feature %s' % (feature),
        'filter_form': filter.form
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = _table_issues_list_or_grid(request, issues, context)
    return generic_sortable_list(request, issues, table, template, context)


def feature_overview(request, feature_id):
    feature = get_gcd_object(Feature, feature_id)

    if feature.feature_type.id == 1:
        issues = Issue.objects.filter(story__feature_object=feature,
                                      story__type__id=19,
                                      story__deleted=False).distinct()\
                              .select_related('series__publisher')
        issues = issues.annotate(
          longest_story_id=Subquery(Story.objects.filter(
                                    feature_object=feature,
                                    issue_id=OuterRef('pk'),
                                    type_id=19, deleted=False)
                                    .values('pk')
                                    .order_by('-page_count')[:1]))
        result_disclaimer = OVERVIEW_DISCLAIMER
    else:
        issues = Issue.objects.none()
        result_disclaimer = 'not supported for this feature type'

    filter = filter_issues(request, issues)
    filter.filters.pop('language')
    issues = filter.qs

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'issue',
        'plural_suffix': 's',
        'publisher': True,
        'filter_form': filter.form,
        'heading': 'overview for feature %s' % (feature)
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = CoverIssueStoryTable(issues,
                                 attrs={'class': 'sortable_listing'},
                                 template_name=TW_SORT_TABLE_TEMPLATE,
                                 order_by=('publication_date'))
    return generic_sortable_list(request, issues, table, template, context, 50)


def feature_characters(request, feature_id):
    feature = get_gcd_object(Feature, feature_id)
    characters = Character.objects.filter(
      character_names__storycharacter__story__feature_object=feature,
      character_names__storycharacter__story__type__id__in=CORE_TYPES,
      character_names__storycharacter__deleted=False,
      deleted=False).distinct()

    characters = characters.annotate(issue_count=Count(
      'character_names__storycharacter__story__issue', distinct=True))
    characters = characters.annotate(first_appearance=Min(
      Case(When(character_names__storycharacter__story__issue__key_date='',
                then=Value('9999-99-99'),
                ),
           default=F('character_names__storycharacter__story__issue__key_date')
           )))
    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'character',
        'plural_suffix': 's',
        'heading': 'in feature %s' % (feature)
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = FeatureCharacterTable(characters,
                                  attrs={'class': 'sortable_listing'},
                                  feature=feature,
                                  template_name=TW_SORT_TABLE_TEMPLATE,
                                  order_by=('character'))
    return generic_sortable_list(request, characters, table, template, context)


def feature_creators(request, feature_id, creator_names=False):
    # list of creators that worked on feature feature_id
    feature = get_gcd_object(Feature, feature_id)
    if creator_names:
        creators = CreatorNameDetail.objects.all()
        if feature.feature_type.id == 1:
            creators = creators.filter(
              storycredit__story__feature_object__id=feature_id,
              storycredit__story__type__id__in=CORE_TYPES,
              storycredit__deleted=False).distinct().select_related('creator')
            result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER
        else:
            creators = creators.filter(
              storycredit__story__feature_object__id=feature_id,
              storycredit__deleted=False).distinct().select_related('creator')
            result_disclaimer = MIGRATE_DISCLAIMER
        creators = _annotate_creator_name_detail_list(creators)
    else:
        creators = Creator.objects.all()
        if feature.feature_type.id == 1:
            creators = creators.filter(
              creator_names__storycredit__story__feature_object__id=feature_id,
              creator_names__storycredit__story__type__id__in=CORE_TYPES,
              creator_names__storycredit__deleted=False).distinct()
            result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER
        else:
            creators = creators.filter(
              creator_names__storycredit__story__feature_object__id=feature_id,
              creator_names__storycredit__deleted=False).distinct()
            result_disclaimer = MIGRATE_DISCLAIMER
        creators = _annotate_creator_list(creators)

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'creator',
        'plural_suffix': 's',
        'heading': 'working on Feature %s' % (feature)
    }
    template = 'gcd/search/tw_list_sortable.html'
    if creator_names:
        table = GenericCreatorNameTable(creators,
                                        resolve_name='feature',
                                        object=feature,
                                        template_name=TW_SORT_TABLE_TEMPLATE,
                                        order_by=('name'))
    else:
        table = _table_creators_list_or_grid(request, creators, context,
                                             resolve_name='feature',
                                             object=feature)
    return generic_sortable_list(request, creators, table, template, context)


def feature_covers(request, feature_id):
    feature = get_gcd_object(Feature, feature_id)
    issues = Issue.objects.filter(story__feature_object=feature,
                                  story__type__id=6,
                                  story__credits__deleted=False).distinct()\
                          .select_related('series__publisher')

    heading = 'with feature %s' % feature

    filter = filter_issues(request, issues)
    filter.filters.pop('language')
    issues = filter.qs

    context = {
        'result_disclaimer': COVER_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER,
        'item_name': 'cover',
        'plural_suffix': 's',
        'heading': heading,
        'filter_form': filter.form
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = CoverIssuePublisherTable(issues,
                                     attrs={'class': 'sortable_listing'},
                                     template_name=TW_SORT_TABLE_TEMPLATE,
                                     order_by=('publication_date'))
    return generic_sortable_list(request, issues, table, template, context)


def feature_logo(request, feature_logo_id):
    """
    Display the details page for a Feature.
    """
    feature_logo = get_gcd_object(FeatureLogo,
                                  object_id=feature_logo_id,
                                  model_name='feature_logo')
    return show_feature_logo(request, feature_logo)


def show_feature_logo(request, feature_logo, preview=False):
    vars = {'feature_logo': feature_logo,
            'error_subject': '%s' % feature_logo,
            'preview': preview}
    return render(request, 'gcd/details/feature_logo.html', vars)


def feature_logo_sequences(request, feature_logo_id, country=None):
    feature_logo = get_gcd_object(FeatureLogo, feature_logo_id)
    stories = Story.objects.filter(feature_logo=feature_logo,
                                   deleted=False).distinct()\
                           .select_related('issue__series__publisher')
    if country:
        country = get_object_or_404(Country, code=country)
        stories = stories.filter(issue__series__country=country)
    heading = 'for feature logo %s' % (feature_logo)

    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'sequence',
        'plural_suffix': 's',
        'heading': heading
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = StoryTable(stories,
                       attrs={'class': 'sortable_listing'},
                       template_name=TW_SORT_TABLE_TEMPLATE,
                       order_by=('issue'))
    return generic_sortable_list(request, stories, table, template, context)


def feature_logo_issuelist_by_id(request, feature_logo_id):
    feature_logo = get_gcd_object(FeatureLogo, feature_logo_id)

    if feature_logo.feature.all()[0].feature_type.id == 1:
        issues = Issue.objects.filter(story__feature_logo=feature_logo,
                                      story__type__id__in=CORE_TYPES,
                                      story__deleted=False).distinct()\
                              .select_related('series__publisher')
        result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER
    else:
        issues = Issue.objects.filter(story__feature_logo=feature_logo,
                                      story__deleted=False).distinct()\
                              .select_related('series__publisher')
        result_disclaimer = MIGRATE_DISCLAIMER

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'for feature logo %s' % (feature_logo)
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = IssueTable(issues,
                       attrs={'class': 'sortable_listing'},
                       template_name=TW_SORT_TABLE_TEMPLATE,
                       order_by=('publication_date'))
    return generic_sortable_list(request, issues, table, template, context)


def feature_relation(request, feature_relation_id):
    feature_relation = get_object_or_404(FeatureRelation,
                                         id=feature_relation_id)
    return show_feature_relation(request, feature_relation)


def show_feature_relation(request, feature_relation, preview=False):
    vars = {'feature_relation': feature_relation,
            'error_subject': feature_relation,
            'preview': preview}
    return render(request, 'gcd/details/feature_relation.html', vars)


def multiverse(request, multiverse_id):
    """
    Display the details page for a Universe.
    """
    multiverse = get_gcd_object(Multiverse, multiverse_id)
    return show_multiverse(request, multiverse)


def show_multiverse(request, multiverse, preview=False):
    vars = {'multiverse': multiverse,
            'error_subject': '%s' % multiverse,
            'preview': preview}
    return render(request, 'gcd/details/multiverse.html', vars)


def universe(request, universe_id):
    """
    Display the details page for a Universe.
    """
    universe = get_gcd_object(Universe, universe_id)
    return show_universe(request, universe)


def show_universe(request, universe, preview=False):
    vars = {'universe': universe,
            'error_subject': '%s' % universe,
            'preview': preview}
    return render(request, 'gcd/details/universe.html', vars)


def universe_sequences(request, universe_id):
    universe = get_gcd_object(Universe, universe_id)
    heading = 'in universe %s' % (universe)

    stories = Story.objects.filter(universe=universe, deleted=False)\
                   .distinct().select_related('issue__series__publisher')

    filter = filter_sequences(request, stories)
    stories = filter.qs

    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'sequence',
        'plural_suffix': 's',
        'heading': heading,
        'filter_form': filter.form,
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = StoryTable(stories,
                       template_name=TW_SORT_TABLE_TEMPLATE,
                       order_by=('publication_date'))
    return generic_sortable_list(request, stories, table, template, context)


def universe_issues(request, universe_id):
    universe = get_gcd_object(Universe, universe_id)
    heading = 'in universe %s' % (universe)

    issues = Issue.objects.filter(
      story__universe=universe,
      story__deleted=False,
      deleted=False).distinct().select_related('series__publisher')

    filter = filter_issues(request, issues)
    issues = filter.qs

    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': heading,
        'filter_form': filter.form,
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = IssueTable(issues,
                       template_name=TW_SORT_TABLE_TEMPLATE,
                       order_by=('publication_date'))
    return generic_sortable_list(request, issues, table, template, context)


def universe_characters(request, universe_id):
    universe = get_gcd_object(Universe, universe_id)
    characters = Character.objects.filter(
      character_names__storycharacter__universe=universe,
      character_names__storycharacter__story__type__id__in=CORE_TYPES,
      character_names__storycharacter__deleted=False,
      deleted=False).distinct()

    characters = characters.annotate(issue_count=Count(
      'character_names__storycharacter__story__issue', distinct=True))
    characters = characters.annotate(first_appearance=Min(
      Case(When(character_names__storycharacter__story__issue__key_date='',
                then=Value('9999-99-99'),
                ),
           default=F('character_names__storycharacter__story__issue__key_date')
           )))
    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'character',
        'plural_suffix': 's',
        'heading': 'from Universe %s' % (universe)
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = UniverseCharacterTable(characters,
                                   universe=universe,
                                   template_name=TW_SORT_TABLE_TEMPLATE,
                                   order_by=('character'))
    return generic_sortable_list(request, characters, table, template, context)


def character(request, character_id):
    """
    Display the details page for a Character.
    """
    character = get_gcd_object(Character, character_id)
    return show_character(request, character)


def show_character(request, character, preview=False):
    if character.universe:
        universe_id = character.universe.id
        if character.active_generalisations():
            filter_character = character.active_generalisations().get()\
                                        .from_character
        else:
            filter_character = character
            universe_id = None
    else:
        filter_character = character
        universe_id = None

    query = {'story__appearing_characters__character__character':
             filter_character,
             'story__appearing_characters__deleted': False,
             'story__type__id': 6,
             'story__deleted': False,
             'cover__isnull': False,
             'cover__deleted': False}

    issues = Issue.objects.filter(Q(**query)).distinct()\
                          .select_related('series__publisher')
    if universe_id:
        query['story__appearing_characters__universe_id'] = universe_id
    issues = Issue.objects.filter(Q(**query)).distinct()\
                          .select_related('series__publisher')

    if issues:
        selected_issue = issues[randint(0, issues.count()-1)]
        image_tag = get_image_tag(cover=selected_issue.cover_set.first(),
                                  zoom_level=ZOOM_MEDIUM,
                                  alt_text='Random Cover from Character')
    else:
        image_tag = ''
        selected_issue = None

    context = {'character': character,
               'additional_names': character.active_names()
                                            .filter(is_official_name=False),
               'error_subject': '%s' % character,
               'image_tag': image_tag,
               'image_issue': selected_issue,
               'preview': preview}
    return render(request, 'gcd/details/tw_character.html', context)


def character_characters(request, character_id):
    character = get_gcd_object(Character, character_id)
    universe_id = None
    if character.universe:
        if character.active_generalisations():
            filter_character = character.active_generalisations().get()\
                                        .from_character
            universe_id = character.universe.id
        else:
            filter_character = character
    else:
        filter_character = character

    query = {'character_names__storycharacter__story__'
             'appearing_characters__character__character':
             filter_character,
             'character_names__storycharacter__deleted': False,
             'character_names__storycharacter__story__type__id__in':
             CORE_TYPES}
    if universe_id:
        query['character_names__storycharacter__story__'
              'appearing_characters__universe_id'] = universe_id
    characters = Character.objects.filter(Q(**query))\
                          .exclude(id=filter_character.id).distinct()

    characters = characters.annotate(issue_count=Count(
      'character_names__storycharacter__story__issue', distinct=True))
    characters = characters.annotate(first_appearance=Min(
      Case(When(character_names__storycharacter__story__issue__key_date='',
                then=Value('9999-99-99'),
                ),
           default=F('character_names__storycharacter__story__issue__key_date')
           )))
    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'character',
        'plural_suffix': 's',
        'heading': 'appearing together with %s' % (character)
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = CharacterCharacterTable(characters,
                                    character=character,
                                    template_name=TW_SORT_TABLE_TEMPLATE,
                                    order_by=('character'))
    return generic_sortable_list(request, characters, table, template, context)


def character_features(request, character_id):
    character = get_gcd_object(Character, character_id)
    features = Feature.objects.filter(
      story__appearing_characters__character__character=character,
      story__type__id__in=CORE_TYPES,
      story__deleted=False,
      deleted=False).distinct()

    features = features.annotate(issue_count=Count(
      'story__issue', distinct=True))
    features = features.annotate(first_appearance=Min(
      Case(When(story__issue__key_date='',
                then=Value('9999-99-99'),
                ),
           default=F('story__issue__key_date')
           )))
    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'feature',
        'plural_suffix': 's',
        'heading': 'with an appearance of %s' % (character)
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = CharacterFeatureTable(features,
                                  character=character,
                                  template_name=TW_SORT_TABLE_TEMPLATE,
                                  order_by=('feature'))
    return generic_sortable_list(request, features, table, template, context)


def character_issues(request, character_id, layer=None, universe_id=None,
                     story_universe_id=None):
    character = get_gcd_object(Character, character_id)
    if character.universe:
        universe_id = character.universe.id
        if character.active_generalisations():
            filter_character = character.active_generalisations().get()\
                                        .from_character
        else:
            filter_character = character
            universe_id = None
    else:
        filter_character = character

    query = {'story__appearing_characters__character__character':
             filter_character,
             'story__appearing_characters__deleted': False,
             'story__type__id__in': CORE_TYPES,
             'story__deleted': False}

    issues = Issue.objects.filter(Q(**query)).distinct()\
                          .select_related('series__publisher')
    if layer == -1 and character.active_specifications().exists():
        characters = character.active_specifications()\
                              .values_list('to_character_id', flat=True)
        issues |= Issue.objects.filter(
            story__appearing_characters__character__character_id__in=list(
              characters),
            story__appearing_characters__deleted=False,
            story__type__id__in=CORE_TYPES,
            story__deleted=False).distinct()\
                                 .select_related('series__publisher')
    elif layer == 1 and character.active_generalisations().exists():
        characters = character.active_generalisations()\
                              .values_list('from_character_id', flat=True)
        issues |= Issue.objects.filter(
            story__appearing_characters__character__character_id__in=list(
              characters),
            story__appearing_characters__deleted=False,
            story__type__id__in=CORE_TYPES,
            story__deleted=False).distinct()\
                                 .select_related('series__publisher')
    else:
        if universe_id:
            if universe_id == '-1':
                query['story__appearing_characters__universe_id__isnull'] = \
                  True
            else:
                query['story__appearing_characters__universe_id'] = universe_id
        if story_universe_id:
            if story_universe_id == '-1':
                query['story__universe__isnull'] = True
            else:
                query['story__universe__in'] = [story_universe_id,]
        issues = Issue.objects.filter(Q(**query)).distinct()\
                              .select_related('series__publisher')

    result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER
    filter = filter_issues(request, issues)
    filter.filters.pop('language')
    issues = filter.qs

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'for character %s' % (character),
        'filter_form': filter.form
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = _table_issues_list_or_grid(request, issues, context)
    return generic_sortable_list(request, issues, table, template, context)


def character_issues_character(request, character_id, character_with_id):
    character = get_gcd_object(Character, character_id)
    character_with = get_gcd_object(Character, character_with_id)

    filter_character = character
    universe_id = None
    if character.universe:
        if character.active_generalisations():
            universe_id = character.universe.id
            filter_character = character.active_generalisations()\
                                        .get().from_character

    query = {'appearing_characters__character__character':
             filter_character,
             'appearing_characters__deleted': False,
             'type__id__in': CORE_TYPES,
             'deleted': False}
    if universe_id:
        query['appearing_characters__universe_id'] = universe_id

    stories = Story.objects.filter(Q(**query))

    filter_character_with = character_with
    if character_with.universe:
        if character_with.active_generalisations():
            universe_id = character_with.universe.id
            filter_character_with = character_with.active_generalisations()\
                                                  .get().from_character
    query_with = {'story__appearing_characters__character__character':
                  filter_character_with,
                  'story__appearing_characters__deleted': False,
                  'story__type__id__in': CORE_TYPES,
                  'story__deleted': False,
                  'story__id__in': stories}

    issues = Issue.objects.filter(Q(**query_with)).distinct()\
                          .select_related('series__publisher')
    filter = filter_issues(request, issues)
    filter.filters.pop('language')
    issues = filter.qs

    result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'for %s with %s' % (character, character_with),
        'filter_form': filter.form
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = _table_issues_list_or_grid(request, issues, context)
    return generic_sortable_list(request, issues, table, template, context)


def character_issues_feature(request, character_id, feature_id):
    character = get_gcd_object(Character, character_id)
    feature = get_gcd_object(Feature, feature_id)

    filter_character = character
    universe_id = None
    if character.universe:
        if character.active_generalisations():
            universe_id = character.universe.id
            filter_character = character.active_generalisations()\
                                        .get().from_character

    query = {'story__appearing_characters__character__character':
             filter_character,
             'story__appearing_characters__deleted': False,
             'story__type__id__in': CORE_TYPES,
             'story__feature_object__id': feature_id,
             'story__deleted': False}

    if universe_id:
        query['story__appearing_characters__universe_id'] = universe_id

    issues = Issue.objects.filter(Q(**query)).distinct()\
                          .select_related('series__publisher')
    filter = filter_issues(request, issues)
    filter.filters.pop('language')
    issues = filter.qs
    result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'for %s in  %s' % (character, feature),
        'filter_form': filter.form
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = _table_issues_list_or_grid(request, issues, context)
    return generic_sortable_list(request, issues, table, template, context)


def character_issues_series(request, character_id, series_id):
    character = get_gcd_object(Character, character_id)
    series = get_gcd_object(Series, series_id)

    filter_character = character
    universe_id = None
    if character.universe:
        if character.active_generalisations():
            universe_id = character.universe.id
            filter_character = character.active_generalisations()\
                                        .get().from_character

    query = {'story__appearing_characters__character__character':
             filter_character,
             'story__appearing_characters__deleted': False,
             'story__type__id__in': CORE_TYPES,
             'series__id': series_id,
             'story__deleted': False}

    if universe_id:
        query['story__appearing_characters__universe_id'] = universe_id

    issues = Issue.objects.filter(Q(**query)).distinct()\
                          .select_related('series__publisher')

    result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'for character %s in %s' % (character, series),
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = IssueTable(issues,
                       template_name=TW_SORT_TABLE_TEMPLATE,
                       order_by=('publication_date'))
    context['list_grid'] = True

    if 'display' not in request.GET or request.GET['display'] == 'list':
        table = IssueTable(issues,
                           template_name=TW_SORT_TABLE_TEMPLATE,
                           order_by=('publication_date'))
    else:
        table = IssueCoverTable(
          issues,
          template_name=TW_SORT_GRID_TEMPLATE,
          order_by=('publication_date'))

    return generic_sortable_list(request, issues, table, template, context)


def character_series(request, character_id):
    character = get_gcd_object(Character, character_id)
    universe_id = None
    heading = 'with character %s' % (character)
    filter_character = character

    if character.universe:
        if character.active_generalisations():
            universe_id = character.universe.id
            filter_character = character.active_generalisations()\
                                        .get().from_character

    if universe_id:
        series = Series.objects.filter(
          issue__story__appearing_characters__character__character=
          filter_character,
          issue__story__appearing_characters__universe_id=universe_id,
          issue__story__appearing_characters__deleted=False,
          issue__story__type__id__in=CORE_TYPES,
          deleted=False).distinct().select_related('publisher')
    else:
        series = Series.objects.filter(
          issue__story__appearing_characters__character__character=
          filter_character,
          issue__story__appearing_characters__deleted=False,
          issue__story__type__id__in=CORE_TYPES,
          deleted=False).distinct().select_related('publisher')
    filter = filter_series(request, series)
    filter.filters.pop('language')
    series = filter.qs

    series = series.annotate(appearances_count=Count('issue', distinct=True))
    series = series.annotate(first_appearance=Min('issue__key_date'))

    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'series',
        'plural_suffix': '',
        'heading': heading,
        'filter_form': filter.form
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = CharacterSeriesTable(series,
                                 character=character,
                                 template_name=TW_SORT_TABLE_TEMPLATE,
                                 order_by=('year'))
    return generic_sortable_list(request, series, table, template, context)


def character_creators(request, character_id, creator_names=False):
    character = get_gcd_object(Character, character_id)
    filter_character = character
    universe_id = None

    if character.universe:
        if character.active_generalisations():
            filter_character = character.active_generalisations().get()\
                                        .from_character
            universe_id = character.universe.id

    if universe_id:
        stories = Story.objects.filter(
          appearing_characters__character__character=filter_character,
          appearing_characters__universe_id=universe_id,
          appearing_characters__deleted=False).distinct()
    else:
        stories = Story.objects.filter(
          appearing_characters__character__character=filter_character,
          appearing_characters__deleted=False).distinct()
    stories = stories.filter(type__id__in=CORE_TYPES)
    filter = filter_sequences(request, stories)
    filter.filters.pop('language')
    stories = filter.qs
    stories_ids = stories.values_list('id', flat=True)
    if creator_names:
        creators = CreatorNameDetail.objects.filter(
          storycredit__story__id__in=stories_ids,
          storycredit__story__type__id__in=CORE_TYPES,
          storycredit__deleted=False,
          storycredit__credit_type__id__lt=6)
        creators = _annotate_creator_name_detail_list(creators)
    else:
        creators = Creator.objects.filter(
          creator_names__storycredit__story__id__in=stories_ids,
          creator_names__storycredit__story__type__id__in=CORE_TYPES,
          creator_names__storycredit__deleted=False,
          creator_names__storycredit__credit_type__id__lt=6)
        creators = _annotate_creator_list(creators)

    result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER
    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'creator',
        'plural_suffix': 's',
        'heading': 'working on character %s' % (character.name),
        'filter_form': filter.form
    }
    template = 'gcd/search/tw_list_sortable.html'
    if creator_names:
        table = GenericCreatorNameTable(creators,
                                        object=character,
                                        resolve_name='character',
                                        template_name=TW_SORT_TABLE_TEMPLATE,
                                        order_by=('name'))
    else:
        table = _table_creators_list_or_grid(request, creators, context,
                                             resolve_name='character',
                                             object=character)
    # TODO: pass filter through to links to combined lists
    return generic_sortable_list(request, creators, table, template, context)


def character_sequences(request, character_id):
    character = get_gcd_object(Character, character_id)
    universe_id = None
    heading = 'for character %s' % (character)

    if character.universe:
        if character.active_generalisations():
            universe_id = character.universe.id
            character = character.active_generalisations().get().from_character

    if universe_id:
        stories = Story.objects.filter(
          appearing_characters__character__character=character,
          appearing_characters__universe_id=universe_id,
          appearing_characters__deleted=False,
          deleted=False).distinct().select_related('issue__series__publisher')
    else:
        stories = Story.objects.filter(
          appearing_characters__character__character=character,
          appearing_characters__deleted=False,
          deleted=False).distinct().select_related('issue__series__publisher')

    filter = filter_sequences(request, stories)
    filter.filters.pop('language')
    stories = filter.qs

    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'sequence',
        'plural_suffix': 's',
        'heading': heading,
        'filter_form': filter.form,
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = StoryTable(stories,
                       attrs={'class': 'sortable_listing'},
                       template_name=TW_SORT_TABLE_TEMPLATE,
                       order_by=('publication_date'))
    return generic_sortable_list(request, stories, table, template, context)


def character_covers(request, character_id):
    character = get_gcd_object(Character, character_id)
    universe_id = None
    heading = 'with character %s' % character

    if character.universe:
        if character.active_generalisations():
            universe_id = character.universe.id
            character = character.active_generalisations().get().from_character

    if universe_id:
        issues = Issue.objects.filter(
          story__appearing_characters__character__character=character,
          story__appearing_characters__universe_id=universe_id,
          story__appearing_characters__deleted=False,
          story__type__id=6,
          story__deleted=False).distinct().select_related('series__publisher')
    else:
        issues = Issue.objects.filter(
          story__appearing_characters__character__character=character,
          story__appearing_characters__deleted=False,
          story__type__id=6,
          story__deleted=False).distinct().select_related('series__publisher')

    filter = filter_issues(request, issues)
    filter.filters.pop('language')
    issues = filter.qs

    context = {
        'result_disclaimer': COVER_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER,
        'item_name': 'cover',
        'plural_suffix': 's',
        'heading': heading,
        'filter_form': filter.form
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = CoverIssuePublisherTable(issues,
                                     template_name=TW_SORT_TABLE_TEMPLATE,
                                     order_by=('publication_date'))
    return generic_sortable_list(request, issues, table, template, context)


def character_name_issues(request, character_name_id, universe_id=None):
    character_name = get_gcd_object(CharacterNameDetail, character_name_id)
    character = character_name.character

    # look for name at generalization
    if not universe_id and character.universe:
        universe_id = character.universe.id
        if character.active_generalisations().filter(
           from_character__character_names__name=character_name.name):
            filter_character = character.active_generalisations().get()\
                                             .from_character
            filter_character_name = filter_character.character_names\
                                                    .get(name=
                                                         character_name.name,
                                                         deleted=False)
        else:
            return render(request, 'indexer/error.html',
                          {'error_text':
                           'Name does not exist at character generalization.'})
    else:
        filter_character_name = character_name

    issues = Issue.objects.filter(
      story__appearing_characters__character=filter_character_name,
      story__appearing_characters__deleted=False,
      story__type__id__in=CORE_TYPES,
      story__deleted=False).distinct().select_related('series__publisher')
    if universe_id:
        if universe_id == '-1':
            issues = Issue.objects.filter(
              story__appearing_characters__character=filter_character_name,
              story__appearing_characters__universe_id__isnull=True,
              story__appearing_characters__deleted=False,
              story__type__id__in=CORE_TYPES,
              story__deleted=False).distinct()\
                     .select_related('series__publisher')
        else:
            issues = Issue.objects.filter(
              story__appearing_characters__character=filter_character_name,
              story__appearing_characters__universe_id=universe_id,
              story__appearing_characters__deleted=False,
              story__type__id__in=CORE_TYPES,
              story__deleted=False).distinct()\
                     .select_related('series__publisher')

    result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER
    filter = filter_issues(request, issues)
    filter.filters.pop('language')
    issues = filter.qs

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'for name %s of character %s' % (character_name,
                                                    character),
        'filter_form': filter.form
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = IssueTable(issues,
                       attrs={'class': 'sortable_listing'},
                       template_name=TW_SORT_TABLE_TEMPLATE,
                       order_by=('publication_date'))
    return generic_sortable_list(request, issues, table, template, context)


def character_relation(request, character_relation_id):
    character_relation = get_gcd_object(CharacterRelation,
                                        character_relation_id,
                                        model_name='character_relation')
    return show_character_relation(request, character_relation)


def show_character_relation(request, character_relation, preview=False):
    vars = {'character_relation': character_relation,
            'error_subject': character_relation,
            'preview': preview}
    return render(request, 'gcd/details/character_relation.html', vars)


def group(request, group_id):
    """
    Display the details page for a Group.
    """
    group = get_gcd_object(Group, group_id)
    return show_group(request, group)


def show_group(request, group, preview=False):
    if group.universe:
        universe_id = group.universe.id
        if group.active_generalisations():
            filter_group = group.active_generalisations().get()\
                                        .from_group
        else:
            filter_group = group
            universe_id = None
    else:
        filter_group = group
        universe_id = None

    query = {'story__appearing_groups__group_name__group':
             filter_group,
             'story__appearing_groups__deleted': False,
             'story__type__id': 6,
             'story__deleted': False,
             'cover__isnull': False,
             'cover__deleted': False}

    issues = Issue.objects.filter(Q(**query)).distinct()\
                          .select_related('series__publisher')

    if universe_id:
        query['story__appearing_groups__universe_id'] = universe_id
    issues = Issue.objects.filter(Q(**query)).distinct()\
                          .select_related('series__publisher')

    if issues:
        selected_issue = issues[randint(0, issues.count()-1)]
        image_tag = get_image_tag(cover=selected_issue.cover_set.first(),
                                  zoom_level=ZOOM_MEDIUM,
                                  alt_text='Random Cover from Group')
    else:
        image_tag = ''
        selected_issue = None

    context = {'group': group,
               'additional_names': group.active_names()
                                        .filter(is_official_name=False),
               'error_subject': '%s' % group,
               'image_tag': image_tag,
               'image_issue': selected_issue,
               'preview': preview}
    return render(request, 'gcd/details/tw_group.html', context)


def group_features(request, group_id):
    group = get_gcd_object(Group, group_id)
    features = Feature.objects.filter(
      story__appearing_groups__group_name__group=group,
      story__type__id__in=CORE_TYPES,
      story__deleted=False,
      deleted=False).distinct()

    features = features.annotate(issue_count=Count(
      'story__issue', distinct=True))
    features = features.annotate(first_appearance=Min(
      Case(When(story__issue__key_date='',
                then=Value('9999-99-99'),
                ),
           default=F('story__issue__key_date')
           )))
    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'feature',
        'plural_suffix': 's',
        'heading': 'with an appearance of %s' % (group)
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = GroupFeatureTable(features,
                              group=group,
                              template_name=TW_SORT_TABLE_TEMPLATE,
                              order_by=('feature'))
    return generic_sortable_list(request, features, table, template, context)


def group_issues(request, group_id, universe_id=None, story_universe_id=None):
    group = get_gcd_object(Group, group_id)

    query = {'story__appearing_groups__group_name__group': group,
             'story__appearing_groups__deleted': False,
             'story__type__id__in': CORE_TYPES,
             'story__deleted': False}

    if universe_id:
        if universe_id == '-1':
            query['story__appearing_groups__universe_id__isnull'] = \
                True
        else:
            query['story__appearing_groups__universe_id'] = universe_id
    if story_universe_id:
        if story_universe_id == '-1':
            query['story__universe__isnull'] = True
        else:
            query['story__universe__in'] = [story_universe_id,]
    issues = Issue.objects.filter(Q(**query)).distinct()\
                          .select_related('series__publisher')

    result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'for group %s' % (group)
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = _table_issues_list_or_grid(request, issues, context)
    return generic_sortable_list(request, issues, table, template, context)


def group_name_issues(request, group_name_id, universe_id=None):
    group_name = get_gcd_object(GroupNameDetail, group_name_id)
    group = group_name.group

    query = {'story__appearing_groups__group_name': group_name,
             'story__appearing_groups__deleted': False,
             'story__type__id__in': CORE_TYPES,
             'story__deleted': False}

    if universe_id:
        if universe_id == '-1':
            query['story__appearing_groups__universe_id__isnull'] = \
                True
        else:
            query['story__appearing_groups__universe_id'] = universe_id
    issues = Issue.objects.filter(Q(**query)).distinct()\
                          .select_related('series__publisher')

    result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'for name %s of group %s' % (group_name, group)
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = _table_issues_list_or_grid(request, issues, context)
    return generic_sortable_list(request, issues, table, template, context)


def group_issues_feature(request, group_id, feature_id):
    group = get_gcd_object(Group, group_id)
    feature = get_gcd_object(Feature, feature_id)

    filter_group = group
    universe_id = None
    if group.universe:
        if group.active_generalisations():
            universe_id = group.universe.id
            filter_group = group.active_generalisations()\
                                .get().from_group

    query = {'story__appearing_groups__group_name__group':
             filter_group,
             'story__appearing_groups__deleted': False,
             'story__type__id__in': CORE_TYPES,
             'story__feature_object__id': feature_id,
             'story__deleted': False}

    if universe_id:
        query['story__appearing_groups__universe_id'] = universe_id

    issues = Issue.objects.filter(Q(**query)).distinct()\
                          .select_related('series__publisher')
    filter = filter_issues(request, issues)
    filter.filters.pop('language')
    issues = filter.qs
    result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'for %s in  %s' % (group, feature),
        'filter_form': filter.form
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = _table_issues_list_or_grid(request, issues, context)
    return generic_sortable_list(request, issues, table, template, context)


def group_issues_series(request, group_id, series_id):
    group = get_gcd_object(Group, group_id)
    series = get_gcd_object(Series, series_id)

    filter_group = group
    universe_id = None
    if group.universe:
        if group.active_generalisations():
            universe_id = group.universe.id
            filter_group = group.active_generalisations()\
                                .get().from_group

    query = {'story__appearing_groups__group_name__group':
             filter_group,
             'story__appearing_groups__deleted': False,
             'story__type__id__in': CORE_TYPES,
             'series__id': series_id,
             'story__deleted': False}

    if universe_id:
        query['story__appearing_groups__universe_id'] = universe_id

    issues = Issue.objects.filter(Q(**query)).distinct()\
                          .select_related('series__publisher')

    result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'for group %s in %s' % (group, series),
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = IssueTable(issues,
                       template_name=TW_SORT_TABLE_TEMPLATE,
                       order_by=('publication_date'))
    context['list_grid'] = True

    if 'display' not in request.GET or request.GET['display'] == 'list':
        table = IssueTable(issues,
                           template_name=TW_SORT_TABLE_TEMPLATE,
                           order_by=('publication_date'))
    else:
        table = IssueCoverTable(
          issues,
          template_name=TW_SORT_GRID_TEMPLATE,
          order_by=('publication_date'))

    return generic_sortable_list(request, issues, table, template, context)


def group_series(request, group_id):
    group = get_gcd_object(Group, group_id)
    universe_id = None
    heading = 'with group %s' % (group)
    filter_group = group

    if group.universe:
        if group.active_generalisations():
            universe_id = group.universe.id
            filter_group = group.active_generalisations()\
                                .get().from_group

    if universe_id:
        series = Series.objects.filter(
          issue__story__appearing_groups__group_name__group=
          filter_group,
          issue__story__appearing_groups__universe_id=universe_id,
          issue__story__appearing_groups__deleted=False,
          issue__story__type__id__in=CORE_TYPES,
          deleted=False).distinct().select_related('publisher')
    else:
        series = Series.objects.filter(
          issue__story__appearing_groups__group_name__group=
          filter_group,
          issue__story__appearing_groups__deleted=False,
          issue__story__type__id__in=CORE_TYPES,
          deleted=False).distinct().select_related('publisher')
    filter = filter_series(request, series)
    filter.filters.pop('language')
    series = filter.qs

    series = series.annotate(appearances_count=Count('issue', distinct=True))
    series = series.annotate(first_appearance=Min('issue__key_date'))

    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'series',
        'plural_suffix': '',
        'heading': heading,
        'filter_form': filter.form
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = GroupSeriesTable(series,
                             group=group,
                             template_name=TW_SORT_TABLE_TEMPLATE,
                             order_by=('year'))
    return generic_sortable_list(request, series, table, template, context)


def group_creators(request, group_id, creator_names=False):
    group = get_gcd_object(Group, group_id)

    if creator_names:
        creators = CreatorNameDetail.objects.all()
        creators = creators.filter(
          storycredit__story__appearing_groups__group_name__group=group,
          storycredit__story__appearing_groups__deleted=False,
          storycredit__story__type__id__in=CORE_TYPES,
          storycredit__deleted=False).distinct()
        result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER
        creators = _annotate_creator_name_detail_list(creators)
    else:
        creators = Creator.objects.all()
        creators = creators.filter(
          creator_names__storycredit__story__appearing_groups__group_name__group=group,
          creator_names__storycredit__story__appearing_groups__deleted=False,
          creator_names__storycredit__story__type__id__in=CORE_TYPES,
          creator_names__storycredit__deleted=False).distinct()
        result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER
        creators = _annotate_creator_list(creators)

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'creator',
        'plural_suffix': 's',
        'heading': 'Creators Working on Group %s' % (group)
    }
    template = 'gcd/search/tw_list_sortable.html'
    if creator_names:
        table = GenericCreatorNameTable(creators,
                                        attrs={'class': 'sortable_listing'},
                                        object=group,
                                        resolve_name='group',
                                        template_name=TW_SORT_TABLE_TEMPLATE,
                                        order_by=('name'))
    else:
        table = GenericCreatorTable(creators,
                                    attrs={'class': 'sortable_listing'},
                                    object=group,
                                    resolve_name='group',
                                    template_name=TW_SORT_TABLE_TEMPLATE,
                                    order_by=('name'))
    return generic_sortable_list(request, creators, table, template, context)


def group_sequences(request, group_id, country=None):
    group = get_gcd_object(Group, group_id)
    stories = Story.objects.filter(
      appearing_groups__group_name__group=group,
      appearing_groups__deleted=False,
      deleted=False).distinct().select_related('issue__series__publisher')
    if country:
        country = get_object_or_404(Country, code=country)
        stories = stories.filter(issue__series__country=country)
    heading = 'Sequences for Group %s' % (group)

    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'sequence',
        'plural_suffix': 's',
        'heading': heading
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = StoryTable(stories, attrs={'class': 'sortable_listing'},
                       template_name=TW_SORT_TABLE_TEMPLATE,
                       order_by=('publication_date'))
    return generic_sortable_list(request, stories, table, template, context)


def group_covers(request, group_id):
    group = get_gcd_object(Group, group_id)
    universe_id = None
    heading = 'with group %s' % group

    if group.universe:
        if group.active_generalisations():
            universe_id = group.universe.id
            group = group.active_generalisations().get().from_group

    if universe_id:
        issues = Issue.objects.filter(
          story__appearing_groups__group_name__group=group,
          story__appearing_groups__universe_id=universe_id,
          story__appearing_groups__deleted=False,
          story__type__id=6,
          story__deleted=False).distinct().select_related('series__publisher')
    else:
        issues = Issue.objects.filter(
          story__appearing_groups__group_name__group=group,
          story__appearing_groups__deleted=False,
          story__type__id=6,
          story__deleted=False).distinct().select_related('series__publisher')

    filter = filter_issues(request, issues)
    filter.filters.pop('language')
    issues = filter.qs

    context = {
        'result_disclaimer': COVER_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER,
        'item_name': 'cover',
        'plural_suffix': 's',
        'heading': heading,
        'filter_form': filter.form
    }
    template = 'gcd/search/tw_list_sortable.html'
    table = CoverIssuePublisherTable(issues,
                                     template_name=TW_SORT_TABLE_TEMPLATE,
                                     order_by=('publication_date'))
    return generic_sortable_list(request, issues, table, template, context)


def group_relation(request, group_relation_id):
    group_relation = get_gcd_object(GroupRelation,
                                    group_relation_id,
                                    model_name='group_relation')
    return show_group_relation(request, group_relation)


def show_group_relation(request, group_relation, preview=False):
    vars = {'group_relation': group_relation,
            'error_subject': group_relation,
            'preview': preview}
    return render(request, 'gcd/details/group_relation.html', vars)


def group_membership(request, group_membership_id):
    group_membership = get_gcd_object(GroupMembership,
                                      group_membership_id,
                                      model_name='group_membership')
    return show_group_membership(request, group_membership)


def show_group_membership(request, group_membership, preview=False):
    vars = {'group_membership': group_membership,
            'error_subject': group_membership,
            'preview': preview}
    return render(request, 'gcd/details/group_membership.html', vars)


def cover(request, issue_id, size):
    """
    Display the cover for a single issue on its own page.
    """

    size = int(size)
    if size not in [ZOOM_SMALL, ZOOM_MEDIUM, ZOOM_LARGE]:
        raise Http404

    issue = get_object_or_404(Issue, id=issue_id)

    if issue.deleted:
        return HttpResponseRedirect(
          urlresolvers.reverse('change_history',
                               kwargs={'model_name': 'issue', 'id': issue_id}))

    [prev_issue, next_issue] = issue.get_prev_next_issue()

    cover_tag = get_image_tags_per_issue(issue, "Cover for %s" %
                                                str(issue.full_name()),
                                         size, variants=True, as_list=True)
    extra = 'cover/%d/' % size  # TODO: remove abstraction-breaking hack.

    covers = Cover.objects.filter(issue__series=issue.series,
                                  issue__sort_code__lt=issue.sort_code,
                                  deleted=False)
    cover_page = int(covers.count()/COVERS_PER_GALLERY_PAGE) + 1

    return render(
      request, 'gcd/details/cover.html',
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


def issue_images(request, issue_id):
    """
    Display the images for a single issue on its own page.
    """

    issue = get_gcd_object(Issue, issue_id)
    [prev_issue, next_issue] = issue.get_prev_next_issue()

    indicia_image = issue.indicia_image
    if indicia_image:
        indicia_tag = get_generic_image_tag(indicia_image, 'indicia scan')
    else:
        indicia_tag = None

    soo_image = issue.soo_image
    if soo_image:
        soo_tag = get_generic_image_tag(soo_image,
                                        'statement of ownership scan')
    else:
        soo_tag = None

    return render(request, 'gcd/details/issue_images.html',
                  {'issue': issue,
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
          urlresolvers.reverse(issue, kwargs={'issue_id': int(id)}) + extra +
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
        return HttpResponseRedirect(
          urlresolvers.reverse('change_history',
                               kwargs={'model_name': 'issue', 'id': issue_id}))

    return show_issue(request, issue)


def show_issue(request, issue, preview=False):
    """
    Helper function to handle the main work of displaying an issue.
    Also used by OI previews.
    """
    alt_text = 'Cover Thumbnail for %s' % issue.full_name()
    zoom_level = ZOOM_MEDIUM

    if 'show_all' in request.GET:
        issue_detail = 2
    elif 'issue_detail' in request.GET:
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
    if 'show_sources' in request.GET:
        show_sources = True
    else:
        show_sources = False
    image_tag = get_image_tags_per_issue(issue=issue,
                                         zoom_level=zoom_level,
                                         alt_text=alt_text)
    images_count = Image.objects.filter(
      object_id=issue.id, deleted=False,
      content_type=ContentType.objects.get_for_model(issue)).count()

    if preview:
        cover_page = 0
    else:
        covers = Cover.objects.filter(issue__series=issue.series,
                                      issue__sort_code__lt=issue.sort_code,
                                      deleted=False)
        cover_page = int(covers.count()/COVERS_PER_GALLERY_PAGE) + 1

    variant_image_tags = []
    for variant_cover in issue.variant_covers():
        variant_image_tags.append(
          [variant_cover.issue,
           get_image_tag(variant_cover, zoom_level=ZOOM_SMALL,
                         alt_text='Cover Thumbnail for %s' %
                                  str(variant_cover.issue))])

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
            oi_indexers.append(i.indexer.id)

    revs = issue.revisions.filter(changeset__state=states.APPROVED)\
                .exclude(changeset__indexer__username=settings.ANON_USER_NAME)\
                .select_related('changeset')
    oi_indexers.extend(revs.values_list('changeset__indexer_id', flat=True))
    revs = issue.cover_revisions.filter(changeset__state=states.APPROVED)\
                .exclude(changeset__indexer__username=settings.ANON_USER_NAME)\
                .select_related('changeset')
    oi_indexers.extend(revs.values_list('changeset__indexer_id', flat=True))
    oi_indexers = list(set(oi_indexers))
    oi_indexers = Indexer.objects.filter(user__id__in=oi_indexers)

    if series.is_singleton:
        country = series.country
        language = series.language
    else:
        country = None
        language = None

    return render(
      request, 'gcd/details/issue.html',
      {'issue': issue,
       'prev_issue': prev_issue,
       'next_issue': next_issue,
       'cover_story': cover_story,
       'stories': stories,
       'oi_indexers': oi_indexers,
       'image_tag': image_tag,
       'variant_image_tags': variant_image_tags,
       'images_count': images_count,
       'cover_page': cover_page,
       'country': country,
       'language': language,
       'error_subject': '%s' % issue,
       'preview': preview,
       'not_shown_types': not_shown_types,
       'show_sources': show_sources,
       'among_others': issue.created and issue.created.year <=
                        settings.NEW_SITE_CREATION_DATE.year,
       'RANDOM_IMAGE': _publisher_image_content(issue.series.publisher_id)
       })


def show_issue_modal(request, issue_id):
    """
    Show short info and cover of an issue in a modal.
    """
    issue = get_object_or_404(
              Issue.objects.select_related('series__publisher'),
              id=issue_id)

    if issue.deleted:
        return HttpResponse("")

    alt_text = 'Cover Thumbnail for %s' % issue.full_name()
    image_tag = get_image_tags_per_issue(issue=issue,
                                         zoom_level=ZOOM_MEDIUM,
                                         alt_text=alt_text)
    cover_story, stories = issue.shown_stories()
    not_shown_types = StoryType.objects.exclude(id__in=CORE_TYPES)\
                               .values_list('id', flat=True)

    return render(request, 'gcd/bits/issue_modal.html',
                  {'issue': issue,
                   'cover_story': cover_story,
                   'stories': stories,
                   'not_shown_types': not_shown_types,
                   'image_tag': image_tag})


def show_story_modal(request, story_id):
    """
    Show a single story in a modal.
    """
    story = get_object_or_404(Story.objects.prefetch_related(
                              'feature_object',
                              'feature_logo__feature',
                              'credits__creator__creator',
                              'credits__creator__type'),
                              id=story_id)

    if story.deleted:
        return HttpResponse("")

    if story.type.name == 'cover':
        alt_text = 'Cover Thumbnail for %s' % story.issue.full_name()
        image_tag = get_image_tags_per_issue(issue=story.issue,
                                             zoom_level=ZOOM_MEDIUM,
                                             alt_text=alt_text)
    else:
        image_tag = ''
    return render(request, 'gcd/bits/single_story_modal.html',
                  {'story': story, 'image_tag': image_tag})


def credit_source(request, credit_id):
    """
    Show the source of a credit for use in a modal.
    """
    credit = get_object_or_404(StoryCredit.objects.select_related(
      'creator', 'credit_type', 'story__issue'), id=credit_id)

    if credit.deleted or not credit.is_sourced:
        return HttpResponse("")

    issue_url = credit.story.issue.get_absolute_url()
    issue_url += '?show_all&show_sources#%d' % credit.story.id

    return render(request, 'gcd/bits/credit_source.html',
                  {'credit': credit, 'issue_url': issue_url})


def credit_type_history(request, story_id, credit_type):
    from apps.oi.templatetags.compare import diff_list
    from apps.oi.models import PreviewStory

    if credit_type not in CREDIT_TYPES:
        raise ValueError

    story = get_object_or_404(Story, id=story_id)
    storyrevisions = story.revisions.filter(changeset__state=states.APPROVED)\
                                    .order_by('modified', 'id')\
                                    .select_related('changeset__indexer')
    old = getattr(storyrevisions[0], credit_type)
    old_rev = storyrevisions[0]
    changes = []
    for storyrev in storyrevisions[1:]:
        new = getattr(storyrev, credit_type)
        changed = old.strip() != new.strip()
        if not changed:
            credits = storyrev.story_credit_revisions.filter(
                              credit_type__name=credit_type)
            if credits:
                for credit in credits:
                    credit.compare_changes()
                    if credit.is_changed:
                        changed = True
                        break
        if changed:
            changes.append((old_rev, storyrev))
        old = new
        old_rev = storyrev
    change_data = []
    for change in changes:
        change_data.append((change[1].changeset, diff_list(change[0],
                                                           change[1],
                                                           credit_type)))

    return render(request, 'gcd/bits/credit_type_history.html',
                  {'changes': change_data,
                   'first': PreviewStory.init(storyrevisions[0]),
                   'credit_type': credit_type})


@xframe_options_sameorigin
def daily_creators(request, offset=0):
    today = datetime.today()
    if offset:
        fetched_day = datetime.today() + timedelta(int(offset))
        day = '%0.2d' % (fetched_day).day
        month = '%0.2d' % (fetched_day).month
        creators = Creator.objects.filter(birth_date__day=day,
                                          birth_date__month=month,
                                          deleted=False)
        return render(
          request,
          'gcd/bits/_daily_creators.html',
          {'creators': creators,
           'day': fetched_day,
           })

    day = '%0.2d' % (today).day
    month = '%0.2d' % (today).month
    creators_today = Creator.objects.filter(birth_date__day=day,
                                            birth_date__month=month,
                                            deleted=False)
    yesterday = datetime.today() - timedelta(1)
    day = '%0.2d' % (yesterday).day
    month = '%0.2d' % (yesterday).month
    creators_yesterday = Creator.objects.filter(birth_date__day=day,
                                                birth_date__month=month,
                                                deleted=False)
    tomorrow = datetime.today() + timedelta(1)
    day = '%0.2d' % (tomorrow).day
    month = '%0.2d' % (tomorrow).month
    creators_tomorrow = Creator.objects.filter(birth_date__day=day,
                                               birth_date__month=month,
                                               deleted=False)

    return render(
      request,
      'gcd/bits/daily_creators.html',
      {'creators_today': creators_today,
       'creators_yesterday': creators_yesterday,
       'creators_tomorrow': creators_tomorrow,
       'today': today,
       'yesterday': yesterday,
       'tomorrow': tomorrow
       })
