import calendar
from operator import itemgetter
from django.core import urlresolvers
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation

from .gcddata import GcdData
from .image import Image
from apps.stddata.models import Country, Date
from apps.oi import states

MONTH_CHOICES = [(i, calendar.month_name[i]) for i in range(1, 13)]


def _display_day(date):
    if date.year:
        display = '%s%s ' % (date.year,
                             '?' if date.year_uncertain else '')
    else:
        display = 'year? '

    if date.month:
        display = '%s%s%s ' % (
          display, calendar.month_name[int(date.month)],
          '?' if date.month_uncertain else '')
    else:
        display += 'month? '

    if date.day:
        display = '%s%s%s ' % (display, date.day.lstrip('0'),
                               '?' if date.day_uncertain else '')
    else:
        display += 'day? '
    return display


def _display_place(self, type):
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

    description = models.TextField(null=True)
    type = models.CharField(max_length=50)

    def __unicode__(self):
        return '%s' % unicode(self.type)


class CreatorNameDetail(GcdData):
    """
    Indicates the various names of creator
    Multiple Name could be checked per creator.
    """

    class Meta:
        db_table = 'gcd_creator_name_detail'
        app_label = 'gcd'
        ordering = ['type__id', 'created', '-id']
        verbose_name_plural = 'CreatorName Details'

    name = models.CharField(max_length=255, db_index=True)
    creator = models.ForeignKey('Creator', related_name='creator_names')
    type = models.ForeignKey('NameType', related_name='nametypes', null=True)

    def __unicode__(self):
        return '%s - %s(%s)' % (unicode(self.creator),
                                unicode(self.name),
                                unicode(self.type.type))


class SourceType(models.Model):
    """
    The data source type for each Name Source should be recorded.
    """

    class Meta:
        db_table = 'gcd_source_type'
        app_label = 'gcd'
        ordering = ('type',)
        verbose_name_plural = 'Source Types'

    type = models.CharField(max_length=50)

    def __unicode__(self):
        return unicode(self.type)


class DataSource(GcdData):
    """
    Indicates the various sources of creator data
    """

    class Meta:
        db_table = 'gcd_data_source'
        app_label = 'gcd'
        ordering = ('source_description',)
        verbose_name_plural = 'Creator Data Source'

    source_type = models.ForeignKey(SourceType)
    source_description = models.TextField()
    field = models.CharField(max_length=256)

    def __unicode__(self):
        return '%s - %s' % (unicode(self.field),
                            unicode(self.source_type.type))


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

    def __unicode__(self):
        return unicode(self.type)


class CreatorManager(models.Manager):
    """
    need to be manage creator model
    with this custom manager in future
    """
    pass


class Creator(GcdData):
    class Meta:
        app_label = 'gcd'
        ordering = ('gcd_official_name', 'created',)
        verbose_name_plural = 'Creators'

    objects = CreatorManager()

    gcd_official_name = models.CharField(max_length=255, db_index=True)

    birth_date = models.ForeignKey(Date, related_name='+', null=True)
    death_date = models.ForeignKey(Date, related_name='+', null=True)

    whos_who = models.URLField(null=True)

    birth_country = models.ForeignKey(Country,
                                      related_name='birth_country',
                                      null=True)
    birth_country_uncertain = models.BooleanField(default=False)
    birth_province = models.CharField(max_length=50)
    birth_province_uncertain = models.BooleanField(default=False)
    birth_city = models.CharField(max_length=200)
    birth_city_uncertain = models.BooleanField(default=False)

    death_country = models.ForeignKey(Country,
                                      related_name='death_country',
                                      null=True)
    death_country_uncertain = models.BooleanField(default=False)
    death_province = models.CharField(max_length=50)
    death_province_uncertain = models.BooleanField(default=False)
    death_city = models.CharField(max_length=200)
    death_city_uncertain = models.BooleanField(default=False)

    portrait = GenericRelation(Image)

    bio = models.TextField()
    sample_scan = GenericRelation(Image)
    notes = models.TextField()

    data_source = models.ManyToManyField(DataSource)

    def _portrait(self):
        content_type = ContentType.objects.get_for_model(self)
        img = Image.objects.filter(object_id=self.id, deleted=False,
                                   content_type=content_type, type__id=4)
        if img:
            return img.get()
        else:
            return None

    portrait = property(_portrait)

    def _samplescan(self):
        content_type = ContentType.objects.get_for_model(self)
        img = Image.objects.filter(object_id=self.id, deleted=False,
                                   content_type=content_type, type__id=5)
        if img:
            return img.get()
        else:
            return None

    samplescan = property(_samplescan)

    def full_name(self):
        return unicode(self)

    def display_birthday(self):
        return _display_day(self.birth_date)

    def display_birthplace(self):
        return _display_place(self, 'birth')

    def display_deathday(self):
        return _display_day(self.death_date)

    def display_deathplace(self):
        return _display_place(self, 'death')

    def has_death_info(self):
        if unicode(self.death_date) != '':
            return True
        else:
            return False

    def deletable(self):
        # TODO check once more, e.g. influence_link
        if self.award_revisions.filter(changeset__state__in=
                                       states.ACTIVE).count():
            return False
        if self.non_comic_work_revisions.filter(changeset__state__in=
                                                states.ACTIVE).count():
            return False
        if self.art_influence_revisions.filter(changeset__state__in=
                                               states.ACTIVE).count():
            return False
        if self.membership_revisions.filter(changeset__state__in=
                                            states.ACTIVE).count():
            return False
        return True

    def pending_deletion(self):
        return self.revisions.filter(changeset__state__in=states.ACTIVE,
                                     deleted=True).count() == 1

    def active_names(self):
        return self.creator_names.exclude(deleted=True)

    def active_art_influences(self):
        return self.art_influence_set.exclude(deleted=True)

    def active_awards(self):
        return self.award_set.exclude(deleted=True)

    def active_degrees(self):
        return self.degree_set.exclude(deleted=True)

    def active_memberships(self):
        return self.membership_set.exclude(deleted=True)

    def active_non_comic_works(self):
        return self.non_comic_work_set.exclude(deleted=True)

    def active_relations(self):
        from_relations = self.from_related_creator.exclude(deleted=True)
        relations = list(from_relations.values_list(
                    'from_creator__id', 'from_creator__gcd_official_name',
                    'relation_type__reverse_type', 'notes', 'id'))
        to_relations = self.to_related_creator.exclude(deleted=True)
        relations.extend(to_relations.values_list(
                  'to_creator__id', 'to_creator__gcd_official_name',
                  'relation_type__type', 'notes', 'id'))
        relations.sort(key=itemgetter(2, 1))
        return relations

    def active_schools(self):
        return self.school_set.exclude(deleted=True)

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_creator',
                kwargs={'creator_id': self.id})

    def __unicode__(self):
        return '%s' % unicode(self.gcd_official_name)


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

    to_creator = models.ForeignKey(Creator,
                                   related_name='from_related_creator')
    from_creator = models.ForeignKey(Creator,
                                     related_name='to_related_creator')
    relation_type = models.ForeignKey(RelationType,
                                      related_name='relation_type')
    notes = models.TextField()
    data_source = models.ManyToManyField(DataSource)

    def __unicode__(self):
        return '%s >Relation< %s :: %s' % (unicode(self.from_creator),
                                           unicode(self.to_creator),
                                           unicode(self.relation_type)
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

    def __unicode__(self):
        return unicode(self.school_name)


class CreatorSchool(GcdData):
    """
    record the schools creators attended
    """

    class Meta:
        db_table = 'gcd_creator_school'
        app_label = 'gcd'
        ordering = ('school_year_began', 'school_year_ended')
        verbose_name_plural = 'Creator Schools'

    creator = models.ForeignKey(Creator, related_name='school_set')
    school = models.ForeignKey(School, related_name='creator')
    school_year_began = models.PositiveSmallIntegerField(null=True)
    school_year_began_uncertain = models.BooleanField(default=False)
    school_year_ended = models.PositiveSmallIntegerField(null=True)
    school_year_ended_uncertain = models.BooleanField(default=False)
    notes = models.TextField()
    data_source = models.ManyToManyField(DataSource)

    def deletable(self):
        return self.creator.pending_deletion() is False

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_creator_school',
                kwargs={'creator_school_id': self.id})

    def __unicode__(self):
        return '%s - %s' % (unicode(self.creator),
                            unicode(self.school.school_name))


class Degree(models.Model):
    """
    record of degrees
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('degree_name',)
        verbose_name_plural = 'Degrees'

    degree_name = models.CharField(max_length=200)

    def __unicode__(self):
        return unicode(self.degree_name)


class CreatorDegree(GcdData):
    """
    record the degrees creators received
    """

    class Meta:
        db_table = 'gcd_creator_degree'
        app_label = 'gcd'
        ordering = ('degree_year',)
        verbose_name_plural = 'Creator Degrees'

    creator = models.ForeignKey(Creator, related_name='degree_set')
    school = models.ForeignKey(School, related_name='degree', null=True)
    degree = models.ForeignKey(Degree, related_name='creator')
    degree_year = models.PositiveSmallIntegerField(null=True)
    degree_year_uncertain = models.BooleanField(default=False)
    notes = models.TextField()
    data_source = models.ManyToManyField(DataSource)

    def deletable(self):
        return self.creator.pending_deletion() is False

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_creator_degree',
                kwargs={'creator_degree_id': self.id})

    def __unicode__(self):
        return '%s - %s' % (unicode(self.creator),
                            unicode(self.degree.degree_name))


class CreatorArtInfluence(GcdData):
    """
    record the Name of artistic influences for creators
    """

    class Meta:
        db_table = 'gcd_creator_art_influence'
        app_label = 'gcd'
        verbose_name_plural = 'Creator Art Influences'

    creator = models.ForeignKey(Creator, related_name='art_influence_set')
    influence_name = models.CharField(max_length=200)
    influence_link = models.ForeignKey(Creator, null=True,
                                       related_name='exist_influencer')
    notes = models.TextField()
    data_source = models.ManyToManyField(DataSource)

    # only one of the two will be set
    def influence(self):
        if self.influence_link:
            return self.influence_link.gcd_official_name
        else:
            return self.influence_name

    def deletable(self):
        return self.creator.pending_deletion() is False

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_creator_art_influence',
                kwargs={'creator_art_influence_id': self.id})

    def __unicode__(self):
        return u'%s > %s' % (self.influence(), self.creator.gcd_official_name)


class MembershipType(models.Model):
    """
    type of Membership
    """

    class Meta:
        db_table = 'gcd_membership_type'
        app_label = 'gcd'
        verbose_name_plural = 'Membership Types'

    type = models.CharField(max_length=100)

    def __unicode__(self):
        return unicode(self.type)


class CreatorMembership(GcdData):
    """
    record societies and other organizations related to their
    artistic profession that creators held memberships in
    """

    class Meta:
        db_table = 'gcd_creator_membership'
        app_label = 'gcd'
        ordering = ('membership_type',)
        verbose_name_plural = 'Creator Memberships'

    creator = models.ForeignKey(Creator, related_name='membership_set')
    organization_name = models.CharField(max_length=200)
    membership_type = models.ForeignKey(MembershipType, null=True)
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

    def deletable(self):
        return self.creator.pending_deletion() is False

    def __unicode__(self):
        return '%s' % unicode(self.organization_name)


class Award(GcdData):
    class Meta:
        app_label = 'gcd'
        ordering = ('name',)
        verbose_name_plural = 'Awards'

    name = models.CharField(max_length=200)
    notes = models.TextField()

    def deletable():
        return False

    def active_awards(self):
        return self.creatoraward_set.exclude(deleted=True)

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_award',
                kwargs={'award_id': self.id})

    def __unicode__(self):
        return unicode(self.name)


class CreatorAward(GcdData):
    """
    record any awards and honors a creator received
    """

    class Meta:
        db_table = 'gcd_creator_award'
        app_label = 'gcd'
        ordering = ('award_year',)
        verbose_name_plural = 'Creator Awards'

    creator = models.ForeignKey(Creator, related_name='award_set')
    award = models.ForeignKey(Award, null=True)
    award_name = models.CharField(max_length=255)
    no_award_name = models.BooleanField(default=False)
    award_year = models.PositiveSmallIntegerField(null=True)
    award_year_uncertain = models.BooleanField(default=False)
    notes = models.TextField()
    data_source = models.ManyToManyField(DataSource)

    def deletable(self):
        return self.creator.pending_deletion() is False

    def display_name(self):
        if not self.no_award_name:
            return self.award_name
        else:
            return '[no name]'

    def display_year(self):
        if not self.award_year:
            return '?'
        else:
            return '%d%s' % (self.award_year, '?' if self.award_year_uncertain else '')

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_creator_award',
                kwargs={'creator_award_id': self.id})

    def __unicode__(self):
        return unicode(self.award_name)


class NonComicWorkType(models.Model):
    """
    record the type of work performed
    """

    class Meta:
        db_table = 'gcd_non_comic_work_type'
        app_label = 'gcd'
        verbose_name_plural = 'NonComic Work Types'

    type = models.CharField(max_length=100)

    def __unicode__(self):
        return unicode(self.type)


class NonComicWorkRole(models.Model):
    """
    record the type of work performed
    """

    class Meta:
        db_table = 'gcd_non_comic_work_role'
        app_label = 'gcd'
        verbose_name_plural = 'NonComic Work Roles'

    role_name = models.CharField(max_length=200)

    def __unicode__(self):
        return unicode(self.role_name)


class CreatorNonComicWork(GcdData):
    """
    record the non-comics work of comics creators
    """

    class Meta:
        db_table = 'gcd_creator_non_comic_work'
        app_label = 'gcd'
        ordering = ('publication_title', 'employer_name', 'work_type')
        verbose_name_plural = 'Creator Non Comic Works'

    creator = models.ForeignKey(Creator, related_name='non_comic_work_set')
    work_type = models.ForeignKey(NonComicWorkType)
    publication_title = models.CharField(max_length=200)
    employer_name = models.CharField(max_length=200)
    work_title = models.CharField(max_length=255)
    work_role = models.ForeignKey(NonComicWorkRole, null=True)
    work_urls = models.TextField()
    data_source = models.ManyToManyField(DataSource)
    notes = models.TextField()

    def deletable(self):
        return self.creator.pending_deletion() is False

    def display_years(self):
        years = self.noncomicworkyears.all().order_by('work_year')
        if not years:
            return u''
        year_string = u'%d' % years[0].work_year
        if years[0].work_year_uncertain:
            year_string += u'?'
        year_before = years[0]
        year_range = False
        for year in years[1:]:
            if year_before.work_year+1 == year.work_year and \
              not year_before.work_year_uncertain and \
              not year.work_year_uncertain:
                year_range = True
            else:
                if year_range:
                    year_string += u' - %d; %d' % (year_before.work_year, year.work_year)
                    if year.work_year_uncertain:
                        year_string += u'?'
                else:
                    year_string += '; %d' % (year.work_year)
                    if year.work_year_uncertain:
                        year_string += u'?'
                year_range = False
            year_before = year
        if year_range:
            year_string += u' - %d' % (year.work_year)
            if year.work_year_uncertain:
                year_string += u'?'
        return year_string

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_creator_non_comic_work',
                kwargs={'creator_non_comic_work_id': self.id})

    def __unicode__(self):
        return '%s' % (unicode(self.publication_title))


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
                                       related_name='noncomicworkyears')
    work_year = models.PositiveSmallIntegerField(null=True)
    work_year_uncertain = models.BooleanField(default=False)

    def __unicode__(self):
        return '%s - %s' % (unicode(self.non_comic_work),
                            unicode(self.work_year))

