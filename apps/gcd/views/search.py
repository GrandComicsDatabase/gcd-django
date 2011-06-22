# -*- coding: utf-8 -*-
"""
View methods related to displaying search and search results pages.
"""

from re import *
from urllib import urlopen, quote, urlencode
from decimal import Decimal
from string import capitalize
from stdnum import isbn as stdisbn

from django.db.models import Q
from django.conf import settings
from django.shortcuts import render_to_response, \
                             get_object_or_404, \
                             get_list_or_404
from django.http import HttpResponseRedirect
from django.core import urlresolvers
from django.views.generic.list_detail import object_list
from django.template import RequestContext

from apps.gcd.models import Publisher, Series, Issue, Cover, Story, StoryType,\
                            Country, Language, Indexer, Brand, IndiciaPublisher
from apps.gcd.views import ViewTerminationError, paginate_response, \
                           ORDER_ALPHA, ORDER_CHRONO
from apps.gcd.forms.search import AdvancedSearch, PAGE_RANGE_REGEXP, \
                                  COUNT_RANGE_REGEXP
from apps.gcd.views.details import issue, COVER_TABLE_WIDTH, IS_EMPTY, IS_NONE
from apps.gcd.views.covers import get_image_tags_per_page

# Should not be importing anything from oi, but we're doing this in several places.
# TODO: states should probably live somewhere else.
from apps.oi import states

class SearchError(Exception):
    pass

def generic_by_name(request, name, q_obj, sort,
                    class_=Story,
                    template='gcd/search/content_list.html',
                    credit=None,
                    related=[]):
    """
    Helper function for the most common search cases.
    """
    name = name.encode('utf-8')
    base_name = 'unknown'
    plural_suffix = 's'
    query_val = {'method': 'icontains'}
    
    if (class_ in (Series, Brand, IndiciaPublisher)):
        if class_ is IndiciaPublisher:
            base_name = 'indicia_publisher'
            display_name = 'Indicia Publisher'
        else:
            display_name = class_.__name__
            base_name = display_name.lower()
        plural_suffix = '' if class_ is Series else 's'
        sort_name = "sort_name" if class_ is Series else "name"
        things = class_.objects.exclude(deleted=True).filter(q_obj)
        if related:
            things = things.select_related(*related)
        if (sort == ORDER_ALPHA):
            things = things.order_by(sort_name, "year_began")
        elif (sort == ORDER_CHRONO):
            things = things.order_by(year_began, sort_name)
        heading = '%s Search Results' % display_name
        # query_string for the link to the advanced search
        query_val['target'] = base_name
        query_val[base_name] = name

    elif class_ is Issue:
        base_name = 'issue'
        things = Issue.objects.exclude(deleted=True).filter(q_obj) \
                   .select_related('series__publisher')
        if (sort == ORDER_ALPHA):
            things = things.order_by("series__sort_name", "key_date")
        elif (sort == ORDER_CHRONO):
            things = things.order_by("key_date", "series__sort_name")
        heading = 'Issue Search Results'
        # query_string for the link to the advanced search
        query_val['target'] = 'issue'
        query_val['isbn'] = name

    elif (class_ is Story):
        # TODO: move this outside when series deletes are implemented
        q_obj &= Q(deleted=False)

        base_name = 'stor'
        plural_suffix = 'y,ies'

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
        heading = 'Story Search Results'
        # build the query_string for the link to the advanced search
        query_val['target'] = 'sequence'
        if credit in ['script', 'pencils', 'inks', 'colors', 'letters',
                      'job_number']:
            query_val[credit] = name
        # remove the ones which are not matched in display of results
        elif credit in ['reprint', 'title', 'feature']:
            query_val[credit] = name
            credit = None
        elif credit.startswith('editing_search'):
            query_val['story_editing'] = name
            query_val['issue_editing'] = name
            query_val['logic'] = True
        elif credit.startswith('any'):
            query_val['logic'] = True
            for credit_type in ['script', 'pencils', 'inks', 'colors', 
                                'letters', 'story_editing', 'issue_editing']:
                query_val[credit_type] = name
        elif credit.startswith('characters'):
            query_val['characters'] = name
            # OR-logic only applies to credits, so we cannnot use it 
            # to mimic the double search for characters and features here
            # query_val['feature'] = name 
            # query_val['logic'] = True
    else:
        raise TypeError, "Unsupported search target!"

    if (sort == ORDER_ALPHA):
        change_order = request.path.replace('alpha', 'chrono')
    elif (sort == ORDER_CHRONO):
        change_order = request.path.replace('chrono', 'alpha')

    vars = { 'item_name': base_name,
             'plural_suffix': plural_suffix,
             'heading': heading,
             'search_term': name,
             'media_url': settings.MEDIA_URL, 
             'query_string': urlencode(query_val),
             'change_order': change_order,
             'which_credit': credit }
    return paginate_response(request, things, template, vars)

def publishers_by_name(request, publisher_name, sort=ORDER_ALPHA):
    #Finds publishers and imprints

    pubs = Publisher.objects.exclude(deleted=True).filter(
      name__icontains = publisher_name)
    if (sort == ORDER_ALPHA):
        pubs = pubs.order_by('name', 'year_began')
    elif (sort == ORDER_CHRONO):
        pubs = pubs.order_by('year_began', 'name')

    get_copy = request.GET.copy()
    get_copy.pop('page', None)

    return paginate_response(request, pubs, 'gcd/search/publisher_list.html',
        { 'items': pubs,
          'item_name': 'publisher',
          'plural_suffix': 's',
          'heading': 'Publisher Search Results',
          'query_string': get_copy.urlencode(),
        })

def brand_by_name(request, brand_name, sort=ORDER_ALPHA):
    q_obj = Q(name__icontains=brand_name)
    return generic_by_name(request, brand_name, q_obj, sort,
                           Brand, 'gcd/search/brand_list.html')

def indicia_publisher_by_name(request, ind_pub_name, sort=ORDER_ALPHA):
    q_obj = Q(name__icontains=ind_pub_name)
    return generic_by_name(request, ind_pub_name, q_obj, sort,
                           IndiciaPublisher,
                           'gcd/search/indicia_publisher_list.html')

def character_by_name(request, character_name, sort=ORDER_ALPHA):
    """Find stories based on characters.  Since characters for whom a feature
    is named are often not also listed under character appearances, this
    search looks at both the feature and characters fields."""

    q_obj = Q(characters__icontains=character_name) | \
            Q(feature__icontains=character_name)
    return generic_by_name(request, character_name, q_obj, sort, 
                           credit="characters:" + character_name)


def writer_by_name(request, writer, sort=ORDER_ALPHA):
    q_obj = Q(script__icontains=writer)
    return generic_by_name(request, writer, q_obj, sort, credit="script")


def penciller_by_name(request, penciller, sort=ORDER_ALPHA):
    q_obj = Q(pencils__icontains=penciller)
    return generic_by_name(request, penciller, q_obj, sort, credit="pencils")


def inker_by_name(request, inker, sort=ORDER_ALPHA):
    q_obj = Q(inks__icontains=inker)
    return generic_by_name(request, inker, q_obj, sort, credit="inks")


def colorist_by_name(request, colorist, sort=ORDER_ALPHA):
    q_obj = Q(colors__icontains=colorist)
    return generic_by_name(request, colorist, q_obj, sort, credit="colors")


def letterer_by_name(request, letterer, sort=ORDER_ALPHA):
    q_obj = Q(letters__icontains=letterer)
    return generic_by_name(request, letterer, q_obj, sort, credit="letters")


def editor_by_name(request, editor, sort=ORDER_ALPHA):
    q_obj = Q(editing__icontains=editor) | Q(issue__editing__icontains=editor)
    return generic_by_name(request, editor, q_obj, sort, 
                           credit="editing_search:"+editor)


def story_by_credit(request, name, sort=ORDER_ALPHA):
    """Implements the 'Any Credit' story search."""
    q_obj = Q(script__icontains=name) | \
            Q(pencils__icontains=name) | \
            Q(inks__icontains=name) | \
            Q(colors__icontains=name) | \
            Q(letters__icontains=name) | \
            Q(editing__icontains=name) | \
            Q(issue__editing__icontains=name)
    return generic_by_name(request, name, q_obj, sort, credit=('any:'+name))


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
    return generic_by_name(request, title, q_obj, sort, credit="title")


def story_by_feature(request, feature, sort=ORDER_ALPHA):
    """Looks up story by feature."""
    q_obj = Q(feature__icontains = feature)
    return generic_by_name(request, feature, q_obj, sort, credit="feature")
    

def series_by_name(request, series_name, sort=ORDER_ALPHA):
    q_obj = Q(name__icontains = series_name)
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

def search(request):
    """
    Handle the form-style URL from the basic search form by mapping
    it into the by-name lookup URLs the system already knows how to handle.
    """

    # redirect if url starts with '/search/' but the rest is of no use
    if not request.GET.has_key('type'):
        return HttpResponseRedirect(urlresolvers.reverse(advanced_search))

    if not request.GET.has_key('query') or not request.GET['query'] or \
       request.GET['query'].isspace():
        # if no query, but a referer page
        if request.META.has_key('HTTP_REFERER'):
            return HttpResponseRedirect(request.META['HTTP_REFERER'])
        else: # rare, but possible
            return HttpResponseRedirect(urlresolvers.reverse(advanced_search))

    # TODO: Redesign this- the current setup is a quick hack to adjust
    # a design that was elegant when it was written, but things have changed.
    object_type = str(request.GET['type'])
    param_type = object_type
    view_type = object_type
    if view_type == 'publisher':
        view_type += 's'
        param_type = 'publisher_name'
    elif view_type == 'brand':
        param_type = 'brand_name'
    elif view_type == 'indicia_publisher':
        param_type = 'ind_pub_name'

    view = 'apps.gcd.views.search.%s_by_name' % view_type

    if object_type == 'story':
        param_type = 'title'
        view = story_by_title
    elif object_type in ('credit', 'job_number', 'feature'):
        view = 'apps.gcd.views.search.story_by_%s' % object_type

    if object_type == 'credit':
        param_type = 'name'
    elif object_type in ('series', 'character'):
        param_type = object_type + '_name'
    elif object_type == 'job_number':
        param_type = 'number'

    if 'sort' in request.GET:
        sort = request.GET['sort']
    else:
        sort = ORDER_ALPHA

    param_type_value = quote(request.GET['query'].strip().encode('utf-8'))
    return HttpResponseRedirect(
      urlresolvers.reverse(view,
                           kwargs = { param_type: param_type_value,
                                      'sort': sort }))


def advanced_search(request):
    """Displays the advanced search page."""

    if ('target' not in request.GET):
        return render_to_response('gcd/search/advanced.html',
          { 'form': AdvancedSearch(auto_id=True) },
          context_instance=RequestContext(request))
    else:
        search_values = request.GET.copy()
        search_values_as_list = dict(request.GET.lists())
        # convert a bit since MultipleChoiceField takes a list of IDs
        search_values['type'] = search_values.getlist('type')
        search_values['indexer'] = search_values.getlist('indexer')
        search_values['country'] = search_values.getlist('country')
        search_values['language'] = search_values.getlist('language')
        return render_to_response('gcd/search/advanced.html',
          { 'form': AdvancedSearch(initial=search_values) },
          context_instance=RequestContext(request))

def do_advanced_search(request):
    """
    Runs advanced searches.
    """
    form = AdvancedSearch(request.GET)
    if not form.is_valid():
        raise ViewTerminationError(response = render_to_response(
          'gcd/search/advanced.html',
          { 'form': form },
          context_instance=RequestContext(request)))

    data = form.cleaned_data
    op = str(data['method'] or 'iregex')

    try:
        stq_obj = search_stories(data, op)
        iq_obj = search_issues(data, op)
        sq_obj = search_series(data, op)
        ipq_obj = search_indicia_publishers(data, op)
        bq_obj = search_brands(data, op)
        pq_obj = search_publishers(data, op)

        # if there are sequence searches limit to type cover
        if data['target'] == 'cover' and stq_obj != None:
            cq_obj = Q(**{ 'issue__story__type': StoryType.objects\
                                                          .get(name='cover') })
        else:
            cq_obj = None
        query = combine_q(data, stq_obj, iq_obj, sq_obj, pq_obj,
                                bq_obj, ipq_obj, cq_obj)
        terms = compute_order(data)
    except SearchError, se:
        raise ViewTerminationError, render_to_response(
          'gcd/search/advanced.html',
          {
              'form': form,
              'error_text': '%s' % se,
          },
          context_instance=RequestContext(request))

    if (not query) and terms:
        raise ViewTerminationError, render_to_response(
          'gcd/search/advanced.html',
          {
            'form': form,
            'error_text': "Please enter at least one search term "
                          "or clear the 'ordering' fields.  Ordered searches "
                          "must have at least one search term."
          },
          context_instance=RequestContext(request))
        
    items = []
    if data['target'] == 'publisher':
        filter = Publisher.objects.exclude(deleted=True)
        if query:
            filter = filter.filter(query)
        items = filter.order_by(*terms).select_related('country').distinct()

    elif data['target'] == 'brand':
        filter = Brand.objects.exclude(deleted=True)
        if query:
            filter = filter.filter(query)
        items = filter.order_by(*terms).select_related('parent').distinct()

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

    elif data['target'] == 'cover':
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

    return items, data['target']


def used_search(search_values):
    del search_values['order1']
    del search_values['order2']
    del search_values['order3']
    if search_values['target'] == 'sequence':
        target = 'Stories'
    elif search_values['target'] == 'indicia_publisher':
        target = 'Indicia Publishers'
    elif search_values['target'] == 'brand':
        target = "Publisher's Brands"
    else:
        target = capitalize(search_values['target'])
        if target[-1] != 's':
            target += 's'

    del search_values['target']
    
    if search_values['method'] == 'iexact':
        method = 'Matches Exactly'
    elif search_values['method'] == 'exact':
        method = 'Matches Excactly (case sensitive)'
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
        text = unicode(indexers[0])
        for indexer in indexers[1:]:
            text += ', %s' % unicode(indexer)
        used_search_terms.append(('indexer', text))
        del search_values['indexer']
    for i in search_values:
        if search_values[i] and search_values[i] not in ['None', 'False']:
            used_search_terms.append((i, search_values[i]))
    return target, method, logic, used_search_terms

def process_advanced(request):
    """
    Runs advanced searches.
    """
    
    try:
        items, target = do_advanced_search(request)
    except ViewTerminationError, response:
        return response.response

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
    
    if item_name == 'cover':
        context['table_width'] = COVER_TABLE_WIDTH
        return paginate_response(request, items, template, context,
                             page_size=50, callback_key='tags',
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
    filtered = filter(lambda x: x != None, qobjs)
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
            q_and_only.append(Q(**begin_after_start) | Q(**end_after_start))
        else:
            q_and_only.append(Q(**end_after_start))

    if data['end_date']:
        begin_before_end = \
          { '%s__lte' % start_name: formatter(data['end_date']) }
        end_before_end = \
          { '%s__lte' % end_name: formatter(data['end_date']) }

        if data['start_date']:
            q_and_only.append(Q(**begin_before_end) | Q(**end_before_end))
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
        if target == 'publisher':
            q_objs.append(pub_name_q)
        else:
            imprint_prefix = compute_prefix(target, 'series')
            imprint_q = Q(**{ '%simprint__name__%s' % (imprint_prefix, op):
                              data['pub_name'] })
            q_objs.append(pub_name_q | imprint_q)
    # one more like this and we should refactor the code :-)
    if data['pub_notes']:
        pub_notes_q = Q(**{ '%snotes__%s' % (prefix, op):
                            data['pub_notes'] })
        if target == 'publisher':
            q_objs.append(pub_notes_q)
        else:
            imprint_prefix = compute_prefix(target, 'series')
            imprint_q = Q(**{ '%simprint__notes__%s' % (imprint_prefix, op):
                              data['pub_notes'] })
            q_objs.append(pub_notes_q | imprint_q)

    if q_and_only or q_objs:
        q_and_only.append(Q(**{'%sdeleted__exact' % prefix: False}))
    return compute_qobj(data, q_and_only, q_objs)

def search_brands(data, op):
    """
    Handle brand fields.
    """
    target = data['target']
    prefix = compute_prefix(target, 'brand')

    q_and_only = []
    q_objs = []
    if data['brand']:
        if data['brand'] == IS_EMPTY:
            return Q(**{ '%sisnull' % prefix: True }) & Q(**{ 'no_brand': False })
        if data['brand'] == IS_NONE:
            return Q(**{ 'no_brand': True })
        q_objs.append(
          Q(**{ '%sname__%s' % (prefix, op): data['brand'] }))
    if data['brand_notes']:
        q_objs.append(
          Q(**{ '%notes__%s' % (prefix, op): data['brand_notes'] }))

    if q_and_only or q_objs:
        q_and_only.append(Q(**{'%sdeleted__exact' % prefix: False}))
    return compute_qobj(data, q_and_only, q_objs)

def search_indicia_publishers(data, op):
    """
    Handle indicia_publisher fields.
    """
    target = data['target']
    prefix = compute_prefix(target, 'indicia_publisher')

    q_and_only = []
    q_objs = []
    if data['indicia_publisher']:
        if data['indicia_publisher'] == IS_EMPTY:
            return Q(**{ '%sisnull' % prefix: True })
        q_objs.append(
          Q(**{ '%sname__%s' % (prefix, op): data['indicia_publisher'] }))
    if data['ind_pub_notes']:
        q_objs.append(
          Q(**{ '%notes__%s' % (prefix, op): data['ind_pub_notes'] }))
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

    if data['language']:
        language_qargs = { '%slanguage__code__in' % prefix: data['language'] }
        q_and_only.append(Q(**language_qargs))

    q_objs = []
    if data['series']:
        q_objs.append(Q(**{ '%sname__%s' % (prefix, op): data['series'] }))
    if 'series_year_began' in data and data['series_year_began']:
        q_and_only.append(Q(**{ '%syear_began' % prefix: int(data['series_year_began']) }))
    if data['format']:
        q_objs.append(Q(**{ '%sformat__%s' % (prefix, op):  data['format'] }))
    if data['series_notes']:
        q_objs.append(Q(**{ '%snotes__%s' % (prefix, op):
                            data['series_notes'] }))
    if data['tracking_notes']:
        q_objs.append(Q(**{ '%stracking_notes__%s' % (prefix, op):
                             data['tracking_notes']}))
    if data['publication_notes']:
        q_objs.append(Q(**{ '%spublication_notes__%s' % (prefix, op):
                             data['publication_notes']}))
    if data['not_reserved']:
        q_objs.append(Q(**{ '%songoing_reservation__isnull' % prefix: True }) &
                      Q(**{ '%sis_current' % prefix: True }))
    if data['is_current']:
        q_objs.append(Q(**{ '%sis_current' % prefix: True }))

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
        raise SearchError, ("Issue count must be an integer or an integer "
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
    if target in ['issue', 'cover', 'feature', 'sequence']:
        date_formatter = lambda d: '%04d.%02d.%02d' % (d.year, d.month, d.day)
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
    if data['issue_date']:
        q_objs.append(
          Q(**{ '%spublication_date__%s' % (prefix, op): data['issue_date'] }))
    if data['cover_needed']:
        q_objs.append(Q(**{ '%scover__isnull' % prefix: True }) |
                      ~Q(**{ '%scover__deleted' % prefix: False }) |
                      Q(**{ '%scover__marked' % prefix: True }))
    if data['is_indexed'] is not None:
        if data['is_indexed'] is True:
            q_objs.append(Q(**{ '%sis_indexed' % prefix: True }))
        else:
            q_objs.append(Q(**{ '%sis_indexed' % prefix: False }))
    if data['indexer']:
        q_objs.append(
          Q(**{ '%srevisions__changeset__indexer__indexer__in' % prefix:
                data['indexer'] }) &
          Q(**{ '%srevisions__changeset__state' % prefix: states.APPROVED }))
    if data['isbn']:
        q_objs.append(compute_isbn_qobj(data['isbn'], prefix, op))
    if data['issue_notes']:
        q_objs.append(Q(**{ '%snotes__%s' % (prefix, op): data['issue_notes'] }))

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
        raise SearchError, ("Page count must be a decimal number or a pair of "
                            "decimal numbers separated by a hyphen.")

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
            num_range = range(int(range_match.group('begin')),
                              int(range_match.group('end')) + 1)
            nums_in.extend(num_range)
        else:
            nums_in.append(esc)

    if nums_in:
        if field == 'issues':
            q_or_only.append(Q(**{ '%snumber__in' % prefix: nums_in }))
        else:
            q_or_only.append(Q(**{ '%svolume__in' % prefix: nums_in }))

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

    for field in ('feature', 'title', 'genre', 'job_number', 'characters',
                  'synopsis', 'reprint_notes', 'notes'):
        if data[field]:
            q_and_only.append(Q(**{ '%s%s__%s' % (prefix, field, op):
                                data[field] }))

    if data['type']:
        q_and_only.append(Q(**{ '%stype__in' % prefix: data['type'] }))

    if data['story_editing']:
        q_objs.append(Q(**{ '%sediting__%s' % (prefix, op):
                            data['story_editing'] }))

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
        raise SearchError, ("Page count must be a decimal number or a pair of "
                            "decimal numbers separated by a hyphen.")

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
        if target in ('brand', 'indicia_publisher'):
            return 'parent__'
        if target == 'issue':
            return 'series__publisher__'
        if target in ('sequence', 'feature', 'cover'):
            return 'issue__series__publisher__'
    elif current == 'brand':
        if target == 'indicia_publisher':
            raise SearchError, ('Cannot search for Indicia Publishers by '
              'Publisher Brand attributes, as they are not directly related')
        if target in ('publisher', 'issue'):
            return 'brand__'
        if target in ('series', 'sequence', 'feature', 'cover'):
            return 'issue__brand__'
    elif current == 'indicia_publisher':
        if target == 'brand':
            raise SearchError, ('Cannot search for Publisher Brands by '
              'Indicia Publisher attributes, as they are not directly related')
        if target == 'publisher':
            return 'indiciapublisher__'
        if target == 'issue':
            return 'indicia_publisher__'
        if target in ('series', 'sequence', 'feature', 'cover'):
            return 'issue__indicia_publisher__'
    elif current == 'series':
        if target in ('issue', 'publisher'):
            return 'series__'
        if target in ('sequence', 'feature', 'cover',
                      'brand', 'indicia_publisher'):
            return 'issue__series__'
    elif current == 'issue':
        if target in ('sequence', 'feature', 'cover', 'series',
                      'brand', 'indicia_publisher'):
            return 'issue__'
        if target == 'publisher':
            return 'series__issue__'
    elif current == 'sequence':
        if target == 'issue':
            return 'story__'
        if target in ('series', 'cover', 'brand', 'indicia_publisher'):
            return 'issue__story__'
        if target == 'publisher':
            return 'series__issue__story__'
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

        elif target == 'brand':
            if order == 'date':
                terms.append('year_began')
            elif order == 'publisher':
                terms.append('parent')
            elif order == 'country':
                terms.append('parent__country__name')

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
            
        elif target in ('sequence', 'feature', 'cover'):
            if order == 'publisher':
                terms.append('issue__series__publisher')
            elif order == 'brand':
                terms.append('issue__brand')
            elif order == 'indicia_publisher':
                terms.append('issue__indicia_publisher')
            elif order == 'series':
                terms.append('issue__series')
            elif order == 'date':
                terms.append('issue__key_date')
            elif order == 'country':
                terms.append('issue__series__country__name')
            elif order == 'language':
                terms.append('issue__series__language__name')
            elif target != 'cover':
                terms.append(order)

    return terms

