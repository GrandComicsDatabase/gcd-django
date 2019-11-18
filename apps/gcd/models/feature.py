from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation
from django.core import urlresolvers

from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from taggit.managers import TaggableManager

from apps.stddata.models import Language
from .gcddata import GcdData, GcdLink
from .image import Image


class FeatureRelationType(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_feature_relation_type'

    # technical name, not to be changed
    name = models.CharField(max_length=255, db_index=True)
    # short description, e.g. shown in selection boxes
    description = models.CharField(max_length=255)
    reverse_description = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class FeatureType(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_feature_type'
        ordering = ('id',)

    name = models.CharField(max_length=255, db_index=True)

    def __str__(self):
        return self.name


class Feature(GcdData):
    class Meta:
        app_label = 'gcd'
        ordering = ('sort_name',)
        db_table = 'gcd_feature'

    name = models.CharField(max_length=255, db_index=True)
    sort_name = models.CharField(max_length=255, db_index=True)
    genre = models.CharField(max_length=255)
    language = models.ForeignKey(Language)
    feature_type = models.ForeignKey(FeatureType)
    year_created = models.IntegerField(db_index=True, null=True)
    year_created_uncertain = models.BooleanField(default=False)
    notes = models.TextField()
    keywords = TaggableManager()

    def has_dependents(self):
        return bool(self.active_logos().exists()) or \
               bool(self.active_stories().exists())

    def active_logos(self):
        return self.featurelogo_set.filter(deleted=False)

    def active_stories(self):
        return self.story_set.filter(deleted=False)

    def display_year_created(self):
        if not self.year_created:
            return '?'
        else:
            return '%d%s' % (self.year_created, 
                             '?' if self.year_created_uncertain else '')

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_feature',
                kwargs={'feature_id': self.id})

    def __str__(self):
        base_name = str('%s (%s)' % (self.name, self.language.name))
        if self.feature_type.id != 1:
            base_name += ' [%s]' % self.feature_type.name[0]
        return base_name


class FeatureLogo(GcdData):
    """
    Logos of features.
    """

    class Meta:
        ordering = ('sort_name',)
        app_label = 'gcd'
        db_table = 'gcd_feature_logo'
        verbose_name_plural = 'Feature Logos'

    feature = models.ManyToManyField(Feature,
                                     db_table='gcd_feature_logo_2_feature')
    name = models.CharField(max_length=255, db_index=True)
    sort_name = models.CharField(max_length=255, db_index=True)
    year_began = models.IntegerField(db_index=True, null=True)
    year_ended = models.IntegerField(null=True)
    year_began_uncertain = models.BooleanField(default=False)
    year_ended_uncertain = models.BooleanField(default=False)
    notes = models.TextField()

    image_resources = GenericRelation(Image)

    @property
    def logo(self):
        img = Image.objects.filter(object_id=self.id, deleted=False,
          content_type = ContentType.objects.get_for_model(self), type__id=6)
        if img:
            return img.get()
        else:
            return None

    def has_dependents(self):
        return bool(self.active_stories().exists())

    def active_stories(self):
        return self.story_set.filter(deleted=False)

    def display_years(self):
        if not self.year_began and not self.year_ended:
            return '?'

        if not self.year_began:
            years = '? - '
        else:
            years = '%d%s - ' % (self.year_began, 
                              '?' if self.year_began_uncertain else '')
        if not self.year_ended:
            years = '%s %s' % (years,
                               '?' if self.year_ended_uncertain else 'present')
        else:
            years = '%s%d%s' % (years, self.year_ended, 
                                '?' if self.year_ended_uncertain else '')
        return years


    def get_absolute_url(self):
        return urlresolvers.reverse(
            'show_feature_logo',
            kwargs={'feature_logo_id': self.id } )

    def full_name(self):
        return self.__str__()

    def __str__(self):
        return str(self.name)


class FeatureRelation(GcdLink):
    """
    Relations between features.
    """

    class Meta:
        db_table = 'gcd_feature_relation'
        app_label = 'gcd'
        ordering = ('to_feature', 'relation_type', 'from_feature')
        verbose_name_plural = 'Feature Relations'

    to_feature = models.ForeignKey(Feature,
                                   related_name='from_related_feature')
    from_feature = models.ForeignKey(Feature,
                                     related_name='to_related_feature')
    relation_type = models.ForeignKey(FeatureRelationType,
                                      related_name='relation_type')
    notes = models.TextField()

    def __str__(self):
        return '%s >Relation< %s :: %s' % (str(self.from_feature),
                                           str(self.to_feature),
                                           str(self.relation_type)
                                          )
