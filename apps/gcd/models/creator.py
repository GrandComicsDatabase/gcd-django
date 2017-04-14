import calendar
from collections import OrderedDict
import datetime
import calendar
from django.core import urlresolvers
from django.db import models
from django.contrib.contenttypes.models import ContentType

from apps.gcd.models import Image
from apps.stddata.models import Country
from apps.oi import states
from django.contrib.contenttypes import generic

MONTH_CHOICES = [(i, calendar.month_name[i]) for i in range(1, 13)]


class NameType(models.Model):
    """
    Indicates the various types of names
    Multiple Name types could be checked per name.
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('type',)
        verbose_name_plural = 'Name Types'

    description = models.TextField(null=True, blank=True)
    type = models.CharField(max_length=50, null=True, blank=True)

    def __unicode__(self):
        return '%s' % unicode(self.type)


class CreatorNameDetail(models.Model):
    """
    Indicates the various names of creator
    Multiple Name could be checked per creator.
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('type',)
        verbose_name_plural = 'CreatorName Details'

    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(null=True, blank=True)
    creator = models.ForeignKey('Creator', related_name='creator_names')
    type = models.ForeignKey('NameType', related_name='nametypes', null=True,
                             blank=True)
    source = models.ManyToManyField('SourceType', related_name='namesources',
                                    null=True, blank=True)

    def __unicode__(self):
        return '%s - %s(%s)' % (
        unicode(self.creator), unicode(self.name), unicode(self.type.type))


class SourceType(models.Model):
    """
    The data source type for each Name Source should be recorded.
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('type',)
        verbose_name_plural = 'Source Types'

    type = models.CharField(max_length=50)

    def __unicode__(self):
        return unicode(self.type)


class CreatorDataSource(models.Model):
    """
    Indicates the various sources of creator data
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('source_description',)
        verbose_name_plural = 'Creator Data Source'

    source_type = models.ForeignKey(SourceType)
    source_description = models.TextField()
    field = models.CharField(max_length=256)

    def __unicode__(self):
        return '%s - %s' % (
        unicode(self.field), unicode(self.source_type.type))


class RelationType(models.Model):
    """
    The type of relation between two creators.
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('type',)
        verbose_name_plural = 'Relation Types'

    type = models.CharField(max_length=50)

    def __unicode__(self):
        return unicode(self.type)


class CreatorManager(models.Manager):
    """
    need to be manage creator model
    with this custom manager in future
    """
    pass


class Creator(models.Model):
    class Meta:
        app_label = 'gcd'
        ordering = ('created',)
        verbose_name_plural = 'Creators'

    objects = CreatorManager()

    gcd_official_name = models.CharField(max_length=255, db_index=True)
    birth_year = models.PositiveSmallIntegerField(null=True, blank=True)
    birth_year_uncertain = models.BooleanField(default=False)
    birth_month = models.PositiveSmallIntegerField(choices=MONTH_CHOICES,
                                                   null=True, blank=True)
    birth_month_uncertain = models.BooleanField(default=False)
    birth_date = models.PositiveSmallIntegerField(null=True, blank=True)
    birth_date_uncertain = models.BooleanField(default=False)

    death_year = models.PositiveSmallIntegerField(null=True, blank=True)
    death_year_uncertain = models.BooleanField(default=False)
    death_month = models.PositiveSmallIntegerField(choices=MONTH_CHOICES,
                                                   null=True, blank=True)
    death_month_uncertain = models.BooleanField(default=False)
    death_date = models.PositiveSmallIntegerField(null=True, blank=True)
    death_date_uncertain = models.BooleanField(default=False)

    whos_who = models.URLField(blank=True, null=True)

    birth_country = models.ForeignKey(Country,
                                      related_name='birth_country',
                                      blank=True,
                                      null=True)
    birth_country_uncertain = models.BooleanField(default=False)
    birth_province = models.CharField(max_length=50, blank=True, null=True)
    birth_province_uncertain = models.BooleanField(default=False)
    birth_city = models.CharField(max_length=200, blank=True, null=True)
    birth_city_uncertain = models.BooleanField(default=False)

    death_country = models.ForeignKey(Country,
                                      related_name='death_country',
                                      blank=True,
                                      null=True)
    death_country_uncertain = models.BooleanField(default=False)
    death_province = models.CharField(max_length=50, blank=True, null=True)
    death_province_uncertain = models.BooleanField(default=False)
    death_city = models.CharField(max_length=200, blank=True, null=True)
    death_city_uncertain = models.BooleanField(default=False)

    portrait = generic.GenericRelation(Image)
    schools = models.ManyToManyField('School', related_name='schoolinformation',
                                     through='CreatorSchoolDetail', null=True,
                                     blank=True)
    degrees = models.ManyToManyField('Degree', related_name='degreeinformation',
                                     through='CreatorDegreeDetail', null=True,
                                     blank=True)
    # creators roles
    bio = models.TextField(blank=True, null=True)
    sample_scan = generic.GenericRelation(Image)
    notes = models.TextField(blank=True, null=True)

    data_source = models.ManyToManyField(CreatorDataSource,
                                         blank=True)

    # Fields related to change management.
    reserved = models.BooleanField(default=False, db_index=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    deleted = models.BooleanField(default=False, db_index=True)

    def __unicode__(self):
        return '%s' % unicode(self.gcd_official_name)

    def _portrait(self):
        img = Image.objects.filter(object_id=self.id, deleted=False,
                                   content_type=ContentType.objects.get_for_model(
                                       self), type__id=4)
        if img:
            return img.get()
        else:
            return None

    portrait = property(_portrait)

    def _samplescan(self):
        img = Image.objects.filter(object_id=self.id, deleted=False,
                                   content_type=ContentType.objects.get_for_model(
                                       self), type__id=5)
        if img:
            return img.get()
        else:
            return None

    samplescan = property(_samplescan)

    def full_name(self):
        return unicode(self)

    def get_link_fields(self):
        links_dict = {}
        links_dict['Whos Who'] = self.whos_who
        return links_dict

    def get_text_fields(self):
        fields_dict = OrderedDict()
        fields_dict['GCD Official Name'] = self.gcd_official_name
        fields_dict['Birth Year'] = self.birth_year
        fields_dict['Birth Year Uncertain'] = self.birth_year_uncertain
        fields_dict['Birth Month'] = calendar.month_name[
            self.birth_month] if self.birth_month else None
        fields_dict['Birth Month Uncertain'] = self.birth_month_uncertain
        fields_dict['Birth Date'] = self.birth_date
        fields_dict['Birth Date Uncertain'] = self.birth_date_uncertain
        fields_dict['Death Year'] = self.death_year
        fields_dict['Death Year Uncertain'] = self.death_year_uncertain
        fields_dict['Death Month'] = calendar.month_name[
            self.death_month] if self.death_month else None
        fields_dict['Death Month Uncertain'] = self.death_month_uncertain
        fields_dict['Death Date'] = self.death_date
        fields_dict['Death Date Uncertain'] = self.death_date_uncertain
        fields_dict[
            'Birth Country'] = self.birth_country.name if self.birth_country \
            else None
        fields_dict['Birth Country Uncertain'] = self.birth_country_uncertain
        fields_dict['Birth Province'] = self.birth_province
        fields_dict['Birth Province Uncertain'] = self.birth_province_uncertain
        fields_dict['Birth City'] = self.birth_city
        fields_dict['Birth City Uncertain'] = self.birth_city_uncertain
        fields_dict[
            'Death Country'] = self.death_country.name if self.death_country \
            else None
        fields_dict['Death Country Uncertain'] = self.death_country_uncertain
        fields_dict['Death Province'] = self.death_province
        fields_dict['Death Province Uncertain'] = self.death_province_uncertain
        fields_dict['Death City'] = self.death_city
        fields_dict['Death City Uncertain'] = self.death_city_uncertain
        fields_dict['Bio'] = self.bio
        fields_dict['Notes'] = self.notes
        return fields_dict

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_creator',
                kwargs={'creator_id': self.id})

    def deletable(self):
        return True

    def pending_deletion(self):
        return self.revisions.filter(changeset__state__in=states.ACTIVE,
                                     deleted=True).count() == 1

    def active_creator_membership(self):
        return self.membership_set.exclude(deleted=True)

    def active_creator_award(self):
        return self.award_set.exclude(deleted=True)

    def active_creator_artinfluence(self):
        return self.artinfluence_set.exclude(deleted=True)

    def active_creator_noncomicwork(self):
        return self.noncomicwork_set.exclude(deleted=True)


class NameRelation(models.Model):
    """
    Relations between creators to relate any GCD Official name to any other
    name.
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('gcd_official_name', 'rel_type', 'to_name')
        verbose_name_plural = 'Name Relations'

    gcd_official_name = models.ForeignKey(
            CreatorNameDetail,
            related_name='creator_gcd_official_name')
    to_name = models.ForeignKey(CreatorNameDetail, related_name='to_name')
    rel_type = models.ForeignKey(RelationType, related_name='relation_type',
                                 null=True, blank=True)
    rel_source = models.ManyToManyField(SourceType, null=True)

    def __unicode__(self):
        return '%s >Name_Relation< %s :: %s' % (unicode(self.gcd_official_name),
                                                unicode(self.to_name),
                                                unicode(self.rel_type)
                                                )


class BirthYearSource(models.Model):
    """
    Indicates the various sources of birthyear
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('source_description',)
        verbose_name_plural = 'Birth Year Source'

    creator = models.ForeignKey(Creator, related_name='creatorbirthyearsource')
    source_type = models.ForeignKey(SourceType,
                                    related_name='creatorbirthyearsourcetype')
    source_description = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return '%s - %s' % (
        unicode(self.creator), unicode(self.source_type.type))


class BirthMonthSource(models.Model):
    """
    Indicates the various sources of birthmonth
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('source_description',)
        verbose_name_plural = 'Birth Month Source'

    creator = models.ForeignKey(Creator, related_name='creatorbirthmonthsource')
    source_type = models.ForeignKey(SourceType,
                                    related_name='creatorbirthmonthsourcetype')
    source_description = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return '%s - %s' % (
        unicode(self.creator), unicode(self.source_type.type))


class BirthDateSource(models.Model):
    """
    Indicates the various sources of birthdate
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('source_description',)
        verbose_name_plural = 'Birth Date Source'

    creator = models.ForeignKey(Creator, related_name='creatorbirthdatesource')
    source_type = models.ForeignKey(SourceType,
                                    related_name='creatorbirthdatesourcetype')
    source_description = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return '%s - %s' % (
        unicode(self.creator), unicode(self.source_type.type))


class DeathYearSource(models.Model):
    """
    Indicates the various sources of deathyear
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('source_description',)
        verbose_name_plural = 'Death Year Source'

    creator = models.ForeignKey(Creator, related_name='creatordeathyearsource')
    source_type = models.ForeignKey(SourceType,
                                    related_name='creatordeathyearsourcetype')
    source_description = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return '%s - %s' % (
        unicode(self.creator), unicode(self.source_type.type))


class DeathMonthSource(models.Model):
    """
    Indicates the various sources of deathmonth
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('source_description',)
        verbose_name_plural = 'Death Month Source'

    creator = models.ForeignKey(Creator, related_name='creatordeathmonthsource')
    source_type = models.ForeignKey(SourceType,
                                    related_name='creatordeathmonthsourcetype')
    source_description = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return '%s - %s' % (
        unicode(self.creator), unicode(self.source_type.type))


class DeathDateSource(models.Model):
    """
    Indicates the various sources of deathdate
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('source_description',)
        verbose_name_plural = 'Death Date Source'

    creator = models.ForeignKey(Creator, related_name='creatordeathdatesource')
    source_type = models.ForeignKey(SourceType,
                                    related_name='creatordeathdatesourcetype')
    source_description = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return '%s - %s' % (
        unicode(self.creator), unicode(self.source_type.type))


class BirthCountrySource(models.Model):
    """
    Indicates the various sources of birthcountry
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('source_description',)
        verbose_name_plural = 'Birth Country Source'

    creator = models.ForeignKey(Creator,
                                related_name='creatorbirthcountrysource')
    source_type = models.ForeignKey(SourceType,
                                    related_name='creatorbirthcountrysourcetype')
    source_description = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return '%s - %s' % (
        unicode(self.creator), unicode(self.source_type.type))


class BirthProvinceSource(models.Model):
    """
    Indicates the various sources of birthprovince
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('source_description',)
        verbose_name_plural = 'Birth Province Source'

    creator = models.ForeignKey(Creator,
                                related_name='creatorbirthprovincesource')
    source_type = models.ForeignKey(SourceType,
                                    related_name='creatorbirthprovincesourcetype')
    source_description = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return '%s - %s' % (
        unicode(self.creator), unicode(self.source_type.type))


class BirthCitySource(models.Model):
    """
    Indicates the various sources of birthcity
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('source_description',)
        verbose_name_plural = 'Birth City Source'

    creator = models.ForeignKey(Creator, related_name='creatorbirthcitysource')
    source_type = models.ForeignKey(SourceType,
                                    related_name='creatorbirthcitysourcetype')
    source_description = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return '%s - %s' % (
        unicode(self.creator), unicode(self.source_type.type))


class DeathCountrySource(models.Model):
    """
    Indicates the various sources of deathcountry
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('source_description',)
        verbose_name_plural = 'Death Country Source'

    creator = models.ForeignKey(Creator,
                                related_name='creatordeathcountrysource')
    source_type = models.ForeignKey(SourceType,
                                    related_name='creatordeathcountrysourcetype')
    source_description = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return '%s - %s' % (
        unicode(self.creator), unicode(self.source_type.type))


class DeathProvinceSource(models.Model):
    """
    Indicates the various sources of deathprovince
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('source_description',)
        verbose_name_plural = 'Death Province Source'

    creator = models.ForeignKey(Creator,
                                related_name='creatordeathprovincesource')
    source_type = models.ForeignKey(SourceType,
                                    related_name='creatordeathprovincesourcetype')
    source_description = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return '%s - %s' % (
        unicode(self.creator), unicode(self.source_type.type))


class DeathCitySource(models.Model):
    """
    Indicates the various sources of deathcity
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('source_description',)
        verbose_name_plural = 'Death City Source'

    creator = models.ForeignKey(Creator, related_name='creatordeathcitysource')
    source_type = models.ForeignKey(SourceType,
                                    related_name='creatordeathcitysourcetype')
    source_description = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return '%s - %s' % (
        unicode(self.creator), unicode(self.source_type.type))


class PortraitSource(models.Model):
    """
    Indicates the various sources of portrait
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('source_description',)
        verbose_name_plural = 'Portrait Source'

    creator = models.ForeignKey(Creator, related_name='creatorportraitsource')
    source_type = models.ForeignKey(SourceType,
                                    related_name='creatorportraitsourcetype')
    source_description = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return '%s - %s' % (
        unicode(self.creator), unicode(self.source_type.type))


class BioSource(models.Model):
    """
    Indicates the various sources of bio
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('source_description',)
        verbose_name_plural = 'Bio Source'

    creator = models.ForeignKey(Creator, related_name='creatorbiosource')
    source_type = models.ForeignKey(SourceType,
                                    related_name='creatorbiosourcetype')
    source_description = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return '%s - %s' % (
        unicode(self.creator), unicode(self.source_type.type))


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


class CreatorSchoolDetail(models.Model):
    """
    record the schools creators attended
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('school_year_began', 'school_year_ended')
        verbose_name_plural = 'Creator School Details'

    creator = models.ForeignKey(Creator, related_name='creator_school')
    school = models.ForeignKey(School, related_name='school_details')
    school_year_began = models.PositiveSmallIntegerField(null=True, blank=True)
    school_year_began_uncertain = models.BooleanField(default=False)
    school_year_ended = models.PositiveSmallIntegerField(null=True, blank=True)
    school_year_ended_uncertain = models.BooleanField(default=False)
    school_source = models.ManyToManyField(SourceType,
                                           related_name='schoolsource',
                                           null=True, blank=True)

    def __unicode__(self):
        return '%s - %s' % (
        unicode(self.creator), unicode(self.school.school_name))


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


class CreatorDegreeDetail(models.Model):
    """
    record the degrees creators received
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('degree_year',)
        verbose_name_plural = 'Creator Degree Details'

    creator = models.ForeignKey(Creator, related_name='creator_degree')
    school = models.ForeignKey(School, related_name='schooldetails', null=True,
                               blank=True)
    degree = models.ForeignKey(Degree, related_name='degreedetails')
    degree_year = models.PositiveSmallIntegerField(null=True, blank=True)
    degree_year_uncertain = models.BooleanField(default=False)

    def __unicode__(self):
        return '%s - %s' % (
        unicode(self.creator), unicode(self.degree.degree_name))


class ArtInfluence(models.Model):
    """
    record the Name of artistic influences for creators
    """

    class Meta:
        app_label = 'gcd'
        verbose_name_plural = 'Art Influences'

    creator = models.ForeignKey(Creator)
    influence_name = models.CharField(max_length=200)
    # is_influence_exist = models.BooleanField(default=False)
    influence_link = models.ForeignKey(
            Creator,
            null=True,
            blank=True,
            related_name='exist_influencer')
    # self identify docs
    is_self_identify = models.BooleanField(default=False)
    self_identify_influences_doc = models.TextField(blank=True, null=True)
    influence_source = models.ManyToManyField(SourceType,
                                              related_name='influencesource',
                                              null=True, blank=True)

    # Fields related to change management.
    reserved = models.BooleanField(default=False, db_index=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    deleted = models.BooleanField(default=False, db_index=True)

    def __unicode__(self):
        return unicode(self.influence_name)

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_creator_artinfluence',
                kwargs={'creator_artinfluence_id': self.id})

    def deletable(self):
        return True


class MembershipType(models.Model):
    """
    type of Membership
    """

    class Meta:
        app_label = 'gcd'
        verbose_name_plural = 'Membership Types'

    type = models.CharField(max_length=100)

    def __unicode__(self):
        return unicode(self.type)


class Membership(models.Model):
    """
    record societies and other organizations related to their
    artistic profession that creators held memberships in
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('membership_type',)
        verbose_name_plural = 'Memberships'

    creator = models.ForeignKey(Creator)
    organization_name = models.CharField(max_length=200)
    membership_type = models.ForeignKey(MembershipType, null=True, blank=True)
    membership_begin_year = models.PositiveSmallIntegerField(null=True,
                                                             blank=True)
    membership_begin_year_uncertain = models.BooleanField(default=False)
    membership_end_year = models.PositiveSmallIntegerField(null=True,
                                                           blank=True)
    membership_end_year_uncertain = models.BooleanField(default=False)
    membership_source = models.ManyToManyField(SourceType,
                                               related_name='membershipsource',
                                               null=True, blank=True)

    # Fields related to change management.
    reserved = models.BooleanField(default=False, db_index=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    deleted = models.BooleanField(default=False, db_index=True)

    def __unicode__(self):
        return '%s' % unicode(self.organization_name)

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_creator_membership',
                kwargs={'creator_membership_id': self.id})

    def deletable(self):
        return True


class Award(models.Model):
    """
    record any awards and honors a creator received
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('award_year',)
        verbose_name_plural = 'Awards'

    creator = models.ForeignKey(Creator)
    award_name = models.CharField(max_length=255)
    award_year = models.PositiveSmallIntegerField(null=True, blank=True)
    award_year_uncertain = models.BooleanField(default=False)
    award_source = models.ManyToManyField(SourceType,
                                          related_name='awardsource', null=True,
                                          blank=True)

    # Fields related to change management.
    reserved = models.BooleanField(default=False, db_index=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    deleted = models.BooleanField(default=False, db_index=True)

    def __unicode__(self):
        return unicode(self.award_name)

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_creator_award',
                kwargs={'creator_award_id': self.id})

    def deletable(self):
        return True


class NonComicWorkType(models.Model):
    """
    record the type of work performed
    """

    class Meta:
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
        app_label = 'gcd'
        verbose_name_plural = 'NonComic Work Roles'

    role_name = models.CharField(max_length=200)

    def __unicode__(self):
        return unicode(self.role_name)


class NonComicWork(models.Model):
    """
    record the non-comics work of comics creators
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('publication_title', 'employer_name', 'work_type')
        verbose_name_plural = 'NonComic Works'

    creator = models.ForeignKey(Creator)
    work_type = models.ForeignKey(NonComicWorkType)
    publication_title = models.CharField(max_length=200)
    employer_name = models.CharField(max_length=200, null=True, blank=True)
    work_title = models.CharField(max_length=255, blank=True, null=True)
    work_role = models.ForeignKey(NonComicWorkRole, null=True)
    work_source = models.ManyToManyField(SourceType, related_name='worksource',
                                         null=True, blank=True)
    work_notes = models.TextField(blank=True, null=True)

    # Fields related to change management.
    reserved = models.BooleanField(default=False, db_index=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    deleted = models.BooleanField(default=False, db_index=True)

    def __unicode__(self):
        return '%s' % (unicode(self.publication_title))

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_creator_noncomicwork',
                kwargs={'creator_noncomicwork_id': self.id})

    def deletable(self):
        return True


class NonComicWorkYear(models.Model):
    """
    record the year of the work
    There may be multiple years recorded
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('work_year',)
        verbose_name_plural = 'NonComic Work Years'

    non_comic_work = models.ForeignKey(NonComicWork, related_name='noncomicworkyears')
    work_year = models.PositiveSmallIntegerField(null=True, blank=True)
    work_year_uncertain = models.BooleanField(default=False)

    def __unicode__(self):
        return '%s - %s' % (
        unicode(self.non_comic_work), unicode(self.work_year))


class NonComicWorkLink(models.Model):
    """
    record a link to either the work or more information about the work
    """

    class Meta:
        app_label = 'gcd'
        verbose_name_plural = 'NonComic Work Links'

    non_comic_work = models.ForeignKey(NonComicWork, related_name='noncomicworklinks')
    link = models.URLField(max_length=255)

    def __unicode__(self):
        return unicode(self.link)

    def deletable(self):
        return True
