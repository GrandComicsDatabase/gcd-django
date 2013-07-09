import datetime
from haystack import indexes
from apps.gcd.models import Issue, Series, Story, Publisher, IndiciaPublisher, Brand


class IssueIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    key_date = indexes.CharField(model_attr='key_date')

    def get_model(self):
        return Issue

    # def index_queryset(self, using=None):
    #     """Used when the entire index for model is updated."""
    #     return self.get_model().objects.filter(pub_date__lte=datetime.datetime.now())


class SeriesIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    year_began = indexes.IntegerField(model_attr='year_began', null=True)
    year_ended = indexes.IntegerField(model_attr='year_ended', null=True)

    def get_model(self):
        return Series

class StoryIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)

    def get_model(self):
        return Story

class PublisherIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True, template_name='search/indexes/gcd/publisher_text.txt')
    year_began = indexes.IntegerField(model_attr='year_began', null=True)
    year_ended = indexes.IntegerField(model_attr='year_ended', null=True)

    def get_model(self):
        return Publisher

class IndiciaPublisherIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True, template_name='search/indexes/gcd/publisher_text.txt')
    year_began = indexes.IntegerField(model_attr='year_began', null=True)
    year_ended = indexes.IntegerField(model_attr='year_ended', null=True)

    def get_model(self):
        return IndiciaPublisher

class BrandIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True, template_name='search/indexes/gcd/publisher_text.txt')
    year_began = indexes.IntegerField(model_attr='year_began', null=True)
    year_ended = indexes.IntegerField(model_attr='year_ended', null=True)

    def get_model(self):
        return Brand

