from datetime import date
from haystack import indexes
from haystack.fields import MultiValueField
from apps.gcd.models import Issue, Series, Story, Publisher, IndiciaPublisher,\
    Brand, BrandGroup, STORY_TYPES, Award, Creator, CreatorMembership,\
    CreatorArtInfluence, ReceivedAward, CreatorNonComicWork, Feature, Printer,\
    Character, Group, Universe

from apps.oi.models import on_sale_date_fields


class ObjectIndex(object):
    def index_queryset(self, using=None):
        """ Used when populating the queryset with db models """
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
        from haystack.exceptions import SkipDocument
        if obj.deleted == True:
            self.remove_object(obj)
            raise SkipDocument

        self.prepared_data = super(ObjectIndex, self).prepare(obj)

        self.prepared_data['sort_name'] = \
          self.prepared_data['sort_name'].lower()

        return self.prepared_data

    # this likely doesn't work
    # use prepare with check on deleted, remove_object and raise SkipDocument ?
    def should_update(self, instance, **kwargs):
        """Overide to check if we need to remove an object from the index."""
        if instance.deleted:
            self.remove_object(instance, **kwargs)
        return not instance.deleted


class IssueIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    title = indexes.CharField(model_attr="title")
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='series__sort_name',
                                  indexed=False)
    key_date = indexes.CharField(model_attr='key_date', indexed=False)
    sort_code = indexes.IntegerField(model_attr='sort_code', indexed=False)
    year = indexes.IntegerField()
    date = indexes.DateField(faceted=True)
    country = indexes.CharField(model_attr='series__country__name',
                                faceted=True, indexed=False)
    language = indexes.CharField(model_attr='series__language__code',
                                 faceted=True, indexed=False)
    publisher = indexes.CharField(model_attr='series__publisher__name',
                                  faceted=True, indexed=False)

    relations_weight = indexes.FloatField()

    def get_model(self):
        return Issue

    def prepare_facet_model_name(self, obj):
        return "issue"

    def prepare_year(self, obj):
        if obj.key_date:
            return int(obj.key_date[:4])
        else:
            return 9999

    def prepare_date(self, obj):
        if obj.key_date:
            year, month, day = on_sale_date_fields(obj.key_date)
            if not month or month < 1 or month > 12:
                month = 1
            if not day or day < 1 or day > 31:
                day = 1
            try:
                return date(year, month, day)
            except ValueError:
                return date(year, month, 1)
        else:
            return None

    def prepare_key_date(self, obj):
        if obj.key_date:
            return obj.key_date
        else:
            return "9999-99-99"

    def prepare_title(self, obj):
        return '%s %s' % (obj.series.name, obj.display_number)

    def prepare_relations_weight(self, obj):
        return obj.to_all_reprints.count()


class SeriesIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    name = indexes.CharField(model_attr="name")
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='sort_name', indexed=False)
    year = indexes.IntegerField()
    date = indexes.DateField(faceted=True)
    country = indexes.CharField(model_attr='country__name',  faceted=True,
                                indexed=False)
    language = indexes.CharField(model_attr='language__code', faceted=True,
                                 indexed=False)
    title_search = indexes.CharField()
    publisher = indexes.CharField(model_attr='publisher__name',
                                  faceted=True, indexed=False)
    issue_count = indexes.IntegerField(model_attr='issue_count',
                                       indexed=False)

    relations_weight = indexes.FloatField()

    def get_model(self):
        return Series

    def prepare_facet_model_name(self, obj):
        return "series"

    def prepare_date(self, obj):
        try:
            return date(obj.year_began, 1, 1)
        except ValueError:
            return None

    def prepare_title_search(self, obj):
        name = obj.name
        if obj.has_issue_title:
            for issue in obj.active_issues():
                if issue.title:
                    name += '\n' + issue.title
        return name

    def prepare_relations_weight(self, obj):
        return float(obj.issue_count)/100.


class StoryIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    title = indexes.CharField(model_attr="title")
    sort_title = indexes.CharField(model_attr="title", indexed=False)

    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='issue__series__sort_name',
                                  indexed=False)
    key_date = indexes.CharField(model_attr='issue__key_date', indexed=False)
    sort_code = indexes.IntegerField(model_attr='issue__sort_code',
                                     indexed=False)
    sequence_number = indexes.IntegerField(model_attr='sequence_number',
                                           indexed=False)
    type = indexes.CharField(model_attr='type__name', faceted=True,
                             indexed=False)
    year = indexes.IntegerField()
    date = indexes.DateField(faceted=True)
    country = indexes.CharField(model_attr='issue__series__country__name',
                                faceted=True, indexed=False)
    language = indexes.CharField(model_attr='issue__series__language__code',
                                 faceted=True, indexed=False)
    publisher = indexes.CharField(model_attr='issue__series__publisher__name',
                                  faceted=True, indexed=False)

    feature = indexes.MultiValueField(faceted=True, null=True)
    characters = indexes.MultiValueField(faceted=True, null=True)

    script = indexes.MultiValueField(faceted=True, null=True)
    pencils = indexes.MultiValueField(faceted=True, null=True)
    inks = indexes.MultiValueField(faceted=True, null=True)
    colors = indexes.MultiValueField(faceted=True, null=True)
    letters = indexes.MultiValueField(faceted=True, null=True)
    editing = indexes.MultiValueField(faceted=True, null=True)

    relations_weight = indexes.FloatField()

    def get_model(self):
        return Story

    def prepare_facet_model_name(self, obj):
        return "story"

    def prepare_year(self, obj):
        if obj.issue.key_date:
            return int(obj.issue.key_date[:4])
        else:
            return 9999

    def prepare_date(self, obj):
        if obj.issue.key_date:
            year, month, day = on_sale_date_fields(obj.issue.key_date)
            if not month or month < 1 or month > 12:
                month = 1
            if not day or day < 1 or day > 31:
                day = 1
            try:
                return date(year, month, day)
            except ValueError:
                return date(year, month, 1)
        else:
            return None

    def prepare_key_date(self, obj):
        if obj.issue.key_date:
            return obj.issue.key_date
        else:
            return "9999-99-99"

    def _prepare_credit(self, obj, field):
        return_val = [(val.strip()) for val in getattr(obj, field).split(';')]
        credits = obj.active_credits.filter(credit_type__name=field)
        if credits:
            if return_val == ['']:
                return_val = [val.creator.display_credit(val, url=False)
                              for val in credits]
            else:
                return_val.extend([val.creator.display_credit(val,
                                                              url=False)
                                   for val in credits])
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

        credits = obj.active_credits.filter(credit_type__name='editing')
        if credits:
            if return_val == ['']:
                return_val = [val.creator.display_credit(val, url=False)
                              for val in credits]
            else:
                return_val.extend([val.creator.display_credit(val,
                                                              url=False)
                                   for val in credits])

        credits = obj.issue.active_credits.filter(credit_type__name='editing')
        if credits:
            if return_val == ['']:
                return_val = [val.creator.display_credit(val, url=False)
                              for val in credits]
            else:
                return_val.extend([val.creator.display_credit(val,
                                                              url=False)
                                   for val in credits])

        if return_val == ['']:
            return None
        else:
            return return_val

    def prepare_feature(self, obj):
        return_val = [(val.strip()) for val in
                      getattr(obj, 'feature').split(';')]
        features = obj.feature_object.all()
        if features:
            if return_val == ['']:
                return_val = [val.name for val in features]
            else:
                return_val.extend([val.name for val in features])
        if return_val == ['']:
            return None
        else:
            return return_val

    def prepare_characters(self, obj):
        return obj.show_characters_as_text()

    def prepare_sort_title(self, obj):
        return obj.show_title(True)

    def prepare(self, obj):
        from haystack.exceptions import SkipDocument
        if obj.type.id == STORY_TYPES['blank']:
            raise SkipDocument
        return super(StoryIndex, self).prepare(obj)

    # I don't think we need this anymore, since we filter out blank
    # stories in the above prepare method.
    #
    # def index_queryset(self, using=None):
    #     """Used when the entire index for model is updated."""
    #     return super(StoryIndex, self).index_queryset(using).exclude(
    #       type=STORY_TYPES['blank'])

    def prepare_relations_weight(self, obj):
        return obj.to_all_reprints.count()


class FeatureIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/feature_text.txt')
    name = indexes.CharField(model_attr="name")
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr="sort_name", indexed=False)
    year = indexes.IntegerField()
    language = indexes.CharField(model_attr='language__code',
                                 faceted=True, indexed=False)

    relations_weight = indexes.FloatField()

    def prepare_year(self, obj):
        if obj.year_first_published:
            return obj.year_first_published
        else:
            return 9999

    def get_model(self):
        return Feature

    def prepare_facet_model_name(self, obj):
        return "feature"

    def prepare_relations_weight(self, obj):
        return obj.to_related_feature.filter(from_feature=obj).count()


class UniverseIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/universe_text.txt')
    name = indexes.CharField()
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(indexed=False)
    year = indexes.IntegerField()

    def prepare_name(self, obj):
        return obj.display_name

    def prepare_sort_name(self, obj):
        return obj.display_name

    def prepare_year(self, obj):
        if obj.year_first_published:
            return obj.year_first_published
        else:
            return 9999

    def get_model(self):
        return Universe

    def prepare_facet_model_name(self, obj):
        return "universe"


class CharacterIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/character_text.txt')
    name = indexes.CharField(model_attr="name")
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr="sort_name", indexed=False)
    year = indexes.IntegerField()
    language = indexes.CharField(model_attr='language__code',
                                 faceted=True, indexed=False)

    relations_weight = indexes.FloatField()

    def prepare_year(self, obj):
        if obj.year_first_published:
            return obj.year_first_published
        else:
            return 9999

    def get_model(self):
        return Character

    def prepare_facet_model_name(self, obj):
        return "character"

    def prepare_relations_weight(self, obj):
        return obj.active_specifications().count() + \
               obj.active_translations().filter(from_character=obj).count()


class GroupIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/group_text.txt')
    name = indexes.CharField(model_attr="name")
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr="sort_name", indexed=False)
    year = indexes.IntegerField()
    language = indexes.CharField(model_attr='language__code',
                                 faceted=True, indexed=False)

    relations_weight = indexes.FloatField()

    def prepare_year(self, obj):
        if obj.year_first_published:
            return obj.year_first_published
        else:
            return 9999

    def get_model(self):
        return Group

    def prepare_facet_model_name(self, obj):
        return "group"

    def prepare_relations_weight(self, obj):
        return obj.active_translations().filter(from_group=obj).count()


class PublisherIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/publisher_text.txt')
    name = indexes.CharField(model_attr="name")
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='name', indexed=False)
    year = indexes.IntegerField()
    country = indexes.CharField(model_attr='country__name', faceted=True,
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
    name = indexes.CharField(model_attr="name")
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='name', indexed=False)
    year = indexes.IntegerField()
    country = indexes.CharField(model_attr='country__name', faceted=True,
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
    name = indexes.CharField(model_attr="name")
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
    name = indexes.CharField(model_attr="name")
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='name', indexed=False)
    year = indexes.IntegerField()
    country = indexes.CharField(model_attr='parent__country__name',
                                faceted=True, indexed=False)
    publisher = indexes.CharField(model_attr='parent__name',
                                  faceted=True, indexed=False)

    def get_model(self):
        return BrandGroup

    def prepare_facet_model_name(self, obj):
        return "brand group"


class PrinterIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/publisher_text.txt')
    name = indexes.CharField(model_attr="name")
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='name', indexed=False)
    year = indexes.IntegerField()
    country = indexes.CharField(model_attr='country__name', faceted=True,
                                indexed=False)

    def get_model(self):
        return Printer

    def prepare_facet_model_name(self, obj):
        return "printer"


class AwardIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/award_text.txt')
    name = indexes.CharField(model_attr="name")
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='name', indexed=False)

    def get_model(self):
        return Award

    def prepare_facet_model_name(self, obj):
        return "award"


# TODO reconsider only award_name for name in index
class ReceivedAwardIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/received_award_text.txt')
    name = indexes.CharField(model_attr="award_name")
    facet_model_name = indexes.CharField(faceted=True)

    year = indexes.IntegerField()
    date = indexes.DateField(faceted=True)
    sort_name = indexes.CharField(model_attr='award_name', indexed=False)

    def prepare_year(self, obj):
        if obj.award_year:
            return obj.award_year
        else:
            return 9999

    def prepare_date(self, obj):
        if obj.award_year:
            try:
                return date(obj.award_year, 1, 1)
            except ValueError:
                return None
        else:
            return None

    def get_model(self):
        return ReceivedAward

    def prepare_facet_model_name(self, obj):
        return "received award"


class CreatorIndex(ObjectIndex, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/creator_text.txt')
    gcd_official_name = indexes.CharField(model_attr="gcd_official_name")
    name = MultiValueField()
    facet_model_name = indexes.CharField(faceted=True)

    year = indexes.IntegerField()
    date = indexes.DateField(faceted=True)
    sort_name = indexes.CharField(model_attr="sort_name", indexed=False)
    country = indexes.CharField(model_attr='birth_country__name',
                                indexed=False, faceted=True, null=True)

    relations_weight = indexes.FloatField()

    def get_model(self):
        return Creator

    def prepare_facet_model_name(self, obj):
        return "creator"

    def prepare_name(self, obj):
        return obj.gcd_official_name

    def prepare_year(self, obj):
        if obj.birth_date.year and '?' not in obj.birth_date.year:
            return int(obj.birth_date.year)
        else:
            return 9999

    def prepare_date(self, obj):
        if obj.birth_date.year:
            try:
                return date(int(obj.birth_date.year), 1, 1)
            except ValueError:
                return None
        else:
            return None

    def prepare_relations_weight(self, obj):
        return obj.active_influenced_creators().count() + \
               obj.active_awards().count() + \
               obj.active_awards_for_issues().count() + \
               obj.active_awards_for_stories().count()


class CreatorMembershipIndex(ObjectIndex, indexes.SearchIndex,
                             indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name=
                             'search/indexes/gcd/creator_membership_text.txt')
    name = indexes.CharField(model_attr="organization_name")
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
    title = indexes.CharField(model_attr="influence")
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='influence', indexed=False)
    country = indexes.CharField(model_attr='creator__birth_country__name',
                                faceted=True, indexed=False, null=True)

    def get_model(self):
        return CreatorArtInfluence

    def prepare_facet_model_name(self, obj):
        return "creator art influence"

    def prepare_title(self, obj):
        return str(obj)


class CreatorNonComicWorkIndex(ObjectIndex, indexes.SearchIndex,
                               indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True,
           template_name='search/indexes/gcd/creator_non_comic_work_text.txt')
    facet_model_name = indexes.CharField(faceted=True)

    sort_name = indexes.CharField(model_attr='publication_title',
                                  indexed=False)
    country = indexes.CharField(model_attr='creator__birth_country__name',
                                faceted=True, indexed=False, null=True)

    def get_model(self):
        return CreatorNonComicWork

    def prepare_facet_model_name(self, obj):
        return "creator non comic work"
