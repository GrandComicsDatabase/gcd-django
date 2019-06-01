from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation
from django.core import urlresolvers

from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from taggit.managers import TaggableManager

from apps.stddata.models import Language
from .gcddata import GcdData
from .image import Image


class Feature(GcdData):
    class Meta:
        app_label = 'gcd'
        ordering = ('name',)
        db_table = 'gcd_feature'

    name = models.CharField(max_length=255)
    genre = models.CharField(max_length=255)
    language = models.ForeignKey(Language)
    year_created = models.IntegerField(db_index=True)
    year_created_uncertain = models.BooleanField(default=False)
    notes = models.TextField()
    keywords = TaggableManager()

    def has_dependents(self):
        return bool(self.active_logos().exists())

    def active_logos(self):
        return self.featurelogo_set.filter(deleted=False)

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

    def __unicode__(self):
        return unicode(self.name)


class FeatureLogo(GcdData):
    class Meta:
        ordering = ('name',)
        app_label = 'gcd'
        db_table = 'gcd_feature_logo'
        verbose_name_plural = 'Feature Logos'

    feature = models.ForeignKey(Feature)
    name = models.CharField(max_length=255)
    year_began = models.IntegerField(db_index=True)
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

    def display_years(self):
        if not self.year_began and not self.year_ended:
            return '?'

        if not self.year_began:
            years = '? - '
        else:
            years = '%d%s - ' % (self.year_began, 
                              '?' if self.year_began_uncertain else '')
        if not self.year_ended:
            years = years + '?'
        else:
            years = '%s%d%s' % (years, self.year_ended, 
                                '?' if self.year_ended_uncertain else '')
        return years


    def get_absolute_url(self):
        return urlresolvers.reverse(
            'show_feature_logo',
            kwargs={'feature_logo_id': self.id } )

    def full_name(self):
        return self.__unicode__()

    def __unicode__(self):
        return unicode(self.name)