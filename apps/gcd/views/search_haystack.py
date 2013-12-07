from haystack.views import FacetedSearchView
from apps.gcd.views import ResponsePaginator


class PaginatedFacetedSearchView(FacetedSearchView):
    def __call__(self, request):
        self.request = request

        self.form = self.build_form()
        self.query = self.get_query()
        self.results = self.get_results()

        self.paginator = ResponsePaginator(self.results,
                                           view=self.create_response)
        return self.paginator.paginate(request)

    def extra_context(self):
        extra = super(PaginatedFacetedSearchView, self).extra_context()
        extra.update(self.paginator.vars)
        return extra
