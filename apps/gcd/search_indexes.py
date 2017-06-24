from haystack import indexes
from haystack.fields import MultiValueField
from apps.gcd.models import Issue, Series, Story, Publisher, IndiciaPublisher,\
    Brand, BrandGroup, STORY_TYPES, Creator, Membership, ArtInfluence, Award, NonComicWork

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

    def get_model(self):
        return Brand

    def prepare_facet_model_name(self, obj):
        return "brand emblem"


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

    def get_model(self):
        return BrandGroup

    def prepare_facet_model_name(self, obj):
        return "brand group"


class CreatorIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/creator_text.txt')
    gcd_official_name = indexes.EdgeNgramField(model_attr="gcd_official_name",
                                               boost=DEFAULT_BOOST)
    name = MultiValueField()
    facet_model_name = indexes.CharField(faceted=True)

    birth_year = indexes.IntegerField(model_attr="birth_year")
    sort_name = indexes.CharField(model_attr="gcd_official_name",indexed=False)
    country = indexes.CharField(model_attr='birth_country__code', indexed=False)

    def get_model(self):
        return Creator

    def prepare_facet_model_name(self, obj):
        return "creator"

    def prepare_name(self, obj):
        return [creator_name.pk for creator_name in obj.creator_names.all()]


class CreatorMembershipIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/creator_membership_text.txt')
    name = indexes.CharField(model_attr="organization_name", boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    birth_year = indexes.IntegerField(model_attr="creator__birth_year")
    sort_name = indexes.CharField(model_attr='organization_name', indexed=False)
    country = indexes.CharField(model_attr='creator__birth_country__code',
                                indexed=False)

    def get_model(self):
        return Membership

    def prepare_facet_model_name(self, obj):
        return "creator membership"


class CreatorArtInfluenceIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/creator_artinfluence_text.txt')
    name = indexes.CharField(model_attr="influence_name", boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    birth_year = indexes.IntegerField(model_attr="creator__birth_year")
    sort_name = indexes.CharField(model_attr='influence_name', indexed=False)
    country = indexes.CharField(model_attr='creator__birth_country__code',
                                indexed=False)

    def get_model(self):
        return ArtInfluence

    def prepare_facet_model_name(self, obj):
        return "creator artinfluence"


class CreatorAwardIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/creator_award_text.txt')
    name = indexes.CharField(model_attr="award_name", boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    birth_year = indexes.IntegerField(model_attr="creator__birth_year")
    sort_name = indexes.CharField(model_attr='award_name', indexed=False)
    country = indexes.CharField(model_attr='creator__birth_country__code',
                                indexed=False)

    def get_model(self):
        return Award

    def prepare_facet_model_name(self, obj):
        return "creator award"


class CreatorNonComicWorkIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/creator_noncomicwork_text.txt')
    name = indexes.CharField(model_attr="publication_title", boost=DEFAULT_BOOST)
    facet_model_name = indexes.CharField(faceted=True)

    birth_year = indexes.IntegerField(model_attr="creator__birth_year")
    sort_name = indexes.CharField(model_attr='publication_title', indexed=False)
    country = indexes.CharField(model_attr='creator__birth_country__code',
                                indexed=False)

    def get_model(self):
        return NonComicWork

    def prepare_facet_model_name(self, obj):
        return "creator noncomicwork"


