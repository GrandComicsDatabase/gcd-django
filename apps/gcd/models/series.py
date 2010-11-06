# -*- coding: utf-8 -*-
from django.db import models

from apps.gcd.models.country import Country
from apps.gcd.models.language import Language
from apps.gcd.models.publisher import Publisher

# TODO: should not be importing oi app into gcd app, dependency should be
# the other way around.  Probably.
from apps.oi import states

class Classification(models.Model):
    class Meta:
        app_label = 'gcd'
        ordering = ('sort_code',)
    name = models.CharField(max_length=255, db_index=True)
    is_singular = models.BooleanField(default=False,
      help_text='True if a series in this category may only ever consist of a '
                'single item')
    is_book_like = models.BooleanField(default=False,
      help_text='True if a series in this category is more like a book than like '
                'a magazine, newspaper insert or other form of publication. ')
    notes = models.TextField(blank=True)
    sort_code = models.IntegerField(unique=True)

    def __unicode__(self):
        return self.name

class Series(models.Model):
    class Meta:
        app_label = 'gcd'
        ordering = ['name', 'year_began']
    
    # Core series fields.
    name = models.CharField(max_length=255, db_index=True)
    classification = models.ForeignKey(Classification, null=True, blank=True)
    format = models.CharField(max_length=255)
    notes = models.TextField()

    year_began = models.IntegerField(db_index=True)
    year_ended = models.IntegerField(null=True)
    is_current = models.BooleanField()
    publication_dates = models.CharField(max_length=255)

    first_issue = models.ForeignKey('Issue', null=True,
      related_name='first_issue_series_set')
    last_issue = models.ForeignKey('Issue', null=True,
      related_name='last_issue_series_set')
    issue_count = models.IntegerField()

    # Publication notes may be merged with regular notes in the near future.
    publication_notes = models.TextField()

    # Fields for tracking relationships between series.
    # Crossref fields don't appear to really be used- nearly all null.
    tracking_notes = models.TextField()

    # Fields related to cover image galleries.
    has_gallery = models.BooleanField(db_index=True)

    # Fields related to indexing activities.
    # Only "reserved" is in active use.  "open_reserve" is a legacy field
    # used only by migration scripts.
    reserved = models.BooleanField(default=0, db_index=True)
    open_reserve = models.IntegerField(null=True)

    # Country and Language info.
    country = models.ForeignKey(Country)
    language = models.ForeignKey(Language)

    # Fields related to the publishers table.
    publisher = models.ForeignKey(Publisher)
    imprint = models.ForeignKey(Publisher, null=True,
                                related_name='imprint_series_set')

    # Fields related to change management.
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    deleted = models.BooleanField(default=0, db_index=True)

    def delete(self):
        self.deleted = True
        self.save()

    def deletable(self):
        return self.issue_count == 0 and \
          self.issue_revisions.filter(changeset__state__in=states.ACTIVE).count() == 0

    def active_issues(self):
        return self.issue_set.exclude(deleted=True)

    def get_ongoing_reservation(self):
        """
        TODO: Rethink usage of 1-1 relation.
        """
        try:
            return self.ongoing_reservation
        except models.ObjectDoesNotExist:
            return None

    def get_absolute_url(self):
        return "/series/%i/" % self.id

    def marked_scans_count(self):
        from apps.gcd.models.cover import Cover
        return Cover.objects.filter(issue__series=self, marked=True).count()

    def scan_count(self):
        from apps.gcd.models.cover import Cover
        return Cover.objects.filter(issue__series=self, deleted=False).count()

    def issues_without_covers(self):
        from apps.gcd.models.issue import Issue
        return Issue.objects.filter(series=self).exclude(deleted=True) \
          .exclude(cover__isnull=False, cover__deleted=False).distinct()

    def scan_needed_count(self):
        return self.issues_without_covers().count() + self.marked_scans_count()

    def issue_indexed_count(self):
        return self.active_issues().filter(is_indexed=True).count()

    def display_publication_dates(self):
        if self.issue_count == 0:
            return unicode(self.year_began)
        elif self.issue_count == 1:
            if self.first_issue.publication_date:
                return self.first_issue.publication_date
            else:
                return unicode(self.year_began)
        else:
            if self.first_issue.publication_date:
                date = u'%s - ' % self.first_issue.publication_date
            else:
                date = u'%s - ' % self.year_began
            if self.is_current:
                date += 'Present'
            elif self.last_issue.publication_date:
                date += self.last_issue.publication_date
            elif self.year_ended:
                date += unicode(self.year_ended)
            else:
                date += u'?'
            return date

    def __unicode__(self):
        return '%s (%s series)' % (self.name, self.year_began)
