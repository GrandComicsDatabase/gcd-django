# -*- coding: utf-8 -*-
"""
View methods related to displaying search and search results pages.
"""

from re import *
from urllib import urlopen, quote, urlencode
from decimal import Decimal
from string import capitalize

from django.db.models import Q
from django.conf import settings
from django.shortcuts import render_to_response, \
                             get_object_or_404, \
                             get_list_or_404
from django.http import HttpResponseRedirect
from django.core import urlresolvers
from django.core.paginator import QuerySetPaginator
from django.views.generic.list_detail import object_list
from django.template import RequestContext

from apps.gcd.models import Publisher, Series, Issue, Cover, Story, StoryType,\
                            Country, Language
from apps.gcd.views import ViewTerminationError, paginate_response, \
                           ORDER_ALPHA, ORDER_CHRONO
from apps.gcd.forms.search import AdvancedSearch, PAGE_RANGE_REGEXP
from apps.gcd.views.details import issue, COVER_TABLE_WIDTH 
from apps.gcd.views.covers import get_image_tags_per_page

# Should not be importing anything from oi, but we're doing this in several places.
# TODO: states should probably live somewhere else.
from apps.oi import states

class SearchError(Exception):
    pass

def generic_by_name(request, name, q_obj, sort,
                    class_=Story,
                    template='gcd/search/content_list.html',
                    credit=None):
    """
    Helper function for the most common search cases.
    """

    base_name = 'unknown'
    plural_suffix = 's'
    query_val = {'method': 'icontains'}
    if (class_ is Series):
        base_name = 'series'
        plural_suffix = ''
        things = Series.objects.exclude(deleted=True).filter(q_obj) \
                   .select_related('publisher')
        if (sort == ORDER_ALPHA):
            things = things.order_by("name", "year_began")
        elif (sort == ORDER_CHRONO):
            things = things.order_by("year_began", "name")
        heading = 'Series Search Results'
        # query_string for the link to the advanced search
        query_val['target'] = 'series'
        query_val['series'] = name
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
            things = things.order_by("issue__series__name",
                                     "issue__series__year_began",
                                     "issue__key_date",
                                     "sequence_number")
        elif (sort == ORDER_CHRONO):
            things = things.order_by("issue__key_date",
                                     "issue__series__name",
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
                                'letters', 'story_editing']:
            #, 'issue_editing']:
            # issue editing doesn't seem to 'or'ed with the other credits ?
                query_val[credit_type] = name
    else:
        raise TypeError, "Unsupported search target!"

    vars = { 'item_name': base_name,
             'plural_suffix': plural_suffix,
             'heading': heading,
             'search_term' : name,
             'media_url' : settings.MEDIA_URL, 
             'style' : 'default',
             'query_string' : urlencode(query_val),
             'which_credit' : credit }
    return paginate_response(request, things, template, vars)

def publishers_by_name(request, publisher_name, sort=ORDER_ALPHA):
    #Finds publishers and imprints

    pubs = Publisher.objects.filter(
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
          'heading' : 'Publisher Search Results',
          'query_string' : get_copy.urlencode(),
          'style' : 'default',
        })

def character_by_name(request, character_name, sort=ORDER_ALPHA):
    """Find stories based on characters.  Since characters for whom a feature
    is named are often not also listed under character appearances, this
    search looks at both the feature and characters fields."""

    q_obj = Q(characters__icontains=character_name) | \
            Q(feature__icontains=character_name)
    return generic_by_name(request, character_name, q_obj, sort)


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
        p = QuerySetPaginator(things, 100)
        page_num = 1
        if (request.GET.has_key('page')):
            page_num = int(request.GET['page'])
        page = p.page(page_num)
        
        context = {
            'items' : things,
            'item_name' : 'issue',
            'plural_suffix' : 's',
            'heading' : series_name + ' #' + issue_nr,
            'style' : 'default',
        }
        if 'style' in request.GET:
            context['style'] = request.GET['style']

        return paginate_response(
          request, things, 'gcd/search/issue_list.html', context)


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
    return HttpResponseRedirect(
      urlresolvers.reverse(view,
                           kwargs = { param_type: quote(request.GET['query'].strip() \
                                                        .encode('utf-8')),
                                      'sort': sort }))


def advanced_search(request):
    """Displays the advanced search page."""

    if ('target' not in request.GET):
        return render_to_response('gcd/search/advanced.html',
          { 'form' : AdvancedSearch(auto_id=True), 'style' : 'default'},
          context_instance=RequestContext(request))
    else:
        return render_to_response('gcd/search/advanced.html',
          { 'form' : AdvancedSearch(initial=request.GET), 'style' : 'default'},
          context_instance=RequestContext(request))

def do_advanced_search(request):
    """
    Runs advanced searches.
    """
    form = AdvancedSearch(request.GET)
    if not form.is_valid():
        raise ViewTerminationError(response = render_to_response(
          'gcd/search/advanced.html',
          { 'form': form, 'style': 'default' },
          context_instance=RequestContext(request)))

    data = form.cleaned_data
    op = str(data['method'] or 'iregex')

    try:
        stq_obj = search_stories(data, op)
        iq_obj = search_issues(data, op)
        sq_obj = search_series(data, op)
        pq_obj = search_publishers(data, op)
        # if there are sequence searches limit to type cover
        if data['target'] == 'cover' and stq_obj != None:
            cq_obj = Q(**{ 'issue__story__type' : StoryType.objects\
                                                  .get(name='cover') })
        else:
            cq_obj = None
        query = combine_q(data, stq_obj, iq_obj, sq_obj, pq_obj, cq_obj)
        terms = compute_order(data)
    except SearchError, se:
        raise ViewTerminationError, render_to_response(
          'gcd/search/advanced.html',
          {
              'form': form,
              'style': 'default',
              'error_text': '%s' % se,
          },
          context_instance=RequestContext(request))

    if (not query) and terms:
        raise ViewTerminationError, render_to_response(
          'gcd/search/advanced.html',
          {
            'form': form,
            'style': 'default',
            'error_text': "Please enter at least one search term "
                          "or clear the 'ordering' fields.  Ordered searches "
                          "must have at least one search term."
          },
          context_instance=RequestContext(request))
        
    items = []
    if data['target'] == 'publisher':
        if query:
            filter = Publisher.objects.filter(query)
        else:
            filter = Publisher.objects.all()
        items = filter.order_by(*terms).select_related('country').distinct()

    elif data['target'] == 'series':
        if query:
            filter = Series.objects.exclude(deleted=True).filter(query)
        else:
            filter = Series.objects.exclude(deleted=True)
        items = filter.order_by(*terms).select_related('publisher').distinct()

    elif data['target'] == 'issue':
        if query:
            filter = Issue.objects.exclude(deleted=True).filter(query)
        else:
            filter = Issue.objects.exclude(deleted=True)
        items = filter.order_by(*terms).select_related(
          'series__publisher').distinct()

    elif data['target'] == 'cover':
        if query:
            filter = Cover.objects.exclude(deleted=True).filter(query)
        else:
            filter = Cover.objects.all()
        items = filter.order_by(*terms).select_related(
          'issue__series__publisher').distinct()

    elif data['target'] == 'sequence':
        if query:
            filter = Story.objects.exclude(deleted=True).filter(query)
        else:
            filter = Story.objects.exclude(deleted=True)
        items = filter.order_by(*terms).select_related(
          'issue__series__publisher', 'type').distinct()

    return items, data['target']


def used_search(search_values):
    del search_values['order1']
    del search_values['order2']
    del search_values['order3']
    if search_values['target'] == 'sequence':
        target = 'Stories'
    elif search_values['target'][-1] == 's':
        target = 'Series'
    else:
        target = capitalize(search_values['target']) + 's'
    del search_values['target']
    
    if search_values['method'] == 'iexact':
        method = 'Matches Exactly'
    elif search_values['method'] == 'istartswith':
        method = 'Starts With'
    else:
        method = 'Contains'
    del search_values['method']

    if search_values['logic'] == 'True':
        logic = 'OR credits, AND other fields'
    else:
        logic = 'AND all fields'
    del search_values['logic']

    used_search_terms = []
    if 'country' in search_values:
        used_search_terms.append(('country',
          Country.objects.get(code=search_values['country']).name))
        del search_values['country']
    if 'language' in search_values:
        used_search_terms.append(('language',
          Language.objects.get(code=search_values['language']).name))
        del search_values['language']
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
        'item_name' : item_name,
        'plural_suffix' : plural_suffix,
        'heading' : target.title() + ' Search Results',
        'query_string' : get_copy.urlencode(),
        'style' : 'default',
    }
    if request.GET.has_key('style'):
        context['style'] = request.GET['style']

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
          { '%s__gte' % start_name : formatter(data['start_date']) }
        end_after_start = \
          { '%s__gte' % end_name : formatter(data['start_date']) }

        if data['end_date']:
            q_and_only.append(Q(**begin_after_start) | Q(**end_after_start))
        else:
            q_and_only.append(Q(**end_after_start))

    if data['end_date']:
        begin_before_end = \
          { '%s__lte' % start_name : formatter(data['end_date']) }
        end_before_end = \
          { '%s__lte' % end_name : formatter(data['end_date']) }

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
        pub_name_q = Q(**{ '%sname__%s' % (prefix, op) : data['pub_name'] })
        if target == 'publisher':
            q_objs.append(pub_name_q)
        else:
            imprint_prefix = compute_prefix(target, 'series')
            imprint_q = Q(**{ '%simprint__name__%s' % (imprint_prefix, op) :
                              data['pub_name'] })
            q_objs.append(pub_name_q | imprint_q)
    # one more like this and we should refactor the code :-)
    if data['pub_notes']:
        pub_notes_q = Q(**{ '%snotes__%s' % (prefix, op) :
                            data['pub_notes'] })
        if target == 'publisher':
            q_objs.append(pub_notes_q)
        else:
            imprint_prefix = compute_prefix(target, 'series')
            imprint_q = Q(**{ '%simprint__notes__%s' % (imprint_prefix, op) :
                              data['pub_notes'] })
            q_objs.append(pub_notes_q | imprint_q)

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
        language_qargs = { '%slanguage__code__in' % prefix : data['language'] }
        q_and_only.append(Q(**language_qargs))

    q_objs = []
    if data['series']:
        q_objs.append(Q(**{ '%sname__%s' % (prefix, op) : data['series'] }))
    if data['format']:
        q_objs.append(Q(**{ '%sformat__%s' % (prefix, op) :  data['format'] }))
    if data['series_notes']:
        q_objs.append(Q(**{ '%snotes__%s' % (prefix, op) :
                            data['series_notes'] }))
    if data['tracking_notes']:
        q_objs.append(Q(**{ '%stracking_notes__%s' % (prefix, op) :
                             data['tracking_notes']}))
    if data['publication_notes']:
        q_objs.append(Q(**{ '%spublication_notes__%s' % (prefix, op) :
                             data['publication_notes']}))
    if data['not_reserved']:
        q_objs.append(Q(**{ '%songoing_reservation__isnull' % prefix : True }) &
                      Q(**{ '%sis_current' % prefix : True }))
    if data['is_current']:
        q_objs.append(Q(**{ '%sis_current' % prefix : True }))

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
          Q(**{ '%spublication_date__%s' % (prefix, op) : data['issue_date'] }))
    if data['brand']:
        q_objs.append(
          Q(**{ '%sbrand__name__%s' % (prefix, op) : data['brand'] }))
    if data['indicia_publisher']:
        q_objs.append(
          Q(**{ '%sindicia_publisher__name__%s' % (prefix, op) :
                data['indicia_publisher'] }))
    if data['cover_needed']:
        q_objs.append(Q(**{ '%scover__isnull' % prefix : True }) |
                      ~Q(**{ '%scover__deleted' % prefix : False }) |
                      Q(**{ '%scover__marked' % prefix : True }))
    if data['is_indexed'] is not None:
        if data['is_indexed'] is True:
            q_objs.append(Q(**{ '%sis_indexed' % prefix : True }))
        else:
            q_objs.append(Q(**{ '%sis_indexed' % prefix : False }))
    if data['indexer']:
        q_objs.append(
          Q(**{ '%srevisions__changeset__indexer__indexer__in' % prefix:
                data['indexer'] }) &
          Q(**{ '%srevisions__changeset__state' % prefix: states.APPROVED }))
    if data['issue_editing']:
        q_objs.append(Q(**{ '%sediting__icontains' % prefix:
                            data['issue_editing'] }))
    if data['issue_notes']:
        q_objs.append(Q(**{ '%snotes__icontains' % prefix: data['issue_notes'] }))

    try:
        if data['issue_pages'] is not None and data['issue_pages'] != '':
            range_match = match(PAGE_RANGE_REGEXP, data['issue_pages'])
            if range_match:
                page_start = Decimal(range_match.group('begin'))
                page_end = Decimal(range_match.group('end'))
                q_objs.append(Q(**{ '%spage_count__range' % prefix :
                                    (page_start, page_end) }))
            else:
                q_objs.append(Q(**{ '%spage_count' % prefix :
                                    Decimal(data['issue_pages']) }))
    except ValueError:
        raise SearchError, ("Page count must be a decimal number or a pair of "
                            "decimal numbers separated by a hyphen.")

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
            q_or_only.append(Q(**{ '%snumber__in' % prefix : nums_in }))
        else:
            q_or_only.append(Q(**{ '%svolume__in' % prefix : nums_in }))

    return reduce(lambda x, y: x | y, q_or_only)

def search_stories(data, op):
    """
    Build the query against the story table.  As it is the lowest
    table in the hierarchy, there are no possible subqueries to run.
    """
    target = data['target']
    prefix = compute_prefix(target, 'sequence')

    q_objs = []
    if target == 'sequence':
        q_objs = [Q(**{'%s%s' % (prefix, 'deleted__exact') : 0})]

    for field in ('feature', 'title', 'genre',
                  'script', 'pencils', 'inks',
                  'colors', 'letters', 'job_number', 'characters',
                  'synopsis', 'reprint_notes', 'notes'):
        if data[field]:
            q_objs.append(Q(**{ '%s%s__%s' % (prefix, field, op) :
                                data[field] }))

    if data['type']:
        q_objs.append(Q(**{ '%stype__in' % prefix : data['type'] }))

    if data['story_editing']:
        q_objs.append(Q(**{ '%sediting__%s' % (prefix, op) :
                            data['story_editing'] }))

    try:
        if data['pages'] is not None and data['pages'] != '':
            range_match = match(PAGE_RANGE_REGEXP, data['pages'])
            if range_match:
                page_start = Decimal(range_match.group('begin'))
                page_end = Decimal(range_match.group('end'))
                q_objs.append(Q(**{ '%spage_count__range' % prefix :
                                    (page_start, page_end) }))
            else:
                q_objs.append(Q(**{ '%spage_count' % prefix :
                                    Decimal(data['pages']) }))

    except ValueError:
        raise SearchError, ("Page count must be a decimal number or a pair of "
                            "decimal numbers separated by a hyphen.")

    return compute_qobj(data, [], q_objs)


def compute_prefix(target, current):
    """
    Advanced search allows searching on any of four tables in a
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
        if target == 'issue':
            return 'series__publisher__'
        if target in ('sequence', 'feature', 'cover'):
            return 'issue__series__publisher__'
    elif current == 'series':
        if target in ('issue', 'publisher'):
            return 'series__'
        if target in ('sequence', 'feature', 'cover'):
            return 'issue__series__'
    elif current == 'issue':
        if target in ('sequence', 'feature', 'cover', 'series'):
            return 'issue__'
        if target == 'publisher':
            return 'series__issue__'
    elif current == 'sequence':
        if target == 'issue':
            return 'story__'
        if target in ('series', 'cover'):
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
            terms.append('name')

        elif target == 'publisher':
            if order == 'date':
                terms.append('year_began')
            elif order == 'country':
                terms.append('country__name')

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
            elif order == 'publisher':
                terms.append('series__publisher')
            elif order == 'country':
                terms.append('series__country__name')
            elif order == 'language':
                terms.append('series__language__name')
            
        elif target in ('sequence', 'feature', 'cover'):
            if order == 'publisher':
                terms.append('issue__series__publisher')
            elif order == 'series':
                terms.append('issue__series')
            elif order == 'date':
                terms.append('issue__key_date')
            elif order == 'country':
                terms.append('issue__series__country__name')
            elif order == 'language':
                terms.append('issue__series__language__name')
            else:
                terms.append(order)

    return terms

