import django.urls as urlresolvers
from django.db import models

from taggit.managers import TaggableManager

from .gcddata import GcdData, GcdLink
from apps.stddata.models import Language
from apps.oi import states


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
        return False

    def pending_deletion(self):
        return self.revisions.filter(changeset__state__in=states.ACTIVE,
                                     deleted=True).count() == 1

    _update_stats = True

    def display_year_first_published(self):
        if not self.year_first_published:
            return '?'
        else:
            return '%d%s' % (self.year_first_published,
                             '?' if self.year_first_published_uncertain else '')

    def __str__(self):
        if self.year_first_published:
            year = '(p. %s)' % self.year_first_published
        else:
            year = ''
        return '%s %s (%s)' % (str(self.name), year, self.language.name)


class Character(CharacterGroupBase):
    class Meta:
        app_label = 'gcd'
        ordering = ('sort_name', 'created',)
        verbose_name_plural = 'Characters'

    def active_names(self):
        return self.character_names.exclude(deleted=True)

    def active_relations(self):
        return self.from_related_character.all() | \
               self.to_related_character.all()

    def active_memberships(self):
        return self.memberships.all().order_by('year_joined',
                                               'group__sort_name')


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



class CharacterRelation(GcdLink):
    """
    Relations between characters to relate any character to any other
    character.
    """

    class Meta:
        db_table = 'gcd_character_relation'
        app_label = 'gcd'
        ordering = ('to_character', 'relation_type', 'from_character')
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
        ordering = ('to_group', 'relation_type', 'from_group')
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
        else:
            years += 'present'
        return years

    def __str__(self):
        return '%s is %s member of %s' % (str(self.character),
                                          str(self.membership_type),
                                          str(self.group))
