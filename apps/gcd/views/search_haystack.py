import shlex
from datetime import datetime, date
from django.utils.http import urlencode
from django.utils.encoding import smart_str as uni

from haystack.views import FacetedSearchView
from apps.gcd.views import ResponsePaginator
from haystack.query import SearchQuerySet
from haystack.inputs import AutoQuery
from haystack.backends import SQ


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
                                   .replace('/', ' ')
        if ((query_string[0] == '"' and query_string[-1] == '"') or
            (query_string[0] == "'" and query_string[-1] == "'")):
            query_return = query_string
        else:
            for phrase in safe_split(query_string):
                # if we also do * in front, searches with 'the' won't work somehow
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
        if 'search_object' in request.GET:
            if request.GET['search_object'] != "all":
                self.form.selected_facets = ['facet_model_name_exact:%s' %
                                             request.GET['search_object']]
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

        self.form.searchqueryset = self.form.searchqueryset\
                                       .facet('facet_model_name', size=100)\
                                       .facet('country', size=100)\
                                       .facet('language', size=100)\
                                       .facet('publisher', size=100)\
                                       .facet('feature', size=100)\
                                       .facet('type', size=100)\
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
        if 'date_facet' in request.GET:
            try:
                year = datetime.strptime(request.GET['date_facet'],
                                         '%Y-%m-%d %H:%M:%S')
                self.results = self.results.filter(date__gte=year)\
                                   .filter(date__lt=year.replace(year=year.year+1))
                self.date_facet = request.GET['date_facet']
            except ValueError:
                self.date_facet = None
        else:
            self.date_facet = None
        if 'sort' in request.GET:
            self.sort = request.GET['sort']
        else:
            self.sort = ''
        if self.sort == 'country':
            self.results = self.results.order_by('country',
                                                 '-_score')
        elif self.sort == 'year':
            self.results = self.results.order_by('year',
                                                 '-_score')
        elif len(self.form.selected_facets) >= 1:
            if self.sort:
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
                   in self.form.selected_facets):
                    if request.GET['sort'] == 'alpha':
                        self.results = self.results.order_by('sort_name',
                                                             'year')
                    elif request.GET['sort'] == 'chrono':
                        self.results = self.results.order_by('year',
                                                             'sort_name')
                elif 'facet_model_name_exact:issue' \
                     in self.form.selected_facets:
                    if request.GET['sort'] == 'alpha':
                        self.results = self.results.order_by('sort_name',
                                                             'key_date',
                                                             'sort_code')
                    elif request.GET['sort'] == 'chrono':
                        self.results = self.results.order_by('key_date',
                                                             'sort_name',
                                                             'sort_code')
                elif 'facet_model_name_exact:story' \
                     in self.form.selected_facets:
                    if request.GET['sort'] == 'alpha':
                        self.results = self.results.order_by('sort_name',
                                                             'key_date',
                                                             'sort_code',
                                                             'sequence_number')
                    elif request.GET['sort'] == 'chrono':
                        self.results = self.results.order_by('key_date',
                                                             'sort_name',
                                                             'sort_code',
                                                             'sequence_number')

                elif self.form.selected_facets[0] in \
                    ['facet_model_name_exact:creator',
                     'facet_model_name_exact:creator membership',
                     'facet_model_name_exact:creator artinfluence',
                     'facet_model_name_exact:creator award',
                     'facet_model_name_exact:creator noncomicwork']:
                    if request.GET['sort'] == 'alpha':
                        self.results = self.results.order_by('sort_name',
                                                             'year')
                    elif request.GET['sort'] == 'chrono':
                        self.results = self.results.order_by('year',
                                                             'sort_name')
        if self.query:
            self.query = urlencode({'q': self.query})
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
        is_model_selected = False
        is_country_selected = False
        is_language_selected = False
        is_publisher_selected = False
        is_feature_selected = False
        is_type_selected = False
        if self.date_facet:
            is_date_selected = True
            facet_page += '&date_facet=%s' % self.date_facet
        else:
            is_date_selected = False
        if self.form.selected_facets:
            for facet in self.form.selected_facets:
                facet_page += '&selected_facets=%s' % facet
                if 'facet_model_name_exact:' in facet:
                    is_model_selected = True
                elif 'country_exact:' in facet:
                    is_country_selected = True
                elif 'language_exact:' in facet:
                    is_language_selected = True
                elif 'publisher_exact:' in facet:
                    is_publisher_selected = True
                elif 'feature_exact:' in facet:
                    is_feature_selected = True
                elif 'type_exact:' in facet:
                    is_type_selected = True
        extra.update({'suggestion': suggestion,
                      'haystack_search': 1,
                      'search_term': self.get_query(),
                      'facet_page': facet_page,
                      'is_date_selected': is_date_selected,
                      'is_model_selected': is_model_selected,
                      'is_country_selected': is_country_selected,
                      'is_language_selected': is_language_selected,
                      'is_publisher_selected': is_publisher_selected,
                      'is_feature_selected': is_feature_selected,
                      'is_type_selected': is_type_selected})
        if self.sort:
            extra.update({'sort': '&sort=%s' % self.sort})
        else:
            extra.update({'sort': ''})
        return extra
