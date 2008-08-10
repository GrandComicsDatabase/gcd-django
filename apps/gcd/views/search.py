"""View methods related to displaying search and search results pages."""

from re import *
from urllib import urlopen

from django.db.models import Q
from django.conf import settings
from django.shortcuts import render_to_response, \
                             get_object_or_404, \
                             get_list_or_404
from django.http import HttpResponseRedirect
from django.core.paginator import QuerySetPaginator
from django.views.generic.list_detail import object_list

from apps.gcd.models import Publisher, Series, Issue, Story
from apps.gcd.views.diggpaginator import DiggPaginator
from apps.gcd.forms.search import AdvancedSearch

ORDER_ALPHA = "alpha"
ORDER_CHRONO = "chrono"


def generic_by_name(request, name, q_obj, sort,
                    class_name = Story,
                    template = 'default_search.html',
                    credit = None):
    """Helper function for the most common search cases."""

    if (class_name is Series):
        things = Series.objects.filter(q_obj)
        if (sort == ORDER_ALPHA):
            things = things.order_by("name")
        elif (sort == ORDER_CHRONO):
            things = things.order_by("year_began", "name")

    else:
        things = class_name.objects.filter(q_obj).filter(issue__index_status=3)
        # TODO: This order_by stuff only works for Stories, which is 
        # TODO: OK for now, but might not always be.
        if (sort == ORDER_ALPHA):
            things = things.order_by("issue__series__name",
                                     "issue__series__year_began",
                                     "issue__key_date",
                                     "sequence_number")
        elif (sort == ORDER_CHRONO):
            things = things.order_by("issue__key_date",
                                     "sequence_number")

    if 'page' in request.GET:
        pageno=request.GET['page']
    else:
        pageno=1    
    if 'entries_per_page' in request.session:
        entries = request.session['entries_per_page']
    else:
        entries = 50
    digg_paginator = DiggPaginator(things,entries,page=pageno, body=7)
    return object_list(request,things, paginate_by = entries, 
                       template_name = template,extra_context = {
                       'search_term' : name,
                       'media_url' : settings.MEDIA_URL, 
                       'digg_paginator' : digg_paginator,
                       'which_credit' : credit})

def publishers_by_name(request, publisher_name, sort=ORDER_ALPHA):
    """Finds publishers that (probably) aren't imprints."""

    pubs = Publisher.objects.filter(
      name__icontains = publisher_name, is_master = 1)
    if (sort == ORDER_ALPHA):
        pubs = pubs.order_by('name', 'year_began')
    elif (sort == ORDER_CHRONO):
        pubs = pubs.order_by('year_began', 'name')

    return render_to_response('publisher_list.html', {
      'publisher_set' : pubs,
      'publisher_count' : len(pubs),
      'media_url' : settings.MEDIA_URL })


def character_appearances(request, character_name, sort=ORDER_ALPHA):
    """Find stories based on characters.  Since characters for whom a feature
    is named are often not also listed under character appearances, this
    search looks at both the feature and characters fields."""

    q_obj = Q(characters__icontains = character_name) | \
            Q(feature__icontains = character_name)
    return generic_by_name(request, character_name, q_obj, sort)


def writer_by_name(request, writer, sort=ORDER_ALPHA):
    q_obj = Q(script__icontains = writer)
    return generic_by_name(request, writer, q_obj, sort, credit="script")


def penciller_by_name(request, penciller, sort=ORDER_ALPHA):
    q_obj = Q(pencils__icontains = penciller)
    return generic_by_name(request, penciller, q_obj, sort, credit="pencils")


def inker_by_name(request, inker, sort=ORDER_ALPHA):
    q_obj = Q(inks__icontains = inker)
    return generic_by_name(request, inker, q_obj, sort, credit="inks")


def colorist_by_name(request, colorist, sort=ORDER_ALPHA):
    q_obj = Q(colors__icontains = colorist)
    return generic_by_name(request, colorist, q_obj, sort, credit="colors")


def letterer_by_name(request, letterer, sort=ORDER_ALPHA):
    q_obj = Q(letters__icontains = letterer)
    return generic_by_name(request, letterer, q_obj, sort, credit="letters")


def editor_by_name(request, editor, sort=ORDER_ALPHA):
    q_obj = Q(editor__icontains = editor)
    return generic_by_name(request, editor, q_obj, sort, credit="editor")


def story_by_credit(request, name, sort=ORDER_ALPHA):
    """Implements the 'Any Credit' story search."""
    q_obj = Q(script__icontains = name) | \
            Q(pencils__icontains = name) | \
            Q(inks__icontains = name) | \
            Q(colors__icontains = name) | \
            Q(letters__icontains = name) | \
            Q(editor__icontains = name)
    return generic_by_name(request, name, q_obj, sort, credit=('any:'+name))


def story_by_job_number(request, number, sort=ORDER_ALPHA):
    q_obj = Q(job_number__icontains = number)
    return generic_by_name(request, number, q_obj, sort, credit="job_number")

def story_by_job_number_name(request, number, sort=ORDER_ALPHA):
    """Handle the form-style URL from the basic search form by mapping
    it into the by-name lookup URLs the system already knows how to handle."""

    return HttpResponseRedirect("/gcd/job_number/" + \
                                number + \
                                "/sort/" + \
                                sort + \
                                "/")

def story_by_reprint(request, reprints, sort=ORDER_ALPHA):
    q_obj = Q(reprints__icontains = reprints)
    return generic_by_name(request, reprints, q_obj, sort)


def story_by_title(request, title, sort=ORDER_ALPHA):
    """Looks up story by story (not issue or series) title."""
    q_obj = Q(title__icontains = title)
    return generic_by_name(request, title, q_obj, sort)

def story_by_feature(request, feature, sort=ORDER_ALPHA):
    """Looks up story by feature."""
    q_obj = Q(feature__icontains = feature)
    return generic_by_name(request, feature, q_obj, sort)
    

def series_by_name(request, series_name, sort=ORDER_ALPHA):
    q_obj = Q(name__icontains = series_name)
    return generic_by_name(request, series_name, q_obj, sort,
                           Series, 'title_search.html')


def search(request):
    """Handle the form-style URL from the basic search form by mapping
    it into the by-name lookup URLs the system already knows how to handle."""

    return HttpResponseRedirect("/gcd/" + \
                                request.GET["type"] + \
                                "/name/" + \
                                request.GET["query"] + \
                                "/sort/" + \
                                request.GET["sort"] + \
                                "/")


def advanced_search(request):
    """Displays the advanced search page."""

    if (not request.GET.has_key("target")):
        return render_to_response('gcd/search/advanced.html', {
          'form' : AdvancedSearch(auto_id=True),
          'style' : 'default',
          'media_url' : settings.MEDIA_URL })

    if (request.GET["target"] == "stories"):
        return search_stories(request)
    else:
        return search_series(request)

    
def process_advanced(request):
    """Runs advanced searches."""
    form = AdvancedSearch(request.GET)
    if not form.is_valid():
        return render_to_response('gcd/search/advanced.html', {
          'form': form,
          'style': 'default',
          'media_url': settings.MEDIA_URL })

    data = form.cleaned_data
    template = None
    context = {}
    op = str(data['method'] or 'iregex')

    stq_obj = search_stories(data, op)
    iq_obj = search_issues(data, op, stq_obj)
    sq_obj = search_series(data, op, iq_obj)
    pq_obj = search_publishers(data, op, sq_obj)
    terms = compute_order(data)

    items = []
    list_template = None
    if data['target'] == 'publisher':
        if pq_obj:
            filter = Publisher.objects.filter(pq_obj)
        else:
            filter = Publisher.objects.all()
        items = filter.order_by(*terms).select_related('country')
        template = 'gcd/search/publisher_list.html'

    elif data['target'] == 'series':
        query = combine_q(data, sq_obj, pq_obj)
        if query:
            filter = Series.objects.filter(query)
        else:
            filter = Series.objects.all()
        items = filter.order_by(*terms).select_related('publisher')

        template = 'gcd/search/series_list.html'

    elif data['target'] == 'issue':
        query = combine_q(data, iq_obj, sq_obj, pq_obj)
        if query:
            filter = Issue.objects.filter(query)
        else:
            filter = Issue.objects.all()
        items = filter.order_by(*terms).select_related('series__publisher')
        template = 'gcd/search/issue_list.html',

    elif data['target'] == 'sequence':
        query = combine_q(data, stq_obj, iq_obj, sq_obj, pq_obj)
        if query:
            filter = Story.objects.filter(query)
        else:
            filter = Story.objects.all()
        items = filter.order_by(*terms).select_related('issue__series')
        template = 'gcd/search/content_list.html'

    p = QuerySetPaginator(items, 100)
    page_num = 1
    if (request.GET.has_key('page')):
        page_num = int(request.GET['page'])
    page = p.page(page_num)

    item_name = data['target']
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
        'items' : page.object_list,
        'item_name' : item_name,
        'plural_suffix' : plural_suffix,
        'page' : page,
        'paginator' : p,
        'page_number': page_num,
        'heading' : data['target'].title() + ' Search Results',
        'query_string' : get_copy.urlencode(),
        'media_url' : settings.MEDIA_URL,
        'style' : 'default',
    }
    if request.GET.has_key('style'):
        context['style'] = request.GET['style']

    return render_to_response(template, context)


def combine_q(data, *qobjs):
    """When targeting a table other than the top table in the hierarchy
    (publishers), the queries objects against all higher tables must
    be anded as they will be run using JOINs in a single query.  The method
    compute_prefix adjusted the query terms to work with the JOIN as they
    were added in each of the search_* methods."""
    filtered = filter(lambda x: x != None, qobjs)
    if filtered:
        return reduce(lambda x, y: x & y, filtered)
    return None


def search_dates(data, formatter=lambda d: d.year,
                 start_name='year_began', end_name='year_ended'):
    """Add query terms for date ranges, which may have either or both
    endpoints, or may be absent.  Note that strftime cannot handle
    years before 1900, hence the formatter callable."""

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


def search_publishers(data, op, series_q=None):
    """Handle publisher fields, running a subquery against series if needed."""
    target = data['target']
    prefix = compute_prefix(target, 'publisher')

    q_and_only = []
    if target == 'publisher':
        if data['country']:
            q_and_only.append(Q(country__code__in=data['country']))
        q_and_only.extend(search_dates(data))

        # Filtering imprints on/off really only makes sense if we're
        # searching for publishers. Currently we don't support searching
        # on a s
        if not data['imprints']:
            q_and_only.append(Q(**{ '%sparent' % prefix : 0 }))

    q_objs = []
    if data['pub_name']:
        q_objs.append(Q(**{ '%sname__%s' % (prefix, op) : data['pub_name'] }))

    predecessor_objs = None
    if series_q and target == 'publisher':
        predecessor_objs = Series.objects

    return compute_qobj(data, q_and_only, q_objs,
                        predecessor_objs, series_q, 'publisher')


def search_series(data, op, issues_q=None):
    """Handle series fields, running a subquery against issues if needed."""
    target = data['target']
    prefix = compute_prefix(target, 'series')

    q_and_only = []
    if target != 'publisher':
        if data['country']:
            country_qargs = { '%scountry_code__in' % prefix : data['country'] }
            q_and_only.append(Q(**country_qargs))
        q_and_only.extend(search_dates(data))

    if data['language']:
        language_qargs = { '%slanguage_code__in' % prefix : data['language'] }
        q_and_only.append(Q(**language_qargs))

    if data['indexer']:
        indexer_qargs = {
            '%sindex_credit_set__indexer__in' %prefix : data['indexer']
        }
        q_and_only.append(Q(**indexer_qargs))

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

    predecessor_objs = None
    if issues_q and (target == 'series' or target == 'publisher'):
        predecessor_objs = Issue.objects

    return compute_qobj(data, q_and_only, q_objs,
                        predecessor_objs, issues_q, 'series')


def search_issues(data, op, stories_q=None):
    """Handle issue fields, running a subquery against stories if needed."""
    target = data['target']
    prefix = compute_prefix(target, 'issue')

    q_and_only = []
    if target == 'issue' or target == 'feature' or target == 'sequence':
        date_formatter = lambda d: '%04d.%02d.%02d' % (d.year, d.month, d.day)
        q_and_only.extend(search_dates(data, date_formatter,
                                       '%skey_date' % prefix,
                                       '%skey_date' % prefix))

        # 3 indicates an approved index.  TODO: constants.
        q_and_only.append(Q(**{ '%sindex_status' % prefix : 3 }))

    q_objs = []
    if data['issues']:
        q_objs.append(handle_issue_numbers(data, prefix))

    predecessor_objs = None
    if stories_q and (target == 'issue' or
                      target == 'series' or
                      target == 'publisher'):
        predecessor_objs = Story.objects

    return compute_qobj(data, q_and_only, q_objs,
                        predecessor_objs, stories_q, 'issue')


def handle_issue_numbers(data, prefix):
    """The issue number field accepts issues, hyphenated issue ranges,
    and comma-separated lists of either form.  Large numeric ranges
    result in large lists passed to the IN clause due to issue numbers
    not really being numeric in our data set.
    """

    # Commas can be backslash-escaped, and a literal backslash before
    # a comma can itself be escaped.  Backslashes elsewhere must not
    # be escaped.  This could be handled more consistently and intuitively.
    q_or_only = []
    issue_nums = split(r'\s*(?<!\\),\s*', data['issues'])
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
        q_or_only.append(Q(**{ '%snumber__in' % prefix : nums_in }))

    return reduce(lambda x, y: x | y, q_or_only)


def search_stories(data, op):
    """Build the query against the story table.  As it is the lowest
    table in the hierarchy, there are no possible subqueries to run."""
    q_objs = []
    for field in ('feature', 'title', 'type', 'script', 'pencils', 'inks',
                  'colors', 'letters', 'job_number', 'characters',
                  'synopsis', 'reprints', 'notes'):
        if data[field]:
            q_objs.append(Q(**{ '%s__%s' % (field, op) : data[field] }))

    for field in ('issue_editor', 'issue_notes', 'issue_reprints'):
        if data[field]:
            m = match(r'issue_(?P<column>.+)', field)
            kwargs = {'%s__%s' % (m.group('column'), op) : data[field],
                      'sequence_number' : 0}
            q_objs.append(Q(**kwargs))

    # The editor field on the first cover sequence is always intended
    # to apply to the whole issue.  However, reprints and notes may
    # apply to either the issue or the cover, so allow them to match
    # either way.
    if data['editor']:
        q_objs.append(Q(**{ 'editor__%s' % op : data['editor'] }) & \
                      ~Q(sequence_number=0))

    if data['pages']:
        range_match = match(r'(?P<begin>\d+)\s*-\s*(?P<end>\d+)$',
                            data['pages'])
        if range_match:
            num_range = range(int(range_match.group('begin')),
                              int(range_match.group('end')) + 1)
            q_objs.append(Q(page_count__in=num_range))
        
    if data['issue_pages']:
        range_match = match(r'(?P<begin>\d+)\s*-\s*(?P<end>\d+)$',
                            data['issue_pages'])
        if range_match:
            num_range = range(int(range_match.group('begin')),
                              int(range_match.group('end')) + 1)
            q_objs.append(Q(page_count__in=num_range, sequence_number=0))
        else:
            q_objs.append(Q(page_count=data['issue_pages'], sequence_number=0))

    return compute_qobj(data, [], q_objs)


def compute_prefix(target, current):
    """Advanced search allows searching on any of four tables in a
    hierarchy using fields from any of those tables.  Depending on
    the relative positioning of the table you're searching in to
    the table that has the field you're searching with, you may need
    to follow relationships to reach the table that contains the field.

    This function works out the realtionship-following prefixes, where
    'current' is the table whose fields are being processed, and 'target'
    is the table the search will ultimately run against.

    Note that this only really applies when you are matching against fields
    further up the hierarchy than the table on which you are searching.
    For handling fields lower in the hierarchy, see the subquery logic
    in compute_qobj."""
    if current == 'publisher':
        if target == 'series':
            return 'publisher__'
        if target == 'issue':
            return 'series__publisher__'
        if target == 'sequence' or target == 'feature':
            return 'issue__series__publisher__'
    if current == 'series':
        if target == 'issue':
            return 'series__'
        if target == 'sequence' or target == 'feature':
            return 'issue__series__'
    if current == 'issue':
        if target == 'sequence' or target == 'feature':
            return 'issue__'
    return ''


def compute_qobj(data, q_and_only, q_objs,
                 objects=None, subquery=None, colname=None):
    """Combines the various sorts of query objects in a standard way,
    and runs a subquery if necessary to restrict the selection of elements
    from a higher table to those matched by elements of a lower table, i.e.
    restrict the set of Publishers selected to only those that published
    Series matching the passed-in subquery.

    Note that this only handles restricting a higher table by fields
    on a lower table.  For handling searching a lower table with fields
    on a higher table, see compute_prefix."""
    if objects:
        # Select only the requested column name/value pairs from the table.
        columns = objects.filter(subquery).values(colname).distinct()

        # Extract the values from the pairs and use in the next query.
        ids = map(lambda x: x[colname], columns.values())
        q_and_only.append(Q(id__in=ids))

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
    """Figures out how to apply the ordering terms to the table the
    final query will run against.  Unlike the 'compute' methods for
    searching, compute_order will ignore orderings that don't apply
    to the primary search table.  This is arguably a bug, or at least
    unduly confusing.  The computation is also an inelegant application
    of brute force."""

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
                terms.append('country__code')
            elif order == 'language':
                terms.append('language__code')

        elif target == 'series':
            if order == 'date':
                terms.append('year_began')
            elif order == 'publisher':
                terms.append('publisher')
            elif order == 'country':
                terms.append('country_code')
            elif order == 'language':
                terms.append('language_code')
            
        elif target == 'issue':
            if order == 'date':
                terms.append('key_date')
            elif order == 'series':
                terms.append('series')
            elif order == 'publisher':
                terms.append('series__publisher')
            elif order == 'country':
                terms.append('series__country_code')
            elif order == 'language':
                terms.append('series__language_code')
            
        elif target == 'sequence' or target == 'feature':
            if order == 'publisher':
                terms.append('issue__series__publisher')
            elif order == 'series':
                terms.append('issue__series')
            elif order == 'date':
                terms.append('issue__key_date')
            elif order == 'country':
                terms.append('issue__series__country_code')
            elif order == 'language':
                terms.append('issue__series__language_code')
            else:
                terms.append(order)

    return terms

