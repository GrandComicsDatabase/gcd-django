from haystack.views import FacetedSearchView
from apps.gcd.views import ResponsePaginator
from haystack.query import SearchQuerySet

class GcdSearchQuerySet(SearchQuerySet):
    def auto_query(self, query_string, fieldname='content'):
        return self

class PaginatedFacetedSearchView(FacetedSearchView):
    def __call__(self, request):
        self.request = request

        self.form = self.build_form()
        self.query = self.get_query()
        #TODO List of fields to add in filter_or should be gathered automatically from our SearchIndex classes
        self.form.searchqueryset = self.form.searchqueryset.filter_or(content=self.query).filter_or(name=self.query).filter_or(title=self.query)

        self.results = self.get_results()
        self.sort = ''
        if len(self.form.selected_facets) == 1:
            if 'sort' in request.GET:
                self.sort = request.GET['sort']
                if self.form.selected_facets[0] in \
                  [u'facet_model_name_exact:publisher',
                   u'facet_model_name_exact:indicia publisher',
                   u'facet_model_name_exact:brand group',
                   u'facet_model_name_exact:brand',
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
