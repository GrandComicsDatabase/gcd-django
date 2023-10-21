import django.urls as urlresolvers
from django.db import models
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from taggit.managers import TaggableManager

import django_tables2 as tables

from .gcddata import GcdData, GcdLink
from apps.stddata.models import Language
from .datasource import ExternalLink


class Multiverse(GcdData):
    class Meta:
        app_label = 'gcd'
        ordering = ('name',)
        verbose_name_plural = 'Multiverses'

    name = models.CharField(max_length=255, db_index=True)
    mainstream = models.ForeignKey('Universe', on_delete=models.CASCADE,
                                   related_name='is_mainstream')


class Universe(GcdData):
    """
    Characters and stories can belong to publisher universe.
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('multiverse', 'designation', 'name')
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
        if self.multiverse:
            display_name = self.multiverse + ': '
        else:
            display_name = ''
        if self.name:
            display_name += self.name
            if self.designation:
                display_name += ' - ' + self.designation
        else:
            display_name += self.designation
        return display_name

    # TODO add queries on story/character links
    def has_dependents(self):
        return True

    def universe_name(self):
        if self.designation:
            return '%s - %s' % (self.name,
                                self.designation)
        else:
            return '%s' % (self.name)

    def __str__(self):
        return '%s : %s' % (self.multiverse, self.universe_name())


class CharacterNameDetail(GcdData):
    """
    Indicates the additional names of a character.
    """

    class Meta:
        db_table = 'gcd_character_name_detail'
        app_label = 'gcd'
        ordering = ['sort_name']
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

    name = models.CharField(max_length=255, db_index=True)
    sort_name = models.CharField(max_length=255, db_index=True, default='')
    disambiguation = models.CharField(max_length=255, db_index=True)

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

    def display_year_first_published(self):
        if not self.year_first_published:
            return '?'
        else:
            return '%d%s' % (self.year_first_published,
                             '?' if self.year_first_published_uncertain
                             else '')

    @property
    def disambiguated(self):
        if self.disambiguation:
            return '%s [%s]' % (self.name, self.disambiguation)
        else:
            return self.name

    def __str__(self):
        if self.year_first_published:
            year = '(p. %s)' % self.year_first_published
        else:
            year = ''
        if self.disambiguation:
            name = '%s [%s]' % (self.name, self.disambiguation)
        else:
            name = self.name
        return '%s %s (%s)' % (name, year, self.language.name)


class Character(CharacterGroupBase):
    class Meta:
        app_label = 'gcd'
        ordering = ('sort_name', 'created',)
        verbose_name_plural = 'Characters'

    external_link = models.ManyToManyField(ExternalLink)
    universe = models.ForeignKey('Universe', on_delete=models.CASCADE,
                                 related_name='characters', null=True)

    def active_names(self):
        return self.character_names.exclude(deleted=True)

    def active_relations(self):
        return self.from_related_character.all() | \
               self.to_related_character.all()

    def active_specifications(self):
        return self.to_related_character.filter(relation_type_id=6)

    def active_generalisations(self):
        return self.from_related_character.filter(relation_type_id=6)

    def active_memberships(self):
        return self.memberships.all().order_by('year_joined',
                                               'group__sort_name')

    def active_universes(self):
        from .story import StoryCharacter
        appearances = StoryCharacter.objects.filter(character__character=self,
                                                    deleted=False)
        universes = appearances.values_list('universe', flat=True).distinct()
        return Universe.objects.filter(id__in=universes)

    def has_dependents(self):
        if self.active_memberships().exists():
            return True
        return super(Character, self).has_dependents()

    # def stat_counts(self):
    #     """
    #     Returns all count values relevant to this character.
    #     """
    #     if self.deleted:
    #         return {}
    #
    #     return {'characters': 1}

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_character',
                kwargs={'character_id': self.id})

    # TODO, should groupds have a universe ?
    def __str__(self):
        string = super(Character, self).__str__()
        if self.universe:
            return string + ' - %s' % self.universe.universe_name()
        else:
            return string


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

    def __str__(self):
        return '%s >Relation< %s :: %s' % (str(self.from_character),
                                           str(self.to_character),
                                           str(self.relation_type)
                                           )


class Group(CharacterGroupBase):
    class Meta:
        app_label = 'gcd'
        ordering = ('sort_name', 'created',)
        verbose_name_plural = 'Groups'

    def active_relations(self):
        return self.from_related_group.all() | \
               self.to_related_group.all()

    def active_members(self):
        return self.members.all().order_by('year_joined',
                                           'character__sort_name')

    def has_dependents(self):
        if self.active_members().exists():
            return True
        return super(Group, self).has_dependents()

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
        ordering = ('character', 'group', 'membership_type')
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

    def __str__(self):
        return '%s is %s member of %s' % (str(self.character),
                                          str(self.membership_type),
                                          str(self.group))


class CharacterTable(tables.Table):
    credits_count = tables.Column(accessor='issue_credits_count',
                                  verbose_name='Issues')
    character = tables.Column(accessor='name',
                              verbose_name='Character')
    first_credit = tables.Column(verbose_name='First Credit')
    role = tables.Column(accessor='script', orderable=False)

    class Meta:
        model = Character
        fields = ('character', 'first_credit')

    def __init__(self, *args, **kwargs):
        self.creator = kwargs.pop('creator')
        super(CharacterTable, self).__init__(*args, **kwargs)

    def render_character(self, record):
        name_link = '<a href="%s">%s</a> (%s)' % (record.get_absolute_url(),
                                                  esc(record.name),
                                                  record.language.name)
        return mark_safe(name_link)

    def render_first_credit(self, value):
        return value[:4]

    def render_credits_count(self, record):
        url = urlresolvers.reverse(
                'creator_character_issues',
                kwargs={'creator_id': self.creator.id,
                        'character_id': record.id})
        return mark_safe('<a href="%s">%s</a>' % (url,
                                                  record.issue_credits_count))

    def value_credits_count(self, record):
        return record.issue_credits_count

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
