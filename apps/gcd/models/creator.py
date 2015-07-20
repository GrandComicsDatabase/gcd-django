from collections import OrderedDict
from django.db import models
from django.conf import settings

from apps.gcd.models.country import Country


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
    type = models.CharField(max_length=50)

    def __unicode__(self):
        return self.type


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
        return self.type


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
        return self.type


class CreatorManager(models.Manager):
    """
    need to be manage creator model
    with this custom manager in future
    """
    pass



class Creator(models.Model):

    class Meta:
        app_label = 'gcd'
        ordering = ('name',)
        verbose_name_plural = 'Creators'

    objects = CreatorManager()

    name = models.CharField(max_length=255, db_index=True)
    name_type = models.ForeignKey(NameType)
    name_source = models.ManyToManyField(SourceType, related_name='namesource', through='NameSource')
    related_person = models.ManyToManyField(
        'self',
        through='NameRelation',
        symmetrical=False)
    birth_year = models.PositiveSmallIntegerField(null=True, blank=True)
    birth_year_uncertain = models.BooleanField(default=False)
    birth_year_source = models.ManyToManyField(SourceType, related_name='birthyearsource', through='BirthYearSource')
    birth_month = models.PositiveSmallIntegerField(null=True, blank=True)
    birth_month_uncertain = models.BooleanField(default=False)
    birth_month_source = models.ManyToManyField(SourceType, related_name='birthmonthsource', through='BirthMonthSource')
    birth_date = models.PositiveSmallIntegerField(null=True, blank=True)
    birth_date_uncertain = models.BooleanField(default=False)
    birth_date_source = models.ManyToManyField(SourceType, related_name='birthdatesource', through='BirthDateSource')
    death_year = models.PositiveSmallIntegerField(null=True, blank=True)
    death_year_uncertain = models.BooleanField(default=False)
    death_year_source = models.ManyToManyField(SourceType, related_name='deathyearsource', through='DeathYearSource')
    death_month = models.PositiveSmallIntegerField(null=True, blank=True)
    death_month_uncertain = models.BooleanField(default=False)
    death_month_source = models.ManyToManyField(SourceType, related_name='deathmonthsource', through='DeathMonthSource')
    death_date = models.PositiveSmallIntegerField(null=True, blank=True)
    death_date_uncertain = models.BooleanField(default=False)
    death_date_source = models.ManyToManyField(SourceType, related_name='deathdatesource', through='DeathDateSource')
    whos_who = models.URLField(default=None, blank=True, null=True)
    birth_country = models.ForeignKey(
        Country,
        related_name='birth_country',
        blank=True,
        null=True)
    birth_country_uncertain = models.BooleanField(default=False)
    birth_country_source = models.ManyToManyField(SourceType, related_name='birthcountrysource', through='BirthCountrySource')
    birth_province = models.CharField(max_length=50, blank=True, null=True)
    birth_province_uncertain = models.BooleanField(default=False)
    birth_province_source = models.ManyToManyField(SourceType, related_name='birthprovincesource', through='BirthProvinceSource')
    birth_city = models.CharField(max_length=200, blank=True, null=True)
    birth_city_uncertain = models.BooleanField(default=False)
    birth_city_source = models.ManyToManyField(SourceType, related_name='birthcitysource', through='BirthCitySource')
    death_country = models.ForeignKey(
        Country,
        related_name='death_country',
        blank=True,
        null=True)
    death_country_uncertain = models.BooleanField(default=False)
    death_country_source = models.ManyToManyField(SourceType, related_name='deathcountrysource', through='DeathCountrySource')
    death_province = models.CharField(max_length=50, blank=True, null=True)
    death_province_uncertain = models.BooleanField(default=False)
    death_province_source = models.ManyToManyField(SourceType, related_name='deathprovincesource', through='DeathProvinceSource')
    death_city = models.CharField(max_length=200, blank=True, null=True)
    death_city_uncertain = models.BooleanField(default=False)
    death_city_source = models.ManyToManyField(SourceType, related_name='deathcitysource', through='DeathCitySource')
    portrait = models.ImageField(upload_to=settings.PORTRAIT_DIR)
    portrait_source = models.ManyToManyField(SourceType, related_name='portraitsource', through='PortraitSource')
    schools = models.ManyToManyField('School', related_name='schoolinformation', through='CreatorSchoolDetail')
    degrees = models.ManyToManyField('Degree', related_name='degreeinformation', through='CreatorDegreeDetail')
    # creators roles
    bio = models.TextField(blank=True, null=True)
    bio_source = models.ManyToManyField(SourceType, related_name='biosource', through='BioSource')
    sample_scan = models.FileField(upload_to=settings.SAMPLE_SCAN_DIR)
    notes = models.TextField(blank=True, null=True)

    def __unicode__(self):
        return '%s (%s)' % (self.name, self.name_type)

    def get_link_fields(self):
        links_dict = {}
        links_dict['Whos Who'] = self.whos_who
        return links_dict

    def get_file_fields(self):
        files_dict = OrderedDict()
        files_dict['Portrait'] = self.portrait
        files_dict['Sample Scan'] = self.sample_scan
        return files_dict

    def get_text_fields(self):
        fields_dict = OrderedDict()
        fields_dict['name'] = self.name
        fields_dict['Name Type'] = self.name_type.type
        fields_dict['Birth Year'] = self.birth_year
        fields_dict['Birth Year Uncertain'] = self.birth_year_uncertain
        fields_dict['Birth Month'] = self.birth_month
        fields_dict['Birth Month Uncertain'] = self.birth_month_uncertain
        fields_dict['Birth Date'] = self.birth_date
        fields_dict['Birth Date Uncertain'] = self.birth_date_uncertain
        fields_dict['Death Year'] = self.death_year
        fields_dict['Death Year Uncertain'] = self.death_year_uncertain
        fields_dict['Death Month'] = self.death_month
        fields_dict['Death Month Uncertain'] = self.death_month_uncertain
        fields_dict['Death Date'] = self.death_date
        fields_dict['Death Date Uncertain'] = self.death_date_uncertain
        fields_dict['whos_who'] = self.whos_who
        fields_dict['Birth Country'] = self.birth_country.name
        fields_dict['Birth Country Uncertain'] = self.birth_country_uncertain
        fields_dict['Birth Province'] = self.birth_province
        fields_dict['Birth Province Uncertain'] = self.birth_province_uncertain
        fields_dict['Birth City'] = self.birth_city
        fields_dict['Birth City Uncertain'] = self.birth_city_uncertain
        fields_dict['Death Country'] = self.death_country.name
        fields_dict['Death Country Uncertain'] = self.death_country_uncertain
        fields_dict['Death Province'] = self.death_province
        fields_dict['Death Province Uncertain'] = self.death_province_uncertain
        fields_dict['Death City'] = self.death_city
        fields_dict['Death City Uncertain'] = self.death_city_uncertain
        fields_dict['Bio'] = self.bio
        fields_dict['Notes'] = self.notes
        return fields_dict


class NameRelation(models.Model):

    """
    Relations between creators to relate any GCD Official name to any other name.
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('gcd_official_name', 'rel_type', 'to_name')
        verbose_name_plural = 'Name Relations'

    gcd_official_name = models.ForeignKey(
        Creator,
        related_name='gcd_official_name')
    to_name = models.ForeignKey(Creator, related_name='to_name')
    rel_type = models.ForeignKey(RelationType, related_name='relation_type')
    rel_source = models.ManyToManyField(SourceType)

    def __unicode__(self):
        return '%s >Name_Relation< %s :: %s' % (self.gcd_official_name,
                                                self.to_name, self.rel_type
                                                )

class NameSource(models.Model):

    """
    Indicates the various sources of names
    Multiple Name sources could be checked per name.
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('source_name',)
        verbose_name_plural = 'Name Source'

    creator = models.ForeignKey(Creator, related_name='creatornamesource')
    source_type = models.ForeignKey(SourceType, related_name='namesourcetype')
    source_name = models.TextField()

    def __unicode__(self):
        return self.source_name


class BirthYearSource(models.Model):

    """
    Indicates the various sources of birthyear
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('source_name',)
        verbose_name_plural = 'Birth Year Source'

    creator = models.ForeignKey(Creator, related_name='creatorbirthyearsource')
    source_type = models.ForeignKey(SourceType, related_name='creatorbirthyearsourcetype')
    source_name = models.TextField()

    def __unicode__(self):
        return self.source_name


class BirthMonthSource(models.Model):

    """
    Indicates the various sources of birthmonth
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('source_name',)
        verbose_name_plural = 'Birth Month Source'

    creator = models.ForeignKey(Creator, related_name='creatorbirthmonthsource')
    source_type = models.ForeignKey(SourceType, related_name='creatorbirthmonthsourcetype')
    source_name = models.TextField()

    def __unicode__(self):
        return self.source_name


class BirthDateSource(models.Model):

    """
    Indicates the various sources of birthdate
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('source_name',)
        verbose_name_plural = 'Birth Date Source'

    creator = models.ForeignKey(Creator, related_name='creatorbirthdatesource')
    source_type = models.ForeignKey(SourceType, related_name='creatorbirthdatesourcetype')
    source_name = models.TextField()

    def __unicode__(self):
        return self.source_name


class DeathYearSource(models.Model):

    """
    Indicates the various sources of deathyear
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('source_name',)
        verbose_name_plural = 'Death Year Source'

    creator = models.ForeignKey(Creator, related_name='creatordeathyearsource')
    source_type = models.ForeignKey(SourceType, related_name='creatordeathyearsourcetype')
    source_name = models.TextField()

    def __unicode__(self):
        return self.source_name


class DeathMonthSource(models.Model):

    """
    Indicates the various sources of deathmonth
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('source_name',)
        verbose_name_plural = 'Death Month Source'

    creator = models.ForeignKey(Creator, related_name='creatordeathmonthsource')
    source_type = models.ForeignKey(SourceType, related_name='creatordeathmonthsourcetype')
    source_name = models.TextField()

    def __unicode__(self):
        return self.source_name


class DeathDateSource(models.Model):

    """
    Indicates the various sources of deathdate
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('source_name',)
        verbose_name_plural = 'Death Date Source'

    creator = models.ForeignKey(Creator, related_name='creatordeathdatesource')
    source_type = models.ForeignKey(SourceType, related_name='creatordeathdatesourcetype')
    source_name = models.TextField()

    def __unicode__(self):
        return self.source_name


class BirthCountrySource(models.Model):

    """
    Indicates the various sources of birthcountry
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('source_name',)
        verbose_name_plural = 'Birth Country Source'

    creator = models.ForeignKey(Creator, related_name='creatorbirthcountrysource')
    source_type = models.ForeignKey(SourceType, related_name='creatorbirthcountrysourcetype')
    source_name = models.TextField()

    def __unicode__(self):
        return self.source_name


class BirthProvinceSource(models.Model):

    """
    Indicates the various sources of birthprovince
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('source_name',)
        verbose_name_plural = 'Birth Province Source'

    creator = models.ForeignKey(Creator, related_name='creatorbirthprovincesource')
    source_type = models.ForeignKey(SourceType, related_name='creatorbirthprovincesourcetype')
    source_name = models.TextField()

    def __unicode__(self):
        return self.source_name


class BirthCitySource(models.Model):

    """
    Indicates the various sources of birthcity
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('source_name',)
        verbose_name_plural = 'Birth City Source'

    creator = models.ForeignKey(Creator, related_name='creatorbirthcitysource')
    source_type = models.ForeignKey(SourceType, related_name='creatorbirthcitysourcetype')
    source_name = models.TextField()

    def __unicode__(self):
        return self.source_name


class DeathCountrySource(models.Model):

    """
    Indicates the various sources of deathcountry
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('source_name',)
        verbose_name_plural = 'Death Country Source'

    creator = models.ForeignKey(Creator, related_name='creatordeathcountrysource')
    source_type = models.ForeignKey(SourceType, related_name='creatordeathcountrysourcetype')
    source_name = models.TextField()

    def __unicode__(self):
        return self.source_name


class DeathProvinceSource(models.Model):

    """
    Indicates the various sources of deathprovince
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('source_name',)
        verbose_name_plural = 'Death Province Source'

    creator = models.ForeignKey(Creator, related_name='creatordeathprovincesource')
    source_type = models.ForeignKey(SourceType, related_name='creatordeathprovincesourcetype')
    source_name = models.TextField()

    def __unicode__(self):
        return self.source_name


class DeathCitySource(models.Model):

    """
    Indicates the various sources of deathcity
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('source_name',)
        verbose_name_plural = 'Death City Source'

    creator = models.ForeignKey(Creator, related_name='creatordeathcitysource')
    source_type = models.ForeignKey(SourceType, related_name='creatordeathcitysourcetype')
    source_name = models.TextField()

    def __unicode__(self):
        return self.source_name


class PortraitSource(models.Model):

    """
    Indicates the various sources of portrait
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('source_name',)
        verbose_name_plural = 'Portrait Source'

    creator = models.ForeignKey(Creator, related_name='creatorportraitsource')
    source_type = models.ForeignKey(SourceType, related_name='creatorportraitsourcetype')
    source_name = models.TextField()

    def __unicode__(self):
        return self.source_name


class BioSource(models.Model):

    """
    Indicates the various sources of bio
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('source_name',)
        verbose_name_plural = 'Bio Source'

    creator = models.ForeignKey(Creator, related_name='creatorbiosource')
    source_type = models.ForeignKey(SourceType, related_name='creatorbiosourcetype')
    source_name = models.TextField()

    def __unicode__(self):
        return self.source_name


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
        return self.school_name


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
    school_source = models.ManyToManyField(SourceType, related_name='schoolsource')

    def __unicode__(self):
        return '%s - %s' % (self.creator.name, self.school.school_name)


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
        return self.degree_name


class CreatorDegreeDetail(models.Model):

    """
    record the degrees creators received
    """

    class Meta:
        app_label = 'gcd'
        ordering = ('degree_year',)
        verbose_name_plural = 'Creator Degree Details'

    creator = models.ForeignKey(Creator, related_name='creator_degree')
    school = models.ForeignKey(School, related_name='schooldetails')
    degree = models.ForeignKey(Degree, related_name='degreedetails')
    degree_year = models.PositiveSmallIntegerField(null=True, blank=True)
    degree_year_uncertain = models.BooleanField(default=False)

    def __unicode__(self):
        return '%s - %s' % (self.creator.name, self.degree.degree_name)


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
    influence_source = models.ManyToManyField(SourceType, related_name='influencesource')

    def __unicode__(self):
        return self.influence_name


class MembershipType(models.Model):

    """
    type of Membership
    """
    class Meta:
        app_label = 'gcd'
        verbose_name_plural = 'Membership Types'

    type = models.CharField(max_length=100)

    def __unicode__(self):
        return self.type


class Membership(models.Model):

    """
    record societies and other organizations related to their
    artistic profession that creators held memberships in
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('membership_type', )
        verbose_name_plural = 'Memberships'

    creator = models.ForeignKey(Creator)
    organization_name = models.CharField(max_length=200)
    membership_type = models.ForeignKey(MembershipType)
    membership_begin_year = models.PositiveSmallIntegerField()
    membership_begin_year_uncertain = models.BooleanField(default=False)
    membership_end_year = models.PositiveSmallIntegerField()
    membership_end_year_uncertain = models.BooleanField(default=False)
    membership_source = models.ManyToManyField(SourceType, related_name='membershipsource')

    def __unicode__(self):
        return '%s - %s' % (self.creator, self.membership_type)


class Award(models.Model):

    """
    record any awards and honors a creator received
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('award_year', )
        verbose_name_plural = 'Awards'

    creator = models.ForeignKey(Creator)
    award_name = models.CharField(max_length=255)
    award_year = models.PositiveSmallIntegerField(null=True, blank=True)
    award_year_uncertain = models.BooleanField(default=False)
    award_source = models.ManyToManyField(SourceType, related_name='awardsource')

    def __unicode__(self):
        return self.award_name


class NonComicWorkType(models.Model):

    """
    record the type of work performed
    """
    class Meta:
        app_label = 'gcd'
        verbose_name_plural = 'NonComic Work Types'

    type = models.CharField(max_length=100)

    def __unicode__(self):
        return self.type


class NonComicWorkRole(models.Model):

    """
    record the type of work performed
    """
    class Meta:
        app_label = 'gcd'
        verbose_name_plural = 'NonComic Work Roles'

    role_name = models.CharField(max_length=200)

    def __unicode__(self):
        return self.role_name


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
    publication_title = models.CharField(max_length=200, blank=True, null=True)
    employer_name = models.CharField(max_length=200, null=True, blank=True)
    work_title = models.CharField(max_length=255, null=True, blank=True)
    work_role = models.ForeignKey(NonComicWorkRole)
    work_source = models.ManyToManyField(SourceType, related_name='worksource')
    work_notes = models.TextField(blank=True, null=True)


    def __unicode__(self):
        return '%s - %s' % (self.creator, self.work_type)


class NonComicWorkYear(models.Model):

    """
    record the year of the work
    There may be multiple years recorded
    """
    class Meta:
        app_label = 'gcd'
        ordering = ('work_year', )
        verbose_name_plural = 'NonComic Work Years'

    non_comic_work = models.ForeignKey(NonComicWork)
    work_year = models.PositiveSmallIntegerField(null=True, blank=True)
    work_year_uncertain = models.BooleanField(default=False)

    def __unicode__(self):
        return '%s - %s' % (self.non_comic_work, self.work_year)


class NonComicWorkLink(models.Model):

    """
    record a link to either the work or more information about the work
    """
    class Meta:
        app_label = 'gcd'
        verbose_name_plural = 'NonComic Work Links'

    non_comic_work = models.ForeignKey(NonComicWork)
    link = models.URLField(max_length=255)

    def __unicode__(self):
        return self.link
