from haystack.backends import BaseEngine
from haystack.backends.elasticsearch7_backend import (
  Elasticsearch7SearchBackend, Elasticsearch7SearchQuery)
from haystack.constants import DEFAULT_ALIAS


class Elasticsearch7BoostingSearchBackend(Elasticsearch7SearchBackend):
    DEFAULT_FIELD_MAPPING = {
        "type": "text",
        "analyzer": "accents_analyzer",
    }

    def __init__(self, connection_alias, **connection_options):
        super().__init__(connection_alias, **connection_options)
        self.DEFAULT_SETTINGS["settings"]["analysis"]['analyzer']\
                             ["accents_analyzer"] = {  # noqa: E211
                               "tokenizer": "standard",
                               "filter": ["lowercase", "asciifolding"]
                             }

    def build_search_kwargs(
        self,
        query_string,
        boost_fields=None,
        boost_negative=None,
        **extra_kwargs
    ):
        kwargs = super(Elasticsearch7BoostingSearchBackend,
                       self).build_search_kwargs(query_string, **extra_kwargs)
        from haystack import connections
        index = connections[self.connection_alias].get_unified_index()
        content_field = index.document_field

        if query_string != "*:*":
            # we are doing boost on some fields, so not just 'default_field'
            kwargs['query']['bool']['must']['query_string'].pop('default_field')
            kwargs['query']['bool']['must']['query_string']['fields'] = [content_field]
            if boost_fields:
                kwargs['query']['bool']['must']['query_string']['fields'] = []
                for boost_field, boost_value in boost_fields.items():
                    kwargs['query']['bool']['must']['query_string']['fields'].append('%s^%s' % (boost_field, boost_value))
            # negativ boost for some matches
            if boost_negative:
                boosting = {
                    'positive': kwargs['query']['bool']['must'],
                    'negative': boost_negative[0],
                    'negative_boost': boost_negative[1]
                }
                kwargs['query']['bool']['must'] = {'boosting': boosting}

        # add function_score for relations_weight
        original_query = kwargs['query']
        function_score_query = {
            'function_score': {
                "field_value_factor": {
                    "field": "relations_weight",
                    "factor": 1,
                    "modifier": "ln1p",
                    "missing": 1
                },
                'query': original_query,
                'boost_mode': 'sum'
            }
        }
        kwargs['query'] = function_score_query
        return kwargs

    def build_schema(self, fields):
        # we modified the globals on the class and use these
        return super(Elasticsearch7BoostingSearchBackend, self)\
                    .build_schema(fields)


class Elasticsearch7BoostingSearchQuery(Elasticsearch7SearchQuery):
    def __init__(self, using=DEFAULT_ALIAS):
        self.boost_fields = {}
        self.boost_negative = []
        super(Elasticsearch7SearchQuery, self).__init__(using=using)

    def build_params(self, spelling_query=None, **kwargs):
        search_kwargs = super(Elasticsearch7SearchQuery,
                              self).build_params(spelling_query, **kwargs)
        if self.boost_fields:
            search_kwargs['boost_fields'] = self.boost_fields
        if self.boost_negative:
            search_kwargs['boost_negative'] = self.boost_negative
        return search_kwargs

    def add_boost_fields(self, fields):
        """Add boosted fields to the query."""
        self.boost_fields = fields

    def add_boost_negative(self, query, negative_boost):
        """Add negative boost to the query."""
        self.boost_negative = [query, negative_boost]

    def _clone(self, klass=None, using=None):
        clone = super(Elasticsearch7SearchQuery, self)._clone(klass, using)
        clone.boost_fields = self.boost_fields.copy()
        clone.boost_negative = self.boost_negative.copy()
        return clone


class Elasticsearch7BoostingSearchEngine(BaseEngine):
    backend = Elasticsearch7BoostingSearchBackend
    query = Elasticsearch7BoostingSearchQuery
