from haystack import indexes
from apps.gcd.models import Issue, Series, Story, Publisher, IndiciaPublisher,\
    Brand


class IssueIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    facet_model_name = indexes.CharField(faceted=True)

    def get_model(self):
        return Issue

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        return self.get_model().objects.filter(deleted=False)

    def get_updated_field(self):
        return "modified"

    def prepare_facet_model_name(self, obj):
        return "issue"


class SeriesIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    facet_model_name = indexes.CharField(faceted=True)

    def get_model(self):
        return Series

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        return self.get_model().objects.filter(deleted=False)

    def get_updated_field(self):
        return "modified"

    def prepare_facet_model_name(self, obj):
        return "series"


class StoryIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    facet_model_name = indexes.CharField(faceted=True)

    def get_model(self):
        return Story

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        return self.get_model().objects.filter(deleted=False)

    def get_updated_field(self):
        return "modified"

    def prepare_facet_model_name(self, obj):
        return "story"


class PublisherIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                               'search/indexes/gcd/publisher_text.txt')
    facet_model_name = indexes.CharField(faceted=True)

    def get_model(self):
        return Publisher

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        return self.get_model().objects.filter(deleted=False)

    def get_updated_field(self):
        return "modified"

    def prepare_facet_model_name(self, obj):
        return "publisher"


class IndiciaPublisherIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                               'search/indexes/gcd/publisher_text.txt')
    facet_model_name = indexes.CharField(faceted=True)

    def get_model(self):
        return IndiciaPublisher

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        return self.get_model().objects.filter(deleted=False)

    def get_updated_field(self):
        return "modified"

    def prepare_facet_model_name(self, obj):
        return "indicia_publisher"


class BrandIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                               'search/indexes/gcd/publisher_text.txt')
    facet_model_name = indexes.CharField(faceted=True)

    def get_model(self):
        return Brand

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        return self.get_model().objects.filter(deleted=False)

    def get_updated_field(self):
        return "modified"

    def prepare_facet_model_name(self, obj):
        return "brand"

