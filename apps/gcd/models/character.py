import django.urls as urlresolvers
from django.db import models
from django.db.models import F
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from taggit.managers import TaggableManager

import django_tables2 as tables

from .gcddata import GcdData, GcdLink
from apps.stddata.models import Language
from .datasource import ExternalLink
from .support_tables import TW_COLUMN_ALIGN_RIGHT, DailyChangesTable


class Multiverse(GcdData):
    class Meta:
        app_label = 'gcd'
        ordering = ('name',)
        verbose_name_plural = 'Multiverses'

    name = models.CharField(max_length=255, db_index=True)
    mainstream = models.ForeignKey('Universe', on_delete=models.CASCADE,
                                   related_name='is_mainstream')

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_multiverse',
                kwargs={'multiverse_id': self.id})

    def active_universes(self):
        return self.universe_set.exclude(deleted=True)

    def __str__(self):
        return '%s' % (self.name)


class Universe(GcdData):
    """
    Characters and stories can belong to publisher universe.
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('verse', 'designation', 'name')
        verbose_name_plural = 'Universes'

    multiverse = models.CharField(max_length=255, db_index=True)
    verse = models.ForeignKey('Multiverse', on_delete=models.CASCADE,
                              null=True)
    name = models.CharField(max_length=255, db_index=True)
    designation = models.CharField(max_length=255, db_index=True)

    year_first_published = models.IntegerField(db_index=True, null=True)
    year_first_published_uncertain = models.BooleanField(default=False)
    description = models.TextField()
    notes = models.TextField()

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_universe',
                kwargs={'universe_id': self.id})

    @property
    def display_name(self):
        if self.verse:
            display_name = self.verse.name + ': '
        else:
            display_name = ''
        if self.name:
            display_name += self.name
            if self.designation:
                display_name += ' - ' + self.designation
        else:
            display_name += self.designation
        return display_name

    def has_dependents(self):
        from .story import Story
        if Story.objects.filter(universe=self, deleted=False).exists():
            return True
        if Character.objects.filter(
          character_names__storycharacter__universe=self,
          character_names__storycharacter__deleted=False,
          deleted=False).exists():
            return True
        return False

    def universe_name(self):
        if self.name and self.designation:
            return '%s - %s' % (self.name,
                                self.designation)
        elif self.designation:
            return '%s' % (self.designation)
        else:
            return '%s' % (self.name)

    def __str__(self):
        verse = str(self.verse) + ' : ' if self.verse else ''
        return '%s%s' % (verse, self.universe_name())


class CharacterNameDetail(GcdData):
    """
    Indicates the additional names of a character.
    """

    class Meta:
        db_table = 'gcd_character_name_detail'
        app_label = 'gcd'
        ordering = ['sort_name', 'character__year_first_published',
                    'character__disambiguation']
        verbose_name_plural = 'CharacterName Details'

    name = models.CharField(max_length=255, db_index=True)
    sort_name = models.CharField(max_length=255, db_index=True, default='')
    character = models.ForeignKey('Character', on_delete=models.CASCADE,
                                  related_name='character_names')
    is_official_name = models.BooleanField(default=False)

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_character',
                kwargs={'character_id': self.character.id})

    def __str__(self):
        return '%s - %s' % (str(self.character), str(self.name))


class CharacterRelationType(models.Model):
    """
    The type of relation between two characters.
    """

    class Meta:
        db_table = 'gcd_character_relation_type'
        app_label = 'gcd'
        ordering = ('type',)
        verbose_name_plural = 'Character Relation Types'

    type = models.CharField(max_length=50)
    reverse_type = models.CharField(max_length=50)

    def __str__(self):
        return str(self.type)


class CharacterGroupBase(GcdData):
    class Meta:
        abstract = True
        app_label = 'gcd'
        ordering = ('sort_name', 'year_first_published',
                    'disambiguation',)

    name = models.CharField(max_length=255, db_index=True)
    sort_name = models.CharField(max_length=255, db_index=True, default='')
    disambiguation = models.CharField(max_length=255, db_index=True)
    universe = models.ForeignKey('Universe', on_delete=models.CASCADE,
                                 null=True)

    year_first_published = models.IntegerField(db_index=True, null=True)
    year_first_published_uncertain = models.BooleanField(default=False)
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    description = models.TextField()
    notes = models.TextField()
    keywords = TaggableManager()

    def has_dependents(self):
        if self.active_relations().exists():
            return True
        return False

    _update_stats = True

    @property
    def disambiguated(self):
        if self.disambiguation:
            return '%s [%s]' % (self.name, self.disambiguation)
        else:
            return self.name

    def descriptor(self, language=False, disambiguation=False, year=True):
        if self.universe:
            universe = ' - %s' % self.universe.universe_name()
        else:
            universe = ''
        if year and self.year_first_published:
            year = ' (p. %s)' % self.year_first_published
        else:
            year = ''
        if disambiguation and self.disambiguation:
            name = '%s [%s]' % (self.name, self.disambiguation)
        else:
            name = self.name
        if language:
            return '%s%s%s (%s)' % (name, year, universe, self.language.name)
        else:
            return '%s%s%s' % (name, year, universe)

    def translation_descriptor(self):
        return self.descriptor(language=True, disambiguation=False)

    def object_page_name(self):
        return self.descriptor(language=True, year=False)

    def object_markdown_name(self):
        return self.descriptor(language=False, disambiguation=True, year=False)

    def __str__(self):
        return self.descriptor(language=True, disambiguation=True)


class Character(CharacterGroupBase):
    class Meta(CharacterGroupBase.Meta):
        verbose_name_plural = 'Characters'

    external_link = models.ManyToManyField(ExternalLink)

    def active_names(self):
        return self.character_names.exclude(deleted=True)

    def active_relations(self):
        return self.from_related_character.all() | \
               self.to_related_character.all()

    def active_relations_own(self):
        return self.active_relations().exclude(relation_type_id=1)

    def active_translations(self):
        return self.active_relations().filter(relation_type_id=1)

    def active_specifications(self):
        return self.to_related_character.filter(relation_type_id=6)

    def active_generalisations(self):
        return self.from_related_character.filter(relation_type_id=6)

    def active_alternate_universe_versions(self):
        if self.universe:
            return self.active_generalisations().get().from_character\
                       .active_specifications().exclude(to_character=self)
        else:
            return None

    def active_memberships(self):
        return self.memberships.all()

    def active_universe_origins(self):
        from .story import StoryCharacter
        appearances = StoryCharacter.objects.filter(character__character=self,
                                                    deleted=False)
        universes = set(appearances.values_list('universe',
                                                flat=True).distinct())
        return Universe.objects.filter(id__in=universes)

    def active_universe_appearances(self):
        from .story import Story
        if self.universe and self.active_generalisations().exists():
            character = self.active_generalisations().get().from_character
            appearances = Story.objects.filter(
              appearing_characters__character__character=character,
              appearing_characters__universe=self.universe,
              appearing_characters__deleted = False,
              deleted=False)
        else:
            appearances = Story.objects.filter(
              appearing_characters__character__character=self,
              appearing_characters__deleted = False,
              deleted=False)
        universes = set(appearances.values_list('universe',
                                                flat=True).distinct())
        return Universe.objects.filter(id__in=universes)

    def active_universe_appearances_with_origin(self, origin_universe):
        from .story import Story
        appearances = Story.objects.filter(
          appearing_characters__character__character=self,
          appearing_characters__universe_id=origin_universe,
          deleted=False)
        universes = appearances.values_list('universe',
                                            flat=True).distinct()
        return Universe.objects.filter(id__in=universes)

    def translated_from(self):
        try:
            relation = self.from_related_character.get(relation_type__id=1)
        except self.from_related_character.model.DoesNotExist:
            return None
        return relation.from_character

    # what is with translation over character records ?
    # German . English - French, copying from first to last ?
    def translations(self, language):
        relations = self.active_translations()
        if relations.filter(to_character__language=language).count():
            return Character.objects.filter(
              language=language,
              from_related_character__from_character=self,
              deleted=False)
        if relations.filter(from_character__language=language).count():
            return Character.objects.filter(
              language=language,
              to_related_character__to_character=self,
              deleted=False)
        return Character.objects.none()

    def official_name(self):
        return self.active_names().get(is_official_name=True)

    def has_dependents(self):
        if super(Character, self).has_dependents() or \
          self.active_memberships().exists():
            return True
        from .story import StoryCharacter
        if StoryCharacter.objects.filter(character__character=self,
                                         deleted=False).exists():
            return True
        return False

    # def stat_counts(self):
    #     """
    #     Returns all count values relevant to this character.
    #     """
    #     if self.deleted:
    #         return {}
    #
    #     return {'characters': 1}

    def get_issue_list_url(self):
        return urlresolvers.reverse('character_issues',
                                    kwargs={'character_id': self.id})

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_character',
                kwargs={'character_id': self.id})


class CharacterRelation(GcdLink):
    """
    Relations between characters to relate any character to any other
    character.
    """

    class Meta:
        db_table = 'gcd_character_relation'
        app_label = 'gcd'
        ordering = ('relation_type', 'to_character', 'from_character')
        verbose_name_plural = 'Character Relations'

    to_character = models.ForeignKey(Character, on_delete=models.CASCADE,
                                     related_name='from_related_character')
    from_character = models.ForeignKey(Character, on_delete=models.CASCADE,
                                       related_name='to_related_character')
    relation_type = models.ForeignKey(CharacterRelationType,
                                      on_delete=models.CASCADE,
                                      related_name='relation_type')
    notes = models.TextField()

    def pre_process_relation(self, character):
        if self.from_character == character:
            return [self.to_character, self.relation_type.type]
        if self.to_character == character:
            return [self.from_character, self.relation_type.reverse_type]

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_character_relation',
                kwargs={'character_relation_id': self.id})

    def object_page_name(self):
        return mark_safe('<a href="%s">%s</a> - <a href="%s">%s</a>' % (
          self.from_character.get_absolute_url(),
          self.from_character.official_name().name,
          self.to_character.get_absolute_url(),
          self.to_character.official_name().name))

    def __str__(self):
        return '%s >Relation< %s :: %s' % (str(self.from_character),
                                           str(self.to_character),
                                           str(self.relation_type)
                                           )


class GroupNameDetail(GcdData):
    """
    Indicates the additional names of a group.
    """

    class Meta:
        db_table = 'gcd_group_name_detail'
        app_label = 'gcd'
        ordering = ['sort_name', 'group__year_first_published',
                    'group__disambiguation']
        verbose_name_plural = 'GroupName Details'

    name = models.CharField(max_length=255, db_index=True)
    sort_name = models.CharField(max_length=255, db_index=True, default='')
    group = models.ForeignKey('Group', on_delete=models.CASCADE,
                              related_name='group_names')
    is_official_name = models.BooleanField(default=False)

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_group',
                kwargs={'group_id': self.group.id})

    def __str__(self):
        return '%s - %s' % (str(self.group), str(self.name))


class Group(CharacterGroupBase):
    class Meta(CharacterGroupBase.Meta):
        verbose_name_plural = 'Groups'

    def active_names(self):
        return self.group_names.exclude(deleted=True)

    def active_relations(self):
        return self.from_related_group.all() | \
               self.to_related_group.all()

    def active_relations_own(self):
        return self.active_relations().exclude(relation_type_id=1)

    def active_specifications(self):
        return self.to_related_group.filter(relation_type_id=5)

    def active_generalisations(self):
        return self.from_related_group.filter(relation_type_id=5)

    def active_translations(self):
        return self.active_relations().filter(relation_type_id=1)

    def active_members(self):
        return self.members.all()

    def active_universe_origins(self):
        from .story import StoryGroup
        appearances = StoryGroup.objects.filter(group_name__group=self,
                                                deleted=False)
        universes = set(appearances.values_list('universe',
                                                flat=True).distinct())
        return Universe.objects.filter(id__in=universes)

    def active_universe_appearances(self):
        from .story import Story
        if self.universe and self.active_generalisations().exists():
            group = self.active_generalisations().get().from_group
            appearances = Story.objects.filter(
              appearing_groups__group_name__group=group,
              appearing_groups__universe=self.universe,
              appearing_groups__deleted=False,
              deleted=False)
        else:
            appearances = Story.objects.filter(
              appearing_groups__group_name__group=self,
              appearing_groups__deleted=False,
              deleted=False)
        universes = set(appearances.values_list('universe',
                                                flat=True).distinct())
        return Universe.objects.filter(id__in=universes)

    def active_universe_appearances_with_origin(self, origin_universe):
        from .story import Story
        appearances = Story.objects.filter(
          appearing_groups__group_name__group=self,
          appearing_groups__universe_id=origin_universe,
          appearing_groups__deleted=False,
          deleted=False)
        universes = appearances.values_list('universe',
                                            flat=True).distinct()
        return Universe.objects.filter(id__in=universes)

    # what is with translation over character records ?
    # German . English - French, copying from first to last ?
    def translations(self, language):
        relations = self.active_translations()
        if relations.filter(to_group__language=language).count():
            return Group.objects.filter(
              language=language,
              from_related_group__from_group=self,
              deleted=False)
        if relations.filter(from_group__language=language).count():
            return Group.objects.filter(
              language=language,
              to_related_group__to_group=self,
              deleted=False)
        return Group.objects.none()

    def translated_from(self):
        try:
            relation = self.from_related_group.get(relation_type__id=1)
        except self.from_related_group.model.DoesNotExist:
            return None
        return relation.from_group

    def official_name(self):
        return self.active_names().get(is_official_name=True)

    def has_dependents(self):
        if super(Group, self).has_dependents() or \
          self.active_members().exists():
            return True
        from .story import StoryGroup
        if StoryGroup.objects.filter(group_name__group=self,
                                     deleted=False).exists():
            return True
        return False

    def get_issue_list_url(self):
        return urlresolvers.reverse('group_issues',
                                    kwargs={'group_id': self.id})

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_group',
                kwargs={'group_id': self.id})


class GroupRelationType(models.Model):
    """
    The type of relation between two groups.
    """

    class Meta:
        db_table = 'gcd_group_relation_type'
        app_label = 'gcd'
        ordering = ('type',)
        verbose_name_plural = 'Group Relation Types'

    type = models.CharField(max_length=50)
    reverse_type = models.CharField(max_length=50)

    def __str__(self):
        return str(self.type)


class GroupRelation(GcdLink):
    """
    Relations between group to relate any group to any other group.
    """

    class Meta:
        db_table = 'gcd_group_relation'
        app_label = 'gcd'
        ordering = ('relation_type', 'to_group', 'from_group')
        verbose_name_plural = 'Group Relations'

    to_group = models.ForeignKey(Group, on_delete=models.CASCADE,
                                 related_name='from_related_group')
    from_group = models.ForeignKey(Group, on_delete=models.CASCADE,
                                   related_name='to_related_group')
    relation_type = models.ForeignKey(GroupRelationType,
                                      on_delete=models.CASCADE,
                                      related_name='relation_type')
    notes = models.TextField()

    def pre_process_relation(self, group):
        if self.from_group == group:
            return [self.to_group, self.relation_type.type]
        if self.to_group == group:
            return [self.from_group, self.relation_type.reverse_type]

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_group_relation',
                kwargs={'group_relation_id': self.id})

    def object_page_name(self):
        return mark_safe('<a href="%s">%s</a> - <a href="%s">%s</a>' % (
          self.from_group.get_absolute_url(),
          self.from_group.official_name().name,
          self.to_group.get_absolute_url(),
          self.to_group.official_name().name))

    def __str__(self):
        return '%s >Relation< %s :: %s' % (str(self.from_group),
                                           str(self.to_group),
                                           str(self.relation_type)
                                           )


class GroupMembershipType(models.Model):
    """
    The type of membership for a character in a group.
    """

    class Meta:
        db_table = 'gcd_group_membership_type'
        app_label = 'gcd'
        ordering = ('type',)
        verbose_name_plural = 'Group Membership Types'

    type = models.CharField(max_length=50)
    reverse_type = models.CharField(max_length=50)

    def __str__(self):
        return str(self.type)


class GroupMembership(GcdLink):
    """
    Characters can belong to any other group.
    """
    class Meta:
        db_table = 'gcd_group_membership'
        app_label = 'gcd'
        ordering = ('character__sort_name', 'group__sort_name', 'year_joined')
        verbose_name_plural = 'Group Memberships'

    character = models.ForeignKey(Character, on_delete=models.CASCADE,
                                  related_name='memberships')
    group = models.ForeignKey(Group, on_delete=models.CASCADE,
                              related_name='members')
    membership_type = models.ForeignKey(GroupMembershipType,
                                        on_delete=models.CASCADE)
    year_joined = models.PositiveSmallIntegerField(null=True, blank=True)
    year_joined_uncertain = models.BooleanField(default=False)
    year_left = models.PositiveSmallIntegerField(null=True, blank=True)
    year_left_uncertain = models.BooleanField(default=False)
    notes = models.TextField()

    def display_years(self):
        if not self.year_joined:
            years = '? - '
        else:
            years = '%d%s - ' % (self.year_joined,
                                 '?' if self.year_joined_uncertain else '')
        if self.year_left:
            years += '%d%s' % (self.year_left,
                               '?' if self.year_left_uncertain else '')
        elif self.year_left_uncertain:
            years += '?'
        else:
            years += 'present'
        return years

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_group_membership',
                kwargs={'group_membership_id': self.id})

    def object_page_name(self):
        return mark_safe('<a href="%s">%s</a> in <a href="%s">%s</a>' % (
          self.character.get_absolute_url(),
          self.character.official_name().name,
          self.group.get_absolute_url(),
          self.group.official_name().name))

    def __str__(self):
        return '%s is %s member of %s' % (str(self.character),
                                          str(self.membership_type),
                                          str(self.group))


class CharacterTable(tables.Table):
    name = tables.Column(verbose_name='Character')
    year_first_published = tables.Column(verbose_name='First Published')

    def __init__(self, *args, **kwargs):
        self.group = kwargs.pop('group', None)
        if self.group:
            self.base_columns['name'].verbose_name = 'Group'
            self.group = False
        else:
            self.base_columns['name'].verbose_name = 'Character'
        super(CharacterTable, self).__init__(*args, **kwargs)

    def order_year_first_published(self, query_set, is_descending):
        if is_descending:
            query_set = query_set.order_by(F('year_first_published')
                                           .desc(nulls_last=True),
                                           'sort_name',
                                           'language__code')
        else:
            query_set = query_set.order_by(F('year_first_published')
                                           .asc(nulls_last=True),
                                           'sort_name',
                                           'language__code')
        return (query_set, True)

    def order_name(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'sort_name',
                                       direction + 'disambiguation',
                                       F('year_first_published')
                                       .asc(nulls_last=True),
                                       'language__code')
        return (query_set, True)

    def render_name(self, record):
        name_link = '<a href="%s">%s</a> (%s)' % (record.get_absolute_url(),
                                                  esc(record.disambiguated),
                                                  record.language.name)
        return mark_safe(name_link)

    def value_name(self, value):
        return value


class DailyChangesCharacterTable(CharacterTable, DailyChangesTable):
    pass


class CharacterSearchTable(CharacterTable):
    issue_count = tables.Column(verbose_name='Issues',
                                initial_sort_descending=True,
                                attrs={'td': {'class':
                                              TW_COLUMN_ALIGN_RIGHT +
                                              'shadow-md p-2'}})

    def order_name(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'sort_name',
                                       direction + 'disambiguation',
                                       F('year_first_published')
                                       .asc(nulls_last=True),
                                       '-issue_count',
                                       'language__code')
        return (query_set, True)

    def order_issue_count(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'issue_count',
                                       'sort_name',
                                       'disambiguation',
                                       F('year_first_published')
                                       .asc(nulls_last=True),
                                       'language__code')
        return (query_set, True)

    def order_year_first_published(self, query_set, is_descending):
        if is_descending:
            query_set = query_set.order_by(F('year_first_published')
                                           .desc(nulls_last=True),
                                           'sort_name',
                                           'disambiguation',
                                           '-issue_count',
                                           'language__code')
        else:
            query_set = query_set.order_by(F('year_first_published')
                                           .asc(nulls_last=True),
                                           'sort_name',
                                           'disambiguation',
                                           '-issue_count',
                                           'language__code')
        return (query_set, True)

    def render_issue_count(self, record):
        return mark_safe('<a href="%s">%s</a>' % (record.get_issue_list_url(),
                                                  record.issue_count))

    def value_issue_count(self, record):
        return record.issue_count


class CreatorCharacterTable(CharacterSearchTable):
    first_credit = tables.Column(verbose_name='First Credit')
    role = tables.Column(accessor='script', orderable=False)

    class Meta:
        model = Character
        fields = ('name', 'year_first_published', 'first_credit',
                  'issue_count', 'role')

    def __init__(self, *args, **kwargs):
        self.creator = kwargs.pop('creator')
        super(CreatorCharacterTable, self).__init__(*args, **kwargs)

    def order_first_credit(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'first_credit',
                                       'sort_name',
                                       'disambiguation',
                                       '-issue_count',
                                       'language__code')
        return (query_set, True)

    def render_first_credit(self, value):
        return value[:4]

    def render_issue_count(self, record):
        url = urlresolvers.reverse(
                'creator_character_issues',
                kwargs={'creator_id': self.creator.id,
                        'character_id': record.id})
        return mark_safe('<a href="%s">%s</a>' % (url,
                                                  record.issue_count))

    def render_role(self, record):
        role = ''
        if record.script:
            role = 'script (%d); ' % record.script
        if record.pencils:
            role += 'pencils (%d); ' % record.pencils
        if record.inks:
            role += 'inks (%d); ' % record.inks
        if record.colors:
            role += 'colors (%d); ' % record.colors
        if record.letters:
            role += 'letters (%d); ' % record.letters
        return role[:-2]


class UniverseCharacterTable(CharacterSearchTable):
    first_appearance = tables.Column(verbose_name='First Appearance')

    class Meta:
        model = Character
        fields = ('name', 'year_first_published', 'first_appearance')

    def __init__(self, *args, **kwargs):
        self.universe = kwargs.pop('universe')
        super(UniverseCharacterTable, self).__init__(*args, **kwargs)

    def order_first_appearance(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'first_appearance',
                                       'sort_name',
                                       '-issue_count',
                                       'language__code')
        return (query_set, True)

    def render_first_appearance(self, value):
        return value

    def render_issue_count(self, record):
        url = urlresolvers.reverse(
                'character_origin_universe_issues',
                kwargs={'universe_id': self.universe.id,
                        'character_id': record.id})
        return mark_safe('<a href="%s">%s</a>' % (url,
                                                  record.issue_count))


class UniverseGroupTable(CharacterSearchTable):
    first_appearance = tables.Column(verbose_name='First Appearance')

    class Meta:
        model = Group
        fields = ('name', 'year_first_published', 'first_appearance')

    def __init__(self, *args, **kwargs):
        self.universe = kwargs.pop('universe')
        kwargs['group'] = True
        super(UniverseGroupTable, self).__init__(*args, **kwargs)

    def order_first_appearance(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'first_appearance',
                                       'sort_name',
                                       '-issue_count',
                                       'language__code')
        return (query_set, True)

    def render_first_appearance(self, value):
        return value

    def render_issue_count(self, record):
        url = urlresolvers.reverse(
          'group_origin_universe_issues',
          kwargs={'universe_id': self.universe.id,
                  'group_id': record.id})
        return mark_safe('<a href="%s">%s</a>' % (url,
                                                  record.issue_count))


class CharacterCharacterTable(UniverseCharacterTable):
    class Meta:
        model = Character
        fields = ('name', 'year_first_published', 'first_appearance')

    def __init__(self, *args, **kwargs):
        self.character = kwargs.pop('character')
        self.universe_id = kwargs.pop('universe_id', None)
        super(UniverseCharacterTable, self).__init__(*args, **kwargs)

    def render_issue_count(self, record):
        if self.universe_id is not None:
            url = urlresolvers.reverse(
                    'character_origin_universe_issues_per_character',
                    kwargs={'character_id': self.character.id,
                            'character_with_id': record.id,
                            'universe_id': self.universe_id})
        else:
            url = urlresolvers.reverse(
                    'character_issues_character',
                    kwargs={'character_id': self.character.id,
                            'character_with_id': record.id})
        return mark_safe('<a href="%s">%s</a>' % (url,
                                                  record.issue_count))


class FeatureCharacterTable(UniverseCharacterTable):
    class Meta:
        model = Character
        fields = ('name', 'year_first_published', 'first_appearance')

    def __init__(self, *args, **kwargs):
        self.feature = kwargs.pop('feature')
        super(UniverseCharacterTable, self).__init__(*args, **kwargs)

    def render_issue_count(self, record):
        url = urlresolvers.reverse(
                'character_issues_per_feature',
                kwargs={'feature_id': self.feature.id,
                        'character_id': record.id})
        return mark_safe('<a href="%s">%s</a>' % (url,
                                                  record.issue_count))


class SeriesCharacterTable(UniverseCharacterTable):
    class Meta:
        model = Character
        fields = ('name', 'year_first_published', 'first_appearance')

    def __init__(self, *args, **kwargs):
        self.series = kwargs.pop('series')
        super(UniverseCharacterTable, self).__init__(*args, **kwargs)

    def render_issue_count(self, record):
        url = urlresolvers.reverse(
                'character_issues_per_series',
                kwargs={'series_id': self.series.id,
                        'character_id': record.id})
        return mark_safe('<a href="%s">%s</a>' % (url,
                                                  record.issue_count))
