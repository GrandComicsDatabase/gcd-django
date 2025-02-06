# -*- coding: utf-8 -*-
from rest_framework import serializers
from apps.gcd.models import Series, Publisher, Issue, Story
from apps.gcd.templatetags.credits import show_creator_credit


class StorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Story
        fields = ['type', 'title', 'feature', 'sequence_number', 'page_count',
                  'script', 'pencils', 'inks', 'colors', 'letters', 'editing',
                  'job_number', 'genre', 'characters', 'synopsis', 'notes',]

    type = serializers.StringRelatedField(read_only=True)

    script = serializers.SerializerMethodField()

    def get_script(self, obj) -> str:
        return (show_creator_credit(obj, 'script', url=False))

    pencils = serializers.SerializerMethodField()

    def get_pencils(self, obj) -> str:
        return (show_creator_credit(obj, 'pencils', url=False))

    inks = serializers.SerializerMethodField()

    def get_inks(self, obj) -> str:
        return (show_creator_credit(obj, 'inks', url=False))

    colors = serializers.SerializerMethodField()

    def get_colors(self, obj) -> str:
        return (show_creator_credit(obj, 'colors', url=False))

    letters = serializers.SerializerMethodField()

    def get_letters(self, obj) -> str:
        return (show_creator_credit(obj, 'letters', url=False))

    editing = serializers.SerializerMethodField()

    def get_editing(self, obj) -> str:
        return (show_creator_credit(obj, 'editing', url=False))

    feature = serializers.SerializerMethodField()

    def get_feature(self, obj) -> str:
        return (obj.show_feature_as_text())

    characters = serializers.SerializerMethodField()

    def get_characters(self, obj) -> str:
        return (obj.show_characters_as_text())


class IssueSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Issue
        fields = ['api_url', 'series_name', 'descriptor', 'publication_date',
                  'price', 'page_count', 'editing', 'indicia_publisher',
                  'brand', 'isbn', 'barcode', 'rating', 'on_sale_date',
                  'indicia_frequency', 'notes', 'variant_of', 'series',
                  'story_set', 'cover']

    story_set = StorySerializer(many=True, read_only=True)

    descriptor = serializers.SerializerMethodField()

    def get_descriptor(self, obj) -> str:
        return (obj.full_descriptor)

    indicia_publisher = serializers.StringRelatedField(read_only=True)
    brand = serializers.StringRelatedField(read_only=True)

    editing = serializers.SerializerMethodField()

    def get_editing(self, obj) -> str:
        return (show_creator_credit(obj, 'editing', url=False))

    cover = serializers.SerializerMethodField()

    def get_cover(self, obj) -> str:
        covers = obj.active_covers()
        if covers:
            cover_links = covers[0].get_base_url() + ("/w400/%d.jpg" %
                                                      covers[0].id)
        else:
            cover_links = ''
        return (cover_links)

    series_name = serializers.StringRelatedField(read_only=True,
                                                 source="series")


class IssueOnlySerializer(IssueSerializer):
    class Meta:
        model = Issue
        fields = ['api_url', 'series_name', 'descriptor', 'publication_date',
                  'price', 'page_count', 'variant_of', 'series',]


class SeriesSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Series
        fields = ['api_url', 'name', 'country', 'language',
                  'active_issues', 'issue_descriptors',
                  'color', 'dimensions', 'paper_stock', 'binding',
                  'publishing_format', 'notes', 'year_began', 'year_ended',
                  "publisher"]

    country = serializers.SlugRelatedField(read_only=True, slug_field='code')
    language = serializers.SlugRelatedField(read_only=True, slug_field='code')

    active_issues = serializers.HyperlinkedRelatedField(
      many=True, read_only=True, view_name='issue-detail')

    issue_descriptors = serializers.SerializerMethodField()

    def get_issue_descriptors(self, obj) -> list:
        return [issue.full_descriptor for issue in obj.active_issues()]


class PublisherSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Publisher
        exclude = ['created', 'deleted', ]

    country = serializers.SlugRelatedField(read_only=True, slug_field='code')


# class BrandSerializer(serializers.HyperlinkedModelSerializer):
#     class Meta:
#         model = Brand
#         exclude = ['created', 'deleted', ]


# class BrandGroupSerializer(serializers.HyperlinkedModelSerializer):
#     class Meta:
#         model = BrandGroup
#         exclude = ['created', 'deleted', ]


# class IndiciaPublisherSerializer(serializers.HyperlinkedModelSerializer):
#     class Meta:
#         model = IndiciaPublisher
#         exclude = ['created', 'deleted', ]

#     country = serializers.PrimaryKeyRelatedField(read_only=True)
