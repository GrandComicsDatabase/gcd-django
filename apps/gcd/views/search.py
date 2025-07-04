# -*- coding: utf-8 -*-
"""
View methods related to displaying search and search results pages.
"""

from re import match, split, sub
from urllib.parse import urlencode, parse_qsl
from decimal import Decimal
from haystack.backends import SQ
from stdnum import isbn as stdisbn
from random import randint

from django.db.models import Q, Count, Min, Case, When, Value, F
from django.conf import settings
from django.http import HttpResponseRedirect
import django.urls as urlresolvers
from django.shortcuts import render
from django.utils.safestring import mark_safe
from urllib.parse import quote, unquote_plus

from djqscsv import render_to_csv_response
from haystack.query import SearchQuerySet

from apps.gcd.views.search_haystack import GcdNameQuery

from apps.stddata.models import Country, Language

from apps.indexer.models import Indexer
from apps.indexer.views import ViewTerminationError, render_error

from apps.gcd.models import Publisher, Series, Issue, Cover, Story, \
                            StoryType, STORY_TYPES, CREDIT_TYPES, \
                            BrandGroup, Brand, IndiciaPublisher, Feature, \
                            Creator, CreatorMembership, \
                            CreatorArtInfluence, CreatorNonComicWork, \
                            CreatorNameDetail, SeriesPublicationType, \
                            Award, ReceivedAward, Character, Group, Universe, \
                            Printer
from apps.gcd.models.character import CharacterSearchTable
from apps.gcd.models.cover import CoverIssuePublisherEditTable
from apps.gcd.models.creator import CreatorSearchTable
from apps.gcd.models.feature import FeatureSearchTable
from apps.gcd.models.issue import INDEXED, IssuePublisherTable, \
                                  BarcodePublisherIssueTable, \
                                  ISBNPublisherIssueTable
from apps.gcd.models.publisher import PublisherSearchTable, \
                                      BrandGroupSearchTable, \
                                      BrandEmblemSearchTable, \
                                      IndiciaPublisherSearchTable, \
                                      PrinterSearchTable
from apps.gcd.models.story import StoryTable, MatchedSearchStoryTable, \
                                  HaystackMatchedStoryTable, HaystackStoryTable
from apps.gcd.models.series import SeriesPublisherTable
from apps.gcd.views import paginate_response, ORDER_ALPHA, ORDER_CHRONO
from apps.gcd.forms.search import AdvancedSearch, \
                                  PAGE_RANGE_REGEXP, COUNT_RANGE_REGEXP
from apps.gcd.views.details import issue, IS_EMPTY, \
                                   IS_NONE, generic_sortable_list, \
                                   TW_SORT_TABLE_TEMPLATE, \
                                   TW_SORT_GRID_TEMPLATE

from apps.select.views import filter_sequences, filter_issues, \
                              filter_haystack, filter_publisher, \
                              filter_series, FilterForLanguage
# Should not be importing anything from oi, but we're doing this
# in several places.
# TODO: states should probably live somewhere else.
from apps.oi import states
from functools import reduce


class SearchError(Exception):
    pass


def generic_by_name(request, name, q_obj, sort,
                    class_=Story,
                    template='gcd/search/content_list.html',
                    include_template='',
                    credit=None,
                    related=[],
                    sqs=None,
                    things=None,
                    selected=None,
                    table_inline=False):
    """
    Helper function for the most common search cases.
    """
    base_name = 'unknown'
    plural_suffix = 's'
    query_val = {'method': 'icontains', 'logic': True}
    heading = "matching your query for '%s'" % (name,)
    display_name = class_.__name__
    base_name = display_name.lower()
    item_name = display_name.lower()
    if (class_ in (Series, BrandGroup, Brand, IndiciaPublisher, Publisher,
                   Printer)):
        if class_ is Brand:
            display_name = "Publisher's Brand Emblem"
            base_name = 'brand_emblem'
        elif class_ is BrandGroup:
            display_name = "Publisher's Brand Group"
            base_name = 'brand_group'
        elif class_ is IndiciaPublisher:
            base_name = 'indicia_publisher'
            display_name = 'Indicia / Colophon Publisher'
        else:
            display_name = class_.__name__
            base_name = display_name.lower()
        item_name = display_name.lower()

        if class_ is Brand:
            selected = 'brand'
        else:
            selected = base_name

        plural_suffix = '' if class_ is Series else 's'
        sort_name = "sort_name" if class_ is Series else "name"
        if sqs is None:
            context = {'item_name': item_name,
                       'plural_suffix': plural_suffix,
                       'selected': base_name,
                       'search_term': name,
                       'heading': heading}

            if things is None:
                things = class_.objects.exclude(deleted=True).filter(q_obj)
            if related:
                things = things.select_related(*related)
            things = things.distinct()

            if sort == ORDER_CHRONO:
                order_by = 'year_began'
            else:
                order_by = 'name'

            if class_ is Publisher:
                table_format = PublisherSearchTable
            elif class_ is Brand:
                table_format = BrandEmblemSearchTable
                context['selected'] = 'brand'
            elif class_ is BrandGroup:
                table_format = BrandGroupSearchTable
            elif class_ is IndiciaPublisher:
                table_format = IndiciaPublisherSearchTable
            elif class_ is Series:
                table_format = SeriesPublisherTable
                if things:
                    filter = filter_series(request, things)
                    things = filter.qs
                    context['filter_form'] = filter.form
            elif class_ is Printer:
                table_format = PrinterSearchTable

            if class_ in [Publisher, IndiciaPublisher, Printer]:
                if things:
                    filter = filter_publisher(request, things)
                    things = filter.qs
                    context['filter_form'] = filter.form

            table = table_format(
              things,
              template_name='gcd/bits/tw_sortable_table.html',
              order_by=(order_by))
            template = 'gcd/search/tw_list_sortable.html'
            if table_inline:
                template = 'gcd/bits/tw_render_table.html'
                table.no_export = True
                table.orderable = False

            return generic_sortable_list(request, things, table, template,
                                         context)

        else:
            things = sqs
            if sort == ORDER_CHRONO:
                things = things.order_by('year',
                                         'sort_name')
            else:
                things = things.order_by('sort_name',
                                         'year')

        # query_string for the link to the advanced search
        query_val['target'] = base_name
        if class_ is Publisher:
            query_val['pub_name'] = name
        else:
            query_val[base_name] = name

    elif class_ in [Award, ]:
        if sqs is None:
            things = class_.objects.exclude(deleted=True).filter(q_obj)
            things = things.order_by("name")
            things = things.distinct()
        else:
            things = sqs
            things = things.order_by('sort_name')
        selected = base_name

        heading = '%s Search Results' % display_name
    elif class_ in [Creator, Character, Group, Feature]:
        context = {'item_name': item_name,
                   'plural_suffix': plural_suffix,
                   'selected': base_name,
                   'search_term': name,
                   'heading': heading}
        if things is None:
            things = class_.objects.exclude(deleted=True).filter(q_obj)
        if related:
            things = things.select_related(*related)
        things = things.distinct()
        if class_ == Feature:
            things = things.annotate(issue_count=Count(
                    'story__issue',
                    filter=Q(story__deleted=False),
                    distinct=True))
            order_by = 'name'
            if sort == ORDER_CHRONO:
                order_by = 'year_first_published'
            filter = FilterForLanguage(request.GET, things,
                                       language='language')
            things = filter.qs
            context['filter_form'] = filter.form

            table = FeatureSearchTable(
                things,
                template_name='gcd/bits/tw_sortable_table.html',
                order_by=(order_by))
        elif class_ == Character:
            order_by = 'name'
            if (sort == ORDER_CHRONO):
                order_by = 'year_first_published'
            things = things.distinct()
            things = things.annotate(issue_count=Count(
                'character_names__storycharacter__story__issue',
                filter=Q(character_names__storycharacter__deleted=False),
                distinct=True))
            filter = FilterForLanguage(request.GET, things,
                                       language='language')
            things = filter.qs
            context['filter_form'] = filter.form
            table = CharacterSearchTable(
                things,
                template_name='gcd/bits/tw_sortable_table.html',
                order_by=(order_by))
        elif class_ == Group:
            order_by = 'name'
            if (sort == ORDER_CHRONO):
                order_by = 'year_first_published'
            things = things.distinct()
            things = things.annotate(issue_count=Count(
                'group_names__storycharacter__story__issue', distinct=True))
            filter = FilterForLanguage(request.GET, things,
                                       language='language')
            things = filter.qs
            context['filter_form'] = filter.form

            table = CharacterSearchTable(
                things,
                template_name='gcd/bits/tw_sortable_table.html',
                order_by=(order_by),
                group=True)
        elif class_ == Creator:
            order_by = 'creator'
            if (sort == ORDER_CHRONO):
                order_by = 'date_of_birth'
            things = things.distinct()
            things = things.annotate(
                first_credit=Min(Case(When(
                  creator_names__storycredit__story__issue__key_date='',
                  then=Value('9999-99-99'),
                ),
                  default=F(
                    'creator_names__storycredit__story__issue__key_date'))))
            things = things.annotate(issue_count=Count(
                'creator_names__storycredit__story__issue',
                distinct=True))
            table = CreatorSearchTable(
                things,
                template_name='gcd/bits/tw_sortable_table.html',
                order_by=(order_by))
        template = 'gcd/search/tw_list_sortable.html'
        if table_inline:
            template = 'gcd/bits/tw_render_table.html'
            table.no_export = True
            table.orderable = False
        return generic_sortable_list(request, things, table, template,
                                     context)
    elif class_ in [Universe,]:
        if sqs is None:
            sort_name = "name"
            sort_year = "year_first_published"
            if things is None:
                things = class_.objects.exclude(deleted=True).filter(q_obj)
            if related:
                things = things.select_related(*related)
            if sort == ORDER_CHRONO:
                things = things.order_by(sort_year, sort_name)
            else:
                things = things.order_by(sort_name, sort_year)
            things = things.distinct()
        else:
            sort_year = "year"
            things = sqs
            if sort == ORDER_CHRONO:
                things = things.order_by(sort_year,
                                         'sort_name')
            else:
                things = things.order_by('sort_name',
                                         sort_year)

        display_name = class_.__name__
        base_name = display_name.lower()
        item_name = display_name.lower()
        selected = base_name

        heading = '%s Search Results' % display_name
        # query_string for the link to the advanced search
        query_val['target'] = base_name
        query_val[base_name] = name

    elif (class_ in (CreatorMembership, ReceivedAward, CreatorArtInfluence,
                     CreatorNonComicWork)):
        if sqs is None:
            sort_year = "creator__birth_date__year"

            if class_ is CreatorMembership:
                sort_name = "organization_name"
            elif class_ is ReceivedAward:
                sort_name = "award_name"
            elif class_ is CreatorArtInfluence:
                sort_name = "influence_name"
            elif class_ is CreatorNonComicWork:
                sort_name = "publication_title"

            things = class_.objects.exclude(deleted=True).filter(q_obj)
            if related:
                things = things.select_related(*related)
            if (sort == ORDER_CHRONO):
                things = things.order_by(sort_year, sort_name)
            else:
                things = things.order_by(sort_name, sort_year)
            things = things.distinct()
        else:
            sort_name = "name"
            things = sqs
            if class_ != ReceivedAward:
                things = things.order_by('sort_name')
            else:
                sort_year = 'year'
                if sort == ORDER_CHRONO:
                    things = things.order_by(sort_year,
                                             sort_name)
                else:
                    things = things.order_by(sort_name,
                                             sort_year)

        display_name = class_.__name__
        base_name = display_name.lower()
        item_name = display_name.lower()

        heading = '%s Search Results' % display_name
        # query_string for the link to the advanced search
        query_val['target'] = base_name
        query_val[base_name] = name

    elif class_ is Issue:
        item_name = 'issue'
        if things is None:
            things = Issue.objects.exclude(deleted=True).filter(q_obj) \
                          .select_related('series__publisher')
        heading = "matching your query for '%s' in %s" % (name, credit)
        # query_string for the link to the advanced search
        query_val['target'] = 'issue'
        if credit == 'isbn':
            query_val['isbn'] = name
            selected = 'isbn'
            table_format = ISBNPublisherIssueTable
        elif credit == 'barcode':
            query_val['barcode'] = name
            selected = 'barcode'
            table_format = BarcodePublisherIssueTable
        else:
            table_format = IssuePublisherTable
        if sort == ORDER_CHRONO:
            order_by = 'publication_date'
        else:
            order_by = 'issue'
        if things:
            filter = filter_issues(request, things)
            things = filter.qs
            filter_form = filter.form
        else:
            filter_form = None
        table = table_format(
          things,
          template_name='gcd/bits/tw_sortable_table.html',
          order_by=(order_by))
        template = 'gcd/search/tw_list_sortable.html'
        context = {'item_name': item_name,
                   'plural_suffix': plural_suffix,
                   'filter_form': filter_form,
                   'search_term': name,
                   'selected': selected,
                   'heading': heading}

        return generic_sortable_list(request, things, table, template,
                                     context)

    elif (class_ is Story):
        template = 'gcd/search/tw_list_sortable.html'
        item_name = 'stor'
        plural_suffix = 'y,ies'
        heading = "matching your query for '%s' in %s" % (name, credit)
        query_val['target'] = 'sequence'
        # build the query_string for the link to the advanced search
        if credit in ['script', 'pencils', 'inks', 'colors', 'letters',
                      'job_number']:
            query_val[credit] = name
        elif credit.startswith('editing_search'):
            query_val['story_editing'] = name
            query_val['issue_editing'] = name
            query_val['logic'] = True
            heading = "matching your query for '%s' in editing" % (name)
        elif credit.startswith('any'):
            heading = "matching your query for '%s' in any credit" % (name)
            query_val['logic'] = True
            for credit_type in ['script', 'pencils', 'inks', 'colors',
                                'letters', 'story_editing', 'issue_editing']:
                query_val[credit_type] = name
        elif credit.startswith('characters'):
            heading = "matching your query for '%s' in characters" % (name)

        if sqs is None:
            if credit in ['script', 'pencils', 'inks', 'colors', 'letters']:
                creators = list(CreatorNameDetail.objects
                                .filter(name__icontains=name)
                                .values_list('id', flat=True))
                if settings.DEBUG:
                    q_obj = Q(credits__creator__id__in=creators,
                              credits__credit_type__id=CREDIT_TYPES[credit],
                              credits__deleted=False)
                else:
                    q_obj |= Q(credits__creator__id__in=creators,
                               credits__credit_type__id=CREDIT_TYPES[credit],
                               credits__deleted=False)
            q_obj &= Q(deleted=False)
            things = class_.objects.filter(q_obj)
            things = things.select_related('issue__series',
                                           'type')
            if sort == ORDER_CHRONO:
                order_by = 'publication_date'
            else:
                order_by = 'issue'
            # build the query_string for the link to the advanced search
            # remove the ones which are not matched in display of results
            if credit in ['title', 'feature']:
                query_val[credit] = name
                credit = None
                things = things.prefetch_related('feature_object')
                filter = filter_sequences(request, things)
                things = filter.qs
                table = StoryTable(
                  things,
                  template_name='gcd/bits/tw_sortable_table.html',
                  order_by=(order_by))
                context = {'item_name': item_name,
                           'plural_suffix': plural_suffix,
                           'filter_form': filter.form,
                           'heading': heading}

                return generic_sortable_list(request, things, table, template,
                                             context)
            elif credit.startswith('characters'):
                target = 'characters:' + name
                query_val['characters'] = name
            elif credit.startswith('any'):
                target = 'any:' + name
                query_val['logic'] = True
            else:
                target = credit
            filter = filter_sequences(request, things)
            things = filter.qs

            table = MatchedSearchStoryTable(
                things, attrs={'class': 'sortable_listing'},
                template_name='gcd/bits/tw_sortable_table.html',
                target=target,
                order_by=(order_by))
            context = {'item_name': item_name,
                       'plural_suffix': plural_suffix,
                       'filter_form': filter.form,
                       'heading': heading}

            return generic_sortable_list(request, things, table, template,
                                         context)
            # OR-logic only applies to credits, so we cannot use it
            # to mimic the double search for characters and features here
            # query_val['feature'] = name
            # query_val['logic'] = True
        else:
            things, filter_form = filter_haystack(request, sqs)

            if credit == 'title':
                table = HaystackStoryTable(
                  things, attrs={'class': 'sortable_listing'},
                  template_name='gcd/bits/tw_sortable_table.html',)
            else:
                table = HaystackMatchedStoryTable(
                  things, attrs={'class': 'sortable_listing'},
                  template_name='gcd/bits/tw_sortable_table.html',
                  target=unquote_plus(credit))

            if not request.GET.get('sort', None):
                if sort == ORDER_CHRONO:
                    table.order_by = 'publication_date'
                else:
                    table.order_by = 'issue'

            context = {'item_name': item_name,
                       'plural_suffix': plural_suffix,
                       'filter_form': filter_form,
                       'selected': selected,
                       'search_term': name,
                       'heading': heading}
            table.no_raw_export = True
            return generic_sortable_list(request, things, table, template,
                                         context)
    else:
        raise TypeError("Unsupported search target!")

    if not selected:
        selected = credit

    if (sort == ORDER_ALPHA):
        change_order = request.path.replace('alpha', 'chrono')
    elif (sort == ORDER_CHRONO):
        change_order = request.path.replace('chrono', 'alpha')
    else:
        change_order = ''
    if change_order == request.path:
        change_order = change_order + 'sort/chrono/'
    vars = {'item_name': item_name,
            'plural_suffix': plural_suffix,
            'heading': heading,
            'search_term': name,
            'query_string': urlencode(query_val),
            'change_order': change_order,
            'which_credit': credit,
            'include_template': include_template,
            'selected': selected}
    return paginate_response(request, things, template, vars)


def award_search_hx(request):
    if request.method == 'GET':
        return render(request, 'gcd/bits/active_search.html',
                      {'object_name': 'Award',
                       'object_type': 'award'})
    award_name = request.POST['search']
    return award_by_name(request, award_name,
                         template='gcd/search/award_base_list.html')


def award_by_name(request, award_name='', sort=ORDER_ALPHA,
                  template='gcd/search/generic_include_list.html'):
    include_template = 'gcd/search/award_base_list.html'
    if settings.USE_ELASTICSEARCH and not award_name == '':
        sqs = SearchQuerySet().filter(name=GcdNameQuery(award_name)) \
                              .models(Award)
        return generic_by_name(request, award_name, None, sort, Award,
                               template, sqs=sqs,
                               include_template=include_template)
    else:
        q_obj = Q(name__icontains=award_name)
        return generic_by_name(request, award_name, q_obj, sort,
                               Award, template,
                               include_template=include_template)


def publisher_search_hx(request):
    if request.method == 'GET':
        return render(request, 'gcd/bits/active_search.html',
                      {'object_name': 'Publishers',
                       'object_type': 'publisher'})
    publisher_name = request.POST['search']
    return publisher_by_name(request, publisher_name, table_inline=True)


def publisher_by_name(request, publisher_name='', sort=ORDER_ALPHA,
                      table_inline=False):
    if settings.USE_ELASTICSEARCH and not publisher_name == '':
        sqs = SearchQuerySet().filter(name=GcdNameQuery(publisher_name)) \
                              .models(Publisher)
        publisher_ids = sqs.values_list('pk', flat=True)
        things = Publisher.objects.filter(id__in=publisher_ids)
        return generic_by_name(request, publisher_name, None, sort, Publisher,
                               things=things, table_inline=table_inline)
    else:
        q_obj = Q(name__icontains=publisher_name)
        return generic_by_name(request, publisher_name, q_obj, sort,
                               Publisher, table_inline=table_inline)


def brand_group_by_name(request, brand_group_name='', sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH and not brand_group_name == '':
        sqs = SearchQuerySet().filter(name=GcdNameQuery(brand_group_name)) \
                              .models(BrandGroup)
        brand_group_ids = sqs.values_list('pk', flat=True)
        things = BrandGroup.objects.filter(id__in=brand_group_ids)
        return generic_by_name(request, brand_group_name, None, sort,
                               BrandGroup, things=things)
    else:
        q_obj = Q(name__icontains=brand_group_name)
        return generic_by_name(request, brand_group_name, q_obj, sort,
                               BrandGroup)


def brand_by_name(request, brand_name='', sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH and not brand_name == '':
        sqs = SearchQuerySet().filter(name=GcdNameQuery(brand_name)) \
                              .models(Brand)
        brand_ids = sqs.values_list('pk', flat=True)
        things = Brand.objects.filter(id__in=brand_ids)
        return generic_by_name(request, brand_name, None, sort, Brand,
                               things=things)
    else:
        q_obj = Q(name__icontains=brand_name)
        return generic_by_name(request, brand_name, q_obj, sort, Brand)


def indicia_publisher_by_name(request, ind_pub_name='', sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH and not ind_pub_name == '':
        sqs = SearchQuerySet().filter(name=GcdNameQuery(ind_pub_name)) \
                            .models(IndiciaPublisher)
        ind_pub_ids = sqs.values_list('pk', flat=True)
        things = IndiciaPublisher.objects.filter(id__in=ind_pub_ids)
        return generic_by_name(request, ind_pub_name, None, sort,
                               IndiciaPublisher, things=things)
    else:
        q_obj = Q(name__icontains=ind_pub_name)
        return generic_by_name(request, ind_pub_name, q_obj, sort,
                               IndiciaPublisher)


def name_search_hx(request):
    return render(request, 'gcd/search/active_search.html',
                  {'object_name': 'Creators',
                   'object_type': 'creator'})


def printer_search_hx(request):
    if request.method == 'GET':
        return render(request, 'gcd/bits/active_search.html',
                      {'object_name': 'Printers',
                       'object_type': 'printer'})
    printer_name = request.POST['search']
    return printer_by_name(request, printer_name, table_inline=True)


def printer_by_name(request, printer_name='', sort=ORDER_ALPHA,
                    table_inline=False):
    if settings.USE_ELASTICSEARCH and not printer_name == '':
        sqs = SearchQuerySet().filter(
          name=GcdNameQuery(printer_name)).models(Printer)
        printer_ids = sqs.values_list('pk', flat=True)
        things = Printer.objects.filter(id__in=printer_ids)
        return generic_by_name(request, printer_name, None, sort, Printer,
                               things=things, table_inline=table_inline)
    else:
        q_obj = Q(name__icontains=printer_name)
        return generic_by_name(
          request, printer_name, q_obj, sort, Printer,
          table_inline=table_inline)


def creator_search_hx(request):
    if request.method == 'GET':
        return render(request, 'gcd/bits/active_search.html',
                      {'object_name': 'Creators',
                       'object_type': 'creator'})
    creator_name = request.POST['search']
    return creator_by_name(request, creator_name, table_inline=True)


def creator_by_name(request, creator_name='', sort=ORDER_ALPHA,
                    template='gcd/search/creator_list.html',
                    table_inline=False):
    if settings.USE_ELASTICSEARCH and not creator_name == '':
        # TODO use name instead ?
        sqs = SearchQuerySet().filter(
          gcd_official_name=GcdNameQuery(creator_name)).models(Creator)
        creator_ids = sqs.values_list('pk', flat=True)
        things = Creator.objects.filter(id__in=creator_ids)
        return generic_by_name(request, creator_name, None, sort, Creator,
                               things=things, template=template,
                               table_inline=table_inline)
    else:
        q_obj = Q(creator_names__name__icontains=creator_name) | Q(
            gcd_official_name__icontains=creator_name)
        return generic_by_name(request, creator_name, q_obj, sort,
                               Creator, template, table_inline=table_inline)


def creator_membership_by_name(request, creator_membership_name,
                               sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(
            name=GcdNameQuery(creator_membership_name)) \
            .models(CreatorMembership)
        return generic_by_name(request, creator_membership_name, None, sort,
                               CreatorMembership,
                               'gcd/search/creator_membership_list.html',
                               sqs=sqs)
    else:
        q_obj = Q(organization_name__icontains=creator_membership_name)
        return generic_by_name(request, creator_membership_name, q_obj, sort,
                               CreatorMembership,
                               'gcd/search/creator_membership_list.html')


def received_award_by_name(request, received_award_name, sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(name=GcdNameQuery(received_award_name)) \
            .models(ReceivedAward)
        return generic_by_name(request, received_award_name, None, sort,
                               ReceivedAward,
                               'gcd/search/received_award_list.html',
                               sqs=sqs)
    else:
        q_obj = Q(award_name__icontains=received_award_name)
        return generic_by_name(request, received_award_name, q_obj, sort,
                               ReceivedAward,
                               'gcd/search/received_award_list.html')


def creator_art_influence_by_name(request, creator_art_influence_name,
                                  sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(
            name=GcdNameQuery(creator_art_influence_name)) \
            .models(CreatorArtInfluence)
        return generic_by_name(request, creator_art_influence_name, None, sort,
                               CreatorArtInfluence,
                               'gcd/search/creator_art_influence_list.html',
                               sqs=sqs)
    else:
        q_obj = Q(influence_name__icontains=creator_art_influence_name) | \
                Q(influence_link__gcd_official_name__icontains=
                  creator_art_influence_name)
        return generic_by_name(request, creator_art_influence_name, q_obj,
                               sort, CreatorArtInfluence,
                               'gcd/search/creator_art_influence_list.html')


def creator_non_comic_work_by_name(request, creator_non_comic_work_name,
                                   sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(
            name=GcdNameQuery(creator_non_comic_work_name)) \
            .models(CreatorNonComicWork)
        return generic_by_name(request, creator_non_comic_work_name, None,
                               sort, CreatorNonComicWork,
                               'gcd/search/creator_non_comic_work_list.html',
                               sqs=sqs)
    else:
        q_obj = Q(publication_title__icontains=creator_non_comic_work_name)
        return generic_by_name(request, creator_non_comic_work_name, q_obj,
                               sort, CreatorNonComicWork,
                               'gcd/search/creator_non_comic_work_list.html')


def story_by_character(request, character, sort=ORDER_ALPHA):
    """Find stories based on characters.  Since characters for whom a feature
    is named are often not also listed under character appearances, this
    search looks at both the feature and characters fields."""

    if len(character) < 4:
        return render_error(
          request,
          'A search for characters must use more than 3 letters.',
          redirect=False)

    if settings.USE_ELASTICSEARCH:
        query_part = GcdNameQuery(character)
        sq = SQ(**{'characters': query_part})
        sq |= SQ(**{'feature': query_part})
        sqs = SearchQuerySet().filter(sq) \
                              .models(Story)
        return generic_by_name(request, character, None, sort,
                               credit="characters:" + character,
                               selected="by_character", sqs=sqs)
    else:
        q_obj = Q(appearing_characters__character__name__icontains=character)
        if not settings.DEBUG:
            q_obj |= Q(characters__icontains=character) | \
                     Q(feature__icontains=character) | \
                     Q(feature_object__name__icontains=character)
        return generic_by_name(request, character, q_obj, sort,
                               credit="characters:" + character,
                               selected="by_character")


def character_search_hx(request):
    if request.method == 'GET':
        return render(request, 'gcd/bits/active_search.html',
                      {'object_name': 'Characters',
                       'object_type': 'character'})
    character_name = request.POST['search']
    return character_by_name(request, character_name, table_inline=True)


def character_by_name(request, character_name='', sort=ORDER_ALPHA,
                      table_inline=False):
    if settings.USE_ELASTICSEARCH and not character_name == '':
        sqs = SearchQuerySet().filter(name=GcdNameQuery(character_name)) \
                              .models(Character)
        character_ids = sqs.values_list('pk', flat=True)
        things = Character.objects.filter(id__in=character_ids)
        return generic_by_name(request, character_name, None, sort, Character,
                               things=things, table_inline=table_inline)
    else:
        q_obj = Q(name__icontains=character_name)
        return generic_by_name(request, character_name, q_obj, sort, Character,
                               table_inline=table_inline)


def group_search_hx(request):
    if request.method == 'GET':
        return render(request, 'gcd/bits/active_search.html',
                      {'object_name': 'Groups',
                       'object_type': 'group'})
    group_name = request.POST['search']
    return group_by_name(request, group_name, table_inline=True)


def group_by_name(request, group_name='', sort=ORDER_ALPHA,
                  table_inline=False):
    if settings.USE_ELASTICSEARCH and not group_name == '':
        sqs = SearchQuerySet().filter(name=GcdNameQuery(group_name)) \
                              .models(Group)
        group_ids = sqs.values_list('pk', flat=True)
        things = Group.objects.filter(id__in=group_ids)
        return generic_by_name(request, group_name, None, sort, Group,
                               things=things, table_inline=table_inline)
    else:
        q_obj = Q(name__icontains=group_name)
        return generic_by_name(request, group_name, q_obj, sort, Group,
                               table_inline=table_inline)


def universe_search_hx(request):
    if request.method == 'GET':
        return render(request, 'gcd/bits/active_search.html',
                      {'object_name': 'Universe',
                       'object_type': 'universe'})
    universe_name = request.POST['search']
    return universe_by_name(request, universe_name,
                            template='gcd/search/character_base_list.html')


def universe_by_name(request, universe_name='', sort=ORDER_ALPHA,
                     template='gcd/search/generic_include_list.html'):
    include_template = 'gcd/search/character_base_list.html'
    if settings.USE_ELASTICSEARCH and not universe_name == '':
        sqs = SearchQuerySet().filter(name=GcdNameQuery(universe_name)) \
                              .models(Universe)
        return generic_by_name(request, universe_name, None, sort, Universe,
                               template, sqs=sqs,
                               include_template=include_template)
    else:
        q_obj = Q(name__icontains=universe_name) | \
                Q(designation__icontains=universe_name)
        return generic_by_name(request, universe_name, q_obj, sort,
                               Universe, template,
                               include_template=include_template)


def feature_search_hx(request):
    if request.method == 'GET':
        return render(request, 'gcd/bits/active_search.html',
                      {'object_name': 'Feature',
                       'object_type': 'feature'})
    feature_name = request.POST['search']
    return feature_by_name(request, feature_name, table_inline=True)


def feature_by_name(request, feature_name='', sort=ORDER_ALPHA,
                    table_inline=False):
    if settings.USE_ELASTICSEARCH and not feature_name == '':
        sqs = SearchQuerySet().filter(name=GcdNameQuery(feature_name)) \
                              .models(Feature)
        feature_ids = sqs.values_list('pk', flat=True)
        things = Feature.objects.filter(id__in=feature_ids)
        return generic_by_name(request, feature_name, None, sort, Feature,
                               things=things, table_inline=table_inline)
    else:
        q_obj = Q(name__icontains=feature_name)
        return generic_by_name(request, feature_name, q_obj, sort, Feature,
                               table_inline=table_inline)


def writer_by_name(request, writer, sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(script=GcdNameQuery(writer)) \
                              .models(Story)
        return generic_by_name(request, writer, None, sort, credit="script",
                               selected="writer", sqs=sqs)
    else:
        q_obj = Q(script__icontains=writer)
        return generic_by_name(request, writer, q_obj, sort, credit="script",
                               selected="writer")


def penciller_by_name(request, penciller, sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(pencils=GcdNameQuery(penciller)) \
                              .models(Story)
        return generic_by_name(request, penciller, None, sort,
                               credit="pencils", selected="penciller", sqs=sqs)
    else:
        q_obj = Q(pencils__icontains=penciller)
        return generic_by_name(request, penciller, q_obj, sort,
                               credit="pencils", selected="penciller")


def inker_by_name(request, inker, sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(inks=GcdNameQuery(inker)) \
                              .models(Story)
        return generic_by_name(request, inker, None, sort, credit="inks",
                               selected="inker", sqs=sqs)
    else:
        q_obj = Q(inks__icontains=inker)
        return generic_by_name(request, inker, q_obj, sort, credit="inks",
                               selected="inker")


def colorist_by_name(request, colorist, sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(colors=GcdNameQuery(colorist)) \
                              .models(Story)
        return generic_by_name(request, colorist, None, sort, credit="colors",
                               selected="colorist", sqs=sqs)
    else:
        q_obj = Q(colors__icontains=colorist)
        return generic_by_name(request, colorist, q_obj, sort, credit="colors",
                               selected="colorist")


def letterer_by_name(request, letterer, sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(letters=GcdNameQuery(letterer)) \
                              .models(Story)
        return generic_by_name(request, letterer, None, sort, credit="letters",
                               selected="letterer", sqs=sqs)
    else:
        q_obj = Q(letters__icontains=letterer)
        return generic_by_name(request, letterer, q_obj, sort,
                               credit="letters", selected="letterer")


def editor_by_name(request, editor, sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(editing=GcdNameQuery(editor)) \
                              .models(Story)
        return generic_by_name(request, editor, None, sort,
                               credit="editing_search:"+editor,
                               selected="editor", sqs=sqs)
    else:
        q_obj = Q(editing__icontains=editor) | \
                Q(issue__editing__icontains=editor)
        return generic_by_name(request, editor, q_obj, sort,
                               credit="editing_search:"+editor,
                               selected="editor")


def story_by_credit(request, name, sort=ORDER_ALPHA):
    """Implements the 'Any Credit' story search."""
    if settings.USE_ELASTICSEARCH:
        query_part = GcdNameQuery(name)
        sq = SQ(**{'script': query_part})
        for field in ['pencils', 'inks', 'colors', 'letters', 'editing']:
            sq |= SQ(**{field: query_part})
        sqs = SearchQuerySet().filter(sq).models(Story)
        return generic_by_name(request, name, None, sort, credit=('any:'+name),
                               selected="credit", sqs=sqs)

    else:
        q_obj = Q(script__icontains=name) | \
                Q(pencils__icontains=name) | \
                Q(inks__icontains=name) | \
                Q(colors__icontains=name) | \
                Q(letters__icontains=name) | \
                Q(editing__icontains=name) | \
                Q(issue__editing__icontains=name)
        return generic_by_name(request, name, q_obj, sort,
                               credit=('any:'+name), selected="credit")


def story_by_job_number(request, number, sort=ORDER_ALPHA):
    q_obj = Q(job_number__icontains=number)
    return generic_by_name(request, number, q_obj, sort, credit="job_number")


def story_by_job_number_name(request, number, sort=ORDER_ALPHA):
    """Handle the form-style URL from the basic search form by mapping
    it into the by-name lookup URLs the system already knows how to handle."""

    return HttpResponseRedirect(
      urlresolvers.reverse(story_by_job_number,
                           kwargs={'number': number, 'sort': sort}))


def story_by_title(request, title, sort=ORDER_ALPHA):
    """Looks up story by story (not issue or series) title."""
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(title=GcdNameQuery(title)) \
                              .models(Story)
        return generic_by_name(request, title, None, sort, credit="title",
                               selected="story", sqs=sqs)
    else:
        q_obj = Q(title__icontains=title)
        return generic_by_name(request, title, q_obj, sort, credit="title",
                               selected="story")


def story_by_feature(request, feature, sort=ORDER_ALPHA):
    """Looks up story by feature."""
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(feature=GcdNameQuery(feature)) \
                              .models(Story)
        return generic_by_name(request, feature, None, sort, credit="feature",
                               selected="by_feature", sqs=sqs)
    else:
        if settings.DEBUG:
            q_obj = Q(feature_object__name__icontains=feature)
        else:
            q_obj = Q(feature__icontains=feature) | \
                Q(feature_object__name__icontains=feature)
        return generic_by_name(request, feature, q_obj, sort, credit="feature",
                               selected="by_feature")


def series_search_hx(request):
    if request.method == 'GET':
        return render(request, 'gcd/bits/active_search.html',
                      {'object_name': 'Series',
                       'object_type': 'series'})
    series_name = request.POST['search']
    return series_by_name(request, series_name, table_inline=True)


def series_by_name(request, series_name='', sort=ORDER_ALPHA,
                   template='gcd/search/series_list.html', table_inline=False):
    if settings.USE_ELASTICSEARCH and not series_name == '':
        sqs = SearchQuerySet().filter(name=GcdNameQuery(series_name)) \
                              .models(Series)
        series_ids = sqs.values_list('pk', flat=True)
        things = Series.objects.filter(id__in=series_ids)
        return generic_by_name(request, series_name, None, sort, Series,
                               things=things, template=template,
                               table_inline=table_inline)
    else:
        q_obj = Q(name__icontains=series_name) | \
                Q(issue__title__icontains=series_name)
        return generic_by_name(request, series_name, q_obj, sort,
                               Series, template, table_inline=table_inline)


def series_and_issue(request, series_name, issue_nr, sort=ORDER_ALPHA):
    """ Looks for issue_nr in series with series_name """
    if settings.USE_ELASTICSEARCH:
        search_term = '"' + series_name + ' ' + issue_nr + '"'
        sqs = SearchQuerySet().filter(title=GcdNameQuery(search_term)) \
                              .models(Issue)
        issue_ids = sqs.values_list('pk', flat=True)
        things = Issue.objects.filter(id__in=issue_ids)
    else:
        things = Issue.objects.exclude(deleted=True) \
                    .filter(series__name__exact=series_name) \
                    .filter(number__exact=issue_nr)

    if things.count() == 1:  # if one display the issue
        return HttpResponseRedirect(urlresolvers.reverse(issue,
                                    kwargs={'issue_id': things[0].id}))
    else:  # if more use generic routine
        return generic_by_name(request, series_name + ' ' + issue_nr, None,
                               sort, Issue, selected='series_and_issue',
                               things=things, credit="series and issue")


def compute_isbn_qobj(isbn, prefix, op):
    if stdisbn.is_valid(isbn):
        isbn_compact = stdisbn.compact(isbn)
        q_obj = Q(**{'%svalid_isbn' % prefix: isbn_compact})
        # need to search for both ISBNs to be safe
        if stdisbn.isbn_type(isbn_compact) == 'ISBN13' and \
           isbn_compact.startswith('978'):
            isbn10 = isbn_compact[3:-1]
            isbn10 += stdisbn._calc_isbn10_check_digit(isbn10)
            q_obj |= Q(**{'%svalid_isbn' % prefix: isbn10})
        elif stdisbn.isbn_type(isbn_compact) == 'ISBN10':
            q_obj |= Q(**{'%svalid_isbn' % prefix:
                          stdisbn.to_isbn13(isbn_compact)})
    else:
        isbn = isbn.replace('-', '')
        q_obj = Q(**{'%svalid_isbn__%s' % (prefix, op): isbn})
    return q_obj


def issue_by_isbn_hx(request):
    if request.method == 'GET':
        return render(request, 'gcd/bits/active_search.html',
                      {'object_name': 'ISBN',
                       'object_type': 'isbn'})
    isbn = request.POST['search']
    return issue_by_isbn(request, isbn,
                         template='gcd/search/issue_base_list.html')


def issue_by_isbn(request, isbn, sort=ORDER_ALPHA,
                  template='gcd/search/issue_list.html'):
    q_obj = compute_isbn_qobj(isbn, '', 'icontains')
    return generic_by_name(request, isbn, q_obj, sort, class_=Issue,
                           template=template, credit="isbn")


def issue_by_isbn_name(request, isbn, sort=ORDER_ALPHA):
    """Handle the form-style URL from the basic search form by mapping
    it into the by-name lookup URLs the system already knows how to handle."""

    return HttpResponseRedirect(
      urlresolvers.reverse(issue_by_isbn,
                           kwargs={'isbn': isbn, 'sort': sort}))


def issue_by_barcode_hx(request):
    if request.method == 'GET':
        return render(request, 'gcd/bits/active_search.html',
                      {'object_name': 'Barcode',
                       'object_type': 'barcode'})
    barcode = request.POST['search']
    return issue_by_barcode(request, barcode,
                            template='gcd/search/issue_base_list.html')


def issue_by_barcode(request, barcode, sort=ORDER_ALPHA,
                     template='gcd/search/issue_list.html'):
    q_obj = Q(barcode__icontains=barcode)
    return generic_by_name(request, barcode, q_obj, sort, class_=Issue,
                           template=template,
                           credit="barcode")


def issue_by_barcode_name(request, barcode, sort=ORDER_ALPHA):
    """Handle the form-style URL from the basic search form by mapping
    it into the by-name lookup URLs the system already knows how to handle."""

    return HttpResponseRedirect(
      urlresolvers.reverse(issue_by_barcode,
                           kwargs={'barcode': barcode, 'sort': sort}))


def search(request):
    """
    Handle the form-style URL from the basic search form by mapping
    it into the by-name lookup URLs the system already knows how to handle.
    """

    # redirect if url starts with '/search/' but the rest is of no use
    if 'search_type' not in request.GET:
        return HttpResponseRedirect(urlresolvers.reverse(advanced_search))

    if 'query' not in request.GET or not request.GET['query'] or \
       request.GET['query'].isspace():
        if request.GET['search_type'] in ['publisher', 'creator', 'series',
                                          'keyword', 'brand', 'brand_group',
                                          'indicia_publisher', 'award',
                                          'character', 'group', 'feature']:
            view = '%s_by_name' % request.GET['search_type']
            return HttpResponseRedirect(urlresolvers.reverse(view))
        else:
            # if no query, but a referer page
            if 'referer' in request.headers:
                return HttpResponseRedirect(request.headers['referer'])
            else:  # rare, but possible
                return HttpResponseRedirect(urlresolvers.reverse(
                  advanced_search))

    if 'sort' in request.GET:
        sort = request.GET['sort']
    else:
        sort = ORDER_ALPHA

    if request.GET['search_type'].find("haystack") >= 0:
        quoted_query = quote(request.GET['query'])

    if request.GET['search_type'] == "mycomics_haystack":
        if sort == ORDER_CHRONO:
            return HttpResponseRedirect(
              urlresolvers.reverse("mycomics_search") + "?q=%s&sort=year" %
              quoted_query)
        else:
            return HttpResponseRedirect(
              urlresolvers.reverse("mycomics_search") + "?q=%s" % quoted_query)

    if request.GET['search_type'] == "haystack":
        if sort == ORDER_CHRONO:
            return HttpResponseRedirect(
              urlresolvers.reverse("haystack_search") + "?q=%s&sort=year" %
              quoted_query)
        else:
            return HttpResponseRedirect(
              urlresolvers.reverse("haystack_search") + "?q=%s" % quoted_query)

    if request.GET['search_type'] == "series_and_issue":
        issue_pos = request.GET['query'].rstrip().rfind(' ')
        if issue_pos > 0:
            series = request.GET['query'][:issue_pos]
            issue = request.GET['query'][issue_pos+1:]
            return HttpResponseRedirect(urlresolvers.reverse(
                                        "series_and_issue",
                                        kwargs={'series_name': series,
                                                'issue_nr': issue,
                                                'sort': sort}))
        else:
            return HttpResponseRedirect(urlresolvers.reverse("series_by_name",
                                        kwargs={'series_name':
                                                request.GET['query'],
                                                'sort': sort}))

    # TODO: Redesign this- the current setup is a quick hack to adjust
    # a design that was elegant when it was written, but things have changed.
    object_type = str(request.GET['search_type'])
    param_type = object_type
    view_type = object_type

    if view_type == 'publisher':
        param_type = 'publisher_name'
    elif view_type == 'brand_group':
        param_type = 'brand_group_name'
    elif view_type == 'brand':
        param_type = 'brand_name'
    elif view_type == 'indicia_publisher':
        param_type = 'ind_pub_name'
    elif view_type == 'award':
        param_type = 'award_name'
    elif view_type == 'character':
        param_type = 'character_name'
    elif view_type == 'by_character':
        param_type = 'character'
    elif view_type == 'group':
        param_type = 'group_name'
    elif view_type == 'by_group':
        param_type = 'group'
    elif view_type == 'feature':
        param_type = 'feature_name'
    elif view_type == 'by_feature':
        param_type = 'feature'
    elif view_type == 'creator':
        param_type = 'creator_name'
    elif view_type == 'creator_membership':
        param_type = 'creator_membership_name'
    elif view_type == 'creator_award':
        param_type = 'creator_award_name'
    elif view_type == 'creator_art_influence':
        param_type = 'creator_art_influence_name'
    elif view_type == 'creator_non_comic_work':
        param_type = 'creator_non_comic_work_name'

    if object_type == 'story':
        param_type = 'title'
        view = story_by_title
    elif object_type in ('credit', 'job_number'):
        view = 'story_by_%s' % object_type
    elif object_type in ('barcode', 'isbn'):
        view = 'issue_by_%s' % object_type
    elif object_type in ('by_character', 'by_feature'):
        view = 'story_%s' % object_type
    else:
        view = '%s_by_name' % view_type

    if object_type == 'credit':
        param_type = 'name'
    elif object_type in ('series',):
        param_type = object_type + '_name'
    elif object_type == 'job_number':
        param_type = 'number'

    param_type_value = request.GET['query'].strip()

    if object_type == 'keyword':
        return HttpResponseRedirect(
          urlresolvers.reverse(view,
                               kwargs={param_type: param_type_value}))
    return HttpResponseRedirect(
      urlresolvers.reverse(view,
                           kwargs={param_type: param_type_value,
                                   'sort': sort}))


def advanced_search(request):
    """Displays the advanced search form."""

    if ('target' not in request.GET):
        return render(request, 'gcd/search/advanced.html',
                      {'form': AdvancedSearch(user=request.user)})
    else:
        search_values = request.GET.copy()
        # convert a bit since MultipleChoiceField takes a list of IDs
        search_values['type'] = search_values.getlist('type')
        search_values['indexer'] = search_values.getlist('indexer')
        search_values['country'] = search_values.getlist('country')
        search_values['language'] = search_values.getlist('language')
        search_values['genre'] = search_values.getlist('genre')
        return render(request, 'gcd/search/advanced.html',
                      {'form': AdvancedSearch(user=request.user,
                                              initial=search_values)})


def do_advanced_search(request):
    """
    Runs advanced searches.
    """
    form = AdvancedSearch(request.GET, user=request.user)
    if not form.is_valid():
        raise ViewTerminationError(
          response=render(request, 'gcd/search/advanced.html',
                          {'form': form}))

    data = form.cleaned_data
    op = str(data['method'] or 'iregex')

    try:
        stq_obj, linked_credits_q_objs, other_stq_obj = search_stories(data,
                                                                       op)
        iq_obj = search_issues(data, op)
        sq_obj = search_series(data, op)
        ipq_obj = search_indicia_publishers(data, op)
        bq_obj = search_brands(data, op)
        bgq_obj = search_brand_groups(data, op)
        pq_obj = search_publishers(data, op)

        # if there are sequence searches limit to type cover
        if data['target'] == 'cover' and stq_obj is not None:
            cq_obj = Q(**{'issue__story__type': StoryType.objects
                                                         .get(name='cover')})
        else:
            cq_obj = None
        query = combine_q(data, stq_obj, iq_obj, sq_obj, pq_obj,
                          bq_obj, bgq_obj, ipq_obj, cq_obj)
        if linked_credits_q_objs:
            query_linked = combine_q(data, other_stq_obj, iq_obj, sq_obj,
                                     pq_obj, bq_obj, bgq_obj, ipq_obj, cq_obj)
        terms = compute_order(data)
    except SearchError as se:
        raise ViewTerminationError(render(
          request, 'gcd/search/advanced.html',
          {
              'form': form,
              'error_text': '%s' % se,
          }))

    if (not query) and (not data['keywords']):
        raise ViewTerminationError(render(
          request, 'gcd/search/advanced.html',
          {
            'form': form,
            'error_text': "Please enter at least one search term "
          }))

    items = []
    if data['target'] == 'publisher':
        filter = Publisher.objects.exclude(deleted=True)
        if query:
            filter = filter.filter(query)
        items = filter.order_by(*terms).select_related('country').distinct()

    elif data['target'] == 'brand_group':
        filter = BrandGroup.objects.exclude(deleted=True)
        if query:
            filter = filter.filter(query)
        items = filter.order_by(*terms).select_related('parent').distinct()

    elif data['target'] == 'brand_emblem':
        filter = Brand.objects.exclude(deleted=True)
        if query:
            filter = filter.filter(query)
        items = filter.order_by(*terms).prefetch_related('group__parent')\
                                       .distinct()

    elif data['target'] == 'indicia_publisher':
        filter = IndiciaPublisher.objects.exclude(deleted=True)
        if query:
            filter = filter.filter(query)
        items = filter.order_by(*terms).select_related('parent').distinct()

    elif data['target'] == 'series':
        filter = Series.objects.exclude(deleted=True)
        if query:
            filter = filter.filter(query)
        items = filter.order_by(*terms).select_related('publisher').distinct()

    elif data['target'] == 'issue':
        filter = Issue.objects.exclude(deleted=True)
        if query:
            text_filter = filter.filter(query)
            if linked_credits_q_objs and data['credit_is_linked'] is not False:
                linked_filter = filter.filter(query_linked)
                for credit_obj in linked_credits_q_objs:
                    linked_filter = linked_filter.filter(credit_obj)
                if data['credit_is_linked'] is None:
                    text_filter = linked_filter
                else:
                    text_filter = text_filter | linked_filter
            filter = text_filter

        items = filter.order_by(*terms).select_related(
          'series__publisher').distinct()

    elif data['target'] in ['cover', 'issue_cover']:
        filter = Cover.objects.exclude(deleted=True)
        if query:
            text_filter = filter.filter(query)
            if linked_credits_q_objs and data['credit_is_linked'] is not False:
                linked_filter = filter.filter(query_linked)
                for credit_obj in linked_credits_q_objs:
                    linked_filter = linked_filter.filter(credit_obj)
                if data['credit_is_linked'] is None:
                    text_filter = linked_filter
                else:
                    text_filter = text_filter | linked_filter
            filter = text_filter

        items = filter.order_by(*terms).select_related(
          'issue__series__publisher').distinct()

    elif data['target'] == 'sequence':
        filter = Story.objects.exclude(deleted=True)
        if query:
            text_filter = filter.filter(query)
            if linked_credits_q_objs and data['credit_is_linked'] is not False:
                linked_filter = filter.filter(query_linked)
                for credit_obj in linked_credits_q_objs:
                    linked_filter = linked_filter.filter(credit_obj)
                if data['credit_is_linked'] is None:
                    text_filter = linked_filter
                else:
                    text_filter = text_filter | linked_filter
            filter = text_filter

        items = filter.order_by(*terms).select_related(
          'issue__series__publisher', 'type').distinct()

    if data['keywords']:
        for keyword in data['keywords'].split(';'):
            if data['target'] == 'cover':
                items = items.filter(Q(**{'issue__story__keywords__name__%s'
                                          % (op): keyword.strip(),
                                          'issue__story__type':
                                          STORY_TYPES['cover']}))
            elif data['target'] == 'issue_cover':
                items = items.filter(Q(**{'issue__story__keywords__name__%s'
                                          % (op): keyword.strip()}))
            else:
                items = items.filter(Q(**{'keywords__name__%s'
                                          % (op): keyword.strip()}))

    if data.get('updated_since'):
        d = data['updated_since']
        items = items.filter(modified__gte='%04d-%02d-%02d' % (d.year,
                                                               d.month,
                                                               d.day))

    return items, data['target']


def used_search(search_values):
    try:
        del search_values['order1']
        del search_values['order2']
        del search_values['order3']
    except KeyError:
        pass
    if search_values['target'] == 'sequence':
        target = 'Stories'
    elif search_values['target'] == 'indicia_publisher':
        target = 'Indicia Publishers'
    elif search_values['target'] == 'brand':
        target = "Publisher's Brands"
    elif search_values['target'] == 'issue_cover':
        target = "Covers"
    else:
        target = search_values['target'].capitalize()
        if target[-1] != 's':
            target += 's'

    del search_values['target']

    if search_values['method'] == 'iexact':
        method = 'Matches Exactly'
    elif search_values['method'] == 'exact':
        method = 'Matches Exactly (case sensitive)'
    elif search_values['method'] == 'istartswith':
        method = 'Starts With'
    elif search_values['method'] == 'startswith':
        method = 'Starts With (case sensitive)'
    elif search_values['method'] == 'contains':
        method = 'Contains (case sensitive)'
    else:
        method = 'Contains'
    del search_values['method']

    if 'logic' in search_values and search_values['logic'] == 'True':
        logic = 'OR credits, AND other fields'
    else:
        logic = 'AND all fields'
    if 'logic' in search_values:
        del search_values['logic']

    used_search_terms = []
    if 'type' in search_values:
        types = StoryType.objects.filter(
          id__in=search_values.getlist('type')).values_list('name', flat=True)
        text = types[0]
        for storytype in types[1:]:
            text += ', %s' % storytype
        used_search_terms.append(('type', text))
        del search_values['type']
    if 'publication_type' in search_values:
        types = SeriesPublicationType.objects.filter(
          id__in=search_values.getlist('publication_type'))\
                              .values_list('name', flat=True)
        text = types[0]
        for publication_type in types[1:]:
            text += ', %s' % publication_type
        used_search_terms.append(('publication_type', text))
        del search_values['publication_type']
    if 'country' in search_values:
        countries = Country.objects.filter(
          code__in=search_values.getlist('country')).values_list('name',
                                                                 flat=True)
        text = countries[0]
        for country in countries[1:]:
            text += ', %s' % country
        used_search_terms.append(('country', text))
        del search_values['country']
    if 'language' in search_values:
        languages = Language.objects.filter(
          code__in=search_values.getlist('language')).values_list('name',
                                                                  flat=True)
        text = languages[0]
        for language in languages[1:]:
            text += ', %s' % language
        used_search_terms.append(('language', text))
        del search_values['language']
    if 'indexer' in search_values:
        indexers = Indexer.objects.filter(
          id__in=search_values.getlist('indexer'))
        text = str(indexers[0])
        for indexer in indexers[1:]:
            text += ', %s' % str(indexer)
        used_search_terms.append(('indexer', text))
        del search_values['indexer']
    if 'credit_is_linked' in search_values:
        if search_values['credit_is_linked'] == 'True':
            used_search_terms.append(('credit_is_linked',
                                      'both linked and text credits'))
        elif search_values['credit_is_linked'] == 'False':
            used_search_terms.append(('credit_is_linked',
                                      'text credits only'))
        else:
            used_search_terms.append(('credit_is_linked',
                                      'linked credits only'))
        del search_values['credit_is_linked']
    if 'genre' in search_values:
        genres = ''
        for genre in search_values.getlist('genre'):
            genres += '%s, ' % genre
        genres = genres[:-2]
        used_search_terms.append(('genre', genres))
        del search_values['genre']
    for i in search_values:
        if search_values[i] and search_values[i] not in ['None', 'False']:
            used_search_terms.append((i, search_values[i]))
    return target, method, logic, used_search_terms


def process_advanced(request, export_csv=False):
    """
    Runs advanced searches.
    """

    try:
        items, target = do_advanced_search(request)
    except ViewTerminationError as response:
        return response.response

    if 'random_search' in request.GET:
        if items.count():
            # using DB random via order_by('?') is rather expensive
            select = randint(0, items.count()-1)
            # nullify imposed ordering, use db one
            item = items.order_by()[select]
            return HttpResponseRedirect(item.get_absolute_url())

    if export_csv:
        fields = [f.name for f in items.model._meta.get_fields()
                  if f.auto_created is False]
        fields = [f for f in fields if f not in {'created', 'modified',
                                                 'deleted', 'keywords',
                                                 'tagged_items'}]
        fields.insert(0, 'id')
        return render_to_csv_response(items.values(*fields),
                                      append_datestamp=True)

    # Store the URL minus the page setting so that we can use
    # it to build the URLs for the links to other pages.
    get_copy = request.GET.copy()
    get_copy.pop('page', None)
    query_string = get_copy.urlencode()
    display_target, method, logic, used_search_terms = used_search(get_copy)
    query_string = urlencode(parse_qsl(query_string))

    if items.count() > 50000:
        return render_error(
          request,
          'More than 50,000 results, please limit the search range. '
          '<a href="%s?%s">Return to Advanced Search</a>' % (
            urlresolvers.reverse(advanced_search), query_string),
          redirect=False, is_safe=True)

    heading = mark_safe('matching your <a href="#search_terms">query</a>')

    context = {'object': target,
               'heading': heading,
               'plural_suffix': 's',
               'query_string': query_string,
               'used_search_terms': used_search_terms,
               'method': method,
               'logic': logic,
               'advanced_search': True,
               }

    template = 'gcd/search/tw_generic_list_sortable.html'

    if target in ['cover', 'issue_cover']:
        context['item_name'] = 'cover'
        if target == 'issue_cover':
            context['item_name'] = 'covers for issue'
        table = CoverIssuePublisherEditTable(
          items, template_name=TW_SORT_GRID_TEMPLATE)
        return generic_sortable_list(request, items, table, template, context,
                                     50)

    if target == 'sequence':
        table = StoryTable(items, template_name=TW_SORT_TABLE_TEMPLATE)
        context['item_name'] = 'sequence'

    if target == 'issue':
        table = IssuePublisherTable(items,
                                    template_name=TW_SORT_TABLE_TEMPLATE)
        context['item_name'] = 'issue'
        if request.user.is_authenticated and not settings.MYCOMICS:
            context['bulk_edit'] = urlresolvers.reverse('edit_issues_in_bulk')

    if target == 'series':
        table = SeriesPublisherTable(items,
                                     template_name=TW_SORT_TABLE_TEMPLATE)
        context['item_name'] = 'series'
        context['plural_suffix'] = ''

    if target == 'publisher':
        table = PublisherSearchTable(items,
                                     template_name=TW_SORT_TABLE_TEMPLATE)
        context['item_name'] = 'publisher'

    if target == 'indicia_publisher':
        table = IndiciaPublisherSearchTable(
          items, template_name=TW_SORT_TABLE_TEMPLATE)
        context['item_name'] = 'indicia publisher'

    if target == 'brand_group':
        table = BrandGroupSearchTable(
          items, template_name=TW_SORT_TABLE_TEMPLATE)
        context['item_name'] = 'brand group'

    if target == 'brand_emblem':
        table = BrandEmblemSearchTable(
          items, template_name=TW_SORT_TABLE_TEMPLATE)
        context['item_name'] = 'brand emblem'

    return generic_sortable_list(request, items, table, template, context)

    raise ValueError

    heading = target.title() + ' Search Results'

    item_name = target
    plural_suffix = 's'
    if item_name == 'sequence':
        item_name = 'content item'
    elif item_name == 'feature':
        item_name = 'content_series'
        plural_suffix = ''
    elif item_name == 'series':
        plural_suffix = ''

    context = {
        'advanced_search': True,
        'item_name': item_name,
        'plural_suffix': plural_suffix,
        'heading': heading,
        'query_string': query_string,
    }

    template = 'gcd/search/%s_list.html' % item_name

    context['target'] = display_target
    context['method'] = method
    context['logic'] = logic
    context['used_search_terms'] = used_search_terms

    return paginate_response(request, items, template, context)


def combine_q(data, *qobjs):
    """
    The queries against each table must be anded as they will be run using
    JOINs in a single query.  The method compute_prefix adjusted the query
    terms to work with the JOIN as they were added in each of the
    search_* methods.
    """
    filtered = [x for x in qobjs if x is not None]
    if filtered:
        return reduce(lambda x, y: x & y, filtered)
    return None


def search_dates(data, formatter=lambda d, start_end: d.year,
                 start_name='year_began', end_name='year_ended'):
    """
    Add query terms for date ranges, which may have either or both
    endpoints, or may be absent.  Note that strftime cannot handle
    years before 1900, hence the formatter callable.
    """

    # TODO: Could probably use __range operator if end dates were more
    #       reliable / structured.
    # TODO: If start and end name are the same, this could be done better.
    q_and_only = []
    if data['start_date']:
        begin_after_start = \
          {'%s__gte' % start_name: formatter(data['start_date'], True)}
        end_after_start = {'%s__gte' % end_name: formatter(data['start_date'],
                                                           True)}

        if data['end_date']:
            q_and_only.append(Q(**begin_after_start) & Q(**end_after_start))
        else:
            q_and_only.append(Q(**begin_after_start))

    if data['end_date']:
        begin_before_end = \
          {'%s__lte' % start_name: formatter(data['end_date'], False)}
        end_before_end = {'%s__lte' % end_name: formatter(data['end_date'],
                                                          False)}

        if data['start_date']:
            q_and_only.append(Q(**begin_before_end) & Q(**end_before_end))
        else:
            q_and_only.append(Q(**begin_before_end))

    return q_and_only


def search_publishers(data, op):
    """
    Handle publisher fields.
    """
    target = data['target']
    prefix = compute_prefix(target, 'publisher')

    q_and_only = []
    if data['country']:
        q_and_only.append(Q(**{'%scountry__code__in' % prefix:
                               data['country']}))
    if target == 'publisher':
        q_and_only.extend(search_dates(data,
                                       start_name='%syear_began' % prefix,
                                       end_name='%syear_ended' % prefix))

    q_objs = []
    if data['pub_name']:
        pub_name_q = Q(**{'%sname__%s' % (prefix, op): data['pub_name']})
        q_objs.append(pub_name_q)
    # one more like this and we should refactor the code :-)
    if data['pub_notes']:
        pub_notes_q = Q(**{'%snotes__%s' % (prefix, op):
                           data['pub_notes']})
        q_objs.append(pub_notes_q)

    if q_and_only or q_objs:
        q_and_only.append(Q(**{'%sdeleted__exact' % prefix: False}))
    return compute_qobj(data, q_and_only, q_objs)


def search_brand_groups(data, op):
    """
    Handle brand group fields.
    """
    target = data['target']
    if data['brand_group'] or data['brand_notes'] or target == 'brand_group':
        prefix = compute_prefix(target, 'brand_group')
    else:
        return None

    q_and_only = []
    q_objs = []
    if target == 'brand_group':
        q_and_only.extend(search_dates(data,
                                       start_name='%syear_began' % prefix,
                                       end_name='%syear_ended' % prefix))
    if data['brand_group']:
        q_objs.append(
          Q(**{'%sname__%s' % (prefix, op): data['brand_group']}))
    if data['brand_notes']:
        q_objs.append(
          Q(**{'%snotes__%s' % (prefix, op): data['brand_notes']}))

    if q_and_only or q_objs:
        q_and_only.append(Q(**{'%sdeleted__exact' % prefix: False}))
    return compute_qobj(data, q_and_only, q_objs)


def search_brands(data, op):
    """
    Handle brand emblem fields.
    """
    target = data['target']
    if data['brand_emblem'] or data['brand_notes'] or target == 'brand_emblem':
        prefix = compute_prefix(target, 'brand_emblem')
    else:
        return None

    q_and_only = []
    q_objs = []
    if target == 'brand_emblem':
        q_and_only.extend(search_dates(data,
                                       start_name='%syear_began' % prefix,
                                       end_name='%syear_ended' % prefix))
    if data['brand_emblem']:
        if data['brand_emblem'] == IS_EMPTY and target == 'issue':
            return Q(**{'%sisnull' % prefix: True}) & Q(**{'no_brand': False})
        if data['brand_emblem'] == IS_NONE and target == 'issue':
            return Q(**{'no_brand': True})
        q_objs.append(
          Q(**{'%sname__%s' % (prefix, op): data['brand_emblem']}))
    if data['brand_notes']:
        q_objs.append(
          Q(**{'%snotes__%s' % (prefix, op): data['brand_notes']}))

    if q_and_only or q_objs:
        q_and_only.append(Q(**{'%sdeleted__exact' % prefix: False}))
    return compute_qobj(data, q_and_only, q_objs)


def search_indicia_publishers(data, op):
    """
    Handle indicia_publisher fields.
    """
    target = data['target']
    if data['indicia_publisher'] or data['ind_pub_notes'] or \
       data['is_surrogate'] or target == 'indicia_publisher':
        prefix = compute_prefix(target, 'indicia_publisher')
    else:
        return None

    q_and_only = []
    q_objs = []
    if target == 'indicia_publisher':
        q_and_only.extend(search_dates(data,
                                       start_name='%syear_began' % prefix,
                                       end_name='%syear_ended' % prefix))
    if data['indicia_publisher']:
        if data['indicia_publisher'] == IS_EMPTY and target == 'issue':
            return Q(**{'%sisnull' % prefix: True})
        q_objs.append(
          Q(**{'%sname__%s' % (prefix, op): data['indicia_publisher']}))
    if data['ind_pub_notes']:
        q_objs.append(
          Q(**{'%snotes__%s' % (prefix, op): data['ind_pub_notes']}))
    if data['is_surrogate'] is not None:
        if data['is_surrogate'] is True:
            q_objs.append(Q(**{'%sis_surrogate' % prefix: True}))
        else:
            q_objs.append(Q(**{'%sis_surrogate' % prefix: False}))

    if q_and_only or q_objs:
        q_and_only.append(Q(**{'%sdeleted__exact' % prefix: False}))
    return compute_qobj(data, q_and_only, q_objs)


def search_series(data, op):
    """
    Handle series fields.
    """
    target = data['target']
    prefix = compute_prefix(target, 'series')

    q_and_only = []
    if target == 'series':
        q_and_only.extend(search_dates(data,
                                       start_name='%syear_began' % prefix,
                                       end_name='%syear_ended' % prefix))

    if data['publication_type']:
        publication_type_qargs = {'%spublication_type__in' % prefix:
                                  data['publication_type']}
        q_and_only.append(Q(**publication_type_qargs))

    if data['language']:
        language_qargs = {'%slanguage__code__in' % prefix: data['language']}
        q_and_only.append(Q(**language_qargs))

    q_objs = []
    if data['series']:
        q_objs.append(Q(**{'%sname__%s' % (prefix, op): data['series']}))
    if 'series_year_began' in data and data['series_year_began']:
        q_and_only.append(Q(**{'%syear_began' % prefix:
                            int(data['series_year_began'])}))
    if data['series_notes']:
        q_objs.append(Q(**{'%snotes__%s' % (prefix, op):
                           data['series_notes']}))
    if data['tracking_notes']:
        q_objs.append(Q(**{'%stracking_notes__%s' % (prefix, op):
                           data['tracking_notes']}))
    if data['not_reserved']:
        q_objs.append(Q(**{'%songoing_reservation__isnull' % prefix: True}) &
                      Q(**{'%sis_current' % prefix: True}))
    if data['is_current']:
        q_objs.append(Q(**{'%sis_current' % prefix: True}))
    if data['is_comics'] is not None:
        if data['is_comics'] is True:
            q_objs.append(Q(**{'%sis_comics_publication' % prefix: True}))
        else:
            q_objs.append(Q(**{'%sis_comics_publication' % prefix: False}))

    # Format fields
    if data['color']:
        q_objs.append(Q(**{'%scolor__%s' % (prefix, op): data['color']}))
    if data['dimensions']:
        q_objs.append(Q(**{'%sdimensions__%s' % (prefix, op):
                           data['dimensions']}))
    if data['paper_stock']:
        q_objs.append(Q(**{'%spaper_stock__%s' % (prefix, op):
                           data['paper_stock']}))
    if data['binding']:
        q_objs.append(Q(**{'%sbinding__%s' % (prefix, op): data['binding']}))
    if data['publishing_format']:
        q_objs.append(Q(**{'%spublishing_format__%s' % (prefix, op):
                           data['publishing_format']}))

    try:
        if data['issue_count'] is not None and data['issue_count'] != '':
            range_match = match(COUNT_RANGE_REGEXP, data['issue_count'])
            if range_match:
                if not range_match.group('min'):
                    q_objs.append(Q(**{'%sissue_count__lte' % prefix:
                                       int(range_match.group('max'))}))
                elif not range_match.group('max'):
                    q_objs.append(Q(**{'%sissue_count__gte' % prefix:
                                       int(range_match.group('min'))}))
                else:
                    q_objs.append(Q(**{'%sissue_count__range' % prefix:
                                       (int(range_match.group('min')),
                                        int(range_match.group('max')))}))
            else:
                q_objs.append(Q(**{'%sissue_count__exact' % prefix:
                                   int(data['issue_count'])}))
    except ValueError:
        raise SearchError("Issue count must be an integer or an integer "
                          "range reparated by a hyphen (e.g. 100-200, "
                          "100-, -200).")

    if q_and_only or q_objs:
        q_and_only.append(Q(**{'%sdeleted__exact' % prefix: False}))

    return compute_qobj(data, q_and_only, q_objs)


def issue_date_formatter(date, start_end):
    month = date.month
    if start_end and date.day == 1:
        day = 0
        if month == 1:
            month = 0
    else:
        day = date.day
    return '%04d-%02d-%02d' % (date.year, month, day)


def search_issues(data, op, stories_q=None):
    """
    Handle issue fields.
    """
    target = data['target']
    prefix = compute_prefix(target, 'issue')

    q_and_only = []
    if target in ['issue', 'cover', 'issue_cover', 'feature', 'sequence']:
        if data['use_on_sale_date']:
            q_and_only.extend(search_dates(data, issue_date_formatter,
                                           '%son_sale_date' % prefix,
                                           '%son_sale_date' % prefix))
        else:
            q_and_only.extend(search_dates(data, issue_date_formatter,
                                           '%skey_date' % prefix,
                                           '%skey_date' % prefix))

    if data['price']:
        q_and_only.append(Q(**{'%sprice__%s' % (prefix, op): data['price']}))

    q_objs = []
    if data['issues']:
        q_objs.append(handle_numbers('issues', data, prefix))
    if data['volume']:
        q_objs.append(handle_numbers('volume', data, prefix))
    if data['issue_title']:
        q_objs.append(Q(**{'%stitle__%s' % (prefix, op):
                        data['issue_title']}) &
                      Q(**{'%sseries__has_issue_title' % prefix: True}))
    if data['variant_name']:
        q_objs.append(Q(**{'%svariant_name__%s' % (prefix, op):
                        data['variant_name']}))
    if data['is_variant'] is not None:
        if data['is_variant'] is True:
            q_objs.append(~Q(**{'%svariant_of' % prefix: None}))
        else:
            q_objs.append(Q(**{'%svariant_of' % prefix: None}))
    if data['issue_date']:
        q_objs.append(
          Q(**{'%spublication_date__%s' % (prefix, op): data['issue_date']}))
    if data['cover_needed']:
        q_objs.append(Q(**{'%scover__isnull' % prefix: True}) |
                      ~Q(**{'%scover__deleted' % prefix: False}) |
                      Q(**{'%scover__marked' % prefix: True}))
    if data['is_indexed'] is not None:
        if data['is_indexed'] is True:
            q_objs.append(Q(**{'%sis_indexed' % prefix: INDEXED['full']}) &
                          Q(**{'%svariant_of' % prefix: None}))
        else:
            q_objs.append(~Q(**{'%sis_indexed' % prefix: INDEXED['full']}) &
                          Q(**{'%svariant_of' % prefix: None}))
    if data['image_resources'] is not None:
        if 'has_soo' in data['image_resources']:
            q_objs.append(Q(**{'%simage_resources__type__name' % prefix:
                               'SoOScan'}))
        if 'needs_soo' in data['image_resources']:
            q_objs.append(
              ((~Q(**{'%simage_resources__type__name' % prefix: 'SoOScan'}))
               & Q(**{'%sstory__type' % prefix: STORY_TYPES['soo']}))
              | Q(**{'%simage_resources__marked' % prefix: True}))
        if 'has_indicia' in data['image_resources']:
            q_objs.append(
              Q(**{'%simage_resources__type__name' % prefix: 'IndiciaScan'}))
        if 'needs_indicia' in data['image_resources']:
            q_objs.append(
              (~Q(**{'%simage_resources__type__name' % prefix: 'IndiciaScan'}))
              | Q(**{'%simage_resources__marked' % prefix: True}))
    if data['indexer']:
        q_objs.append(
          Q(**{'%srevisions__changeset__indexer__indexer__in' % prefix:
               data['indexer']}) &
          Q(**{'%srevisions__changeset__state' % prefix: states.APPROVED}))
    if data['isbn']:
        q_objs.append(compute_isbn_qobj(data['isbn'], prefix, op) &
                      Q(**{'%sseries__has_isbn' % prefix: True}))
    if data['barcode']:
        q_objs.append(Q(**{'%sbarcode__%s' % (prefix, op): data['barcode']}) &
                      Q(**{'%sseries__has_barcode' % prefix: True}))
    if data['indicia_frequency']:
        q_objs.append(Q(**{'%sindicia_frequency__%s' % (prefix, op):
                           data['indicia_frequency']}) &
                      Q(**{'%sseries__has_indicia_frequency' % prefix: True}))
    if data['rating']:
        q_objs.append(Q(**{'%srating__%s' % (prefix, op): data['rating']}) &
                      Q(**{'%sseries__has_rating' % prefix: True}))
    if data['issue_notes']:
        q_objs.append(Q(**{'%snotes__%s' % (prefix, op): data['issue_notes']}))

    if data['issue_reprinted'] is not None:
        if data['issue_reprinted'] == 'has_reprints':
            q_objs.append(Q(**{'%sfrom_all_reprints__isnull' % prefix: False}))
        elif data['issue_reprinted'] == 'is_reprinted':
            q_objs.append(Q(**{'%sto_all_reprints__isnull' % prefix: False}))
        elif data['issue_reprinted'] == 'issue_level_reprints':
            q_objs.append(Q(**{'%sfrom_all_reprints__target__isnull' % prefix:
                               True}) &
                          ~Q(**{'%sfrom_all_reprints__origin__isnull' % prefix:
                                True}))
        elif data['issue_reprinted'] == 'issue_level_reprinted':
            q_objs.append(Q(**{'%sto_all_reprints__origin__isnull' % prefix:
                               True}) &
                          ~Q(**{'%sto_all_reprints__target__isnull' % prefix:
                                True}))

    if 'in_collection' in data and data['in_collection']:
        if data['in_selected_collection']:
            q_objs.append(Q(**{'%scollectionitem__collections__in' % prefix:
                               data['in_collection']}))
        else:
            q_objs.append(~Q(**{'%scollectionitem__collections__in' % prefix:
                                data['in_collection']}))

    try:
        if data['issue_pages'] is not None and data['issue_pages'] != '':
            range_match = match(PAGE_RANGE_REGEXP, data['issue_pages'])
            if range_match:
                page_start = Decimal(range_match.group('begin'))
                page_end = Decimal(range_match.group('end'))
                q_objs.append(Q(**{'%spage_count__range' % prefix:
                                   (page_start, page_end)}))
            else:
                q_objs.append(Q(**{'%spage_count' % prefix:
                                   Decimal(data['issue_pages'])}))
    except ValueError:
        raise SearchError("Page count must be a decimal number or a pair of "
                          "decimal numbers separated by a hyphen.")
    if data['issue_pages_uncertain'] is not None:
        q_objs.append(Q(**{'%spage_count_uncertain' %
                           prefix: data['issue_pages_uncertain']}))

    # issue_editing is handled in search_stories since it is a credit
    # need to account for that here
    if q_and_only or q_objs or data['issue_editing']:
        q_and_only.append(Q(**{'%sdeleted__exact' % prefix: False}))

    return compute_qobj(data, q_and_only, q_objs)


def handle_numbers(field, data, prefix):
    """
    The issue and volume number fields accepts issues, hyphenated issue ranges,
    and comma-separated lists of either form.  Large numeric ranges
    result in large lists passed to the IN clause due to issue numbers
    not really being numeric in our data set.
    """
    # Commas can be backslash-escaped, and a literal backslash before
    # a comma can itself be escaped.  Backslashes elsewhere must not
    # be escaped.  This could be handled more consistently and intuitively.
    q_or_only = []
    issue_nums = split(r'\s*(?<!\\),\s*', data[field])
    nums_in = []
    for num in issue_nums:
        esc = sub(r'\\,', ',', num)
        range_match = match(r'(?P<begin>\d+)\s*-\s*(?P<end>\d+)$', esc)
        if range_match:
            # Sadly, issues are not really numbers all the time and
            # therefore the "between" operator (__range) does not
            # function properly on them, nor do numeric comparisions
            # as provided by __gte and __lte.  This is true even
            # when they *are* numbers because the database thinks
            # they are strings.
            num_range = list(range(int(range_match.group('begin')),
                                   int(range_match.group('end')) + 1))
            nums_in.extend(num_range)
        else:
            nums_in.append(esc)

    if nums_in:
        if field == 'issues':
            q_or_only.append(Q(**{'%snumber__in' % prefix: nums_in}))
        else:
            q_or_only.append(Q(**{'%svolume__in' % prefix: nums_in}) &
                             Q(**{'%sseries__has_volume' % prefix: True}))

    # add verbatim search when nothing processed (e.g. 100-1) or actual range
    if len(nums_in) != 1:
        if field == 'issues':
            q_or_only.append(Q(**{'%snumber' % prefix: data[field]}))
        else:
            q_or_only.append(Q(**{'%svolume' % prefix: data[field]}) &
                             Q(**{'%sseries__has_volume' % prefix: True}))

    return reduce(lambda x, y: x | y, q_or_only)


def search_stories(data, op):
    """
    Build the query against the story table.  As it is the lowest
    table in the hierarchy, there are no possible subqueries to run.
    """
    target = data['target']
    prefix = compute_prefix(target, 'sequence')

    q_objs = []
    text_credits_q_objs = []
    linked_credits_q_objs = []
    q_and_only = []

    for field in ('script', 'pencils', 'inks', 'colors', 'letters'):
        if data[field]:
            text_credits_q_objs.append(
              Q(**{'%s%s__%s' % (prefix, field, op): data[field]}))
            for creator in data[field].split(';'):
                creator = creator.strip()
                creator_q_obj = Q(**{'name__%s' % (op): creator})
                creator_q_obj |= Q(**{'creator__gcd_official_name__%s' % (op):
                                      creator})
                creators = list(CreatorNameDetail.objects.filter(creator_q_obj)
                                                 .values_list('id', flat=True))
                stories = list(Story.objects.filter(
                  credits__creator__id__in=creators,
                  credits__deleted=False,
                  credits__credit_type__id=CREDIT_TYPES[field])
                  .values_list('id', flat=True))
                if (stories):
                    linked_credits_q_objs.append(
                      (Q(**{'%sid__in' % (prefix): stories}))
                    )

    if data['story_editing']:
        text_credits_q_objs.append(Q(**{'%sediting__%s' % (prefix, op):
                                   data['story_editing']}))

        creator_q_obj = Q(**{'name__%s' % (op): data['story_editing']})
        creator_q_obj |= Q(**{'creator__gcd_official_name__%s' % (op):
                              data['story_editing']})
        creators = list(CreatorNameDetail.objects.filter(creator_q_obj)
                                         .values_list('id', flat=True))
        stories = list(Story.objects.filter(
          credits__creator__id__in=creators,
          credits__deleted=False,
          credits__credit_type__id=CREDIT_TYPES[field])
          .values_list('id', flat=True))
        if (stories):
            linked_credits_q_objs.append(
                (Q(**{'%sid__in' % (prefix): stories}))
            )

    for field in ('title', 'first_line', 'job_number', 'characters',
                  'synopsis', 'reprint_notes', 'notes'):
        if data[field]:
            q_and_only.append(Q(**{'%s%s__%s' % (prefix, field, op):
                                data[field]}))

    if data['feature']:
        if data['feature_is_linked'] is None:
            q_and_only.append(Q(**{'%s%s__%s' % (prefix,
                                                 'feature_object__name', op):
                              data['feature']}) |
                              Q(**{'%s%s__%s' % (prefix, 'feature', op):
                                   data['feature']}))
        elif data['feature_is_linked'] is True:
            q_and_only.append(Q(**{'%s%s__%s' % (prefix,
                                                 'feature_object__name', op):
                              data['feature']}))
        else:
            q_and_only.append(Q(**{'%s%s__%s' % (prefix, 'feature', op):
                                   data['feature']}))

    if data['type']:
        q_and_only.append(Q(**{'%stype__in' % prefix: data['type']}))

    if data['genre']:
        for genre in data['genre']:
            q_and_only.append(Q(**{'%sgenre__icontains' % prefix: genre}) |
                              Q(**{'%sfeature_object__genre__icontains' %
                                   prefix: genre}))

    if data['story_reprinted'] != '':
        if data['story_reprinted'] == 'from':
            q_and_only.append(Q(**{'%sfrom_all_reprints__isnull' % prefix:
                                   False}))
        elif data['story_reprinted'] == 'in':
            q_and_only.append(Q(**{'%sto_all_reprints__isnull' % prefix:
                                   False}))
        elif data['story_reprinted'] == 'not':
            q_and_only.append(Q(**{'%sfrom_all_reprints__isnull' % prefix:
                                   True}))
    try:
        if data['pages'] is not None and data['pages'] != '':
            range_match = match(PAGE_RANGE_REGEXP, data['pages'])
            if range_match:
                page_start = Decimal(range_match.group('begin'))
                page_end = Decimal(range_match.group('end'))
                q_and_only.append(Q(**{'%spage_count__range' % prefix:
                                       (page_start, page_end)}))
            else:
                q_and_only.append(Q(**{'%spage_count' % prefix:
                                       Decimal(data['pages'])}))
    except ValueError:
        raise SearchError("Page count must be a decimal number or a pair of "
                          "decimal numbers separated by a hyphen.")

    if data['pages_uncertain'] is not None:
        q_objs.append(Q(**{'%spage_count_uncertain' %
                           prefix: data['pages_uncertain']}))

    if q_and_only or q_objs or text_credits_q_objs or linked_credits_q_objs:
        q_and_only.append(Q(**{'%sdeleted__exact' % prefix: False}))

    # since issue_editing is credit use it here to allow correct 'OR' behavior
    if data['issue_editing']:
        creator_q_obj = Q(**{'name__%s' % (op): data['issue_editing']})
        creator_q_obj |= Q(**{'creator__gcd_official_name__%s' % (op):
                              data['issue_editing']})
        creators = list(CreatorNameDetail.objects.filter(creator_q_obj)
                                                 .values_list('id', flat=True))
        issues = list(Issue.objects.filter(
            credits__creator__id__in=creators,
            credits__deleted=False,
            credits__credit_type__id=CREDIT_TYPES['editing'])
            .values_list('id', flat=True))
        if issues:
            if target == 'sequence':  # no prefix in this case
                text_credits_q_objs.append(Q(**{'issue__editing__%s' % op:
                                           data['issue_editing']}))

                linked_credits_q_objs.append((Q(**{'issue__id__in': issues})))
            else:  # cut off 'story__'
                text_credits_q_objs.append(Q(**{'%sediting__%s' % (prefix[:-7],
                                                                   op):
                                           data['issue_editing']}))
                linked_credits_q_objs.append((Q(**{'%sid__in' % (prefix[:-7]):
                                                issues})))

    text_credits_q_objs.extend(q_objs)
    if data['logic'] is True:  # OR credits
        if data['credit_is_linked'] is None:
            linked_credits_q_objs.extend(q_objs)
            return compute_qobj(data, q_and_only, linked_credits_q_objs), \
                None, None
        elif data['credit_is_linked'] is True:
            text_credits_q_objs.extend(linked_credits_q_objs)
        return compute_qobj(data, q_and_only, text_credits_q_objs), None, None
    else:  # AND credits
        return compute_qobj(data, q_and_only, text_credits_q_objs), \
          linked_credits_q_objs, compute_qobj(data, q_and_only, q_objs),


def compute_prefix(target, current):
    """
    Advanced search allows searching on any of six tables in a
    hierarchy using fields from any of those tables.  Depending on
    the relative positioning of the table you're searching in to
    the table that has the field you're searching with, you may need
    to follow relationships to reach the table that contains the field.

    This function works out the realtionship-following prefixes, where
    'current' is the table whose fields are being processed, and 'target'
    is the table the search will ultimately run against.
    """
    if current == 'publisher':
        if target == 'series':
            return 'publisher__'
        if target in ('brand_group', 'indicia_publisher'):
            return 'parent__'
        if target in ('brand_emblem'):
            return 'group__parent__'
        if target == 'issue':
            return 'series__publisher__'
        if target in ('sequence', 'feature', 'cover', 'issue_cover'):
            return 'issue__series__publisher__'
    elif current == 'brand_group':
        if target == 'indicia_publisher':
            raise SearchError("Cannot search for Indicia Publishers by "
                              "Publisher's Brand attributes, as they are not "
                              "directly related")
        if target == 'publisher':
            return 'brandgroup__'
        if target == 'issue':
            return 'brand__group__'
        if target in ('series', 'sequence', 'feature', 'cover', 'issue_cover'):
            return 'issue__brand__group__'
    elif current == 'brand_emblem':
        if target == 'indicia_publisher':
            raise SearchError("Cannot search for Indicia Publishers by "
                              "Publisher's Brand attributes, as they are not "
                              "directly related")
        if target == 'publisher':
            return 'brandgroup__brand__'
        if target == 'issue':
            return 'brand__'
        if target in ('series', 'sequence', 'feature', 'cover', 'issue_cover'):
            return 'issue__brand__'
    elif current == 'indicia_publisher':
        if target in ('brand_group', 'brand_emblem'):
            raise SearchError('Cannot search for Publisher Brands by '
                              'Indicia Publisher attributes, as they are '
                              'not directly related')
        if target == 'publisher':
            return 'indiciapublisher__'
        if target == 'issue':
            return 'indicia_publisher__'
        if target in ('series', 'sequence', 'feature', 'cover', 'issue_cover'):
            return 'issue__indicia_publisher__'
    elif current == 'series':
        if target in ('issue', 'publisher'):
            return 'series__'
        if target in ('sequence', 'feature', 'cover', 'issue_cover',
                      'brand_emblem', 'indicia_publisher'):
            return 'issue__series__'
        if target == 'brand_group':
            return 'brand__issue__series__'
    elif current == 'issue':
        if target in ('sequence', 'feature', 'cover', 'issue_cover', 'series',
                      'brand_emblem', 'indicia_publisher'):
            return 'issue__'
        if target == 'publisher':
            return 'series__issue__'
        if target == 'brand_group':
            return 'brand__issue__'
    elif current == 'sequence':
        if target == 'issue':
            return 'story__'
        if target in ('series', 'cover', 'issue_cover', 'brand_emblem',
                      'indicia_publisher'):
            return 'issue__story__'
        if target == 'publisher':
            return 'series__issue__story__'
        if target == 'brand_group':
            return 'brand__issue__story__'
    return ''


def compute_qobj(data, q_and_only, q_objs):
    """
    Combines the various sorts of query objects in a standard way.
    """
    q_combined = None
    if q_objs:
        # Should be bool, but is string.  TODO: Find out why.
        if data['logic'] is True:
            q_combined = reduce(lambda x, y: x | y, q_objs)
        else:
            q_combined = reduce(lambda x, y: x & y, q_objs)

    if q_combined:
        return reduce(lambda x, y: x & y, q_and_only, q_combined)
    if q_and_only:
        return reduce(lambda x, y: x & y, q_and_only)
    return None


def compute_order(data):
    """
    Figures out how to apply the ordering terms to the table the
    final query will run against.  Unlike the 'compute' methods for
    searching, compute_order will ignore orderings that don't apply
    to the primary search table.  This is arguably a bug, or at least
    unduly confusing.  The computation is also an inelegant application
    of brute force.
    """

    target = data['target']
    terms = []
    for order in (data['order1'], data['order2'], data['order3']):
        if not order:
            continue

        if order == target:
            if target != 'series':
                terms.append('name')
            else:
                terms.append('sort_name')

        elif target == 'publisher':
            if order == 'date':
                terms.append('year_began')
            elif order == 'country':
                terms.append('country__name')

        elif target == 'brand_group':
            if order == 'date':
                terms.append('year_began')
            elif order == 'publisher':
                terms.append('parent')
            elif order == 'country':
                terms.append('parent__country__name')

        elif target == 'brand_emblem':
            if order == 'date':
                terms.append('year_began')

        elif target == 'indicia_publisher':
            if order == 'date':
                terms.append('year_began')
            elif order == 'publisher':
                terms.append('parent')
            elif order == 'country':
                # TODO: Should we allow indicia publisher country?
                # We do not currently search it, so no ordering either for now.
                terms.append('parent__country__name')

        elif target == 'series':
            if order == 'date':
                terms.append('year_began')
            elif order == 'publisher':
                terms.append('publisher')
            elif order == 'country':
                terms.append('country__name')
            elif order == 'language':
                terms.append('language__name')

        elif target == 'issue':
            if order == 'date':
                if data['use_on_sale_date']:
                    terms.append('on_sale_date')
                else:
                    terms.append('key_date')
            elif order == 'series':
                terms.append('series')
            elif order == 'indicia_publisher':
                terms.append('indicia_publisher')
            elif order == 'brand':
                terms.append('brand')
            elif order == 'publisher':
                terms.append('series__publisher')
            elif order == 'country':
                terms.append('series__country__name')
            elif order == 'language':
                terms.append('series__language__name')

        elif target in ('sequence', 'feature', 'cover', 'issue_cover'):
            if order == 'publisher':
                terms.append('issue__series__publisher')
            elif order == 'brand':
                terms.append('issue__brand')
            elif order == 'indicia_publisher':
                terms.append('issue__indicia_publisher')
            elif order == 'series':
                terms.append('issue__series')
            elif order == 'date':
                if data['use_on_sale_date']:
                    terms.append('issue__on_sale_date')
                else:
                    terms.append('issue__key_date')
            elif order == 'country':
                terms.append('issue__series__country__name')
            elif order == 'language':
                terms.append('issue__series__language__name')
            elif target not in ['cover', 'issue_cover']:
                terms.append(order)
        else:
            raise ValueError
        if target == 'issue':
            terms.append('sort_code')

    return terms
