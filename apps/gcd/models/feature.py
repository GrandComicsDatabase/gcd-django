from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation
import django.urls as urlresolvers
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from taggit.managers import TaggableManager

import django_tables2 as tables

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
    disambiguation = models.CharField(max_length=255, default='',
                                      db_index=True)
    genre = models.CharField(max_length=255)
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    feature_type = models.ForeignKey(FeatureType, on_delete=models.CASCADE)
    year_created = models.IntegerField(db_index=True, null=True)
    year_created_uncertain = models.BooleanField(default=False)
    notes = models.TextField()
    keywords = TaggableManager()

    def has_dependents(self):
        return bool(self.active_logos().exists()) or \
               bool(self.active_stories().exists()) or \
               bool(self.from_related_feature.all().exists()) or \
               bool(self.to_related_feature.all().exists())

    def active_logos(self):
        return self.featurelogo_set.filter(deleted=False)

    def active_stories(self):
        return self.story_set.filter(deleted=False)

    def other_translations(self):
        if self.from_related_feature.filter(relation_type__id=1).count() == 1:
            source = self.from_related_feature.get(relation_type__id=1)
            other_translations = source.from_feature.to_related_feature\
                                 .filter(to_feature__language=self.language)
            return other_translations.exclude(to_feature=self)
        return None

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

    def name_with_disambiguation(self):
        extra = ''
        if self.disambiguation:
            extra = ' [%s]' % self.disambiguation
        base_name = str('%s%s' % (self.name, extra))
        if self.feature_type.id != 1:
            base_name += ' [%s]' % self.feature_type.name[0]
        return base_name

    def __str__(self):
        extra = ''
        if self.disambiguation:
            extra = ' [%s]' % self.disambiguation
        base_name = str('%s%s (%s)' % (self.name, extra, self.language.name))
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
    generic = models.BooleanField(default=False)
    year_began = models.IntegerField(db_index=True, null=True)
    year_ended = models.IntegerField(null=True)
    year_began_uncertain = models.BooleanField(default=False)
    year_ended_uncertain = models.BooleanField(default=False)
    notes = models.TextField()

    image_resources = GenericRelation(Image)

    @property
    def logo(self):
        img = Image.objects.filter(
          object_id=self.id, deleted=False,
          content_type=ContentType.objects.get_for_model(self), type__id=6)
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
            kwargs={'feature_logo_id': self.id})

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

    to_feature = models.ForeignKey(Feature, on_delete=models.CASCADE,
                                   related_name='from_related_feature')
    from_feature = models.ForeignKey(Feature, on_delete=models.CASCADE,
                                     related_name='to_related_feature')
    relation_type = models.ForeignKey(FeatureRelationType,
                                      on_delete=models.CASCADE,
                                      related_name='relation_type')
    notes = models.TextField()

    def __str__(self):
        return '%s >Relation< %s :: %s' % (str(self.from_feature),
                                           str(self.to_feature),
                                           str(self.relation_type)
                                           )


class FeatureTable(tables.Table):
    credits_count = tables.Column(accessor='issue_credits_count',
                                  verbose_name='Issues')
    feature = tables.Column(accessor='name',
                            verbose_name='Feature')
    first_credit = tables.Column(verbose_name='First Credit')
    role = tables.Column(accessor='script', orderable=False)

    class Meta:
        model = Feature
        fields = ('feature', 'first_credit')

    def __init__(self, *args, **kwargs):
        self.creator = kwargs.pop('creator')
        super(FeatureTable, self).__init__(*args, **kwargs)

    def render_feature(self, record):
        name_link = '<a href="%s">%s</a> (%s)' % (record.get_absolute_url(),
                                                  esc(record.name),
                                                  record.language.name)
        return mark_safe(name_link)

    def render_first_credit(self, value):
        return value[:4]

    def render_credits_count(self, record):
        url = urlresolvers.reverse(
                'creator_feature_issues',
                kwargs={'creator_id': self.creator.id,
                        'feature_id': record.id})
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
