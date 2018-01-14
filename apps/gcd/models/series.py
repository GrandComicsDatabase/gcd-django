# -*- coding: utf-8 -*-
from django.db import models
from django.core import urlresolvers
from django.db.models import Count, Case, When
from django.template.defaultfilters import pluralize
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from taggit.managers import TaggableManager

from apps.stddata.models import Country, Language
from apps.gcd.models.publisher import Publisher, Brand, IndiciaPublisher
from apps.gcd.models.seriesbond import SeriesRelativeBond

# TODO: should not be importing oi app into gcd app, dependency should be
# the other way around.  Probably.
from apps.oi import states

class SeriesPublicationType(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_series_publication_type'
        ordering = ['name']

    name = models.CharField(max_length=255, db_index=True)
    notes = models.TextField()

    def __unicode__(self):
        return self.name

class Series(models.Model):
    class Meta:
        app_label = 'gcd'
        ordering = ['sort_name', 'year_began']

    # Core series fields.
    name = models.CharField(max_length=255, db_index=True)
    sort_name = models.CharField(max_length=255, db_index=True)

    # The "format" field is a legacy field that is being split into
    # color, dimensions, paper_stock, binding, and publishing_format
    format = models.CharField(max_length=255, default=u'')
    color = models.CharField(max_length=255, default=u'')
    dimensions = models.CharField(max_length=255, default=u'')
    paper_stock = models.CharField(max_length=255, default=u'')
    binding = models.CharField(max_length=255, default=u'')
    publishing_format = models.CharField(max_length=255, default=u'')

    publication_type = models.ForeignKey(SeriesPublicationType, null=True, blank=True)
    notes = models.TextField()
    keywords = TaggableManager()

    year_began = models.IntegerField(db_index=True)
    year_ended = models.IntegerField(null=True)
    year_began_uncertain = models.BooleanField(default=False)
    year_ended_uncertain = models.BooleanField(default=False)
    is_current = models.BooleanField(default=False, db_index=True)
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

    # Fields for handling the presence of certain issue fields
    has_barcode = models.BooleanField(default=False)
    has_indicia_frequency = models.BooleanField(default=False)
    has_isbn = models.BooleanField(default=False)
    has_issue_title = models.BooleanField(default=False)
    has_volume = models.BooleanField(default=False)
    has_rating = models.BooleanField(default=False)

    is_comics_publication = models.BooleanField(default=False)
    is_singleton = models.BooleanField(default=False)

    # Fields related to cover image galleries.
    has_gallery = models.BooleanField(default=False, db_index=True)

    # Fields related to indexing activities.
    # Only "reserved" is in active use.  "open_reserve" is a legacy field
    # used only by migration scripts.
    reserved = models.BooleanField(default=False, db_index=True)
    open_reserve = models.IntegerField(null=True)

    # Country and Language info.
    country = models.ForeignKey(Country)
    language = models.ForeignKey(Language)

    # Fields related to the publishers table.
    publisher = models.ForeignKey(Publisher)

    # Fields related to change management.
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    deleted = models.BooleanField(default=False, db_index=True)

    def has_keywords(self):
        return self.keywords.exists()

    def has_tracking(self):
        return self.tracking_notes or self.has_series_bonds()

    def has_series_bonds(self):
        return self.to_series_bond.exists() or self.from_series_bond.exists()

    def series_relative_bonds(self, **filter_args):
        """
        Returns an unsorted list (not queryset!) of SeriesRelativeBond objects.

        SeriesRelativeBonds are not database objects, but can be sorted
        uniformly and provide access to the underlying SeriesBond.

        Does *not* automatically call has_series_bonds.
        """
        bonds = []
        bonds = [SeriesRelativeBond(self, b)
                 for b in self.to_series_bond.filter(**filter_args)]
        bonds.extend([SeriesRelativeBond(self, b)
                      for b in self.from_series_bond.filter(**filter_args)])
        return bonds

    def delete(self):
        self.deleted = True
        self.reserved = False
        self.save()

    def deletable(self):
        active = self.issue_revisions.filter(changeset__state__in=states.ACTIVE)
        return self.issue_count == 0 and active.count() == 0

    def pending_deletion(self):
        return self.revisions.filter(changeset__state__in=states.ACTIVE,
                                     deleted=True).count() == 1

    def active_issues(self):
        return self.issue_set.exclude(deleted=True)

    def active_base_issues(self):
        return self.active_issues().exclude(variant_of__series=self)

    def active_base_issues_variant_count(self):
        issues = self.active_base_issues()
        issues = issues.annotate(variant_count=\
                                 Count(Case(When(variant_set__deleted=False,
                                                 then=1))))
        return issues

    def ordered_brands(self):
        """
        Provide information on publisher's brands in the order they first
        appear within the series.  Returned as a list so that the UI can check
        the length of the list and the contents with only one DB call.
        """
        return list(Brand.objects.filter(issue__series=self,
                                         issue__deleted=False)\
          .annotate(first_by_brand=models.Min('issue__sort_code'),
                    used_issue_count=models.Count('issue'))\
          .order_by('first_by_brand'))

    def brand_info_counts(self):
        """
        Simple method for the UI to use, as the UI can't pass parameters.
        """

        # There really should be a way to do this in one annotate clause, but I
        # can't figure it out and the ORM may just not do it.  The SQL would be:
        # SELECT (brand_id IS NULL AND no_brand = 0) AS unknown, COUNT(*)
        #   FROM gcd_issue WHERE series_id=x GROUP BY unknown;
        # replacing x with the series id of course.
        return {
            'no_brand': self.active_issues().filter(no_brand=True).count(),
            'unknown': self.active_issues().filter(no_brand=False,
                                                   brand__isnull=True).count(),
        }

    def ordered_indicia_publishers(self):
        """
        Provide information on indicia publishers in the order they first
        appear within the series.  Returned as a list so that the UI can check
        the length of the list and the contents with only one DB call.
        """
        return list(IndiciaPublisher.objects.filter(issue__series=self,
                                                    issue__deleted=False)\
          .annotate(first_by_ind_pub=models.Min('issue__sort_code'),
                    used_issue_count=models.Count('issue'))\
          .order_by('first_by_ind_pub'))

    def indicia_publisher_info_counts(self):
        """
        Simple method for the UI to use.  Called _counts (plural) for symmetry
        with brand_info_counts which actually does return two counts.
        """
        return {
            'unknown': self.active_issues().filter(indicia_publisher__isnull=True)\
                                           .count(),
        }

    def get_ongoing_reservation(self):
        """
        TODO: Rethink usage of 1-1 relation.
        """
        try:
            return self.ongoing_reservation
        except models.ObjectDoesNotExist:
            return None

    def get_absolute_url(self):
        return urlresolvers.reverse(
            'show_series',
            kwargs={'series_id': self.id } )

    def marked_scans_count(self):
        from apps.gcd.models.cover import Cover
        return Cover.objects.filter(issue__series=self, marked=True).count()

    def scan_count(self):
        from apps.gcd.models.cover import Cover
        return Cover.objects.filter(issue__series=self, deleted=False).count()

    def issues_without_covers(self):
        from apps.gcd.models.issue import Issue
        issues = Issue.objects.filter(series=self).exclude(deleted=True)
        return issues.exclude(cover__isnull=False, cover__deleted=False).distinct()

    def scan_needed_count(self):
        return self.issues_without_covers().count() + self.marked_scans_count()

    def issue_indexed_count(self):
        from apps.gcd.models.issue import INDEXED
        return self.active_base_issues()\
                   .exclude(is_indexed=INDEXED['skeleton']).count()

    def _date_uncertain(self, flag):
        return u' ?' if flag else u''

    def display_publication_dates(self):
        if self.issue_count == 0:
            return u'%s%s' % (unicode(self.year_began),
                  self._date_uncertain(self.year_began_uncertain))
        elif self.issue_count == 1:
            if self.first_issue.publication_date:
                return self.first_issue.publication_date
            else:
                return u'%s%s' % (unicode(self.year_began),
                  self._date_uncertain(self.year_began_uncertain))
        else:
            if self.first_issue.publication_date:
                date = u'%s - ' % self.first_issue.publication_date
            else:
                date = u'%s%s - ' % (self.year_began,
              self._date_uncertain(self.year_began_uncertain))
            if self.is_current:
                date += 'Present'
            elif self.last_issue.publication_date:
                date += self.last_issue.publication_date
            elif self.year_ended:
                date += u'%s%s' % (unicode(self.year_ended),
                  self._date_uncertain(self.year_ended_uncertain))
            else:
                date += u'?'
            return date

    def search_result_name(self):
        if self.issue_count <= 1 and not self.is_current:
            date = u'%s%s' % (unicode(self.year_began),
              self._date_uncertain(self.year_began_uncertain))
        else:
            date = u'%s%s - ' % (self.year_began,
              self._date_uncertain(self.year_began_uncertain))
            if self.is_current:
                date += 'Present'
            elif self.year_ended:
                date += u'%s%s' % (unicode(self.year_ended),
                  self._date_uncertain(self.year_ended_uncertain))
            else:
                date += u'?'

        if self.is_singleton:
            issues = ''
        else:
            issues = '%d issue%s in' % (self.issue_count, 
                                        pluralize(self.issue_count))

        return '%s (%s) %s %s' % (self.name, self.publisher, issues, date)

    def full_name(self):
        return '%s (%s, %s%s series)' % (self.name, self.publisher,
          self.year_began, self._date_uncertain(self.year_began_uncertain))

    def full_name_with_link(self, publisher=False):
        if publisher:
            name_link = '<a href="%s">%s</a> (<a href="%s">%s</a>, %s%s series)' \
              % (self.get_absolute_url(), esc(self.name),
                 self.publisher.get_absolute_url(), self.publisher,
                 self.year_began,
                 self._date_uncertain(self.year_began_uncertain))
        else:
            name_link = '<a href="%s">%s</a>' % (self.get_absolute_url(),
                                                 esc(self.full_name()))
        return mark_safe(name_link)

    def __unicode__(self):
        return '%s (%s%s series)' % (self.name, self.year_began,
          self._date_uncertain(self.year_began_uncertain))
