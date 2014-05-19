import shlex
from django.utils.http import urlencode
from django.utils.encoding import smart_unicode as uni

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
    return list(lex)

def parse_query_into_sq(query, fields):
    sq = None
    not_sq = None
    or_flag = False
    for phrase in safe_split(query.encode('utf-8')):
        if phrase[0] == '-':
            query_part = AutoQuery('"%s"' % uni(phrase[1:]))
            for field in fields:
                if not not_sq:
                    not_sq = SQ(**{field:query_part})
                else:
                    not_sq |= SQ(**{field:query_part})
            or_flag = False
        elif phrase == 'OR':
            or_flag = True
        else:
            query_part = AutoQuery('"%s"' % uni(phrase))
            field_sq = None
            for field in fields:
                if not field_sq:
                    field_sq = SQ(**{field:query_part})
                else:
                    field_sq |= SQ(**{field:query_part})
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
    # request sent to search engine (to be exact it uses default operator that's
    # set, but we want AND as default operator) which results in not finding
    # objects where some searched terms are only present in fields that are not
    # added to template of 'text' field for such object. So instead we want to
    # control creating such conditions by adding appropriate filter_or() below
    # in __call__() method of PaginatedFacetedSearchView class.

    def auto_query(self, query_string, fieldname='content'):
        return self

class PaginatedFacetedSearchView(FacetedSearchView):
    def __call__(self, request):
        self.request = request

        self.form = self.build_form()
        if 'search_object' in request.GET:
            if request.GET['search_object'] != "all":
                self.form.selected_facets = [u'facet_model_name_exact:%s' % \
                                              request.GET['search_object']]
        self.query = self.get_query()
        #TODO List of fields should be gathered
        # automatically from our SearchIndex classes
        fields = ['content', 'name' , 'title']
        sq, not_sq = parse_query_into_sq(self.query, fields)
        if sq:
            self.form.searchqueryset = self.form.searchqueryset.filter(sq)
        if not_sq:
            self.form.searchqueryset = self.form.searchqueryset.exclude(not_sq)

        self.results = self.get_results()
        self.sort = ''
        if len(self.form.selected_facets) == 1:
            if 'sort' in request.GET:
                self.sort = request.GET['sort']
                if self.form.selected_facets[0] in \
                  [u'facet_model_name_exact:publisher',
                   u'facet_model_name_exact:indicia publisher',
                   u'facet_model_name_exact:brand group',
                   u'facet_model_name_exact:brand emblem',
                   u'facet_model_name_exact:series']:
                    if request.GET['sort'] == 'alpha':
                        self.results = self.results.order_by('sort_name',
                                                             'year_began')
                    elif request.GET['sort'] == 'chrono':
                        self.results = self.results.order_by('year_began',
                                                             'sort_name')
                elif u'facet_model_name_exact:issue' in self.form.selected_facets:
                    if request.GET['sort'] == 'alpha':
                        self.results = self.results.order_by('sort_name',
                                                             'key_date',
                                                             'sort_code')
                    elif request.GET['sort'] == 'chrono':
                        self.results = self.results.order_by('key_date',
                                                             'sort_name',
                                                             'sort_code')
                elif u'facet_model_name_exact:story' in self.form.selected_facets:
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
        if self.query:
            self.query = urlencode({'q': self.query.encode('utf-8')})
        self.paginator = ResponsePaginator(self.results,
                                           view=self.create_response)
        return self.paginator.paginate(request)

    def extra_context(self):
        extra = super(PaginatedFacetedSearchView, self).extra_context()
        extra.update(self.paginator.vars)

        suggestion = self.form.get_suggestion()
        if suggestion == self.query.lower():
            suggestion = u''
        facet_page = ''
        if self.form.selected_facets:
            for facet in self.form.selected_facets:
                facet_page += '&selected_facets=%s' % facet
        extra.update({'suggestion': suggestion,
                     'facet_page': facet_page})
        if self.sort:
            extra.update({'sort': '&sort=%s' % self.sort})
        else:
            extra.update({'sort': ''})
        return extra
