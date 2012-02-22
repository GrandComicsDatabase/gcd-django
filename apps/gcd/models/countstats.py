# -*- coding: utf-8 -*-
from django.db import models

from apps.gcd.models.publisher import Publisher, Brand, IndiciaPublisher
from apps.gcd.models.language import Language
from apps.gcd.models.series import Series
from apps.gcd.models.issue import Issue, INDEXED
from apps.gcd.models.story import Story
from apps.gcd.models.cover import Cover

class CountStatsManager(models.Manager):

    def init_stats(self, language):
        self.filter(language=language).delete()

        if language is None:
            self.create(name='publishers', language=language,
              count=Publisher.objects.filter(deleted=False).count())
            self.create(name='brands', language=language,
              count=Brand.objects.filter(deleted=False).count())
            self.create(name='indicia publishers', language=language,
              count=IndiciaPublisher.objects.filter(deleted=False).count())

            self.create(name='series', language=language,
              count=Series.objects.filter(deleted=False).count())
            self.create(name='issues', language=language,
              count=Issue.objects.filter(deleted=False).count())
            self.create(name='variant issues', language=language,
              count=Issue.objects.filter(deleted=False)\
              .exclude(variant_of=None).count())
            self.create(name='issue indexes', language=language,
              count=Issue.objects.filter(deleted=False)\
                         .exclude(is_indexed=INDEXED['skeleton']).count())
            self.create(name='covers', language=language,
              count=Cover.objects.filter(deleted=False).count())
            self.create(name='stories', language=language,
              count=Story.objects.filter(deleted=False).count())

            return

        self.create(name='series', language=language,
          count=Series.objects.filter(language=language, deleted=False).count())

        self.create(name='issues', language=language,
          count=Issue.objects.filter(series__language=language,
                                     deleted=False).count())
                                     
        self.create(name='variant issues', language=language,
          count=Issue.objects.filter(series__language=language, \
              deleted=False).exclude(variant_of=None).count())

        self.create(name='issue indexes', language=language,
          count=Issue.objects.filter(series__language=language,
                                     deleted=False)\
                     .exclude(is_indexed=INDEXED['skeleton']).count())

        self.create(name='covers', language=language,
          count=Cover.objects.filter(issue__series__language=language,
                                     deleted=False).count())

        self.create(name='stories', language=language,
          count=Story.objects.filter(issue__series__language=language,
                                     deleted=False).count())

class CountStats(models.Model):
    """
    Store stats from gcd database.
    """
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_count_stats'

    class Admin:
        pass

    objects = CountStatsManager()

    name = models.CharField(max_length=40, null=True)
    count = models.IntegerField()
    language = models.ForeignKey(Language, null=True)

    def __unicode__(self):
        return self.name + ": " + str(self.count)

