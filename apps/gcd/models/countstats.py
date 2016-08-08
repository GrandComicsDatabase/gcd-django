# -*- coding: utf-8 -*-
from django.db import models

from apps.stddata.models import Country, Language
from apps.gcd.models.publisher import Publisher, Brand, IndiciaPublisher
from apps.gcd.models.series import Series
from apps.gcd.models.issue import Issue, INDEXED
from apps.gcd.models.story import Story
from apps.gcd.models.cover import Cover

class CountStatsManager(models.Manager):

    def init_stats(self, language=None, country=None):
        if language and country:
            raise ValueError('either country or language stats')
        self.filter(language=language, country=country).delete()
        if country:
            kwargs = { 'country': country, 'deleted': False }
        else:
            kwargs = { 'deleted': False }

        if language is None:
            self.create(name='publishers', country=country,
              count=Publisher.objects.filter(**kwargs).count())
            if not country:
                self.create(name='brands', 
                  count=Brand.objects.filter(**kwargs).count())
            self.create(name='indicia publishers', country=country,
              count=IndiciaPublisher.objects.filter(**kwargs).count())
        else:
            kwargs['language'] = language

        self.create(name='series', language=language, country=country,
          count=Series.objects.filter(is_comics_publication=True,
                                      **kwargs).count())
        if 'language' in kwargs:
            kwargs['series__language'] = kwargs['language']
            kwargs.pop('language')
        if 'country' in kwargs:
            kwargs['series__country'] = kwargs['country']
            kwargs.pop('country')
        kwargs['series__is_comics_publication'] = True

        self.create(name='issues', language=language, country=country,
          count=Issue.objects.filter(variant_of=None, **kwargs).count())

        self.create(name='variant issues', language=language, country=country,
          count=Issue.objects.filter(**kwargs)\
                                     .exclude(variant_of=None).count())

        self.create(name='issue indexes', language=language, country=country,
          count=Issue.objects.filter(variant_of=None, **kwargs)\
                     .exclude(is_indexed=INDEXED['skeleton']).count())

        if 'series__language' in kwargs:
            kwargs['issue__series__language'] = kwargs['series__language']
            kwargs.pop('series__language')
        if 'series__country' in kwargs:
            kwargs['issue__series__country'] = kwargs['series__country']
            kwargs.pop('series__country')
        kwargs.pop('series__is_comics_publication')
            
        self.create(name='covers', language=language, country=country,
          count=Cover.objects.filter(**kwargs).count())

        self.create(name='stories', language=language, country=country,
          count=Story.objects.filter(**kwargs).count())

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

    name = models.CharField(max_length=40, db_index=True)
    count = models.IntegerField()
    language = models.ForeignKey(Language, null=True)
    country = models.ForeignKey(Country, null=True)

    def __unicode__(self):
        return self.name + ": " + str(self.count)

