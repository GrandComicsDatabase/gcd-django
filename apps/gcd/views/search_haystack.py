import shlex
from datetime import date
from django.utils.encoding import smart_str as uni

from haystack.views import FacetedSearchView
from apps.gcd.views import ResponsePaginator
from haystack.query import SearchQuerySet
from haystack.inputs import AutoQuery
from haystack.backends import SQ

from apps.select.views import filter_facets, form_filter_facets
from apps.gcd.templatetags.credits import get_native_language_name


def safe_split(value):
    try:
        return shlex.split(value)
    except ValueError as inst:
        if str(inst) != 'No closing quotation':
            raise
    lex = shlex.shlex(value)
    lex.quotes = '"'
    lex.whitespace_split = True
    lex.commenters = ''
    # sometimes only single ", need to catch that as well
    try:
        return list(lex)
    except ValueError as inst:
        if str(inst) != 'No closing quotation':
            raise
    lex = shlex.shlex(value)
    lex.quotes = ''
    lex.whitespace_split = True
    lex.commenters = ''
    return list(lex)


class GcdNameQuery(AutoQuery):
    def prepare(self, query_obj):
        query_string = super(GcdNameQuery, self).prepare(query_obj)
        query_return = ''
        query_string = query_string.replace('[', '\[')\
                                   .replace(']', '\]')\
                                   .replace('{', '\{')\
                                   .replace('}', '\}')\
                                   .replace(':', '\:')\
                                   .replace('!', '\!')\
                                   .replace('/', ' ')
        if ((query_string[0] == '"' and query_string[-1] == '"') or
           (query_string[0] == "'" and query_string[-1] == "'")):
            query_return = query_string
        else:
            for phrase in safe_split(query_string):
                # if we also do * in front, searches with 'the' won't work
                # somehow
                query_return += phrase + '* '
        return query_return


class GcdAutoQuery(AutoQuery):
    def prepare(self, query_obj):
        query_string = super(GcdAutoQuery, self).prepare(query_obj)
        if '\*' in query_string and len(query_string) > 2:
            query_string = query_string.replace('\*', '*')
        if ' ' in query_string:
            query_string = '"' + query_string + '"'
        return query_string


def prepare_sq(phrase, fields, sq):
    new_sq = sq
    query_part = GcdAutoQuery('%s' % uni(phrase))
    if '*' in phrase:
        query_part_2 = AutoQuery('%s' % uni(phrase))
    else:
        query_part_2 = None
    for field in fields:
        if not new_sq:
            new_sq = SQ(**{field: query_part})
        else:
            new_sq |= SQ(**{field: query_part})
        if query_part_2:
            new_sq |= SQ(**{field: query_part_2})
    return new_sq


# it may be, that we can do this as our own Query, i.e. similar
# to the above GcdAutoQuery.
def parse_query_into_sq(query, fields):
    sq = None
    not_sq = None
    or_flag = False
    for phrase in safe_split(query):
        if phrase[0] == '-' and len(phrase) > 1:
            not_sq = prepare_sq(phrase[1:], fields, not_sq)
            or_flag = False
        elif phrase == 'OR':
            or_flag = True
        else:
            field_sq = prepare_sq(phrase, fields, None)
            if not sq:
                sq = field_sq
            else:
                if or_flag:
                    sq |= field_sq
                else:
                    sq &= field_sq
            or_flag = False
    return sq, not_sq


class GcdSearchQuerySet(SearchQuerySet):
    # SearchQuerySet class by default adds 'AND (query)' condition to the
    # request sent to search engine (to be exact it uses default operator that
    # is set, but we want AND as default operator) which results in not finding
    # objects where some searched terms are only present in fields that are not
    # added to template of 'text' field for such object. So instead we want to
    # control creating such conditions by adding appropriate filter_or() below
    # in __call__() method of PaginatedFacetedSearchView class.

    def auto_query(self, query_string, fieldname='content'):
        return self

    def boost_fields(self, fields):
        """Boosts fields."""
        clone = self._clone()
        clone.query.add_boost_fields(fields)
        return clone

    def boost_negative(self, query, negative_boost):
        """Boost negatively."""
        clone = self._clone()
        clone.query.add_boost_negative(query, negative_boost)
        return clone


class PaginatedFacetedSearchView(FacetedSearchView):
    def __call__(self, request, context=None):
        self.request = request

        self.form = self.build_form()
        self.selected_model = None
        self.search_object = False
        if 'search_object' in request.GET:
            if request.GET['search_object'] != "all":
                self.form.selected_facets = ['facet_model_name_exact:%s' %
                                             request.GET['search_object']]
                self.search_object = True
        self.query = self.get_query().strip('\\')
        # TODO List of fields should be gathered
        # automatically from our SearchIndex classes
        #
        # TODO search over three fields is by now handled via boost_fields
        # in ES (or generally fields), so we could refactor
        # parse_query_into_sq, where we use to parse the AND/OR query for ES
        # into the three fields
        fields = ['content', ]
        sq, not_sq = parse_query_into_sq(self.query, fields)
        if sq:
            self.form.searchqueryset = self.form.searchqueryset.filter(sq)
        if not_sq:
            self.form.searchqueryset = self.form.searchqueryset.exclude(not_sq)

        filter_fields = ['country', 'language', 'publisher', 'type', 'feature',
                         'facet_model_name']
        self.form.searchqueryset = filter_facets(request,
                                                 self.form.searchqueryset,
                                                 filter_fields)
        filter_fields.remove('facet_model_name')
        self.form.searchqueryset = self.form.searchqueryset\
                                       .date_facet('date',
                                                   start_date=date(1000, 1, 1),
                                                   end_date=date(3000, 1, 1),
                                                   gap_by='year')
        self.form.searchqueryset = self.form.searchqueryset\
                                       .boost_fields({'name': 5,
                                                      'text': 1,
                                                      'title': 3})\
                                       .boost_negative({'terms': {'type': [
                                         'comics-form advertising',
                                         'promo (ad from the publisher)',
                                         'advertisement',
                                         'preview (from the publisher)',
                                         'in-house column']}}, 0.2)

        self.results = self.get_results()
        if 'sort' in request.GET:
            self.sort = request.GET['sort']
        else:
            self.sort = ''
        if self.sort:
            # do not use the default sort by relevance
            if len(self.form.selected_facets) == 0:
                if self.sort == 'chrono':
                    self.results = self.results.order_by('year',
                                                        '-_score')
                elif self.sort == '-chrono':
                    self.results = self.results.order_by('-year',
                                                        '-_score')
            else:
                direction = '-' if self.sort[0] == '-' else ''
                if ('facet_model_name_exact:publisher'
                    in self.form.selected_facets) or \
                  ('facet_model_name_exact:indicia publisher'
                   in self.form.selected_facets) or \
                  ('facet_model_name_exact:brand group'
                   in self.form.selected_facets) or \
                  ('facet_model_name_exact:brand emblem'
                   in self.form.selected_facets) or \
                  ('facet_model_name_exact:series'
                   in self.form.selected_facets) or \
                  ('facet_model_name_exact:character'
                   in self.form.selected_facets) or \
                  ('facet_model_name_exact:feature'
                   in self.form.selected_facets) or \
                  ('facet_model_name_exact:story_arc'
                   in self.form.selected_facets):
                    if 'alpha' in self.sort:
                        self.results = self.results.order_by(
                          direction + 'sort_name', 'year')
                    if 'chrono' in self.sort:
                        self.results = self.results.order_by(
                          direction + 'year', 'sort_name')
                elif 'facet_model_name_exact:issue' \
                     in self.form.selected_facets:
                    if 'alpha' in self.sort:
                        self.results = self.results.order_by(
                          direction + 'sort_name', 'key_date', 'sort_code')
                    if 'chrono' in self.sort:
                        self.results = self.results.order_by(
                          direction + 'key_date', 'sort_name', 'sort_code')
                elif 'facet_model_name_exact:story' \
                     in self.form.selected_facets:
                    if 'alpha' in self.sort:
                        self.results = self.results.order_by(
                          direction + 'sort_name', 'key_date',
                          'sort_code', 'sequence_number')
                    if 'chrono' in self.sort:
                        self.results = self.results.order_by(
                          direction + 'key_date', 'sort_name',
                          'sort_code', 'sequence_number')

                elif self.form.selected_facets[0] in \
                    ['facet_model_name_exact:creator',
                     'facet_model_name_exact:creator membership',
                     'facet_model_name_exact:creator artinfluence',
                     'facet_model_name_exact:creator award',
                     'facet_model_name_exact:creator noncomicwork']:
                    if 'alpha' in self.sort:
                        self.results = self.results.order_by(
                          direction + 'sort_name', 'year')
                    if 'chrono' in self.sort:
                        self.results = self.results.order_by(
                          direction + 'year', 'sort_name')
        self.filter_form = form_filter_facets(self.results, filter_fields,
                                              {'language':
                                               get_native_language_name},
                                              dates=True)
        self.selected = []
        if self.query:
            self.filter_form = self.filter_form(request.GET)
            self.filter_form['type'].label = 'Sequence'
            self.filter_form['dates'].label = 'Year'
            filter_fields.append('dates')
            for field in filter_fields:
                if field in request.GET:
                    self.selected.append(self.filter_form[field].label)

        get_copy = request.GET.copy()
        get_copy.pop('page', None)
        get_copy.pop('search_object', None)
        get_copy.pop('sort', None)

        if self.query:
            self.query = get_copy.urlencode()
        self.paginator = ResponsePaginator(self.results,
                                           vars=context)
        self.paginator.vars['page'] = self.paginator.paginate(request)
        return self.create_response()

    def extra_context(self):
        extra = super(PaginatedFacetedSearchView, self).extra_context()
        extra.update(self.paginator.vars)

        suggestion = self.form.get_suggestion()
        if suggestion == self.get_query().lower():
            suggestion = ''
        facet_page = ''
        if self.form.selected_facets:
            for facet in self.form.selected_facets:
                if self.search_object:
                    facet_page += '&selected_facets=%s' % facet
                if 'facet_model_name_exact:' in facet:
                    self.selected_model = facet
        extra.update({'suggestion': suggestion,
                      'haystack_search': 1,
                      'is_search_object': self.search_object,
                      'search_term': self.get_query(),
                      'filter_form': self.filter_form,
                      'facet_page': facet_page,
                      'selected': self.selected,
                      'selected_model': self.selected_model})
        if self.sort:
            extra.update({'sort': '&sort=%s' % self.sort})
        else:
            extra.update({'sort': ''})
        return extra
