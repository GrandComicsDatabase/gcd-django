# -*- coding: utf-8 -*-
from rest_framework import serializers
from apps.gcd.models import Series, Publisher, Issue, Story
from apps.gcd.templatetags.credits import show_creator_credit, \
                                          show_keywords_as_text


class StorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Story
        fields = ['type', 'title', 'feature', 'sequence_number', 'page_count',
                  'script', 'pencils', 'inks', 'colors', 'letters', 'editing',
                  'job_number', 'genre', 'first_line', 'characters',
                  'synopsis', 'notes', 'keywords']

    type = serializers.StringRelatedField(read_only=True)

    script = serializers.SerializerMethodField()

    def _get_credit(self, obj, credit_type) -> str:
        if getattr(obj, f'no_{credit_type}', True):
            return "None"
        return (show_creator_credit(obj, credit_type, url=False))

    def get_script(self, obj) -> str:
        return (self._get_credit(obj, 'script'))

    pencils = serializers.SerializerMethodField()

    def get_pencils(self, obj) -> str:
        return (self._get_credit(obj, 'pencils'))

    inks = serializers.SerializerMethodField()

    def get_inks(self, obj) -> str:
        return (self._get_credit(obj, 'inks'))

    colors = serializers.SerializerMethodField()

    def get_colors(self, obj) -> str:
        return (self._get_credit(obj, 'colors'))

    letters = serializers.SerializerMethodField()

    def get_letters(self, obj) -> str:
        return (self._get_credit(obj, 'letters'))

    editing = serializers.SerializerMethodField()

    def get_editing(self, obj) -> str:
        return (self._get_credit(obj, 'editing'))

    feature = serializers.SerializerMethodField()

    def get_feature(self, obj) -> str:
        return (obj.show_feature_as_text())

    characters = serializers.SerializerMethodField()

    def get_characters(self, obj) -> str:
        return (obj.show_characters_as_text())

    keywords = serializers.SerializerMethodField()

    def get_keywords(self, obj) -> str:
        return (show_keywords_as_text(obj))


class IssueSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Issue
        fields = ['api_url', 'series_name', 'descriptor', 'number', 'volume',
                  'variant_name', 'title', 'publication_date', 'key_date',
                  'price', 'page_count', 'editing', 'indicia_publisher',
                  'brand_emblem', 'isbn', 'barcode', 'rating', 'on_sale_date',
                  'indicia_frequency', 'notes', 'variant_of', 'series',
                  'indicia_printer', 'keywords', 'story_set', 'cover']

    story_set = StorySerializer(many=True, read_only=True)

    descriptor = serializers.SerializerMethodField()

    def get_descriptor(self, obj) -> str:
        return (obj.full_descriptor)

    indicia_publisher = serializers.StringRelatedField(read_only=True)
    brand_emblem = serializers.SerializerMethodField()
    def get_brand_emblem(self, obj) -> str:
        emblem_string = ''
        for brand_emblem in obj.brand_emblem.all():
            if emblem_string != '':
                emblem_string += '; '
            emblem_string += brand_emblem.name
        return (emblem_string)

    indicia_printer = serializers.SerializerMethodField()
    def get_indicia_printer(self, obj) -> str:
        printer_string = ''
        if obj.series.has_indicia_printer:
            for indicia_printer in obj.indicia_printer.all():
                if printer_string != '':
                    printer_string += '; '
                printer_string += indicia_printer.name
        return (printer_string)

    editing = serializers.SerializerMethodField()

    def get_editing(self, obj) -> str:
        return (show_creator_credit(obj, 'editing', url=False))

    keywords = serializers.SerializerMethodField()

    def get_keywords(self, obj) -> str:
        return (show_keywords_as_text(obj))

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


class SeriesOverviewItemSerializer(serializers.ModelSerializer):
    """
    Serializes one row of the Cover and Main Story Overview table
    (/series/<id>/overview/) as structured JSON.

    Fields mirror what the HTML view renders per issue:
    - cover_url: direct image link (empty string if no scan exists)
    - longest_story: the longest comic-story sequence (type 19) for the issue,
      or null if none exists.  Variant issues fall back to their parent's story,
      matching the HTML table behaviour.
    """

    class Meta:
        model = Issue
        fields = [
            'issue_id', 'descriptor', 'number', 'publication_date',
            'on_sale_date', 'key_date', 'cover_url', 'longest_story',
        ]

    issue_id = serializers.IntegerField(source='id')

    descriptor = serializers.SerializerMethodField()

    def get_descriptor(self, obj) -> str:
        return obj.full_descriptor

    cover_url = serializers.SerializerMethodField()

    def get_cover_url(self, obj) -> str:
        covers = obj.active_covers()
        if covers:
            cover = covers[0]
            return cover.get_base_url() + ("/w400/%d.jpg" % cover.id)
        return ""

    longest_story = serializers.SerializerMethodField()

    def get_longest_story(self, obj):
        from apps.gcd.models.story import Story

        story_id = getattr(obj, 'longest_story_id', None)
        if story_id:
            try:
                story = Story.objects.prefetch_related(
                    'credits__creator__creator').get(id=story_id)
                return StorySerializer(story).data
            except Story.DoesNotExist:
                pass

        # Fallback: variant issues — check parent issue's longest story
        if obj.variant_of_id:
            story_qs = obj.variant_of.active_stories()\
                          .filter(type_id=19, deleted=False)\
                          .prefetch_related('credits__creator__creator')\
                          .order_by('-page_count')
            if story_qs.exists():
                return StorySerializer(story_qs[0]).data

        return None


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
        exclude = ['created', 'deleted', 'external_link']

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
