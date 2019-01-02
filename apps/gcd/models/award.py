import calendar
from operator import itemgetter
from django.core import urlresolvers
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey, \
                                               GenericRelation

from .datasource import SourceType, DataSource
from .gcddata import GcdData
from apps.oi import states


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
        return self.receivedaward_set.exclude(deleted=True)

    def get_absolute_url(self):
        return urlresolvers.reverse(
                'show_award',
                kwargs={'award_id': self.id})

    def __unicode__(self):
        return unicode(self.name)


class ReceivedAward(GcdData):
    """
    record received awards
    """
    class Meta:
        db_table = 'gcd_received_award'
        app_label = 'gcd'
        ordering = ('award_year',)
        verbose_name_plural = 'Received Awards'
      
    content_type = models.ForeignKey(ContentType, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    recipient = GenericForeignKey('content_type', 'object_id')
    
    award = models.ForeignKey(Award, null=True)
    award_name = models.CharField(max_length=255, blank=True)
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
                'show_received_award',
                kwargs={'received_award_id': self.id})

    def __unicode__(self):
        return unicode(self.award_name)
