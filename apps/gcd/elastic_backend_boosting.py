from django.conf import settings

from haystack.backends import BaseEngine
from haystack.backends.elasticsearch7_backend import (
  Elasticsearch7SearchBackend, Elasticsearch7SearchEngine,
  Elasticsearch7SearchQuery)
from haystack.query import SearchQuerySet
from haystack.forms import FacetedSearchForm, SearchForm
from haystack.constants import DEFAULT_OPERATOR, DEFAULT_ALIAS, DJANGO_CT, DJANGO_ID, FUZZINESS
from haystack.utils import get_model_ct

#DEFAULT_FIELD_MAPPING = {
#    "type": "text",
#    "analyzer": "standard",
#}

class Elasticsearch7BoostingSearchBackend(Elasticsearch7SearchBackend):
    DEFAULT_FIELD_MAPPING = {
        "type": "text",
        "analyzer": "standard",
    }
    def build_search_kwargs(
        self,
        query_string,
        sort_by=None,
        start_offset=0,
        end_offset=None,
        fields="",
        highlight=False,
        boost_fields=None,
        boost_negative=None,
        facets=None,
        date_facets=None,
        query_facets=None,
        narrow_queries=None,
        spelling_query=None,
        within=None,
        dwithin=None,
        distance_point=None,
        models=None,
        limit_to_registered_models=None,
        result_class=None,
        **extra_kwargs
    ):
        from haystack import connections
        index = connections[self.connection_alias].get_unified_index()
        content_field = index.document_field

        if query_string == "*:*":
            kwargs = {"query": {"match_all": {}}}
        else:
            kwargs = {
                "query": {
                    "query_string": {
                        'fields': [content_field],
                        "default_operator": DEFAULT_OPERATOR,
                        "query": query_string,
                        "analyze_wildcard": True,
                        "fuzziness": FUZZINESS,
                    }
                }
            }
            # these two boost_*-parts, these as options above and changing 
            # 'fields': [content_field], instead of "default_field": content_field,
            # are the only changes against django-haystack==3.2.1
            if boost_fields:
                kwargs['query']['query_string']['fields'] = []
                for boost_field, boost_value in boost_fields.items():
                    kwargs['query']['query_string']['fields'].append('%s^%s' % (boost_field, boost_value))
            if boost_negative:
                boosting = {
                    'positive': kwargs['query'],
                    'negative': boost_negative[0],
                    'negative_boost': boost_negative[1]
                }
                kwargs['query'] = {'boosting': boosting}
            # print (kwargs)
        filters = []

        if fields:
            if isinstance(fields, (list, set)):
                fields = " ".join(fields)

            kwargs["stored_fields"] = fields

        if sort_by is not None:
            order_list = []
            for field, direction in sort_by:
                if field == "distance" and distance_point:
                    # Do the geo-enabled sort.
                    lng, lat = distance_point["point"].coords
                    sort_kwargs = {
                        "_geo_distance": {
                            distance_point["field"]: [lng, lat],
                            "order": direction,
                            "unit": "km",
                        }
                    }
                else:
                    if field == "distance":
                        warnings.warn(
                            "In order to sort by distance, you must call the '.distance(...)' method."
                        )

                    # Regular sorting.
                    sort_kwargs = {field: {"order": direction}}

                order_list.append(sort_kwargs)

            kwargs["sort"] = order_list

        # From/size offsets don't seem to work right in Elasticsearch's DSL. :/
        # if start_offset is not None:
        #     kwargs['from'] = start_offset

        # if end_offset is not None:
        #     kwargs['size'] = end_offset - start_offset

        if highlight:
            # `highlight` can either be True or a dictionary containing custom parameters
            # which will be passed to the backend and may override our default settings:

            kwargs["highlight"] = {"fields": {content_field: {}}}

            if isinstance(highlight, dict):
                kwargs["highlight"].update(highlight)

        if self.include_spelling:
            kwargs["suggest"] = {
                "suggest": {
                    "text": spelling_query or query_string,
                    "term": {
                        # Using content_field here will result in suggestions of stemmed words.
                        "field": "text",  # ES7 does not support '_all' field
                    },
                }
            }

        if narrow_queries is None:
            narrow_queries = set()

        if facets is not None:
            kwargs.setdefault("aggs", {})
            for facet_fieldname, extra_options in facets.items():
                facet_options = {
                    "meta": {"_type": "terms"},
                    "terms": {"field": index.get_facet_fieldname(facet_fieldname), 'size': 100},
                }
                if "order" in extra_options:
                    facet_options["meta"]["order"] = extra_options.pop("order")
                # Special cases for options applied at the facet level (not the terms level).
                if extra_options.pop("global_scope", False):
                    # Renamed "global_scope" since "global" is a python keyword.
                    facet_options["global"] = True
                if "facet_filter" in extra_options:
                    facet_options["facet_filter"] = extra_options.pop("facet_filter")
                facet_options["terms"].update(extra_options)
                kwargs["aggs"][facet_fieldname] = facet_options

        if date_facets is not None:
            kwargs.setdefault("aggs", {})

            for facet_fieldname, value in date_facets.items():
                # Need to detect on gap_by & only add amount if it's more than one.
                interval = value.get("gap_by").lower()

                # Need to detect on amount (can't be applied on months or years).
                if value.get("gap_amount", 1) != 1 and interval not in (
                    "month",
                    "year",
                ):
                    # Just the first character is valid for use.
                    interval = "%s%s" % (value["gap_amount"], interval[:1])

                kwargs["aggs"][facet_fieldname] = {
                    "meta": {"_type": "date_histogram"},
                    "date_histogram": {"field": facet_fieldname, "interval": interval},
                    "aggs": {
                        facet_fieldname: {
                            "date_range": {
                                "field": facet_fieldname,
                                "ranges": [
                                    {
                                        "from": self._from_python(
                                            value.get("start_date")
                                        ),
                                        "to": self._from_python(value.get("end_date")),
                                    }
                                ],
                            }
                        }
                    },
                }

        if query_facets is not None:
            kwargs.setdefault("aggs", {})

            for facet_fieldname, value in query_facets:
                kwargs["aggs"][facet_fieldname] = {
                    "meta": {"_type": "query"},
                    "filter": {"query_string": {"query": value}},
                }

        if limit_to_registered_models is None:
            limit_to_registered_models = getattr(
                settings, "HAYSTACK_LIMIT_TO_REGISTERED_MODELS", True
            )

        if models and len(models):
            model_choices = sorted(get_model_ct(model) for model in models)
        elif limit_to_registered_models:
            # Using narrow queries, limit the results to only models handled
            # with the current routers.
            model_choices = self.build_models_list()
        else:
            model_choices = []

        if len(model_choices) > 0:
            filters.append({"terms": {DJANGO_CT: model_choices}})

        for q in narrow_queries:
            filters.append({"query_string": {"query": q}})

        if within is not None:
            filters.append(self._build_search_query_within(within))

        if dwithin is not None:
            filters.append(self._build_search_query_dwithin(dwithin))

        # if we want to filter, change the query type to bool
        if filters:
            kwargs["query"] = {"bool": {"must": kwargs.pop("query")}}
            if len(filters) == 1:
                kwargs["query"]["bool"]["filter"] = filters[0]
            else:
                kwargs["query"]["bool"]["filter"] = {"bool": {"must": filters}}

        if extra_kwargs:
            kwargs.update(extra_kwargs)

        return kwargs

    def build_schema(self, fields):
        DEFAULT_FIELD_MAPPING = {
            "type": "text",
            "analyzer": "standard",
        }
        # make pull request to modify Elasticsearch7SearchBackend to have
        # the globals on the class and use them per self
        return super(Elasticsearch7BoostingSearchBackend, self).build_schema(fields)
        content_field_name = ""
        mapping = self._get_common_mapping()

        for _, field_class in fields.items():
            field_mapping = FIELD_MAPPINGS.get(
                field_class.field_type, DEFAULT_FIELD_MAPPING
            ).copy()
            if field_class.boost != 1.0:
                field_mapping["boost"] = field_class.boost

            if field_class.document is True:
                content_field_name = field_class.index_fieldname

            # Do this last to override `text` fields.
            if field_mapping["type"] == "text":
                if field_class.indexed is False or hasattr(field_class, "facet_for"):
                    field_mapping["type"] = "keyword"
                    del field_mapping["analyzer"]

            mapping[field_class.index_fieldname] = field_mapping

        return (content_field_name, mapping)


class Elasticsearch7BoostingSearchQuery(Elasticsearch7SearchQuery):
    def __init__(self, using=DEFAULT_ALIAS):
        self.boost_fields = {}
        self.boost_negative = []
        super(Elasticsearch7SearchQuery, self).__init__(using=using)

    def build_params(self, spelling_query=None, **kwargs):
        search_kwargs = super(Elasticsearch7SearchQuery, self).build_params(spelling_query, **kwargs)
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
