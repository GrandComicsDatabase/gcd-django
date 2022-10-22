# -*- coding: utf-8 -*-

"""View methods for pages displaying entity details."""

import re
from urllib.parse import urlencode, quote
from datetime import date, datetime, time, timedelta
from calendar import monthrange
from operator import attrgetter
from random import randint

from django.db.models import F, Q, Min, Count, Sum, Case, When, Value
from django.conf import settings
import django.urls as urlresolvers
from django.shortcuts import get_object_or_404, \
                             render
from django.http import HttpResponseRedirect, Http404, JsonResponse, \
                        HttpResponse
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.views.decorators.clickjacking import xframe_options_sameorigin

from django_tables2 import RequestConfig
from django_tables2.paginators import LazyPaginator
from django_tables2.export.export import TableExport

from djqscsv import render_to_csv_response

from apps.indexer.views import ViewTerminationError

from apps.stddata.models import Country, Language
from apps.stats.models import CountStats

from apps.gcd.models import Publisher, Series, Issue, StoryType, Image,\
                            IndiciaPublisher, Brand, BrandGroup, Cover,\
                            SeriesBond, Award, Creator, CreatorMembership,\
                            ReceivedAward, CreatorDegree, CreatorArtInfluence,\
                            CreatorRelation, CreatorSchool, CreatorNameDetail,\
                            CreatorNonComicWork, CreatorSignature, \
                            Feature, FeatureLogo, FeatureRelation, \
                            Printer, IndiciaPrinter, School, Story, \
                            Character, Group, Universe, StoryCredit, \
                            CharacterRelation, GroupRelation, GroupMembership
from apps.gcd.models.creator import FeatureCreatorTable, SeriesCreatorTable,\
                                    CharacterCreatorTable, GroupCreatorTable,\
                                    NAME_TYPES
from apps.gcd.models.character import CharacterTable
from apps.gcd.models.feature import FeatureTable
from apps.gcd.models.issue import IssueTable, BrandGroupIssueTable,\
                                  BrandEmblemIssueTable,\
                                  IndiciaPublisherIssueTable,\
                                  IssuePublisherTable, PublisherIssueTable
from apps.gcd.models.series import SeriesTable, CreatorSeriesTable
from apps.gcd.models.story import CREDIT_TYPES, CORE_TYPES, AD_TYPES, \
                                  StoryTable
from apps.gcd.views import paginate_response, ORDER_ALPHA, ORDER_CHRONO,\
                           ResponsePaginator
from apps.gcd.views.covers import get_image_tag, get_generic_image_tag, \
                                  get_image_tags_per_issue, \
                                  get_image_tags_per_page
from apps.gcd.models.cover import CoverIssuePublisherTable, \
                                  ZOOM_SMALL, ZOOM_MEDIUM, ZOOM_LARGE
from apps.gcd.forms import get_generic_select_form
from apps.oi import states
from apps.oi.models import IssueRevision, SeriesRevision, PublisherRevision, \
                           BrandGroupRevision, BrandRevision, CoverRevision, \
                           IndiciaPublisherRevision, ImageRevision, Changeset,\
                           SeriesBondRevision, CreatorRevision, CTYPES

KEY_DATE_REGEXP = \
  re.compile(r'^(?P<year>\d{4})\-(?P<month>\d{2})\-(?P<day>\d{2})$')

# TODO: Pull this from the DB somehow, but not on every page load.
MIN_GCD_YEAR = 1800

COVER_TABLE_WIDTH = 5
COVERS_PER_GALLERY_PAGE = 50

IS_EMPTY = '[IS_EMPTY]'
IS_NONE = '[IS_NONE]'

ISSUE_CHECKLIST_DISCLAIMER = 'In the checklist results for stories, covers, '\
                             'and cartoons are shown.'
COVER_CHECKLIST_DISCLAIMER = 'In the checklist results for covers are shown.'
MIGRATE_DISCLAIMER = ' Text credits are currently being migrated to '\
                     'links. Therefore not all credits in our '\
                     'database are shown here.'


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


def generic_sortable_list(request, items, table, template, context):
    paginator = ResponsePaginator(items, per_page=100, vars=context)
    page_number = paginator.paginate(request).number

    if 'sort' in request.GET:
        extra_string = 'sort=%s' % (request.GET['sort'])
    else:
        extra_string = ''

    RequestConfig(request, paginate={"paginator_class": LazyPaginator,
                                     'per_page': 100,
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
                                                 'tagged_items'}]
        fields.insert(0, 'id')
        if export_format == 'db_csv':
            return render_to_csv_response(items.values(*fields),
                                          append_datestamp=True)
        if export_format == 'db_json':
            data = list(items.values(*fields))
            return JsonResponse(data, safe=False)

    context['table'] = table
    # are using /search/list_header.html in the template
    context['extra_string'] = extra_string

    return render(request, template, context)


def _handle_date_picker(request, url_reverse,
                        show_date=None, monthly=False, kwargs={}):
    try:
        daily = not monthly
        if 'year' in request.GET:
            year = int(request.GET['year'])
            month = int(request.GET['month'])
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
                        kwargs=kwargs)), False
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
    return render(request, 'gcd/details/creator.html', vars)


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
        creator_names = list(_get_creator_names_for_checklist(creator))

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
        heading = 'Sequences for Creator %s in Series %s' % (creator,
                                                             series)
    elif creator_name:
        heading = 'Sequences for Name %s of Creator %s' % (creator,
                                                           creator.creator)
    elif signature:
        stories = stories.filter(credits__signature=signature,
                                 credits__deleted=False)
        heading = 'Sequences for Signature %s of Creator %s' % (signature,
                                                                creator)
    else:
        heading = 'Sequences for Creator %s' % (creator)

    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'sequence',
        'plural_suffix': 's',
        'heading': heading
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = StoryTable(stories, attrs={'class': 'sortable_listing'},
                       template_name='gcd/bits/sortable_table.html',
                       order_by=('issue'))
    return generic_sortable_list(request, stories, table, template, context)


def creator_characters(request, creator_id, country=None):
    creator = get_gcd_object(Creator, creator_id)
    names = list(_get_creator_names_for_checklist(creator))

    characters = Character.objects.filter(
      character_names__storycharacter__story__credits__creator__in=names,
      character_names__storycharacter__story__credits__deleted=False)\
        .distinct()

    characters = characters.annotate(issue_credits_count=Count(
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
        'heading': 'Characters for Creator %s' % (creator)
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = CharacterTable(characters, attrs={'class': 'sortable_listing'},
                           creator=creator,
                           template_name='gcd/bits/sortable_table.html',
                           order_by=('feature'))
    return generic_sortable_list(request, characters, table, template, context)


def creator_features(request, creator_id, country=None, language=None):
    creator = get_gcd_object(Creator, creator_id)
    names = list(_get_creator_names_for_checklist(creator))

    features = Feature.objects.filter(story__credits__creator__in=names,
                                      story__credits__deleted=False).distinct()
    if language:
        language = get_object_or_404(Language, code=language)
        features = features.filter(language=language)

    features = features.annotate(issue_credits_count=Count('story__issue',
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
        'heading': 'Features for Creator %s' % (creator)
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = FeatureTable(features, attrs={'class': 'sortable_listing'},
                         creator=creator,
                         template_name='gcd/bits/sortable_table.html',
                         order_by=('feature'))
    return generic_sortable_list(request, features, table, template, context)


def creator_issues(request, creator_id, series_id,
                   country=None, language=None):
    return checklist_by_id(request, creator_id, series_id=series_id,
                           country=country, language=language)


def creator_edited_issues(request, creator_id, series_id=None,
                          country=None, language=None):
    return checklist_by_id(request, creator_id, series_id=series_id,
                           country=country, language=language, edits=True)


def _get_creator_names_for_checklist(creator):
    creator_names = creator.creator_names.filter(deleted=False)
    if creator.official_creator_detail.type_id == NAME_TYPES['house']:
        house_names = creator.from_related_creator.filter(
            relation_type_id=4, creator_name__isnull=False)\
            .values_list('creator_name', flat=True)
        creator_names |= CreatorNameDetail.objects.filter(id__in=house_names)
    creator_names = creator_names.values_list('id', flat=True)
    return creator_names


def creator_series(request, creator_id, country=None, language=None):
    if '_export' in request.GET:
        if request.GET['_export'] in ['db_csv', 'db_json']:
            return render(request, 'indexer/error.html',
                          {'error_text':
                           'There is no raw export for these objects.'})
    creator = get_gcd_object(Creator, creator_id)
    names = list(_get_creator_names_for_checklist(creator))

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
        'heading': 'Series for Creator %s' % (creator)
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = CreatorSeriesTable(series, attrs={'class': 'sortable_listing'},
                               creator=creator,
                               template_name='gcd/bits/sortable_table.html',
                               order_by=('name'))
    return generic_sortable_list(request, series, table, template, context)


def checklist_by_id(request, creator_id, series_id=None, character_id=None,
                    feature_id=None, edits=False, country=None, language=None):
    """
    Provides checklists for a Creator. These include results for all
    CreatorNames and for the overall House Name all uses of that House Name.
    """
    creator = get_gcd_object(Creator, creator_id)
    creator_names = list(_get_creator_names_for_checklist(creator))

    if edits:
        issues = Issue.objects.filter(credits__creator__in=creator_names,
                                      credits__deleted=False)\
                              .distinct().select_related('series__publisher')
    else:
        issues = Issue.objects.filter(story__credits__creator__in=creator_names,
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
        heading = 'Issues for Creator %s in Series %s' % (creator,
                                                          series)
    elif character_id:
        character = get_gcd_object(Character, character_id)
        issues = issues.filter(
          story__appearing_characters__character__character=character,
          story__appearing_characters__deleted=False)
        heading = 'Issues for Creator %s for Character %s' % (creator,
                                                              character)
    elif feature_id:
        feature = get_gcd_object(Feature, feature_id)
        issues = issues.filter(story__credits__creator__creator=creator,
                               story__feature_object=feature)
        heading = 'Issues for Creator %s on Feature %s' % (creator,
                                                           feature)
    elif edits:
        heading = 'Issue Edit List for Creator %s' % (creator)
    else:
        heading = 'Issue Checklist for Creator %s' % (creator)

    context = {
        'result_disclaimer': ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER,
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': heading
    }
    if edits:
        context['result_disclaimer'] = MIGRATE_DISCLAIMER
    template = 'gcd/search/issue_list_sortable.html'
    table = IssuePublisherTable(issues, attrs={'class': 'sortable_listing'},
                                template_name='gcd/bits/sortable_table.html',
                                order_by=('publication_date'))
    return generic_sortable_list(request, issues, table, template, context)


def cover_checklist_by_id(request, creator_id, series_id=None,
                          country=None, language=None):
    creator = get_gcd_object(Creator, creator_id)
    creator_names = list(_get_creator_names_for_checklist(creator))
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
        heading = 'Covers from Creator %s in Series %s' % (creator,
                                                           series)
    else:
        heading = 'Cover Checklist for Creator %s' % (creator)

    context = {
        'result_disclaimer': COVER_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER,
        'item_name': 'cover',
        'plural_suffix': 's',
        'heading': heading
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = CoverIssuePublisherTable(
      issues,
      attrs={'class': 'sortable_listing'},
      template_name='gcd/bits/sortable_table.html',
      order_by=('publication_date'))
    return generic_sortable_list(request, issues, table, template, context)


def checklist_by_name(request, creator, country=None, language=None,
                      to_be_migrated=False):
    creator = creator.replace('+', ' ').title()
    context = {
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'Issue Checklist for Creator ' + creator,
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
    issues = Issue.objects.filter(q_objs_text).distinct()\
                          .annotate(series_name=F('series__sort_name'))
    if 'sort' in request.GET:
        if request.GET['sort'] in ['issue', '-issue']:
            issues = issues.annotate(series__year_began=F(
                                     'series__year_began'))\
                           .annotate(series__id=F('series__id'))
        elif request.GET['sort'] in ['publisher', '-publisher']:
            issues = issues.annotate(publisher_name=F(
                                     'series__publisher__name'))
    creator = Creator.objects.filter(gcd_official_name__iexact=creator)
    if creator and not to_be_migrated:
        q_objs_credits = Q(**{'%scredits__creator__creator__in' % (prefix): creator,
                              '%stype__id__in' % (prefix): CORE_TYPES})
        items2 = Issue.objects.filter(q_objs_credits).distinct()\
                              .annotate(series_name=F('series__sort_name'))
        if 'sort' in request.GET:
            if request.GET['sort'] in ['issue', '-issue']:
                items2 = items2.annotate(
                  series__year_began=F('series__year_began')).annotate(
                  series__id=F('series__id'))
            elif request.GET['sort'] in ['publisher', '-publisher']:
                items2 = items2.annotate(
                  publisher_name=F('series__publisher__name'))
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
        issues = issues.union(items2)
    template = 'gcd/search/issue_list_sortable.html'
    table = IssuePublisherTable(issues, attrs={'class': 'sortable_listing'},
                                template_name='gcd/bits/sortable_table.html',
                                order_by=('publication_date'))
    return generic_sortable_list(request, issues, table, template, context)


def creator_name_checklist(request, creator_name_id, character_id=None,
                           group_id=None, feature_id=None, series_id=None,
                           country=None, language=None):
    """
    Provides checklists for a CreatorNameDetail.
    """
    creator = get_gcd_object(CreatorNameDetail, creator_name_id)

    issues = Issue.objects.filter(story__credits__creator=creator,
                                  story__type__id__in=CORE_TYPES,
                                  story__credits__deleted=False).distinct()\
                          .select_related('series__publisher')
    if character_id:
        character = get_gcd_object(Character, character_id)
        issues = issues.filter(
          story__appearing_characters__character__character=character,
          story__appearing_characters__deleted=False)
        heading_addon = 'Character %s' % (character)
    if group_id:
        group = get_gcd_object(Group, group_id)
        issues = issues.filter(
          story__appearing_characters__group=group,
          story__appearing_characters__deleted=False)
        heading_addon = 'Group %s' % (group)
    if feature_id:
        feature = get_gcd_object(Feature, feature_id)
        issues = issues.filter(story__credits__creator=creator,
                               story__feature_object=feature)
        heading_addon = 'Feature %s' % (feature)
    if series_id:
        series = get_gcd_object(Series, series_id)
        issues = issues.filter(story__credits__creator=creator,
                               story__issue__series=series)
        heading_addon = '%s' % (series)
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
        'heading': 'Issue Checklist for Creator %s and %s' % (creator,
                                                              heading_addon)
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = IssueTable(issues, attrs={'class': 'sortable_listing'},
                       template_name='gcd/bits/sortable_table.html',
                       order_by=('publication_date'))
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
                             'gcd/details/award.html',
                             vars)


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

    context = {'publisher': publisher,
               'current': publisher.series_set.filter(deleted=False,
                                                      is_current=True),
               'error_subject': publisher,
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
                        template_name='gcd/bits/sortable_table.html',
                        order_by=('name'))
    RequestConfig(request, paginate={'per_page': 100,
                                     'page': page_number}).configure(table)
    context['table'] = table
    context['extra_string'] = extra_string

    return generic_sortable_list(request, publisher_series, table,
                                 'gcd/details/publisher.html', context)


def show_publisher_issues(request, publisher_id):
    publisher = get_gcd_object(Publisher, publisher_id)
    issues = Issue.objects.filter(series__publisher=publisher,
                                  deleted=False).order_by(
      'series__sort_name', 'sort_code').prefetch_related('series', 'brand',
                                                         'indicia_publisher')
    context = {'object': publisher,
               'description': 'showing all issues'
               }

    table = PublisherIssueTable(
      issues, attrs={'class': 'sortable_listing'},
      template_name='gcd/bits/sortable_table.html', order_by=('issues'))
    return generic_sortable_list(request, issues, table,
                                 'gcd/bits/generic_list.html', context)


def show_publisher_current_series(request, publisher_id):
    publisher = get_gcd_object(Publisher, publisher_id)
    current_series = publisher.active_series().filter(deleted=False,
                                                      is_current=True)

    context = {'object': publisher,
               'description': 'showing current series'
               }
    table = SeriesTable(current_series, attrs={'class': 'sortable_listing'},
                        template_name='gcd/bits/sortable_table.html',
                        order_by=('name'))
    return generic_sortable_list(request, current_series, table,
                                 'gcd/bits/generic_list.html', context)


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

    table_width = COVER_TABLE_WIDTH

    covers = Cover.objects.filter(issue__series__publisher=publisher,
                                  deleted=False).select_related('issue')
    if use_on_sale:
        covers = \
          covers.filter(issue__on_sale_date__gte='%d-%02d-50' % (year,
                                                                 month-1),
                        issue__on_sale_date__lte='%d-%02d-32' % (year,
                                                                 month))\
                .order_by('issue__on_sale_date', 'issue__series')
    else:
        covers = \
          covers.filter(issue__key_date__gte='%d-%02d-50' % (year, month-1),
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
      'monthly': True,
      'years': range(date.today().year,
                     (publisher.year_began or 1900) - 1,
                     -1),
      'choose_url': choose_url,
      'choose_url_after': choose_url_after,
      'choose_url_before': choose_url_before,
      'use_on_sale': use_on_sale,
      'table_width': table_width,
      'RANDOM_IMAGE': _publisher_image_content(publisher.id)
    }

    return paginate_response(
      request, covers, 'gcd/details/publisher_monthly_covers.html', vars,
      per_page=COVERS_PER_GALLERY_PAGE,
      callback_key='tags', callback=get_image_tags_per_page)


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
    context = {'indicia_publisher': indicia_publisher,
               'error_subject': '%s' % indicia_publisher,
               'preview': preview}

    table = IndiciaPublisherIssueTable(
      indicia_publisher_issues, attrs={'class': 'sortable_listing'},
      template_name='gcd/bits/sortable_table.html', order_by=('issues'))
    return generic_sortable_list(request, indicia_publisher_issues, table,
                                 'gcd/details/indicia_publisher.html', context)


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

    brand_emblems = brand_group.active_emblems()

    context = {'brand': brand_group,
               'brand_emblems': brand_emblems,
               'error_subject': '%s' % brand_group,
               'preview': preview
               }

    table = BrandGroupIssueTable(
      brand_issues, attrs={'class': 'sortable_listing'}, brand=brand_group,
      template_name='gcd/bits/sortable_table.html', order_by=('issues'))
    return generic_sortable_list(request, brand_issues, table,
                                 'gcd/details/brand_group.html', context)


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
    uses = brand.in_use.all()
    context = {'brand': brand,
               'uses': uses,
               'error_subject': '%s' % brand,
               'preview': preview
               }

    table = BrandEmblemIssueTable(
      brand_issues, attrs={'class': 'sortable_listing'},
      template_name='gcd/bits/sortable_table.html', order_by=('issues'))
    return generic_sortable_list(request, brand_issues, table,
                                 'gcd/details/brand.html', context)


def imprint(request, imprint_id):
    """
    Redirect to the change history page for an Imprint, which all are deleted.
    """
    get_object_or_404(Publisher, id=imprint_id, deleted=True)

    return HttpResponseRedirect(
      urlresolvers.reverse('change_history',
                           kwargs={'model_name': 'imprint', 'id': imprint_id}))


def brands(request, publisher_id):
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

    sort = ORDER_ALPHA
    if 'sort' in request.GET:
        sort = request.GET['sort']

    if (sort == ORDER_CHRONO):
        brands = brands.order_by('year_began', 'name')
    else:
        brands = brands.order_by('name', 'year_began')

    return paginate_response(request, brands, 'gcd/details/brands.html', {
      'publisher': publisher,
      'error_subject': '%s brands' % publisher,
    })


def brand_uses(request, publisher_id):
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

    sort = ORDER_ALPHA
    if 'sort' in request.GET:
        sort = request.GET['sort']

    if (sort == ORDER_CHRONO):
        brand_uses = brand_uses.order_by('year_began', 'emblem__name')
    else:
        brand_uses = brand_uses.order_by('emblem__name', 'year_began')

    return paginate_response(
      request, brand_uses,
      'gcd/details/brand_uses.html', {
        'publisher': publisher,
        'error_subject': '%s brands' % publisher,
      })


def indicia_publishers(request, publisher_id):
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

    sort = ORDER_ALPHA
    if 'sort' in request.GET:
        sort = request.GET['sort']

    if (sort == ORDER_CHRONO):
        indicia_publishers = indicia_publishers.order_by('year_began', 'name')
    else:
        indicia_publishers = indicia_publishers.order_by('name', 'year_began')

    return paginate_response(
      request, indicia_publishers,
      'gcd/details/indicia_publishers.html',
      {
        'publisher': publisher,
        'error_subject': '%s indicia publishers' % publisher,
      })


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
    return render(request, 'gcd/details/printer.html', vars)


def printer_issues(request, printer_id):
    printer = get_gcd_object(Printer, printer_id)

    issues = Issue.objects.filter(indicia_printer__parent=printer,
                                  deleted=False).distinct()\
                          .select_related('series__publisher')

    context = {
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'Issue List for Printer %s' % (printer)
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = IssueTable(issues, attrs={'class': 'sortable_listing'},
                       template_name='gcd/bits/sortable_table.html',
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
    return render(request, 'gcd/details/indicia_printer.html', context)


def indicia_printer_issues(request, indicia_printer_id):
    indicia_printer = get_gcd_object(IndiciaPrinter, indicia_printer_id)

    issues = Issue.objects.filter(indicia_printer=indicia_printer,
                                  deleted=False).distinct()\
                          .select_related('series__publisher')

    context = {
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'Issue List for Indicia Printer %s' % (indicia_printer)
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = IssueTable(issues, attrs={'class': 'sortable_listing'},
                       template_name='gcd/bits/sortable_table.html',
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
        issue_status_width = "status_wide"
    else:
        issue_status_width = "status_small"

    if series.has_issue_title:
        cover_status_width = "status_wide"
    elif series.active_issues().exclude(variant_name='').count():
        cover_status_width = "status_medium"
    else:
        cover_status_width = "status_small"

    images = series.active_issues().filter(variant_of=None)\
                   .annotate(num_scans=Sum('image_resources__type__id'))\
                   .order_by('sort_code')

    return render(
      request, 'gcd/details/series.html',
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

    return render(
      request, 'gcd/details/series_details.html',
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


def series_creatorlist(request, series_id):
    series = get_gcd_object(Series, series_id)

    creators = CreatorNameDetail.objects.all()
    creators = creators.filter(storycredit__story__issue__series=series,
                               storycredit__story__type__id__in=CORE_TYPES,
                               storycredit__deleted=False).distinct()\
                       .select_related('creator')

    creators = creators.annotate(
      first_credit=Min('storycredit__story__issue__key_date'))
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
      credits_count=Count('storycredit__story__issue', distinct=True),
      script=script,
      pencils=pencils,
      inks=inks,
      colors=colors,
      letters=letters)

    context = {
        'result_disclaimer': ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER,
        'item_name': 'creator',
        'plural_suffix': 's',
        'heading': 'Creators Working on %s' % (series)
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = SeriesCreatorTable(creators, attrs={'class': 'sortable_listing'},
                               series=series,
                               template_name='gcd/bits/sortable_table.html',
                               order_by=('creator__sort_name'))
    return generic_sortable_list(request, creators, table, template, context)


def series_issues_to_migrate(request, series_id):
    series = get_gcd_object(Series, series_id)
    issues = series.issues_to_migrate

    context = {
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'Issues with Text Credits to Migrate for %s' % (series)
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = IssueTable(issues, attrs={'class': 'sortable_listing'},
                       template_name='gcd/bits/sortable_table.html')
    return generic_sortable_list(request, issues, table, template, context)


def keyword(request, keyword, model_name='story'):
    """
    Display the objects associated to a keyword.
    """
    from apps.oi.views import DISPLAY_CLASSES
    if model_name not in ['story', 'issue']:
        return render(
            request, 'indexer/error.html',
            {'error_text':
             'There are no keyword-lists for these objects.'})

    objs = DISPLAY_CLASSES[model_name].objects.filter(keywords__name=keyword,
                                                      deleted=False)
    if model_name == 'story':
        table = StoryTable(objs, attrs={'class': 'sortable_listing'},
                           template_name='gcd/bits/sortable_table.html',
                           order_by=('name'))
        description = 'showing %d stories for keyword' % objs.count()
    elif model_name == 'issue':
        table = IssuePublisherTable(
          objs, attrs={'class': 'sortable_listing'},
          template_name='gcd/bits/sortable_table.html',
          order_by=('name'))
        description = 'showing %d issues for keyword' % objs.count()
    context = {'object': keyword,
               'description': description
               }
    return generic_sortable_list(request, objs, table,
                                 'gcd/bits/generic_list.html', context)


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


def on_sale_weekly(request, year=None, week=None):
    issues_on_sale, vars = do_on_sale_weekly(request, year, week)
    if vars is None:
        # MYCOMICS
        return issues_on_sale

    table = IssuePublisherTable(
      issues_on_sale, attrs={'class': 'sortable_listing'},
      template_name='gcd/bits/sortable_table.html', order_by=('issues'))
    return generic_sortable_list(request, issues_on_sale, table,
                                 'gcd/status/issues_on_sale.html', vars)

    return paginate_response(request, issues_on_sale,
                             'gcd/status/issues_on_sale.html', vars)


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
    heading = "Issues on-sale in %s" % (start_date.strftime('%B %Y'))
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
        'query_string': urlencode(query_val),
        'date': start_date,
    }
    return issues_on_sale, vars


def on_sale_monthly(request, year=None, month=None):
    issues_on_sale, vars = do_on_sale_monthly(request, year, month)
    if vars is None:
        return issues_on_sale

    table = IssuePublisherTable(
      issues_on_sale, attrs={'class': 'sortable_listing'},
      template_name='gcd/bits/sortable_table.html', order_by=('issues'))
    return generic_sortable_list(request, issues_on_sale, table,
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
    logos = feature.active_logos().order_by(
      'year_began', 'name')

    vars = {'feature': feature,
            'error_subject': '%s' % feature,
            'preview': preview}
    return paginate_response(request,
                             logos,
                             'gcd/details/feature.html',
                             vars)


def feature_sequences(request, feature_id, country=None):
    feature = get_gcd_object(Feature, feature_id)
    stories = Story.objects.filter(feature_object=feature,
                                   deleted=False).distinct()\
                           .select_related('issue__series__publisher')
    if country:
        country = get_object_or_404(Country, code=country)
        stories = stories.filter(issue__series__country=country)
    heading = 'Sequences for Feature %s' % (feature)

    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'sequence',
        'plural_suffix': 's',
        'heading': heading
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = StoryTable(stories, attrs={'class': 'sortable_listing'},
                       template_name='gcd/bits/sortable_table.html',
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

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'Issue List for Feature %s' % (feature)
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = IssueTable(issues, attrs={'class': 'sortable_listing'},
                       template_name='gcd/bits/sortable_table.html',
                       order_by=('publication_date'))
    return generic_sortable_list(request, issues, table, template, context)


def feature_creatorlist(request, feature_id):
    feature = get_gcd_object(Feature, feature_id)

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

    creators = creators.annotate(
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
      credits_count=Count('storycredit__story__issue', distinct=True),
      script=script,
      pencils=pencils,
      inks=inks,
      colors=colors,
      letters=letters)

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'creator',
        'plural_suffix': 's',
        'heading': 'Creators Working on Feature %s' % (feature)
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = FeatureCreatorTable(creators, attrs={'class': 'sortable_listing'},
                                feature=feature,
                                template_name='gcd/bits/sortable_table.html',
                                order_by=('creator__sort_name'))
    return generic_sortable_list(request, creators, table, template, context)


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
    heading = 'Sequences for Feature Logo %s' % (feature_logo)

    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'sequence',
        'plural_suffix': 's',
        'heading': heading
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = StoryTable(stories, attrs={'class': 'sortable_listing'},
                       template_name='gcd/bits/sortable_table.html',
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
        'heading': 'Issue List for Feature Logo %s' % (feature_logo)
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = IssueTable(issues, attrs={'class': 'sortable_listing'},
                       template_name='gcd/bits/sortable_table.html',
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


def universe(request, universe_id):
    """
    Display the details page for a Universe.
    """
    universe = get_gcd_object(Universe, universe_id)
    return show_universe(request, universe)


def show_universe(request, universe, preview=False):
    vars = {'universe': universe,
            'error_subject': '%s' % feature,
            'preview': preview}
    return render(request, 'gcd/details/universe.html', vars)


def character(request, character_id):
    """
    Display the details page for a Character.
    """
    character = get_gcd_object(Character, character_id)
    return show_character(request, character)


def show_character(request, character, preview=False):
    vars = {'character': character,
            'additional_names': character.active_names()
                                         .filter(is_official_name=False),
            'error_subject': '%s' % character,
            'preview': preview}
    return render(request, 'gcd/details/character.html', vars)


def character_issues(request, character_id, layer=None):
    character = get_gcd_object(Character, character_id)

    issues = Issue.objects.filter(
      story__appearing_characters__character__character=character,
      story__appearing_characters__deleted=False,
      story__type__id__in=CORE_TYPES,
      story__deleted=False).distinct().select_related('series__publisher')
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
    if layer == 1 and character.active_generalisations().exists():
        characters = character.active_generalisations()\
                              .values_list('from_character_id', flat=True)
        issues |= Issue.objects.filter(
            story__appearing_characters__character__character_id__in=list(
              characters),
            story__appearing_characters__deleted=False,
            story__type__id__in=CORE_TYPES,
            story__deleted=False).distinct()\
                                 .select_related('series__publisher')
    result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'Issue List for Character %s' % (character)
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = IssueTable(issues, attrs={'class': 'sortable_listing'},
                       template_name='gcd/bits/sortable_table.html',
                       order_by=('publication_date'))
    return generic_sortable_list(request, issues, table, template, context)


def character_creators(request, character_id):
    character = get_gcd_object(Character, character_id)

    creators = CreatorNameDetail.objects.all()
    creators = creators.filter(
      storycredit__story__appearing_characters__character__character=character,
      storycredit__story__appearing_characters__deleted=False,
      storycredit__story__type__id__in=CORE_TYPES,
      storycredit__deleted=False).distinct().select_related('creator')
    result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER

    creators = creators.annotate(
      first_credit=Min('storycredit__story__issue__key_date'))
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
      credits_count=Count('storycredit__story__issue', distinct=True),
      script=script,
      pencils=pencils,
      inks=inks,
      colors=colors,
      letters=letters)

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'creator',
        'plural_suffix': 's',
        'heading': 'Creators Working on Character %s' % (character)
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = CharacterCreatorTable(creators, attrs={'class':
                                                   'sortable_listing'},
                                  character=character,
                                  template_name='gcd/bits/sortable_table.html',
                                  order_by=('creator__sort_name'))
    return generic_sortable_list(request, creators, table, template, context)


def character_sequences(request, character_id, country=None):
    character = get_gcd_object(Character, character_id)
    stories = Story.objects.filter(
      appearing_characters__character__character=character,
      appearing_characters__deleted=False,
      deleted=False).distinct().select_related('issue__series__publisher')
    if country:
        country = get_object_or_404(Country, code=country)
        stories = stories.filter(issue__series__country=country)
    heading = 'Sequences for Character %s' % (character)

    context = {
        'result_disclaimer': MIGRATE_DISCLAIMER,
        'item_name': 'sequence',
        'plural_suffix': 's',
        'heading': heading
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = StoryTable(stories, attrs={'class': 'sortable_listing'},
                       template_name='gcd/bits/sortable_table.html',
                       order_by=('issue'))
    return generic_sortable_list(request, stories, table, template, context)


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
    vars = {'group': group,
            'error_subject': '%s' % group,
            'preview': preview}
    return render(request, 'gcd/details/group.html', vars)


def group_issues(request, group_id):
    group = get_gcd_object(Group, group_id)

    issues = Issue.objects.filter(
      story__appearing_characters__group=group,
      story__appearing_characters__deleted=False,
      story__type__id__in=CORE_TYPES,
      story__deleted=False).distinct().select_related('series__publisher')
    result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'Issue List for Group %s' % (group)
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = IssueTable(issues, attrs={'class': 'sortable_listing'},
                       template_name='gcd/bits/sortable_table.html',
                       order_by=('publication_date'))
    return generic_sortable_list(request, issues, table, template, context)


def group_creators(request, group_id):
    group = get_gcd_object(Group, group_id)

    creators = CreatorNameDetail.objects.all()
    creators = creators.filter(
      storycredit__story__appearing_characters__group=group,
      storycredit__story__appearing_characters__deleted=False,
      storycredit__story__type__id__in=CORE_TYPES,
      storycredit__deleted=False).distinct().select_related('creator')
    result_disclaimer = ISSUE_CHECKLIST_DISCLAIMER + MIGRATE_DISCLAIMER

    creators = creators.annotate(
      first_credit=Min('storycredit__story__issue__key_date'))
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
      credits_count=Count('storycredit__story__issue', distinct=True),
      script=script,
      pencils=pencils,
      inks=inks,
      colors=colors,
      letters=letters)

    context = {
        'result_disclaimer': result_disclaimer,
        'item_name': 'creator',
        'plural_suffix': 's',
        'heading': 'Creators Working on Group %s' % (group)
    }
    template = 'gcd/search/issue_list_sortable.html'
    table = GroupCreatorTable(creators, attrs={'class':
                                               'sortable_listing'},
                              group=group,
                              template_name='gcd/bits/sortable_table.html',
                              order_by=('creator__sort_name'))
    return generic_sortable_list(request, creators, table, template, context)


def group_sequences(request, group_id, country=None):
    group = get_gcd_object(Group, group_id)
    stories = Story.objects.filter(
      appearing_characters__group=group,
      appearing_characters__deleted=False,
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
    template = 'gcd/search/issue_list_sortable.html'
    table = StoryTable(stories, attrs={'class': 'sortable_listing'},
                       template_name='gcd/bits/sortable_table.html',
                       order_by=('issue'))
    return generic_sortable_list(request, stories, table, template, context)


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
    cover_page = covers.count()/COVERS_PER_GALLERY_PAGE + 1

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


def covers(request, series_id):
    """
    Display the cover gallery for a series.
    """

    series = get_gcd_object(Series, series_id)
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

    return paginate_response(
      request, covers, 'gcd/details/covers.html', vars,
      per_page=COVERS_PER_GALLERY_PAGE, callback_key='tags',
      callback=lambda page: get_image_tags_per_page(page, series))


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
        cover_page = covers.count()/COVERS_PER_GALLERY_PAGE + 1

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
            oi_indexers.append(i.indexer)

    res = IssueRevision.objects.filter(issue=issue)\
                               .select_related('changeset__indexer__indexer')
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
