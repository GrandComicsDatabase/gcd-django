import calendar
import django.urls as urlresolvers
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

import django_tables2 as tables

from .gcddata import GcdData
from .award import ReceivedAward
from .datasource import DataSource, ExternalLink
from .image import Image
from apps.stddata.models import Country, Date, Script

MONTH_CHOICES = [(i, calendar.month_name[i]) for i in range(1, 13)]

NAME_TYPES = {
    'house': 5,
    'studio': 8,
    'ghost': 12,
    'joint': 13,
}


def _display_day(date, table=False):
    if date.year:
        display = '%s%s ' % (date.year,
                             '?' if date.year_uncertain else '')
    else:
        if table:
            return mark_safe('&mdash;')
        display = 'year? '

    if date.month:
        display = '%s%s%s ' % (
          display, calendar.month_name[int(date.month)],
          '?' if date.month_uncertain else '')
    else:
        if table:
            return display
        display += 'month? '

    if date.day:
        display = '%s%s%s ' % (display, date.day.lstrip('0'),
                               '?' if date.day_uncertain else '')
    else:
        if table:
            return display
        display += 'day? '

    return display


def _display_place(self, type, table=False):
    city = '%s_city' % type
    if getattr(self, city):
        display = '%s%s' % (getattr(self, city),
                            '?' if getattr(self, city + '_uncertain') else '')
    else:
        display = ''

    province = '%s_province' % type
    if getattr(self, province):
        if display:
            display += ', '
        display = '%s%s%s' % (display, getattr(self, province),
                              '?' if getattr(self,
                                             province + '_uncertain') else '')

    country = '%s_country' % type
    if getattr(self, country):
        if display:
            display += ', '
        display = '%s%s%s' % (display, getattr(self, country),
                              '?' if getattr(self,
                                             country + '_uncertain') else '')

    if display == '':
        if table:
            return mark_safe('&mdash;')
        else:
            return '?'
    return display


class NameType(models.Model):
    """
    Indicates the various types of names
    Multiple Name types could be checked per name.
    """

    class Meta:
        db_table = 'gcd_name_type'
        app_label = 'gcd'
        ordering = ('type',)
        verbose_name_plural = 'Name Types'

    description = models.TextField(default='', blank=True)
    type = models.CharField(max_length=50)

    def __str__(self):
        return '%s' % str(self.type)


class CreatorNameDetail(GcdData):
    """
    Indicates the various names of creator
    Multiple Name could be checked per creator.
    """

    class Meta:
        db_table = 'gcd_creator_name_detail'
        app_label = 'gcd'
        ordering = ['sort_name', '-creator__birth_date__year', 'type_id']
        verbose_name_plural = 'CreatorName Details'

    name = models.CharField(max_length=255, db_index=True)
    sort_name = models.CharField(max_length=255, db_index=True, default='')
    is_official_name = models.BooleanField(default=False)
    given_name = models.CharField(max_length=255, db_index=True, default='')
    family_name = models.CharField(max_length=255, db_index=True, default='')
    creator = models.ForeignKey('Creator', on_delete=models.CASCADE,
                                related_name='creator_names')
    type = models.ForeignKey('NameType', on_delete=models.CASCADE,
                             related_name='creator_name_details', null=True)
    in_script = models.ForeignKey(Script, on_delete=models.CASCADE,
                                  default=Script.LATIN_PK)

    def display_credit(self, credit, url=True, compare=False, search=False,
                       show_sources=False):
        co_name = ''
        as_name = ''
        extra_name = ''
        compare_info = ''
        if search:
            url = False
        if self.is_official_name:
            name = self.name
            if compare and self.creator.disambiguation:
                name += ' [%s]' % self.creator.disambiguation
            if self.type and self.type_id == NAME_TYPES['house']:
                if credit.credit_name:
                    credit.credit_name += ', house name'
                else:
                    credit.credit_name = 'house name'
            elif self.type and self.type_id == NAME_TYPES['joint']:
                if credit.credit_name:
                    credit.credit_name += ', joint name'
                else:
                    credit.credit_name = 'joint name'
        else:
            name = self.creator.gcd_official_name
            if compare and self.creator.disambiguation:
                name += ' [%s]' % self.creator.disambiguation
            if (credit.is_credited and not credit.credited_as) \
               or (self.type and self.type_id == NAME_TYPES['studio']) \
               or (self.in_script != self.creator.creator_names.get(
                                          is_official_name=True).in_script):
                as_name = self
            if self.type and self.type_id == NAME_TYPES['ghost']:
                if self.creator_relation.exists():
                    as_name = self.creator_relation.get().to_creator
                else:
                    as_name = self
            elif self.type and self.type_id == NAME_TYPES['house']:
                if self.creator_relation.exists():
                    as_name = self.creator_relation.get().to_creator\
                                  .active_names().get(is_official_name=True)
                else:
                    as_name = self
            elif self.type and self.type_id == NAME_TYPES['joint']:
                if self.creator_relation.exists():
                    as_name = self.creator_relation.get().to_creator\
                                  .active_names().get(is_official_name=True)
                else:
                    as_name = self
            elif compare or search:
                # for compare and search use uncredited non-official-name
                as_name = self
            if self.type and self.type_id == NAME_TYPES['studio'] \
               and self.creator_relation.count():
                co_name = self.creator_relation.filter(deleted=False).get()\
                              .to_creator

        if credit.uncertain:
            name += ' ?'

        # no credited_as, signed_as
        if hasattr(credit, 'is_signed') and (
          credit.is_signed and not credit.signed_as) and (
          credit.is_signed and not credit.signature) and (
          credit.is_credited and not credit.credited_as) and (
          credit.is_credited and credit.creator.is_official_name):
            credit_attribute = 'credited, signed'
        elif hasattr(credit, 'is_signed') and (
          credit.is_signed and not credit.signed_as) and (
          credit.is_signed and not credit.signature):
            credit_attribute = 'signed'
        elif (credit.is_credited and not credit.credited_as and
              credit.creator.is_official_name):
            credit_attribute = 'credited'
        else:
            credit_attribute = ''

        if url:
            credit_text = '<a href="%s">%s</a>' % \
                          (self.creator.get_absolute_url(),
                           esc(name))
        else:
            credit_text = esc(name)
        if co_name:
            if self.type_id == NAME_TYPES['studio']:
                if url:
                    credit_text += ' of <a href="%s">%s</a>' % \
                                    (co_name.get_absolute_url(),
                                     esc(co_name.gcd_official_name))
                else:
                    credit_text += ' of %s' % esc(co_name.gcd_official_name)
            else:
                raise ValueError
        if as_name:
            if self.type_id == NAME_TYPES['ghost']:
                attribute = 'ghosted for '
                if self.creator_relation.exists():
                    display_as_name = as_name.gcd_official_name
                    if self.name != display_as_name:
                        extra_name = self.name
                else:
                    display_as_name = as_name.name
            elif self.type_id == NAME_TYPES['house']:
                attribute = 'under house name '
                display_as_name = as_name.name
            elif self.type_id == NAME_TYPES['joint']:
                attribute = 'under joint name '
                display_as_name = as_name.name
            elif credit.is_credited and not credit.credited_as:
                attribute = 'credited as '
                display_as_name = as_name.name
            elif self.in_script != self.creator.creator_names.get(
                                        is_official_name=True).in_script:
                attribute = ''
                display_as_name = as_name.name
            else:
                attribute = 'as '
                display_as_name = as_name.name
                if compare and self.type_id not in [NAME_TYPES['studio'], ]:
                    compare_info = '<br> Note: Non-official name '\
                                    'selected without credited-flag.'
            if url:
                credit_text += ' (%s<a href="%s">%s</a>)' % \
                                (attribute,
                                 as_name.get_absolute_url(),
                                 esc(display_as_name))
            else:
                credit_text += ' (%s %s)' % \
                                (attribute,
                                 esc(display_as_name))
            if extra_name:
                credit_text = credit_text[:-1] + ' as %s)' % extra_name
        if credit_attribute:
            credit_text += ' (%s)' % credit_attribute
        if hasattr(credit, 'signature') and credit.signature:
            if url:
                from apps.gcd.templatetags.display import absolute_url
                credit_text += ' (signed as %s)' % \
                               absolute_url(credit.signature,
                                            credit.signature.signature,
                                            esc(credit.signature.name))
            else:
                credit_text += ' (signed as %s)' % esc(credit.signature.name)

        if credit.credited_as and getattr(credit, 'signed_as', None) and \
           (credit.credited_as == credit.signed_as):
            credit_text += ' (credited, signed as %s)' % \
                           esc(credit.credited_as)
        else:
            if credit.credited_as:
                credit_text += ' (credited as %s)' % esc(credit.credited_as)
            if hasattr(credit, 'is_signed') and credit.signed_as:
                credit_text += ' (signed as %s)' % esc(credit.signed_as)

        if credit.is_sourced:
            if show_sources:
                credit_text += ' (sourced: %s)' % esc(credit.sourced_by)
            else:
                if url:
                    credit_text += ' <a hx-get="/credit/%d/source/"' % \
                      credit.id
                    credit_text += ' hx-target="body" hx-swap="beforeend"' +\
                                   ' style="cursor: pointer; color: #00e;">' +\
                                   '(sourced)</a>'
                else:
                    credit_text += ' (sourced)'

        if credit.credit_name:
            credit_text += ' (%s)' % esc(credit.credit_name)

        if compare_info:
            credit_text += compare_info

        return mark_safe(credit_text)

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_creator',
                kwargs={'creator_id': self.creator.id})

    def __str__(self):
        if self.creator.disambiguation:
            extra = ' [%s]' % self.creator.disambiguation
        else:
            extra = ''
        if self.is_official_name:
            return '%s%s' % (str(self.creator), extra)
        else:
            return '%s%s - %s' % (str(self.creator), extra, str(self.name))


class RelationType(models.Model):
    """
    The type of relation between two creators.
    """

    class Meta:
        db_table = 'gcd_relation_type'
        app_label = 'gcd'
        ordering = ('type',)
        verbose_name_plural = 'Relation Types'

    type = models.CharField(max_length=50)
    reverse_type = models.CharField(max_length=50)

    def __str__(self):
        return str(self.type)


class CreatorManager(models.Manager):
    """
    need to be manage creator model
    with this custom manager in future
    """
    pass


class Creator(GcdData):
    class Meta:
        app_label = 'gcd'
        ordering = ('sort_name', 'created',)
        verbose_name_plural = 'Creators'

    objects = CreatorManager()

    gcd_official_name = models.CharField(max_length=255, db_index=True)
    sort_name = models.CharField(max_length=255, db_index=True, default='')
    disambiguation = models.CharField(max_length=255, default='',
                                      db_index=True)

    birth_date = models.ForeignKey(Date, on_delete=models.CASCADE,
                                   related_name='+', null=True)
    death_date = models.ForeignKey(Date, on_delete=models.CASCADE,
                                   related_name='+', null=True)

    whos_who = models.URLField(null=True)
    external_link = models.ManyToManyField(ExternalLink)

    birth_country = models.ForeignKey(Country, on_delete=models.CASCADE,
                                      related_name='birth_country',
                                      null=True)
    birth_country_uncertain = models.BooleanField(default=False)
    birth_province = models.CharField(max_length=50)
    birth_province_uncertain = models.BooleanField(default=False)
    birth_city = models.CharField(max_length=200)
    birth_city_uncertain = models.BooleanField(default=False)

    death_country = models.ForeignKey(Country, on_delete=models.CASCADE,
                                      related_name='death_country',
                                      null=True)
    death_country_uncertain = models.BooleanField(default=False)
    death_province = models.CharField(max_length=50)
    death_province_uncertain = models.BooleanField(default=False)
    death_city = models.CharField(max_length=200)
    death_city_uncertain = models.BooleanField(default=False)

    portrait = GenericRelation(Image)
    awards = GenericRelation(ReceivedAward)

    bio = models.TextField()
    sample_scan = GenericRelation(Image)
    notes = models.TextField()

    data_source = models.ManyToManyField(DataSource)

    def _portrait(self):
        content_type = ContentType.objects.get_for_model(self)
        img = Image.objects.filter(object_id=self.id, deleted=False,
                                   content_type=content_type, type_id=4)
        if img:
            return img.get()
        else:
            return None

    portrait = property(_portrait)

    def _samplescan(self):
        content_type = ContentType.objects.get_for_model(self)
        img = Image.objects.filter(object_id=self.id, deleted=False,
                                   content_type=content_type, type_id=5)
        if img:
            return img.get()
        else:
            return None

    samplescan = property(_samplescan)

    def full_name(self):
        return str(self)

    def display_birthday(self):
        return _display_day(self.birth_date)

    def display_birthday_table(self):
        return _display_day(self.birth_date, table=True)

    def display_birthplace(self):
        return _display_place(self, 'birth')

    def display_birthplace_table(self):
        return _display_place(self, 'birth', table=True)

    def display_deathday(self):
        return _display_day(self.death_date)

    def display_deathplace(self):
        return _display_place(self, 'death')

    def linked_issues_count(self):
        from .issue import Issue
        return Issue.objects.filter(story__credits__creator__creator=self,
                                    story__credits__deleted=False)\
                            .distinct().count()

    def has_death_info(self):
        if str(self.death_date) != '':
            return True
        else:
            return False

    def has_dependents(self):
        if self.creator_names.filter(storycredit__deleted=False).exists():
            return True
        if self.art_influence_revisions.active_set().exists():
            return True
        # TODO how to handle GenericRelation for ReceivedAward
        # if self.award_revisions.filter.active_set().count():
            # return True
        if self.degree_revisions.active_set().exists():
            return True
        if self.membership_revisions.active_set().exists():
            return True
        if self.non_comic_work_revisions.active_set().exists():
            return True
        if self.school_revisions.active_set().exists():
            return True
        if self.active_relations().exists():
            return True
        if self.active_influenced_creators().exists():
            return True

        return False

    def active_names(self):
        return self.creator_names.exclude(deleted=True)

    def _official_creator_detail(self):
        return self.creator_names.get(is_official_name=True)

    official_creator_detail = property(_official_creator_detail)

    def active_art_influences(self):
        return self.art_influences.exclude(deleted=True)\
                   .order_by('influence_link__sort_name', 'influence_name')

    def active_influenced_creators(self):
        return self.influenced_creators.exclude(deleted=True)\
                   .order_by('creator__sort_name')

    def active_awards(self):
        return self.awards.exclude(deleted=True)

    def active_awards_for_issues(self):
        from .issue import Issue
        issues = Issue.objects.filter(story__credits__creator__creator=self,
                                      story__type_id__in=[10, 19, 20, 21, 27],
                                      awards__isnull=False).distinct()
        content_type = ContentType.objects.get(model='Issue')
        awards = ReceivedAward.objects.filter(content_type=content_type,
                                              object_id__in=issues)
        return awards

    def active_awards_for_stories(self):
        from .story import Story
        stories = Story.objects.filter(credits__creator__creator=self,
                                       awards__isnull=False).distinct()
        content_type = ContentType.objects.get(model='Story')
        awards = ReceivedAward.objects.filter(content_type=content_type,
                                              object_id__in=stories)
        return awards

    def active_degrees(self):
        return self.degree_set.exclude(deleted=True)

    def active_memberships(self):
        return self.membership_set.exclude(deleted=True)

    def active_non_comic_works(self):
        return self.non_comic_work_set.exclude(deleted=True)

    def active_relations(self):
        return self.from_related_creator.exclude(deleted=True) | \
               self.to_related_creator.exclude(deleted=True)

    def active_schools(self):
        return self.school_set.exclude(deleted=True)

    def active_signatures(self):
        return self.signatures.exclude(deleted=True)

    _update_stats = True

    def stat_counts(self):
        """
        Returns all count values relevant to this creator.
        """
        if self.deleted:
            return {}

        return {'creators': 1}

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_creator',
                kwargs={'creator_id': self.id})

    def search_result_name(self):
        if self.disambiguation:
            extra = ' [%s]' % self.disambiguation
        else:
            extra = ''
        return self.__str__(extra)

    def __str__(self, extra=''):
        if self.birth_date.year:
            extra += ' (b. %s)' % self.birth_date.year
        return '%s%s' % (str(self.gcd_official_name), extra)


class CreatorSignature(GcdData):
    """
    Various signatures of a creator.
    """

    class Meta:
        db_table = 'gcd_creator_signature'
        app_label = 'gcd'
        ordering = ['name', '-creator__sort_name',
                    '-creator__birth_date__year']
        verbose_name_plural = 'Creator Signatures'

    name = models.CharField(max_length=255, db_index=True)
    creator = models.ForeignKey('Creator', on_delete=models.CASCADE,
                                related_name='signatures')
    notes = models.TextField()
    generic = models.BooleanField(default=False)
    data_source = models.ManyToManyField(DataSource)

    def _signature(self):
        content_type = ContentType.objects.get_for_model(self)
        img = Image.objects.filter(object_id=self.id, deleted=False,
                                   content_type=content_type, type_id=7)
        if img:
            return img.get()
        else:
            return None

    signature = property(_signature)

    def has_dependents(self):
        if self.credits.filter(deleted=False).exists():
            return True
        if self.storycreditrevision_set.active_set().exists():
            return True

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_creator_signature',
                kwargs={'creator_signature_id': self.id})

    def full_name(self):
        return str(self)

    def __str__(self):
        return '%s signature %s' % (str(self.creator),
                                    self.name)


class CreatorRelation(GcdData):
    """
    Relations between creators to relate any GCD Official name to any other
    name.
    """

    class Meta:
        db_table = 'gcd_creator_relation'
        app_label = 'gcd'
        ordering = ('to_creator', 'relation_type', 'from_creator')
        verbose_name_plural = 'Creator Relations'

    to_creator = models.ForeignKey(Creator, on_delete=models.CASCADE,
                                   related_name='from_related_creator')
    from_creator = models.ForeignKey(Creator, on_delete=models.CASCADE,
                                     related_name='to_related_creator')
    relation_type = models.ForeignKey(RelationType, on_delete=models.CASCADE,
                                      related_name='relation_type')
    creator_name = models.ManyToManyField(CreatorNameDetail,
                                          related_name='creator_relation')
    notes = models.TextField()
    data_source = models.ManyToManyField(DataSource)

    def pre_process_relation(self, creator):
        if self.from_creator == creator:
            return [self.to_creator, self.relation_type.type]
        if self.to_creator == creator:
            return [self.from_creator, self.relation_type.reverse_type]

    def __str__(self):
        return '%s >Relation< %s :: %s' % (str(self.from_creator),
                                           str(self.to_creator),
                                           str(self.relation_type)
                                           )


class School(models.Model):
    """
    record of schools
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('school_name',)
        verbose_name_plural = 'Schools'

    school_name = models.CharField(max_length=200)

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_school',
                kwargs={'school_id': self.id})

    def __str__(self):
        return str(self.school_name)


class CreatorSchool(GcdData):
    """
    record the schools creators attended
    """

    class Meta:
        db_table = 'gcd_creator_school'
        app_label = 'gcd'
        ordering = ('creator__sort_name',
                    'school_year_began', 'school_year_ended')
        verbose_name_plural = 'Creator Schools'

    creator = models.ForeignKey(Creator, on_delete=models.CASCADE,
                                related_name='school_set')
    school = models.ForeignKey(School, on_delete=models.CASCADE,
                               related_name='creator')
    school_year_began = models.PositiveSmallIntegerField(null=True)
    school_year_began_uncertain = models.BooleanField(default=False)
    school_year_ended = models.PositiveSmallIntegerField(null=True)
    school_year_ended_uncertain = models.BooleanField(default=False)
    notes = models.TextField()
    data_source = models.ManyToManyField(DataSource)

    def has_dependents(self):
        return self.creator.pending_deletion()

    def display_years(self):
        if not self.school_year_began and not self.school_year_ended:
            return '?'

        if not self.school_year_began:
            years = '? - '
        else:
            years = '%d%s - ' % (self.school_year_began,
                                 '?' if self.school_year_began_uncertain
                                 else '')
        if not self.school_year_ended:
            years = '%s ?' % (years)
        else:
            years = '%s%d%s' % (years, self.school_year_ended,
                                '?' if self.school_year_ended_uncertain
                                else '')
        return years

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_creator_school',
                kwargs={'creator_school_id': self.id})

    def __str__(self):
        return '%s - %s' % (str(self.creator),
                            str(self.school.school_name))


class Degree(models.Model):
    """
    record of degrees
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('degree_name',)
        verbose_name_plural = 'Degrees'

    degree_name = models.CharField(max_length=200)

    def __str__(self):
        return str(self.degree_name)


class CreatorDegree(GcdData):
    """
    record the degrees creators received
    """

    class Meta:
        db_table = 'gcd_creator_degree'
        app_label = 'gcd'
        ordering = ('degree_year',)
        verbose_name_plural = 'Creator Degrees'

    creator = models.ForeignKey(Creator, on_delete=models.CASCADE,
                                related_name='degree_set')
    school = models.ForeignKey(School, on_delete=models.CASCADE,
                               related_name='degree', null=True)
    degree = models.ForeignKey(Degree, on_delete=models.CASCADE,
                               related_name='creator')
    degree_year = models.PositiveSmallIntegerField(null=True)
    degree_year_uncertain = models.BooleanField(default=False)
    notes = models.TextField()
    data_source = models.ManyToManyField(DataSource)

    def has_dependents(self):
        return self.creator.pending_deletion()

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_creator_degree',
                kwargs={'creator_degree_id': self.id})

    def __str__(self):
        return '%s - %s' % (str(self.creator),
                            str(self.degree.degree_name))


class CreatorArtInfluence(GcdData):
    """
    record the Name of artistic influences for creators
    """

    class Meta:
        db_table = 'gcd_creator_art_influence'
        app_label = 'gcd'
        verbose_name_plural = 'Creator Art Influences'

    creator = models.ForeignKey(Creator, on_delete=models.CASCADE,
                                related_name='art_influences')
    influence_name = models.CharField(max_length=200)
    influence_link = models.ForeignKey(Creator,
                                       on_delete=models.CASCADE,
                                       null=True,
                                       related_name='influenced_creators')
    notes = models.TextField()
    data_source = models.ManyToManyField(DataSource)

    # only one of the two will be set
    def influence(self):
        if self.influence_link:
            return self.influence_link.gcd_official_name
        else:
            return self.influence_name

    def has_dependents(self):
        return self.creator.pending_deletion()

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_creator_art_influence',
                kwargs={'creator_art_influence_id': self.id})

    def __str__(self):
        return '%s > %s' % (self.influence(), self.creator.gcd_official_name)


class MembershipType(models.Model):
    """
    type of Membership
    """

    class Meta:
        db_table = 'gcd_membership_type'
        app_label = 'gcd'
        verbose_name_plural = 'Membership Types'

    type = models.CharField(max_length=100)

    def __str__(self):
        return str(self.type)


class CreatorMembership(GcdData):
    """
    record societies and other organizations related to their
    artistic profession that creators held memberships in
    """

    class Meta:
        db_table = 'gcd_creator_membership'
        app_label = 'gcd'
        ordering = ('membership_type', 'organization_name')
        verbose_name_plural = 'Creator Memberships'

    creator = models.ForeignKey(Creator, on_delete=models.CASCADE,
                                related_name='membership_set')
    organization_name = models.CharField(max_length=200)
    membership_type = models.ForeignKey(MembershipType,
                                        on_delete=models.CASCADE,
                                        null=True)
    membership_year_began = models.PositiveSmallIntegerField(null=True)
    membership_year_began_uncertain = models.BooleanField(default=False)
    membership_year_ended = models.PositiveSmallIntegerField(null=True)
    membership_year_ended_uncertain = models.BooleanField(default=False)
    notes = models.TextField()
    data_source = models.ManyToManyField(DataSource)

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_creator_membership',
                kwargs={'creator_membership_id': self.id})

    def display_years(self):
        if not self.membership_year_began and not self.membership_year_ended:
            return ''

        if not self.membership_year_began:
            years = '? - '
        else:
            years = '%d%s - ' % (self.membership_year_began,
                                 '?' if self.membership_year_began_uncertain
                                 else '')
        if not self.membership_year_ended:
            years = '%s ?' % (years)
        else:
            years = '%s%d%s' % (years, self.membership_year_ended,
                                '?' if self.membership_year_ended_uncertain
                                else '')
        return years

    def has_dependents(self):
        return self.creator.pending_deletion()

    def __str__(self):
        return '%s' % str(self.organization_name)


class NonComicWorkType(models.Model):
    """
    record the type of work performed
    """

    class Meta:
        db_table = 'gcd_non_comic_work_type'
        app_label = 'gcd'
        verbose_name_plural = 'NonComic Work Types'

    type = models.CharField(max_length=100)

    def __str__(self):
        return str(self.type)


class NonComicWorkRole(models.Model):
    """
    record the type of work performed
    """

    class Meta:
        db_table = 'gcd_non_comic_work_role'
        app_label = 'gcd'
        verbose_name_plural = 'NonComic Work Roles'

    role_name = models.CharField(max_length=200)

    def __str__(self):
        return str(self.role_name)


class CreatorNonComicWork(GcdData):
    """
    record the non-comics work of comics creators
    """

    class Meta:
        db_table = 'gcd_creator_non_comic_work'
        app_label = 'gcd'
        ordering = ('publication_title', 'employer_name', 'work_type')
        verbose_name_plural = 'Creator Non Comic Works'

    creator = models.ForeignKey(Creator, on_delete=models.CASCADE,
                                related_name='non_comic_work_set')
    work_type = models.ForeignKey(NonComicWorkType, on_delete=models.CASCADE)
    publication_title = models.CharField(max_length=200)
    employer_name = models.CharField(max_length=200)
    work_title = models.CharField(max_length=255)
    work_role = models.ForeignKey(NonComicWorkRole, on_delete=models.CASCADE,
                                  null=True)
    work_urls = models.TextField()
    data_source = models.ManyToManyField(DataSource)
    notes = models.TextField()

    def has_dependents(self):
        return self.creator.pending_deletion()

    def display_years(self):
        years = self.noncomicworkyears.all().order_by('work_year')
        if not years:
            return ''
        year_string = '%d' % years[0].work_year
        if years[0].work_year_uncertain:
            year_string += '?'
        year_before = years[0]
        year_range = False
        for year in years[1:]:
            if year_before.work_year+1 == year.work_year and \
              not year_before.work_year_uncertain and \
              not year.work_year_uncertain:
                year_range = True
            else:
                if year_range:
                    year_string += ' - %d; %d' % (year_before.work_year,
                                                  year.work_year)
                    if year.work_year_uncertain:
                        year_string += '?'
                else:
                    year_string += '; %d' % (year.work_year)
                    if year.work_year_uncertain:
                        year_string += '?'
                year_range = False
            year_before = year
        if year_range:
            year_string += ' - %d' % (year.work_year)
            if year.work_year_uncertain:
                year_string += '?'
        return year_string

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_creator_non_comic_work',
                kwargs={'creator_non_comic_work_id': self.id})

    def __str__(self):
        return '%s' % (str(self.publication_title))


class NonComicWorkYear(models.Model):
    """
    record the year of the work
    There may be multiple years recorded
    """

    class Meta:
        db_table = 'gcd_non_comic_work_year'
        app_label = 'gcd'
        ordering = ('work_year',)
        verbose_name_plural = 'NonComic Work Years'

    non_comic_work = models.ForeignKey(CreatorNonComicWork,
                                       on_delete=models.CASCADE,
                                       related_name='noncomicworkyears')
    work_year = models.PositiveSmallIntegerField(null=True)
    work_year_uncertain = models.BooleanField(default=False)

    def __str__(self):
        return '%s - %s' % (str(self.non_comic_work),
                            str(self.work_year))


class CreatorTable(tables.Table):
    name = tables.Column(accessor='creator__gcd_official_name',
                         verbose_name='Creator Name')
    detail_name = tables.Column(accessor='name', verbose_name='Used Name')
    first_credit = tables.Column(verbose_name='First Credit')
    credits_count = tables.Column(accessor='credits_count',
                                  verbose_name='# Issues',
                                  initial_sort_descending=True)
    role = tables.Column(accessor='script', orderable=False)

    def order_name(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'creator__sort_name')
        return (query_set, True)

    def order_detail_name(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'sort_name')
        return (query_set, True)

    def render_first_credit(self, value):
        return value[:4]

    def render_name(self, record):
        from apps.gcd.templatetags.display import absolute_url
        return absolute_url(record.creator)

    def value_name(self, record):
        return str(record.creator)

    def render_credits_count(self, record):
        url = urlresolvers.reverse(
                'creator_name_checklist',
                kwargs={'creator_name_id': record.id,
                        '%s_id' % self.resolve_name:
                        getattr(self, self.resolve_name).id})
        return mark_safe('<a href="%s">%s</a>' % (url, record.credits_count))

    def value_credits_count(self, record):
        return record.credits_count

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


class CharacterCreatorTable(CreatorTable):
    def __init__(self, *args, **kwargs):
        self.character = kwargs.pop('character')
        self.resolve_name = 'character'
        super(CreatorTable, self).__init__(*args, **kwargs)


class CreatorCreatorTable(CreatorTable):
    name = tables.Column(accessor='gcd_official_name',
                         verbose_name='Creator Name')
    credits_count = tables.Column(accessor='issue_credits_count',
                                  verbose_name='# Issues',
                                  initial_sort_descending=True)
    detail_name = None

    def __init__(self, *args, **kwargs):
        self.creator = kwargs.pop('creator')
        self.resolve_name = 'creator'
        super(CreatorTable, self).__init__(*args, **kwargs)

    def order_name(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'sort_name')
        return (query_set, True)

    class Meta:
        model = Creator
        fields = ('name', 'credits_count', 'first_credit', 'role')

    def render_credits_count(self, record):
        # return record.issue_credits_count
        url = urlresolvers.reverse(
                'creator_cocreator_issues',
                kwargs={'co_creator_id': record.id,
                        '%s_id' % self.resolve_name:
                        getattr(self, self.resolve_name).id})
        return mark_safe('<a href="%s">%s</a>' % (url,
                                                  record.issue_credits_count))

    def value_credits_count(self, record):
        return record.issue_credits_count

    def render_name(self, record):
        from apps.gcd.templatetags.display import absolute_url
        return absolute_url(record)

    def value_name(self, record):
        return str(record)


class GroupCreatorTable(CreatorTable):
    def __init__(self, *args, **kwargs):
        self.group = kwargs.pop('group')
        self.resolve_name = 'group'
        super(CreatorTable, self).__init__(*args, **kwargs)


class FeatureCreatorTable(CreatorTable):
    def __init__(self, *args, **kwargs):
        self.feature = kwargs.pop('feature')
        self.resolve_name = 'feature'
        super(CreatorTable, self).__init__(*args, **kwargs)


class SeriesCreatorTable(CreatorTable):
    def __init__(self, *args, **kwargs):
        self.series = kwargs.pop('series')
        self.resolve_name = 'series'
        super(CreatorTable, self).__init__(*args, **kwargs)
