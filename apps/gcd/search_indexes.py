from haystack import indexes
from haystack.fields import MultiValueField
from apps.gcd.models import Issue, Series, Story, Publisher, IndiciaPublisher,\
    Brand, BrandGroup, STORY_TYPES, Award, Creator, CreatorMembership,\
    CreatorArtInfluence, CreatorAward, CreatorNonComicWork

DEFAULT_BOOST = 15.0


class ObjectIndex(object):
    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        return self.get_model().objects.filter(deleted=False)

    def get_updated_field(self):
        return "modified"

    def prepare_year(self, obj):
        if obj.year_began:
            return obj.year_began
        else:
            return 9999

    def prepare(self, obj):
        self.prepared_data = super(ObjectIndex, self).prepare(obj)

        self.prepared_data['sort_name'] = \
          self.prepared_data['sort_name'].lower()

        return self.prepared_data

    def should_update(self, instance, **kwargs):
        """Overide to check if we need to remove an object from the index."""
        if instance.deleted:
            self.remove_object(instance, **kwargs)
        return not instance.deleted


class IssueIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    title = indexes.CharField(model_attr="title", boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='series__sort_name',
                                  indexed=False)
    key_date = indexes.CharField(model_attr='key_date', indexed=False)
    sort_code = indexes.IntegerField(model_attr='sort_code', indexed=False)
    year = indexes.IntegerField()
    country = indexes.CharField(model_attr='series__country__code',
                                faceted=True, indexed=False)
    language = indexes.CharField(model_attr='series__language__code',
                                 faceted=True, indexed=False)
    publisher = indexes.CharField(model_attr='series__publisher__name',
                                  faceted=True, indexed=False)

    def get_model(self):
        return Issue

    def prepare_facet_model_name(self, obj):
        return "issue"

    def prepare_year(self, obj):
        if obj.key_date:
            return int(obj.key_date[:4])
        else:
            return 9999

    def prepare_key_date(self, obj):
        if obj.key_date:
            return obj.key_date
        else:
            return "9999-99-99"

    def prepare_title(self, obj):
        return obj.short_name()


class SeriesIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    name = indexes.CharField(model_attr="name", boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='sort_name', indexed=False)
    year = indexes.IntegerField()
    country = indexes.CharField(model_attr='country__code',  faceted=True,
                                indexed=False)
    language = indexes.CharField(model_attr='language__code', faceted=True,
                                 indexed=False)
    title_search = indexes.CharField()
    publisher = indexes.CharField(model_attr='publisher__name',
                                  faceted=True, indexed=False)

    def get_model(self):
        return Series

    def prepare_facet_model_name(self, obj):
        return "series"

    def prepare_title_search(self, obj):
        name = obj.name
        if obj.has_issue_title:
            for issue in obj.active_issues():
                if issue.title:
                    name += '\n' + issue.title
        return name


class StoryIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    title = indexes.CharField(model_attr="title", boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='issue__series__sort_name',
                                  indexed=False)
    key_date = indexes.CharField(model_attr='issue__key_date', indexed=False)
    sort_code = indexes.IntegerField(model_attr='issue__sort_code',
                                     indexed=False)
    sequence_number = indexes.IntegerField(model_attr='sequence_number',
                                           indexed=False)
    type = indexes.CharField(model_attr='type__name', indexed=False)
    year = indexes.IntegerField()
    country = indexes.CharField(model_attr='issue__series__country__code',
                                faceted=True, indexed=False)
    language = indexes.CharField(model_attr='issue__series__language__code',
                                 faceted=True, indexed=False)
    publisher = indexes.CharField(model_attr='issue__series__publisher__name',
                                  faceted=True, indexed=False)

    feature = indexes.MultiValueField(faceted=True, indexed=False, null=True)

    script = indexes.MultiValueField(faceted=True, null=True)
    pencils = indexes.MultiValueField(faceted=True, null=True)
    inks = indexes.MultiValueField(faceted=True, null=True)
    colors = indexes.MultiValueField(faceted=True, null=True)
    letters = indexes.MultiValueField(faceted=True, null=True)
    editing = indexes.MultiValueField(faceted=True, null=True)

    def get_model(self):
        return Story

    def prepare_facet_model_name(self, obj):
        return "story"

    def prepare_year(self, obj):
        if obj.issue.key_date:
            return int(obj.issue.key_date[:4])
        else:
            return 9999

    def prepare_key_date(self, obj):
        if obj.issue.key_date:
            return obj.issue.key_date
        else:
            return "9999-99-99"

    def _prepare_credit(self, obj, field):
        return_val = [(val.strip()) for val in getattr(obj, field).split(';')]
        if return_val == ['']:
            return None
        else:
            return return_val

    def prepare_script(self, obj):
        return self._prepare_credit(obj, 'script')

    def prepare_pencils(self, obj):
        return self._prepare_credit(obj, 'pencils')

    def prepare_inks(self, obj):
        return self._prepare_credit(obj, 'inks')

    def prepare_colors(self, obj):
        return self._prepare_credit(obj, 'colors')

    def prepare_letters(self, obj):
        return self._prepare_credit(obj, 'letters')

    def prepare_editing(self, obj):
        return_val = [(val.strip()) for val in
                      getattr(obj, 'editing').split(';')]
        return_val.extend([(val.strip()) for val in
                          getattr(obj.issue, 'editing').split(';')])
        if return_val == ['']:
            return None
        else:
            return return_val

    def prepare_feature(self, obj):
        return self._prepare_credit(obj, 'feature')

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        return super(ObjectIndex, self).index_queryset(using).exclude(
            type=STORY_TYPES['blank']).filter(deleted=False)


class PublisherIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/publisher_text.txt')
    name = indexes.CharField(model_attr="name", boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='name', indexed=False)
    year = indexes.IntegerField()
    country = indexes.CharField(model_attr='country__code', faceted=True,
                                indexed=False)
    publisher = indexes.CharField(model_attr='name',
                                  faceted=True, indexed=False)

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
    year = indexes.IntegerField()
    country = indexes.CharField(model_attr='country__code', faceted=True,
                                indexed=False)
    publisher = indexes.CharField(model_attr='parent__name',
                                  faceted=True, indexed=False)

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
    year = indexes.IntegerField()

    publisher = MultiValueField(faceted=True, indexed=False)

    def get_model(self):
        return Brand

    def prepare_facet_model_name(self, obj):
        return "brand emblem"

    def prepare_publisher(self, obj):
        return [(brand_group.parent.name) for brand_group in obj.group.all()]


class BrandGroupIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/publisher_text.txt')
    name = indexes.CharField(model_attr="name", boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='name', indexed=False)
    year = indexes.IntegerField()
    country = indexes.CharField(model_attr='parent__country__code',
                                faceted=True, indexed=False)
    publisher = indexes.CharField(model_attr='parent__name',
                                  faceted=True, indexed=False)

    def get_model(self):
        return BrandGroup

    def prepare_facet_model_name(self, obj):
        return "brand group"


class AwardIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/award_text.txt')
    name = indexes.CharField(model_attr="name", boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='name', indexed=False)

    def get_model(self):
        return Award

    def prepare_facet_model_name(self, obj):
        return "award"


class CreatorIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/creator_text.txt')
    gcd_official_name = indexes.CharField(model_attr="gcd_official_name",
                                          boost=DEFAULT_BOOST)
    name = MultiValueField(boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    year = indexes.IntegerField()
    sort_name = indexes.CharField(model_attr="gcd_official_name",
                                  indexed=False)
    country = indexes.CharField(model_attr='birth_country__code',
                                indexed=False, faceted=True, null=True)

    def get_model(self):
        return Creator

    def prepare_facet_model_name(self, obj):
        return "creator"

    def prepare_name(self, obj):
        return [(creator_name.name) for creator_name in
                obj.creator_names.all()]

    def prepare_year(self, obj):
        if obj.birth_date.year and '?' not in obj.birth_date.year:
            return int(obj.birth_date.year)
        else:
            return 9999


class CreatorMembershipIndex(ObjectIndex, indexes.SearchIndex,
                             indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/creator_membership_text.txt')
    name = indexes.CharField(model_attr="organization_name",
                             boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='organization_name',
                                  indexed=False)

    def get_model(self):
        return CreatorMembership

    def prepare_facet_model_name(self, obj):
        return "creator membership"


class CreatorArtInfluenceIndex(ObjectIndex, indexes.SearchIndex,
                               indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True,
             template_name='search/indexes/gcd/creator_art_influence_text.txt')
    name = indexes.CharField(model_attr="influence", boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='influence', indexed=False)
    country = indexes.CharField(model_attr='creator__birth_country__code',
                                indexed=False, null=True)

    def get_model(self):
        return CreatorArtInfluence

    def prepare_facet_model_name(self, obj):
        return "creator art influence"


class CreatorAwardIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/creator_award_text.txt')
    name = indexes.CharField(model_attr="award_name", boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    year = indexes.IntegerField()
    sort_name = indexes.CharField(model_attr='award_name', indexed=False)

    def prepare_year(self, obj):
        if obj.award_year:
            return obj.award_year
        else:
            return 9999

    def get_model(self):
        return CreatorAward

    def prepare_facet_model_name(self, obj):
        return "creator award"


class CreatorNonComicWorkIndex(ObjectIndex, indexes.SearchIndex,
                               indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True,
           template_name='search/indexes/gcd/creator_non_comic_work_text.txt')
    name = indexes.CharField(model_attr="publication_title",
                             boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='publication_title',
                                  indexed=False)
    country = indexes.CharField(model_attr='creator__birth_country__code',
                                indexed=False, null=True)

    def get_model(self):
        return CreatorNonComicWork

    def prepare_facet_model_name(self, obj):
        return "creator non comic work"
