from haystack import indexes
from apps.gcd.models import Issue, Series, Story, Publisher, IndiciaPublisher,\
    Brand, BrandGroup

DEFAULT_BOOST = 15.0

class ObjectIndex(object):
    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        return self.get_model().objects.filter(deleted=False)

    def get_updated_field(self):
        return "modified"


class IssueIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    title = indexes.CharField(model_attr="title", boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='series__sort_name', indexed=False)
    key_date = indexes.CharField(model_attr='key_date', indexed=False)
    sort_code = indexes.IntegerField(model_attr='sort_code', indexed=False)

    def get_model(self):
        return Issue

    def prepare_facet_model_name(self, obj):
        return "issue"


class SeriesIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    name = indexes.CharField(model_attr="name", boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='sort_name', indexed=False)
    year_began = indexes.IntegerField(model_attr='year_began')

    def get_model(self):
        return Series

    def prepare_facet_model_name(self, obj):
        return "series"


class StoryIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    title = indexes.CharField(model_attr="title", boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='issue__series__sort_name', indexed=False)
    key_date = indexes.CharField(model_attr='issue__key_date', indexed=False)
    sort_code = indexes.IntegerField(model_attr='issue__sort_code', indexed=False)
    sequence_number = indexes.IntegerField(model_attr='sequence_number', indexed=False)

    def get_model(self):
        return Story

    def prepare_facet_model_name(self, obj):
        return "story"


class PublisherIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/publisher_text.txt')
    name = indexes.CharField(model_attr="name", boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='name', indexed=False)
    year_began = indexes.IntegerField(model_attr='year_began', default=0)

    def get_model(self):
        return Publisher

    def prepare_facet_model_name(self, obj):
        return "publisher"


class IndiciaPublisherIndex(ObjectIndex, indexes.SearchIndex,
                            indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/publisher_text.txt')
    name = indexes.CharField(model_attr="name", boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='name', indexed=False)
    year_began = indexes.IntegerField(model_attr='year_began', default=0)

    def get_model(self):
        return IndiciaPublisher

    def prepare_facet_model_name(self, obj):
        return "indicia publisher"


class BrandIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/publisher_text.txt')
    name = indexes.CharField(model_attr="name", boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='name', indexed=False)
    year_began = indexes.IntegerField(model_attr='year_began', default=0)

    def get_model(self):
        return Brand

    def prepare_facet_model_name(self, obj):
        return "brand"


class BrandGroupIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/publisher_text.txt')
    name = indexes.CharField(model_attr="name", boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='name', indexed=False)
    year_began = indexes.IntegerField(model_attr='year_began', default=0)

    def get_model(self):
        return BrandGroup

    def prepare_facet_model_name(self, obj):
        return "brand group"
