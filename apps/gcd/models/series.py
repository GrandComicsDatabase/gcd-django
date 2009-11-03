# -*- coding: utf-8 -*-
from django.db import models

from country import Country
from language import Language
from publisher import Publisher

class Series(models.Model):
    class Meta:
        app_label = 'gcd'
        ordering = ['name', 'year_began']
    
    # Core series fields.
    name = models.CharField(max_length=255, null=True, db_index=True)
    format = models.CharField(max_length=255, null=True)
    notes = models.TextField(null=True)
    year_began = models.IntegerField(db_index=True)
    year_ended = models.IntegerField(null=True)
    publication_dates = models.CharField(max_length=255, null=True)
    issue_count = models.IntegerField(null=True)

    # Publication notes are not displayed in the current UI but may
    # be accessed in the OI.
    publication_notes = models.TextField(null=True)

    # Fields for tracking relationships between series.
    # Crossref fields don't appear to really be used- nearly all null.
    tracking_notes = models.TextField(null=True)

    # Fields related to cover image galleries.
    has_gallery = models.BooleanField(db_index=True)

    # Fields related to indexing activities.
    # Only "reserved" is in active use.  "open_reserve" is a legacy field
    # used only by migration scripts.
    reserved = models.BooleanField(default=0, db_index=True)
    open_reserve = models.IntegerField(null=True)

    # Issue tracking info that should probably be read from issues table.
    # Note that in the issues table, issues can be 25 characters.
    first_issue = models.CharField(max_length=50, null=True)
    last_issue = models.CharField(max_length=50, null=True)

    # Country and Language info.
    country = models.ForeignKey(Country)
    language = models.ForeignKey(Language)

    # Fields related to the publishers table.
    publisher = models.ForeignKey(Publisher, null=True)
    imprint = models.ForeignKey(Publisher, null=True,
                                related_name='imprint_series_set')

    # Fields related to change management.
    created = models.DateTimeField(auto_now_add=True, null=True)
    modified = models.DateTimeField(auto_now=True, null=True)

    def get_absolute_url(self):
        return "/series/%i/" % self.id

    def marked_scan_count(self):
        return self.cover_set.filter(marked=True, has_image='1').count()

    def scan_count(self):
        return self.cover_set.filter(has_image='1').count()

    def scan_needed(self):
        return self.issue_count - self.scan_count() + self.marked_scan_count()

    def __unicode__(self):
        return '%s (%s series)' % (self.name, self.year_began)

