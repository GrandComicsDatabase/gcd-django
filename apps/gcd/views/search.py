# -*- coding: utf-8 -*-
"""
View methods related to displaying search and search results pages.
"""

from re import match, split, sub
from urllib.parse import urlencode
from decimal import Decimal
from haystack.backends import SQ
from stdnum import isbn as stdisbn
from random import randint

from django.db.models import Q
from django.conf import settings
from django.http import HttpResponseRedirect
from django.core import urlresolvers
from django.shortcuts import render
from django.utils.http import urlquote

from djqscsv import render_to_csv_response
from haystack.query import SearchQuerySet

from apps.gcd.views.search_haystack import GcdNameQuery

from apps.stddata.models import Country, Language

from apps.indexer.models import Indexer
from apps.indexer.views import ViewTerminationError, render_error

from apps.gcd.models import Publisher, Series, Issue, Cover, Story, StoryType,\
                            BrandGroup, Brand, IndiciaPublisher, STORY_TYPES, \
                            Award, Creator, CreatorMembership, ReceivedAward, \
                            CreatorArtInfluence, CreatorNonComicWork, \
                            CreatorNameDetail, SeriesPublicationType
from apps.gcd.models.issue import INDEXED
from apps.gcd.views import paginate_response, ORDER_ALPHA, ORDER_CHRONO
from apps.gcd.forms.search import AdvancedSearch, PAGE_RANGE_REGEXP, \
                                  COUNT_RANGE_REGEXP
from apps.gcd.views.details import issue, COVER_TABLE_WIDTH, IS_EMPTY, IS_NONE
from apps.gcd.views.covers import get_image_tags_per_page

# Should not be importing anything from oi, but we're doing this in several places.
# TODO: states should probably live somewhere else.
from apps.oi import states
from functools import reduce


class SearchError(Exception):
    pass


def generic_by_name(request, name, q_obj, sort,
                    class_=Story,
                    template='gcd/search/content_list.html',
                    credit=None,
                    related=[],
                    sqs=None,
                    selected=None):
    """
    Helper function for the most common search cases.
    """
    name = name.encode('utf-8')
    base_name = 'unknown'
    plural_suffix = 's'
    query_val = {'method': 'icontains', 'logic': 'True'}

    if (class_ in (Series, BrandGroup, Brand, IndiciaPublisher, Publisher)):
        if class_ is IndiciaPublisher:
            base_name = 'indicia_publisher'
            display_name = 'Indicia / Colophon Publisher'
        elif class_ is Brand:
            display_name = 'Brand Emblem'
            base_name = 'brand_emblem'
        elif class_ is BrandGroup:
            display_name = 'Brand Group'
            base_name = 'brand_group'
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
            things = class_.objects.exclude(deleted=True).filter(q_obj)
            if related:
                things = things.select_related(*related)
            if (sort == ORDER_ALPHA):
                things = things.order_by(sort_name, "year_began")
            elif (sort == ORDER_CHRONO):
                things = things.order_by("year_began", sort_name)
            things = things.distinct()
        else:
            things = sqs
            if (sort == ORDER_ALPHA):
                things = things.order_by('sort_name',
                                         'year')
            elif (sort == ORDER_CHRONO):
                things = things.order_by('year',
                                         'sort_name')
        heading = '%s Search Results' % display_name
        # query_string for the link to the advanced search
        query_val['target'] = base_name
        if class_ is Publisher:
            query_val['pub_name'] = name
        else:
            query_val[base_name] = name

    elif class_ is Award:
        sort_name = "name"

        if sqs is None:
            things = class_.objects.exclude(deleted=True).filter(q_obj)
            things = things.order_by(sort_name)
            things = things.distinct()
        else:
            things = sqs
            things = things.order_by(sort_name)
        display_name = class_.__name__
        base_name = display_name.lower()
        item_name = display_name.lower()
        selected = base_name

        heading = '%s Search Results' % display_name

    elif class_ is Creator:
        sort_name = "sort_name"

        if sqs is None:
            sort_year = "birth_date__year"
            things = class_.objects.exclude(deleted=True).filter(q_obj)
            if related:
                things = things.select_related(*related)
            if (sort == ORDER_ALPHA):
                things = things.order_by(sort_name, sort_year)
            elif (sort == ORDER_CHRONO):
                things = things.order_by(sort_year, sort_name)
            things = things.distinct()
        else:
            sort_year = "year"
            things = sqs
            if (sort == ORDER_ALPHA):
                things = things.order_by(sort_name,
                                         sort_year)
            elif (sort == ORDER_CHRONO):
                things = things.order_by(sort_year,
                                         sort_name)
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
            if (sort == ORDER_ALPHA):
                things = things.order_by(sort_name, sort_year)
            elif (sort == ORDER_CHRONO):
                things = things.order_by(sort_year, sort_name)
            things = things.distinct()
        else:
            sort_name = "name"
            things = sqs
            if class_ != ReceivedAward:
                things = things.order_by('sort_name')
            else:
                sort_year = 'year'
                if (sort == ORDER_ALPHA):
                    things = things.order_by(sort_name,
                                             sort_year)
                elif (sort == ORDER_CHRONO):
                    things = things.order_by(sort_year,
                                             sort_name)
        display_name = class_.__name__
        base_name = display_name.lower()
        item_name = display_name.lower()

        heading = '%s Search Results' % display_name
        # query_string for the link to the advanced search
        query_val['target'] = base_name
        query_val[base_name] = name

    elif class_ is Issue:
        item_name = 'issue'
        things = Issue.objects.exclude(deleted=True).filter(q_obj) \
                   .select_related('series__publisher')
        if (sort == ORDER_ALPHA):
            things = things.order_by("series__sort_name", "key_date")
        elif (sort == ORDER_CHRONO):
            things = things.order_by("key_date", "series__sort_name")
        heading = 'Issue Search Results'
        # query_string for the link to the advanced search
        query_val['target'] = 'issue'
        if credit == 'isbn':
            query_val['isbn'] = name
        else:
            query_val['barcode'] = name

    elif (class_ is Story):
        item_name = 'stor'
        plural_suffix = 'y,ies'
        heading = 'Story Search Results'
        query_val['target'] = 'sequence'
        # build the query_string for the link to the advanced search
        if credit in ['script', 'pencils', 'inks', 'colors', 'letters',
                      'job_number']:
            query_val[credit] = name
        elif credit.startswith('editing_search'):
            query_val['story_editing'] = name
            query_val['issue_editing'] = name
            query_val['logic'] = True
        elif credit.startswith('any'):
            query_val['logic'] = True
            for credit_type in ['script', 'pencils', 'inks', 'colors',
                                'letters', 'story_editing', 'issue_editing']:
                query_val[credit_type] = name
        if sqs is None:
            # TODO: move this outside when series deletes are implemented
            q_obj &= Q(deleted=False)

            things = class_.objects.filter(q_obj)
            things = things.select_related('issue__series__publisher',
                                           'type')

            # TODO: This order_by stuff only works for Stories, which is
            # TODO: OK for now, but might not always be.
            if (sort == ORDER_ALPHA):
                things = things.order_by("issue__series__sort_name",
                                         "issue__series__year_began",
                                         "issue__key_date",
                                         "sequence_number")
            elif (sort == ORDER_CHRONO):
                things = things.order_by("issue__key_date",
                                         "issue__series__sort_name",
                                         "issue__series__year_began",
                                         "sequence_number")
            # build the query_string for the link to the advanced search
            # remove the ones which are not matched in display of results
            if credit in ['reprint', 'title', 'feature']:
                query_val[credit] = name
                credit = None
            elif credit.startswith('characters'):
                query_val['characters'] = name
                # OR-logic only applies to credits, so we cannnot use it
                # to mimic the double search for characters and features here
                # query_val['feature'] = name
                # query_val['logic'] = True
        else:
            things = sqs
            if (sort == ORDER_ALPHA):
                things = things.order_by("sort_name",
                                         "key_date",
                                         "sequence_number")
            elif (sort == ORDER_CHRONO):
                things = things.order_by("key_date",
                                         "sort_name",
                                         "sequence_number")

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

    vars = { 'item_name': item_name,
             'plural_suffix': plural_suffix,
             'heading': heading,
             'search_term': name,
             'query_string': urlencode(query_val),
             'change_order': change_order,
             'which_credit': credit,
             'selected': selected }
    return paginate_response(request, things, template, vars)


def award_by_name(request, award_name, sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(name=GcdNameQuery(award_name)) \
                              .models(Award)
        return generic_by_name(request, award_name, None, sort, Award,
                               'gcd/search/award_list.html', sqs=sqs)
    else:
        q_obj = Q(name__icontains=award_name)
        return generic_by_name(request, award_name, q_obj, sort,
                               Award, 'gcd/search/award_list.html')


def publisher_by_name(request, publisher_name, sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(name=GcdNameQuery(publisher_name)) \
                              .models(Publisher)
        return generic_by_name(request, publisher_name, None, sort, Publisher,
                               'gcd/search/publisher_list.html', sqs=sqs)
    else:
        q_obj = Q(name__icontains=publisher_name)
        return generic_by_name(request, publisher_name, q_obj, sort,
                               Publisher, 'gcd/search/publisher_list.html')


def brand_group_by_name(request, brand_group_name, sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(name=GcdNameQuery(brand_group_name)) \
                              .models(BrandGroup)
        return generic_by_name(request, brand_group_name, None, sort,
                               BrandGroup, 'gcd/search/brand_group_list.html',
                               sqs=sqs)
    else:
        q_obj = Q(name__icontains=brand_group_name)
        return generic_by_name(request, brand_group_name, q_obj, sort,
                               BrandGroup, 'gcd/search/brand_group_list.html')


def brand_by_name(request, brand_name, sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(name=GcdNameQuery(brand_name)) \
                              .models(Brand)
        return generic_by_name(request, brand_name, None, sort, Brand, 
                               'gcd/search/brand_list.html', sqs=sqs)
    else:
        q_obj = Q(name__icontains=brand_name)
        return generic_by_name(request, brand_name, q_obj, sort,
                               Brand, 'gcd/search/brand_list.html')


def indicia_publisher_by_name(request, ind_pub_name, sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(name=GcdNameQuery(ind_pub_name)) \
                            .models(IndiciaPublisher)
        return generic_by_name(request, ind_pub_name, None, sort,
                               IndiciaPublisher,
                               'gcd/search/indicia_publisher_list.html', 
                               sqs=sqs)
    else:
        q_obj = Q(name__icontains=ind_pub_name)
        return generic_by_name(request, ind_pub_name, q_obj, sort,
                               IndiciaPublisher,
                               'gcd/search/indicia_publisher_list.html')


def creator_by_name(request, creator_name, sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH:
        # TODO use name instead ?
        sqs = SearchQuerySet().filter(gcd_official_name=\
                                      GcdNameQuery(creator_name)) \
                              .models(Creator)
        return generic_by_name(request, creator_name, None, sort,
                               Creator,
                               'gcd/search/creator_list.html',
                               sqs=sqs)
    else:
        q_obj = Q(creator_names__name__icontains=creator_name) | Q(
            gcd_official_name__icontains=creator_name)
        return generic_by_name(request, creator_name, q_obj, sort,
                               Creator,
                               'gcd/search/creator_list.html')


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
                Q(influence_link__gcd_official_name__icontains=creator_art_influence_name)
        return generic_by_name(request, creator_art_influence_name, q_obj, sort,
                               CreatorArtInfluence,
                               'gcd/search/creator_art_influence_list.html')


def creator_non_comic_work_by_name(request, creator_non_comic_work_name,
                                   sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(
            name=GcdNameQuery(creator_non_comic_work_name)) \
            .models(CreatorNonComicWork)
        return generic_by_name(request, creator_non_comic_work_name, None, sort,
                               CreatorNonComicWork,
                               'gcd/search/creator_non_comic_work_list.html',
                               sqs=sqs)
    else:
        q_obj = Q(publication_title__icontains=creator_non_comic_work_name)
        return generic_by_name(request, creator_non_comic_work_name, q_obj, sort,
                               CreatorNonComicWork,
                               'gcd/search/creator_non_comic_work_list.html')


def character_by_name(request, character_name, sort=ORDER_ALPHA):
    """Find stories based on characters.  Since characters for whom a feature
    is named are often not also listed under character appearances, this
    search looks at both the feature and characters fields."""

    if len(character_name) < 4:
        return render_error(request,
          'A search for characters must use more than 3 letters.', redirect=False)

    q_obj = Q(characters__icontains=character_name) | \
            Q(feature__icontains=character_name)
    return generic_by_name(request, character_name, q_obj, sort,
                           credit="characters:" + character_name,
                           selected="character")


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
        return generic_by_name(request, penciller, None, sort, credit="pencils",
                               selected="penciller", sqs=sqs)
    else:
        q_obj = Q(pencils__icontains=penciller)
        return generic_by_name(request, penciller, q_obj, sort, credit="pencils",
                               selected="penciller")


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
        return generic_by_name(request, letterer, q_obj, sort, credit="letters",
                               selected="letterer")


def editor_by_name(request, editor, sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(editing=GcdNameQuery(editor)) \
                              .models(Story)
        return generic_by_name(request, editor, None, sort,
                               credit="editing_search:"+editor,
                               selected="editor", sqs=sqs)
    else:
        q_obj = Q(editing__icontains=editor) | Q(issue__editing__icontains=editor)
        return generic_by_name(request, editor, q_obj, sort,
                               credit="editing_search:"+editor,
                               selected="editor")


def story_by_credit(request, name, sort=ORDER_ALPHA):
    """Implements the 'Any Credit' story search."""
    if settings.USE_ELASTICSEARCH:
        query_part = GcdNameQuery(name)
        sq = SQ(**{'script':query_part})
        for field in ['pencils', 'inks', 'colors', 'letters', 'editing']:
            sq |= SQ(**{field:query_part})
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
        return generic_by_name(request, name, q_obj, sort, credit=('any:'+name),
                               selected="credit")


def story_by_job_number(request, number, sort=ORDER_ALPHA):
    q_obj = Q(job_number__icontains = number)
    return generic_by_name(request, number, q_obj, sort, credit="job_number")

def story_by_job_number_name(request, number, sort=ORDER_ALPHA):
    """Handle the form-style URL from the basic search form by mapping
    it into the by-name lookup URLs the system already knows how to handle."""

    return HttpResponseRedirect(
      urlresolvers.reverse(story_by_job_number,
                           kwargs={ 'number': number, 'sort': sort }))

def story_by_reprint(request, reprints, sort=ORDER_ALPHA):
    q_obj = Q(reprint_notes__icontains = reprints)
    return generic_by_name(request, reprints, q_obj, sort, credit="reprint")


def story_by_title(request, title, sort=ORDER_ALPHA):
    """Looks up story by story (not issue or series) title."""
    q_obj = Q(title__icontains = title)
    return generic_by_name(request, title, q_obj, sort, credit="title",
                           selected="story")


def story_by_feature(request, feature, sort=ORDER_ALPHA):
    """Looks up story by feature."""
    q_obj = Q(feature__icontains = feature)
    return generic_by_name(request, feature, q_obj, sort, credit="feature",
                           selected="feature")


def series_by_name(request, series_name, sort=ORDER_ALPHA):
    if settings.USE_ELASTICSEARCH:
        sqs = SearchQuerySet().filter(title_search=GcdNameQuery(series_name)) \
                              .models(Series)
        return generic_by_name(request, series_name, None, sort, Series,
                               'gcd/search/series_list.html', sqs=sqs)
    else:
        q_obj = Q(name__icontains=series_name) | \
                Q(issue__title__icontains=series_name)
        return generic_by_name(request, series_name, q_obj, sort,
                               Series, 'gcd/search/series_list.html')


def series_and_issue(request, series_name, issue_nr, sort=ORDER_ALPHA):
    """ Looks for issue_nr in series_name """
    things = Issue.objects.exclude(deleted=True) \
               .filter(series__name__exact = series_name) \
               .filter(number__exact = issue_nr)

    if things.count() == 1: # if one display the issue
        return HttpResponseRedirect(urlresolvers.reverse(issue,
                                    kwargs={ 'issue_id': things[0].id }))
    else: # if more or none use issue_list.html from search
        context = {
            'items': things,
            'item_name': 'issue',
            'plural_suffix': 's',
            'heading': series_name + ' #' + issue_nr,
        }

        return paginate_response(
          request, things, 'gcd/search/issue_list.html', context)


def compute_isbn_qobj(isbn, prefix, op):
    if stdisbn.is_valid(isbn):
        isbn_compact = stdisbn.compact(isbn)
        q_obj = Q(**{ '%svalid_isbn' % prefix: isbn_compact})
        # need to search for both ISBNs to be safe
        if stdisbn.isbn_type(isbn_compact) == 'ISBN13' and \
          isbn_compact.startswith('978'):
            isbn10 = isbn_compact[3:-1]
            isbn10 += stdisbn._calc_isbn10_check_digit(isbn10)
            q_obj |= Q(**{ '%svalid_isbn' % prefix: isbn10})
        elif stdisbn.isbn_type(isbn_compact) == 'ISBN10':
            q_obj |= Q(**{ '%svalid_isbn' % prefix:
                           stdisbn.to_isbn13(isbn_compact)})
    else:
        q_obj = Q(**{ '%sisbn__%s' % (prefix, op): isbn})
    return q_obj


def issue_by_isbn(request, isbn, sort=ORDER_ALPHA):
    q_obj = compute_isbn_qobj(isbn, '', 'icontains')
    return generic_by_name(request, isbn, q_obj, sort, class_=Issue,
                           template='gcd/search/issue_list.html',
                           credit="isbn")


def issue_by_isbn_name(request, isbn, sort=ORDER_ALPHA):
    """Handle the form-style URL from the basic search form by mapping
    it into the by-name lookup URLs the system already knows how to handle."""

    return HttpResponseRedirect(
      urlresolvers.reverse(issue_by_isbn,
                           kwargs={ 'isbn': isbn, 'sort': sort }))


def issue_by_barcode(request, barcode, sort=ORDER_ALPHA):
    q_obj = Q(barcode__icontains = barcode)
    return generic_by_name(request, barcode, q_obj, sort, class_=Issue,
                           template='gcd/search/issue_list.html',
                           credit="barcode")


def issue_by_barcode_name(request, barcode, sort=ORDER_ALPHA):
    """Handle the form-style URL from the basic search form by mapping
    it into the by-name lookup URLs the system already knows how to handle."""

    return HttpResponseRedirect(
      urlresolvers.reverse(issue_by_barcode,
                           kwargs={ 'barcode': barcode, 'sort': sort }))


def search(request):
    """
    Handle the form-style URL from the basic search form by mapping
    it into the by-name lookup URLs the system already knows how to handle.
    """

    # redirect if url starts with '/search/' but the rest is of no use
    if 'type' not in request.GET:
        return HttpResponseRedirect(urlresolvers.reverse(advanced_search))

    if 'query' not in request.GET or not request.GET['query'] or \
       request.GET['query'].isspace():
        # if no query, but a referer page
        if 'HTTP_REFERER' in request.META:
            return HttpResponseRedirect(request.META['HTTP_REFERER'])
        else: # rare, but possible
            return HttpResponseRedirect(urlresolvers.reverse(advanced_search))

    if 'sort' in request.GET:
        sort = request.GET['sort']
    else:
        sort = ORDER_ALPHA

    if request.GET['type'].find("haystack") >= 0:
        quoted_query = urlquote(request.GET['query'])

    if request.GET['type'] == "mycomics_haystack":
        if sort == ORDER_CHRONO:
            return HttpResponseRedirect(urlresolvers.reverse("mycomics_search") + \
            "?q=%s&sort=year" % quoted_query)
        else:
            return HttpResponseRedirect(urlresolvers.reverse("mycomics_search") + \
            "?q=%s" % quoted_query)

    if request.GET['type'] == "haystack":
        if sort == ORDER_CHRONO:
            return HttpResponseRedirect(urlresolvers.reverse("haystack_search") + \
            "?q=%s&sort=year" % quoted_query)
        else:
            return HttpResponseRedirect(urlresolvers.reverse("haystack_search") + \
            "?q=%s" % quoted_query)

    if request.GET['type'] == "haystack_issue":
        return HttpResponseRedirect(urlresolvers.reverse("haystack_search") + \
          '?q="%s"&search_object=issue&sort=%s' % (quoted_query, sort))

    # TODO: Redesign this- the current setup is a quick hack to adjust
    # a design that was elegant when it was written, but things have changed.
    object_type = str(request.GET['type'])
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

    view = '%s_by_name' % view_type

    if object_type == 'story':
        param_type = 'title'
        view = story_by_title
    elif object_type in ('credit', 'job_number', 'feature'):
        view = 'story_by_%s' % object_type
    elif object_type in ('barcode', 'isbn'):
        view = 'issue_by_%s' % object_type

    if object_type == 'credit':
        param_type = 'name'
    elif object_type in ('series', 'character'):
        param_type = object_type + '_name'
    elif object_type == 'job_number':
        param_type = 'number'

    param_type_value = request.GET['query'].strip().encode('utf-8')
    return HttpResponseRedirect(
      urlresolvers.reverse(view,
                           kwargs={param_type: param_type_value,
                                      'sort': sort}))


def checklist_by_name(request, creator, country=None, language=None):
    creator = creator.replace('+', ' ').title()
    get = request.GET.copy()
    get['target'] = 'issue'
    get['script'] = creator
    get['pencils'] = creator
    get['inks'] = creator
    get['colors'] = creator
    get['letters'] = creator
    get['story_editing'] = creator
    get['logic'] = 'True'
    get['order1'] = 'series'
    get['order2'] = 'date'
    get['method'] = 'icontains'
    if country and Country.objects.filter(code=country).count() == 1:
        get['country'] = country
    if language and Language.objects.filter(code=language).count() == 1:
        get['language'] = language
    request.GET = get.copy()
    get.pop('page', None)

    try:
        items, target = do_advanced_search(request)
    except ViewTerminationError as response:
        return response.response

    context = {
        'item_name': 'issue',
        'plural_suffix': 's',
        'heading': 'Issue Checklist for Creator ' + creator,
        'query_string': get.urlencode(),
    }

    template = 'gcd/search/issue_list.html'

    target, method, logic, used_search_terms = used_search(get)
    context['target'] = target
    context['method'] = method
    context['logic'] = logic
    context['used_search_terms'] = used_search_terms

    return paginate_response(request, items, template, context)

        
def advanced_search(request):
    """Displays the advanced search page."""

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
          response = render(request, 'gcd/search/advanced.html',
          { 'form': form }))

    data = form.cleaned_data
    op = str(data['method'] or 'iregex')

    try:
        stq_obj = search_stories(data, op)
        iq_obj = search_issues(data, op)
        sq_obj = search_series(data, op)
        ipq_obj = search_indicia_publishers(data, op)
        bq_obj = search_brands(data, op)
        bgq_obj = search_brand_groups(data, op)
        pq_obj = search_publishers(data, op)

        # if there are sequence searches limit to type cover
        if data['target'] == 'cover' and stq_obj != None:
            cq_obj = Q(**{ 'issue__story__type': StoryType.objects\
                                                          .get(name='cover') })
        else:
            cq_obj = None
        query = combine_q(data, stq_obj, iq_obj, sq_obj, pq_obj,
                                bq_obj, bgq_obj, ipq_obj, cq_obj)
        terms = compute_order(data)
    except SearchError as se:
        raise ViewTerminationError(render(
          request, 'gcd/search/advanced.html',
          {
              'form': form,
              'error_text': '%s' % se,
          }))

    if (not query) and terms and (not data['keywords']):
        raise ViewTerminationError(render(
          request, 'gcd/search/advanced.html',
          {
            'form': form,
            'error_text': "Please enter at least one search term "
                          "or clear the 'ordering' fields.  Ordered searches "
                          "must have at least one search term."
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
            filter = filter.filter(query)
        items = filter.order_by(*terms).select_related(
          'series__publisher').distinct()

    elif data['target'] in ['cover', 'issue_cover']:
        filter = Cover.objects.exclude(deleted=True)
        if query:
            filter = filter.filter(query)
        items = filter.order_by(*terms).select_related(
          'issue__series__publisher').distinct()

    elif data['target'] == 'sequence':
        filter = Story.objects.exclude(deleted=True)
        if query:
            filter = filter.filter(query)
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

    if search_values['logic'] == 'True':
        logic = 'OR credits, AND other fields'
    else:
        logic = 'AND all fields'
    del search_values['logic']

    used_search_terms = []
    if 'type' in search_values:
        types = StoryType.objects.filter(id__in=\
          search_values.getlist('type')).values_list('name', flat=True)
        text = types[0]
        for storytype in types[1:]:
            text += ', %s' % storytype
        used_search_terms.append(('type', text))
        del search_values['type']
    if 'publication_type' in search_values:
        types = SeriesPublicationType.objects.filter(id__in=\
          search_values.getlist('publication_type')).values_list('name',
                                                                 flat=True)
        text = types[0]
        for publication_type in types[1:]:
            text += ', %s' % publication_type
        used_search_terms.append(('publication_type', text))
        del search_values['publication_type']
    if 'country' in search_values:
        countries = Country.objects.filter(code__in=\
          search_values.getlist('country')).values_list('name', flat=True)
        text = countries[0]
        for country in countries[1:]:
            text += ', %s' % country
        used_search_terms.append(('country', text))
        del search_values['country']
    if 'language' in search_values:
        languages = Language.objects.filter(code__in=\
          search_values.getlist('language')).values_list('name', flat=True)
        text = languages[0]
        for language in languages[1:]:
            text += ', %s' % language
        used_search_terms.append(('language', text))
        del search_values['language']
    if 'indexer' in search_values:
        indexers = Indexer.objects.filter(id__in=\
          search_values.getlist('indexer'))
        text = str(indexers[0])
        for indexer in indexers[1:]:
            text += ', %s' % str(indexer)
        used_search_terms.append(('indexer', text))
        del search_values['indexer']
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

    count = items.count()
    if count and 'random_search' in request.GET:
        # using DB random via order_by('?') is rather expensive
        select = randint(0, count-1)
        # nullify imposed ordering, use db one
        item = items.order_by()[select]
        return HttpResponseRedirect(item.get_absolute_url())

    item_name = target
    plural_suffix = 's'
    if item_name == 'sequence':
        item_name = 'content item'
    elif item_name == 'feature':
        item_name = 'content_series'
        plural_suffix = ''
    elif item_name == 'series':
        plural_suffix = ''

    # Store the URL minus the page setting so that we can use
    # it to build the URLs for the links to other pages.
    get_copy = request.GET.copy()
    get_copy.pop('page', None)

    context = {
        'advanced_search': True,
        'item_name': item_name,
        'plural_suffix': plural_suffix,
        'heading': target.title() + ' Search Results',
        'query_string': get_copy.urlencode(),
    }

    template = 'gcd/search/%s_list.html' % \
                 ('content' if target == 'sequence' else item_name)

    search_values = request.GET.copy()
    target, method, logic, used_search_terms = used_search(search_values)
    context['target'] = target
    context['method'] = method
    context['logic'] = logic
    context['used_search_terms'] = used_search_terms

    if export_csv:
        fields = [f.name for f in items.model._meta.get_fields()
                              if f.auto_created==False]
        fields = [f for f in fields if f not in {'created', 'modified',
                                                 'deleted', 'keywords',
                                                 'tagged_items'}]
        fields.insert(0, 'id')
        return render_to_csv_response(items.values(*fields),
                                      append_datestamp=True)

    if item_name in ['cover', 'issue_cover']:
        context['table_width'] = COVER_TABLE_WIDTH
        context['NO_ADS'] = True
        return paginate_response(request, items, template, context,
                                 per_page=50, callback_key='tags',
                                 callback=get_image_tags_per_page)
    else:
        return paginate_response(request, items, template, context)


def combine_q(data, *qobjs):
    """
    The queries against each table must be anded as they will be run using
    JOINs in a single query.  The method compute_prefix adjusted the query
    terms to work with the JOIN as they were added in each of the
    search_* methods.
    """
    filtered = [x for x in qobjs if x != None]
    if filtered:
        return reduce(lambda x, y: x & y, filtered)
    return None


def search_dates(data, formatter=lambda d: d.year,
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
          { '%s__gte' % start_name: formatter(data['start_date']) }
        end_after_start = \
          { '%s__gte' % end_name: formatter(data['start_date']) }

        if data['end_date']:
            q_and_only.append(Q(**begin_after_start) & Q(**end_after_start))
        else:
            q_and_only.append(Q(**begin_after_start))

    if data['end_date']:
        begin_before_end = \
          { '%s__lte' % start_name: formatter(data['end_date']) }
        end_before_end = \
          { '%s__lte' % end_name: formatter(data['end_date']) }

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
        q_and_only.append(Q(**{ '%scountry__code__in' % prefix:
                                data['country'] }))
    if target == 'publisher':
        q_and_only.extend(search_dates(data,
                                       start_name='%syear_began' % prefix,
                                       end_name='%syear_ended' % prefix))

    q_objs = []
    if data['pub_name']:
        pub_name_q = Q(**{ '%sname__%s' % (prefix, op): data['pub_name'] })
        q_objs.append(pub_name_q)
    # one more like this and we should refactor the code :-)
    if data['pub_notes']:
        pub_notes_q = Q(**{ '%snotes__%s' % (prefix, op):
                            data['pub_notes'] })
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
          Q(**{ '%sname__%s' % (prefix, op): data['brand_group'] }))
    if data['brand_notes']:
        q_objs.append(
          Q(**{ '%snotes__%s' % (prefix, op): data['brand_notes'] }))

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
            return Q(**{ '%sisnull' % prefix: True }) & Q(**{ 'no_brand': False })
        if data['brand_emblem'] == IS_NONE and target == 'issue':
            return Q(**{ 'no_brand': True })
        q_objs.append(
          Q(**{ '%sname__%s' % (prefix, op): data['brand_emblem'] }))
    if data['brand_notes']:
        q_objs.append(
          Q(**{ '%snotes__%s' % (prefix, op): data['brand_notes'] }))

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
            return Q(**{ '%sisnull' % prefix: True })
        q_objs.append(
          Q(**{ '%sname__%s' % (prefix, op): data['indicia_publisher'] }))
    if data['ind_pub_notes']:
        q_objs.append(
          Q(**{ '%snotes__%s' % (prefix, op): data['ind_pub_notes'] }))
    if data['is_surrogate'] is not None:
        if data['is_surrogate'] is True:
            q_objs.append(Q(**{ '%sis_surrogate' % prefix: True }))
        else:
            q_objs.append(Q(**{ '%sis_surrogate' % prefix: False }))

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
        publication_type_qargs = { '%spublication_type__in' % prefix:
                                   data['publication_type'] }
        q_and_only.append(Q(**publication_type_qargs))

    if data['language']:
        language_qargs = { '%slanguage__code__in' % prefix: data['language'] }
        q_and_only.append(Q(**language_qargs))

    q_objs = []
    if data['series']:
        q_objs.append(Q(**{ '%sname__%s' % (prefix, op): data['series'] }))
    if 'series_year_began' in data and data['series_year_began']:
        q_and_only.append(Q(**{ '%syear_began' % prefix: int(data['series_year_began']) }))
    if data['series_notes']:
        q_objs.append(Q(**{ '%snotes__%s' % (prefix, op):
                            data['series_notes'] }))
    if data['tracking_notes']:
        q_objs.append(Q(**{ '%stracking_notes__%s' % (prefix, op):
                             data['tracking_notes']}))
    if data['not_reserved']:
        q_objs.append(Q(**{ '%songoing_reservation__isnull' % prefix: True }) &
                      Q(**{ '%sis_current' % prefix: True }))
    if data['is_current']:
        q_objs.append(Q(**{ '%sis_current' % prefix: True }))
    if data['is_comics'] is not None:
        if data['is_comics'] is True:
            q_objs.append(Q(**{ '%sis_comics_publication' % prefix: True }))
        else:
            q_objs.append(Q(**{ '%sis_comics_publication' % prefix: False }))

    # Format fields
    if data['color']:
        q_objs.append(Q(**{ '%scolor__%s' % (prefix, op): data['color'] }))
    if data['dimensions']:
        q_objs.append(Q(**{ '%sdimensions__%s' % (prefix, op):
                            data['dimensions'] }))
    if data['paper_stock']:
        q_objs.append(Q(**{ '%spaper_stock__%s' % (prefix, op):
                            data['paper_stock'] }))
    if data['binding']:
        q_objs.append(Q(**{ '%sbinding__%s' % (prefix, op): data['binding'] } ))
    if data['publishing_format']:
        q_objs.append(Q(**{ '%spublishing_format__%s' % (prefix, op):
                            data['publishing_format'] }))

    try:
        if data['issue_count'] is not None and data['issue_count'] != '':
            range_match = match(COUNT_RANGE_REGEXP, data['issue_count'])
            if range_match:
                if not range_match.group('min'):
                    q_objs.append(Q(**{ '%sissue_count__lte' % prefix:
                                        int(range_match.group('max')) }))
                elif not range_match.group('max'):
                    q_objs.append(Q(**{ '%sissue_count__gte' % prefix:
                                        int(range_match.group('min')) }))
                else:
                    q_objs.append(Q(**{ '%sissue_count__range' % prefix:
                                        (int(range_match.group('min')),
                                         int(range_match.group('max'))) }))
            else:
                q_objs.append(Q(**{ '%sissue_count__exact' % prefix:
                                    int(data['issue_count']) }))
    except ValueError:
        raise SearchError("Issue count must be an integer or an integer "
                            "range reparated by a hyphen (e.g. 100-200, "
                            "100-, -200).")

    if q_and_only or q_objs:
        q_and_only.append(Q(**{'%sdeleted__exact' % prefix: False}))

    return compute_qobj(data, q_and_only, q_objs)


def search_issues(data, op, stories_q=None):
    """
    Handle issue fields.
    """
    target = data['target']
    prefix = compute_prefix(target, 'issue')

    q_and_only = []
    if target in ['issue', 'cover', 'issue_cover', 'feature', 'sequence']:
        date_formatter = lambda d: '%04d-%02d-%02d' % (d.year, d.month, d.day)
        if data['use_on_sale_date']:
            q_and_only.extend(search_dates(data, date_formatter,
                                        '%son_sale_date' % prefix,
                                        '%son_sale_date' % prefix))
        else:
            q_and_only.extend(search_dates(data, date_formatter,
                                        '%skey_date' % prefix,
                                        '%skey_date' % prefix))

    if data['price']:
        q_and_only.append(Q(**{ '%sprice__%s' % (prefix, op): data['price'] }))

    q_objs = []
    if data['issues']:
        q_objs.append(handle_numbers('issues', data, prefix))
    if data['volume']:
        q_objs.append(handle_numbers('volume', data, prefix))
    if data['issue_title']:
        q_objs.append(Q(**{ '%stitle__%s' % (prefix, op): \
                        data['issue_title'] }) &\
                      Q(**{ '%sseries__has_issue_title' % prefix: True }))
    if data['variant_name']:
        q_objs.append(Q(**{ '%svariant_name__%s' % (prefix, op): \
                        data['variant_name'] }))
    if data['is_variant'] is not None:
        if data['is_variant'] is True:
            q_objs.append(~Q(**{ '%svariant_of' % prefix: None }))
        else:
            q_objs.append(Q(**{ '%svariant_of' % prefix: None }))
    if data['issue_date']:
        q_objs.append(
          Q(**{ '%spublication_date__%s' % (prefix, op): data['issue_date'] }))
    if data['cover_needed']:
        q_objs.append(Q(**{ '%scover__isnull' % prefix: True }) |
                      ~Q(**{ '%scover__deleted' % prefix: False }) |
                      Q(**{ '%scover__marked' % prefix: True }))
    if data['is_indexed'] is not None:
        if data['is_indexed'] is True:
            q_objs.append(Q(**{ '%sis_indexed' % prefix: INDEXED['full'] }) &\
                          Q(**{ '%svariant_of' % prefix: None }))
        else:
            q_objs.append(~Q(**{ '%sis_indexed' % prefix: INDEXED['full'] }) &\
                          Q(**{ '%svariant_of' % prefix: None }))
    if data['image_resources'] is not None:
        if 'has_soo' in data['image_resources']:
            q_objs.append(Q(**{ '%simage_resources__type__name' % prefix: 'SoOScan' }))
        if 'needs_soo' in data['image_resources']:
            q_objs.append(\
              ( (~Q(**{ '%simage_resources__type__name' % prefix: 'SoOScan' })) \
                 & Q(**{ '%sstory__type' % prefix: STORY_TYPES['soo'] })) \
              | Q(**{ '%simage_resources__marked' % prefix: True }))
        if 'has_indicia' in data['image_resources']:
            q_objs.append(\
              Q(**{ '%simage_resources__type__name' % prefix: 'IndiciaScan' }))
        if 'needs_indicia' in data['image_resources']:
            q_objs.append(\
              (~Q(**{ '%simage_resources__type__name' % prefix: 'IndiciaScan' }))\
              | Q(**{ '%simage_resources__marked' % prefix: True }))
    if data['indexer']:
        q_objs.append(
          Q(**{ '%srevisions__changeset__indexer__indexer__in' % prefix:
                data['indexer'] }) &
          Q(**{ '%srevisions__changeset__state' % prefix: states.APPROVED }))
    if data['isbn']:
        q_objs.append(compute_isbn_qobj(data['isbn'], prefix, op) &\
                             Q(**{ '%sseries__has_isbn' % prefix: True }))
    if data['barcode']:
        q_objs.append(Q(**{ '%sbarcode__%s' % (prefix, op): data['barcode'] }) &\
                             Q(**{ '%sseries__has_barcode' % prefix: True }))
    if data['indicia_frequency']:
        q_objs.append(Q(**{ '%sindicia_frequency__%s' % (prefix, op): \
                             data['indicia_frequency'] }) &\
                      Q(**{ '%sseries__has_indicia_frequency' % prefix: True }))
    if data['rating']:
        q_objs.append(Q(**{ '%srating__%s' % (prefix, op): data['rating'] }) &\
                             Q(**{ '%sseries__has_rating' % prefix: True }))
    if data['issue_notes']:
        q_objs.append(Q(**{ '%snotes__%s' % (prefix, op): data['issue_notes'] }))

    if data['issue_reprinted'] is not None:
        if data['issue_reprinted'] == True:
            q_objs.append(Q(**{ '%sfrom_reprints__isnull' % prefix: False }) | \
                   Q(**{ '%sfrom_issue_reprints__isnull' % prefix: False }))
        else:
            q_objs.append(Q(**{ '%sto_reprints__isnull' % prefix: False }) | \
                   Q(**{ '%sto_issue_reprints__isnull' % prefix: False }))

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
                q_objs.append(Q(**{ '%spage_count__range' % prefix:
                                    (page_start, page_end) }))
            else:
                q_objs.append(Q(**{ '%spage_count' % prefix:
                                    Decimal(data['issue_pages']) }))
    except ValueError:
        raise SearchError("Page count must be a decimal number or a pair of "
                            "decimal numbers separated by a hyphen.")
    if data['issue_pages_uncertain'] is not None:
        q_objs.append(Q(**{ '%spage_count_uncertain' % \
                            prefix: data['issue_pages_uncertain'] }))

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
            q_or_only.append(Q(**{ '%snumber__in' % prefix: nums_in }))
        else:
            q_or_only.append(Q(**{ '%svolume__in' % prefix: nums_in }) &\
                             Q(**{ '%sseries__has_volume' % prefix: True }))

    # add verbatim search when nothing processed (e.g. 100-1) or actual range
    if len(nums_in) != 1:
        if field == 'issues':
            q_or_only.append(Q(**{ '%snumber' % prefix: data[field] }))
        else:
            q_or_only.append(Q(**{ '%svolume' % prefix: data[field] }) &\
                                Q(**{ '%sseries__has_volume' % prefix: True }))

    return reduce(lambda x, y: x | y, q_or_only)


def search_stories(data, op):
    """
    Build the query against the story table.  As it is the lowest
    table in the hierarchy, there are no possible subqueries to run.
    """
    target = data['target']
    prefix = compute_prefix(target, 'sequence')

    q_objs = []
    q_and_only = []

    for field in ('script', 'pencils', 'inks', 'colors', 'letters'):
        if data[field]:
            q_objs.append(Q(**{ '%s%s__%s' % (prefix, field, op):
                                data[field] }))

    for field in ('feature', 'title', 'first_line', 'job_number', 'characters',
                  'synopsis', 'reprint_notes', 'notes'):
        if data[field]:
            q_and_only.append(Q(**{ '%s%s__%s' % (prefix, field, op):
                                data[field] }))

    if data['type']:
        q_and_only.append(Q(**{ '%stype__in' % prefix: data['type'] }))

    if data['genre']:
        for genre in data['genre']:
            q_and_only.append(Q(**{ '%sgenre__icontains' % prefix: genre }))

    if data['story_editing']:
        q_objs.append(Q(**{ '%sediting__%s' % (prefix, op):
                            data['story_editing'] }))

    if data['story_reprinted'] != '':
        if data['story_reprinted'] == 'from':
            q_objs.append(Q(**{ '%sfrom_reprints__isnull' % prefix: False }) | \
                   Q(**{ '%sfrom_issue_reprints__isnull' % prefix: False }))
        elif data['story_reprinted'] == 'in':
            q_objs.append(Q(**{ '%sto_reprints__isnull' % prefix: False }) | \
                   Q(**{ '%sto_issue_reprints__isnull' % prefix: False }))
        elif data['story_reprinted'] == 'not':
            q_objs.append(Q(**{ '%sfrom_reprints__isnull' % prefix: True }) & \
                   Q(**{ '%sfrom_issue_reprints__isnull' % prefix: True }))
    try:
        if data['pages'] is not None and data['pages'] != '':
            range_match = match(PAGE_RANGE_REGEXP, data['pages'])
            if range_match:
                page_start = Decimal(range_match.group('begin'))
                page_end = Decimal(range_match.group('end'))
                q_and_only.append(Q(**{ '%spage_count__range' % prefix:
                                        (page_start, page_end) }))
            else:
                q_and_only.append(Q(**{ '%spage_count' % prefix:
                                        Decimal(data['pages']) }))
    except ValueError:
        raise SearchError("Page count must be a decimal number or a pair of "
                            "decimal numbers separated by a hyphen.")

    if data['pages_uncertain'] is not None:
        q_objs.append(Q(**{ '%spage_count_uncertain' % \
                            prefix: data['pages_uncertain'] }))

    if q_and_only or q_objs:
        q_and_only.append(Q(**{'%sdeleted__exact' % prefix: False}))

    # since issue_editing is credit use it here to allow correct 'OR' behavior
    if data['issue_editing']:
        if target == 'sequence': # no prefix in this case
            q_objs.append(Q(**{ 'issue__editing__%s' % op:
                                data['issue_editing'] }))
        else: # cut off 'story__'
            q_objs.append(Q(**{ '%sediting__%s' % (prefix[:-7], op):
                                data['issue_editing'] }))

    return compute_qobj(data, q_and_only, q_objs)


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
            raise SearchError('Cannot search for Indicia Publishers by '
              'Publisher Brand attributes, as they are not directly related')
        if target == 'publisher':
            return 'brandgroup__'
        if target == 'issue':
            return 'brand__group__'
        if target in ('series', 'sequence', 'feature', 'cover', 'issue_cover'):
            return 'issue__brand__group__'
    elif current == 'brand_emblem':
        if target == 'indicia_publisher':
            raise SearchError('Cannot search for Indicia Publishers by '
              'Publisher Brand attributes, as they are not directly related')
        if target == 'publisher':
            return 'brandgroup__brand__'
        if target == 'issue':
            return 'brand__'
        if target in ('series', 'sequence', 'feature', 'cover', 'issue_cover'):
            return 'issue__brand__'
    elif current == 'indicia_publisher':
        if target in ('brand_group', 'brand_emblem'):
            raise SearchError('Cannot search for Publisher Brands by '
              'Indicia Publisher attributes, as they are not directly related')
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
        if data['logic'] == 'True':
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

