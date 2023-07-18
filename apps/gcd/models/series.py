# -*- coding: utf-8 -*-

from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
import django.urls as urlresolvers
from django.db.models import Count, Case, When, F, Q
from django.template.defaultfilters import pluralize
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc
from django.utils.functional import cached_property
import django_tables2 as tables

from taggit.managers import TaggableManager

from apps.stddata.models import Country, Language
from .gcddata import GcdData
from .publisher import Publisher, Brand, IndiciaPublisher
from .story import Story, AD_TYPES
from .issue import Issue, INDEXED
from .cover import Cover
from .seriesbond import SeriesRelativeBond
from .award import ReceivedAward


class SeriesPublicationType(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_series_publication_type'
        ordering = ['name']

    name = models.CharField(max_length=255, db_index=True)
    notes = models.TextField()

    def __str__(self):
        return self.name


class Series(GcdData):
    class Meta:
        app_label = 'gcd'
        ordering = ['sort_name', 'year_began']

    # Core series fields.
    name = models.CharField(max_length=255, db_index=True)
    sort_name = models.CharField(max_length=255, db_index=True)

    # The "format" field is a legacy field that is being split into
    # color, dimensions, paper_stock, binding, and publishing_format
    format = models.CharField(max_length=255, default='')
    color = models.CharField(max_length=255, default='')
    dimensions = models.CharField(max_length=255, default='')
    paper_stock = models.CharField(max_length=255, default='')
    binding = models.CharField(max_length=255, default='')
    publishing_format = models.CharField(max_length=255, default='')

    publication_type = models.ForeignKey(SeriesPublicationType,
                                         on_delete=models.CASCADE,
                                         null=True,
                                         blank=True)
    notes = models.TextField()
    keywords = TaggableManager()

    year_began = models.IntegerField(db_index=True)
    year_ended = models.IntegerField(null=True)
    year_began_uncertain = models.BooleanField(default=False)
    year_ended_uncertain = models.BooleanField(default=False)
    is_current = models.BooleanField(default=False, db_index=True)
    publication_dates = models.CharField(max_length=255)

    first_issue = models.ForeignKey('Issue',
                                    on_delete=models.CASCADE,
                                    null=True,
                                    related_name='first_issue_series_set')
    last_issue = models.ForeignKey('Issue',
                                   on_delete=models.CASCADE,
                                   null=True,
                                   related_name='last_issue_series_set')
    issue_count = models.IntegerField(default=0)

    # Fields for tracking relationships between series.
    tracking_notes = models.TextField()

    awards = GenericRelation(ReceivedAward)

    # Fields for handling the presence of certain issue fields
    has_barcode = models.BooleanField(default=False)
    has_indicia_frequency = models.BooleanField(default=False)
    has_indicia_printer = models.BooleanField(default=False)
    has_isbn = models.BooleanField(default=False)
    has_issue_title = models.BooleanField(default=False)
    has_volume = models.BooleanField(default=False)
    has_rating = models.BooleanField(default=False)
    has_about_comics = models.BooleanField(default=False)
    has_publisher_code_number = models.BooleanField(default=False)

    is_comics_publication = models.BooleanField(default=False)
    is_singleton = models.BooleanField(default=False)

    # Fields related to cover image galleries.
    has_gallery = models.BooleanField(default=False, db_index=True)

    # Country and Language info.
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    language = models.ForeignKey(Language, on_delete=models.CASCADE)

    # Fields related to the publishers table.
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE)

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
        bonds = [SeriesRelativeBond(self, b)
                 for b in self.to_series_bond.filter(**filter_args)]
        bonds.extend([SeriesRelativeBond(self, b)
                      for b in self.from_series_bond.filter(**filter_args)])
        return bonds

    def has_dependents(self):
        # use active_issues() rather than issue_count to include variants.
        # TODO allow deletes of singletons with the issues, including
        #      all variants ?
        # return ((not self.is_singleton and self.active_issues().exists()) or
        return (self.active_issues().exists() or
                self.issue_revisions.active_set().exists() or
                self.has_series_bonds())

    def active_issues(self):
        return self.issue_set.exclude(deleted=True)

    def active_base_issues(self):
        """
        All base issues, plus variants whose base is not in this series.

        For the purpose of ensuring that each logical issue has
        a representative in a list, logical issues that do not have
        a base issue in this series need to be represented by a variant.
        """
        # TODO:  What happens if there are two variants in this series
        #        of the same logical issue that has its base in a
        #        different series?
        return self.active_issues().exclude(variant_of__series=self)

    def active_base_issues_variant_count(self):
        issues = self.active_base_issues().order_by('sort_code')
        issues = issues.annotate(
          variant_count=Count(Case(When(variant_set__deleted=False, then=1))))
        return issues

    def active_non_base_variants(self):
        """
        All non-base variants, including those with a base in another series.

        We want to be able to count all variant records related to this series,
        so we leave in the variants with bases in other series, as they can
        be further filtered out in cases where they are not desirable.
        """
        return self.active_issues().exclude(variant_of=None)

    def active_indexed_issues(self):
        return self.active_issues().exclude(is_indexed=INDEXED['skeleton'])

    def set_first_last_issues(self):
        issues = self.active_issues().order_by('sort_code')
        if issues.count() == 0:
            self.first_issue = None
            self.last_issue = None
        else:
            self.first_issue = issues[0]
            self.last_issue = issues[len(issues) - 1]
        self.save()

    _update_stats = True

    def active_awards(self):
        return self.awards.exclude(deleted=True)

    def stat_counts(self):
        """
        Returns all count values relevant to this series.

        Includes a count for the series itself.

        Non-comics publications do not return series and issue
        counts as they do not contribute those types of statistics.
        Story and cover statistics are tracked for all publications.
        """
        if self.deleted:
            return {}

        counts = {
            'covers': self.scan_count,
            'stories': Story.objects.filter(issue__series=self)
                                    .exclude(deleted=True).count(),
        }
        if self.is_comics_publication:
            counts['series'] = 1
            # Need to filter out variants of bases in other series, which
            # are considered "base issues" with respect to this series.
            counts['issues'] = self.active_base_issues() \
                                   .filter(variant_of=None).count()
            counts['variant issues'] = self.active_non_base_variants().count()
            counts['issue indexes'] = self.active_indexed_issues().count()
        else:
            # Non comics publications do not count for global stats, but
            # for publisher series counts. But not for issue counts.
            # TODO correctly process this
            counts['publisher series'] = 1
        return counts

    def update_cached_counts(self, deltas, negate=False):
        """
        Updates the database fields that cache child object counts.

        Expects a deltas object in the form returned by stat_counts()
        methods, and also expected by CountStats.update_all_counts().

        In the case of series, there is only one local count (for issues).
        Note that we use 'series issues' rather than 'issues' for this
        count, because the series issue count tracks all non-variant issues,
        while all other issue counts ignore issues that are part of
        series that are not comics publications.
        """
        if negate:
            deltas = deltas.copy()
            for k, v in deltas.items():
                deltas[k] = -v

        # Don't apply F() if delta is 0, because we don't want
        # a lazy evaluation F-object result in a count field
        # if we don't absolutely need it.
        if deltas.get('series issues', 0):
            self.issue_count = F('issue_count') + deltas['series issues']

    def ordered_brands(self):
        """
        Provide information on publisher's brands in the order they first
        appear within the series.  Returned as a list so that the UI can check
        the length of the list and the contents with only one DB call.
        """
        return list(
          Brand.objects.filter(issue__series=self, issue__deleted=False)
          .annotate(first_by_brand=models.Min('issue__sort_code'),
                    used_issue_count=models.Count('issue'))
          .order_by('first_by_brand'))

    def brand_info_counts(self):
        """
        Simple method for the UI to use, as the UI can't pass parameters.
        """

        # There really should be a way to do this in one annotate clause, but I
        # can't figure it out and the ORM may just not do it. The SQL would be:
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
        return list(
          IndiciaPublisher.objects.filter(issue__series=self,
                                          issue__deleted=False)
          .annotate(first_by_ind_pub=models.Min('issue__sort_code'),
                    used_issue_count=models.Count('issue'))
          .order_by('first_by_ind_pub'))

    def indicia_publisher_info_counts(self):
        """
        Simple method for the UI to use.  Called _counts (plural) for symmetry
        with brand_info_counts which actually does return two counts.
        """
        return {
            'unknown': self.active_issues()
                           .filter(indicia_publisher__isnull=True).count(),
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
        if self.id:
            return urlresolvers.reverse(
                'show_series',
                kwargs={'series_id': self.id})
        else:
            return ''

    def marked_scans_count(self):
        return Cover.objects.filter(issue__series=self, marked=True).count()

    @cached_property
    def scan_count(self):
        return Cover.objects.filter(issue__series=self, deleted=False).count()

    def issues_without_covers(self):
        issues = Issue.objects.filter(series=self).exclude(deleted=True)
        return issues.exclude(cover__isnull=False, cover__deleted=False)\
                     .distinct()

    @cached_property
    def scan_needed_count(self):
        return self.issues_without_covers().count() + self.marked_scans_count()

    @cached_property
    def issue_indexed_count(self):
        return self.active_base_issues()\
                   .exclude(is_indexed=INDEXED['skeleton']).count()

    @cached_property
    def issues_to_migrate(self):
        stories = Story.objects.exclude(Q(script='')
                                        | Q(script__startswith='?'),
                                        Q(pencils='')
                                        | Q(pencils__startswith='?')
                                        | Q(pencils__startswith='various'),
                                        Q(inks='') | Q(inks__startswith='?')
                                        | Q(inks__startswith='various'),
                                        Q(colors='')
                                        | Q(colors__startswith='?')
                                        | Q(colors__startswith='various'),)\
                                        .filter(issue__series__id=self.id)\
                                        .exclude(type__in=AD_TYPES)\
                                        .filter(deleted=False)
        issues = self.active_issues().filter(id__in=set(stories.values_list(
                                                        'issue', flat=True)))
        return issues

    def _date_uncertain(self, flag):
        return ' ?' if flag else ''

    def display_publication_dates(self):
        if not self.issue_count:
            return '%s%s' % (str(self.year_began),
                             self._date_uncertain(self.year_began_uncertain))
        elif self.issue_count == 1:
            if self.first_issue.publication_date:
                return self.first_issue.publication_date
            else:
                return '%s%s' % (str(self.year_began),
                                 self._date_uncertain(
                                   self.year_began_uncertain))
        else:
            if self.first_issue.publication_date:
                date = '%s - ' % self.first_issue.publication_date
            else:
                date = '%s%s - ' % (self.year_began,
                                    self._date_uncertain(
                                      self.year_began_uncertain))
            if self.is_current:
                date += 'present'
            elif self.last_issue.publication_date:
                date += self.last_issue.publication_date
            elif self.year_ended:
                date += '%s%s' % (str(self.year_ended),
                                  self._date_uncertain(
                                    self.year_ended_uncertain))
            else:
                date += '?'
            return date

    def search_result_name(self):
        if self.issue_count <= 1 and not self.is_current:
            date = '%s%s' % (str(self.year_began),
                             self._date_uncertain(self.year_began_uncertain))
        else:
            date = '%s%s - ' % (self.year_began,
                                self._date_uncertain(
                                  self.year_began_uncertain))
            if self.is_current:
                date += 'Present'
            elif self.year_ended:
                date += '%s%s' % (str(self.year_ended),
                                  self._date_uncertain(
                                    self.year_ended_uncertain))
            else:
                date += '?'

        if self.is_singleton:
            issues = ''
        else:
            issues = '%d issue%s in' % (self.issue_count,
                                        pluralize(self.issue_count))

        return '%s %s (%s) %s %s' % (self.name, self.short_pub_type(),
                                     self.publisher, issues, date)

    def short_pub_type(self):
        if self.publication_type:
            return '[' + self.publication_type.name[0] + ']'
        else:
            return ''

    def full_name(self):
        return '%s (%s, %s%s series)' % (self.name, self.publisher,
                                         self.year_began,
                                         self._date_uncertain(
                                           self.year_began_uncertain))

    def full_name_with_link(self, publisher=False):
        if publisher:
            name_link = '<a href="%s">%s</a> (<a href="%s">%s</a>,' \
                        ' %s%s series)' \
              % (self.get_absolute_url(), esc(self.name),
                 self.publisher.get_absolute_url(), self.publisher,
                 self.year_began,
                 self._date_uncertain(self.year_began_uncertain))
        else:
            name_link = '<a href="%s">%s</a>' % (self.get_absolute_url(),
                                                 esc(self.full_name()))
        return mark_safe(name_link)

    def cover_status_info(self):
        if not self.issue_count or not self.is_comics_publication:
            return "No Covers"
        else:
            gallery_url = urlresolvers.reverse("series_covers",
                                               kwargs={'series_id': self.id})
            table_url = urlresolvers.reverse("series_scan_table",
                                             kwargs={'series_id': self.id})
            if not self.scan_needed_count:
                return mark_safe('<a href="%s">Gallery</a>' % (gallery_url))
            elif self.has_gallery:
                return mark_safe(
                  '<a href="%s">Have %d</a> (<a href="%s">Need %d</a>)'
                  % (gallery_url,
                     self.scan_count,
                     table_url,
                     self.scan_needed_count))
            else:
                return mark_safe('<a href="%s">Add</a>' % (table_url))

    def __str__(self):
        return '%s (%s%s series)' % (self.name, self.year_began,
                                     self._date_uncertain(
                                       self.year_began_uncertain))


class CoversColumn(tables.Column):
    def render(self, record):
        return record.cover_status_info()

    def value(self, record):
        return record.scan_count


class PublishedColumn(tables.Column):
    def render(self, record):
        return record.display_publication_dates()


class NameColumn(tables.Column):
    def render(self, record):
        name_link = '<a href="%s">%s</a> %s' % (record.get_absolute_url(),
                                                esc(record.name),
                                                record.short_pub_type())
        return mark_safe(name_link)

    def order(self, QuerySet, is_descending):
        QuerySet = QuerySet.order_by(('-' if is_descending else '')
                                     + 'sort_name', 'year_began')
        return (QuerySet, True)


class SeriesTable(tables.Table):
    name = NameColumn(verbose_name='Series')
    year = tables.Column(accessor='year_began', verbose_name='Year')
    issue_count = tables.Column(attrs={'td': {'style': "text-align: right"}},
                                verbose_name='Issues',
                                initial_sort_descending=True)
    covers = CoversColumn(accessor='scan_count',
                          attrs={'td': {'style': "text-align: right"}},
                          initial_sort_descending=True)
    published = PublishedColumn(accessor='year_began',
                                attrs={'td': {'style': "text-align: right"}},
                                orderable=False,
                                verbose_name='Published')

    class Meta:
        model = Series
        fields = ('name', 'year', 'issue_count', 'covers', 'published')

    def order_covers(self, query_set, is_descending):
        query_set = query_set.annotate(
          covers=Count('issue__cover', filter=Q(issue__cover__deleted=False)))
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'covers',
                                       'sort_name',
                                       'year_began')
        return (query_set, True)

    def order_year(self, QuerySet, is_descending):
        QuerySet = QuerySet.order_by(('-' if is_descending else '')
                                     + 'year_began', 'sort_name')
        return (QuerySet, True)

    def order_issue_count(self, QuerySet, is_descending):
        QuerySet = QuerySet.order_by(('-' if is_descending else '')
                                     + 'issue_count', 'sort_name',
                                     'year_began')
        return (QuerySet, True)

    def render_issue_count(self, record):
        return '%d issues (%d indexed)' % (record.issue_count,
                                           record.issue_indexed_count)

    def value_name(self, value):
        return str(value)


class SeriesPublisherTable(SeriesTable):
    publisher = tables.Column(accessor='publisher',
                              verbose_name='Publisher')

    class Meta:
        model = Series
        fields = ('publisher', 'name', 'year', 'issue_count', 'covers',
                  'published')

    def order_publisher(self, query_set, is_descending):
        query_set = query_set.annotate(publisher_name=F('publisher__name'))
        query_set = query_set.annotate(series_name=F('sort_name'))
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'publisher_name',
                                       direction + 'series_name')
        return (query_set, True)

    def render_publisher(self, value):
        from apps.gcd.templatetags.display import absolute_url
        from apps.gcd.templatetags.credits import show_country_info
        display_publisher = "<img %s>" % (show_country_info(value.country))
        return mark_safe(display_publisher) + absolute_url(value)

    def value_publisher(self, value):
        return str(value)


class CreatorSeriesTable(SeriesTable):
    credits_count = tables.Column(accessor='issue_credits_count',
                                  verbose_name='Issues',
                                  initial_sort_descending=True)
    covers = None
    published = None
    first_credit = tables.Column(verbose_name='First Credit')
    issue_count = None
    role = tables.Column(accessor='script', orderable=False)

    def __init__(self, *args, **kwargs):
        self.creator = kwargs.pop('creator')
        self.resolve_name = 'creator'
        super(SeriesTable, self).__init__(*args, **kwargs)

    class Meta:
        model = Series
        fields = ('name', 'year', 'publisher', 'first_credit')

    def order_credits_count(self, QuerySet, is_descending):
        if is_descending:
            QuerySet = QuerySet.order_by('-issue_credits_count', 'sort_name',
                                         'year_began')
        else:
            QuerySet = QuerySet.order_by('issue_credits_count', 'sort_name',
                                         'year_began')
        return (QuerySet, True)

    def render_first_credit(self, value):
        return value[:4]

    def render_credits_count(self, record):
        url = urlresolvers.reverse(
                'creator_series_issues',
                kwargs={'series_id': record.id,
                        '%s_id' % self.resolve_name:
                        getattr(self, self.resolve_name).id})
        return mark_safe('<a href="%s">%s</a>' % (url,
                                                  record.issue_credits_count))

    def value_credits_count(self, record):
        return record.issue_credits_count

    def render_publisher(self, value):
        from apps.gcd.templatetags.display import absolute_url
        from apps.gcd.templatetags.credits import show_country_info
        display_publisher = "<img %s>" % (show_country_info(value.country))
        return mark_safe(display_publisher) + absolute_url(value)

    def value_publisher(self, value):
        return str(value)

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
