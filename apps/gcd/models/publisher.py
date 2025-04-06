# -*- coding: utf-8 -*-


from django.db import models
from django.conf import settings
from django.db.models import F
import django.urls as urlresolvers
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation
from django.utils.safestring import mark_safe

from taggit.managers import TaggableManager
import django_tables2 as tables

from apps.oi import states
from apps.stddata.models import Country
from .gcddata import GcdData, GcdLink
from .image import Image
from .support_tables import render_publisher, TW_COLUMN_ALIGN_RIGHT


def _display_year(year, flag):
    if year:
        return str(year) + (' ?' if flag else '')
    else:
        return '?'


class BasePublisher(GcdData):
    class Meta:
        abstract = True

    # Core publisher fields.
    name = models.CharField(max_length=255, db_index=True)
    year_began = models.IntegerField(db_index=True, null=True)
    year_ended = models.IntegerField(null=True)
    year_began_uncertain = models.BooleanField(default=False, db_index=True)
    year_ended_uncertain = models.BooleanField(default=False, db_index=True)
    year_overall_began = models.IntegerField(db_index=True, null=True)
    year_overall_ended = models.IntegerField(null=True)
    year_overall_began_uncertain = models.BooleanField(default=False,
                                                       db_index=True)
    year_overall_ended_uncertain = models.BooleanField(default=False,
                                                       db_index=True)
    notes = models.TextField()
    keywords = TaggableManager()
    url = models.URLField(max_length=255, blank=True, default='')

    def update_cached_counts(self, deltas, negate=False):
        """
        Updates the database fields that cache child object counts.

        Expects a deltas object in the form returned by stat_counts()
        methods, and also expected by CountStats.update_all_counts().

        Most classes derived from this base class only have an issue
        count, so a default implementation is provided here.
        """
        if negate:
            deltas = deltas.copy()
            for k, v in deltas.items():
                deltas[k] = -v

        # TODO: Reconsider use of F() objects due to undesired behavior
        #       if multiple F() objects are used on a field before saving.
        #
        # Don't apply F() if delta is 0, because we don't want
        # a lazy evaluation F-object result in a count field
        # if we don't absolutely need it.
        if deltas.get('issues', 0):
            self.issue_count = F('issue_count') + deltas['issues']

    def full_name(self):
        return str(self)

    def __str__(self):
        return self.name


class Publisher(BasePublisher):
    class Meta:
        ordering = ['name']
        app_label = 'gcd'

    country = models.ForeignKey(Country, on_delete=models.CASCADE)

    # Cached counts.
    brand_count = models.IntegerField(default=0, db_index=True)
    indicia_publisher_count = models.IntegerField(default=0, db_index=True)
    series_count = models.IntegerField(default=0)
    issue_count = models.IntegerField(default=0)

    def active_brand_groups(self):
        return self.brandgroup_set.exclude(deleted=True)

    # BrandGroups are used like Brands used to be in the display
    def active_brands(self):
        return self.active_brand_groups()

    def active_brand_emblems(self):
        return Brand.objects.filter(in_use__publisher=self, deleted=False)

    def active_indicia_publishers(self):
        return self.indiciapublisher_set.exclude(deleted=True)

    def active_series(self):
        return self.series_set.exclude(deleted=True)

    def has_dependents(self):
        return bool(self.series_count or
                    self.issue_count or
                    self.brand_count or
                    self.active_brands().exists() or
                    self.brand_group_revisions.active_set().exists() or
                    self.brand_use_revisions.active_set().exists() or
                    self.indicia_publisher_revisions.active_set().exists() or
                    self.series_revisions.active_set().exists())

    def update_cached_counts(self, deltas, negate=False):
        """
        Updates the database fields that cache child object counts.

        Expects a deltas object in the form returned by stat_counts()
        methods, and also expected by CountStats.update_all_counts().
        """
        if negate:
            deltas = deltas.copy()
            for k, v in deltas.items():
                deltas[k] = -v

        # Don't apply F() if delta is 0, because we don't want
        # a lazy evaluation F-object result in a count field
        # if we don't absolutely need it.
        if deltas.get('brands', 0):
            self.brand_count = F('brand_count') + deltas['brands']
        if deltas.get('indicia publishers', 0):
            self.indicia_publisher_count = (F('indicia_publisher_count') +
                                            deltas['indicia publishers'])
        if deltas.get('series', 0):
            self.series_count = F('series_count') + deltas['series']
        # special case for non-comics publications,
        # counts for publisher series, but not for stats
        if deltas.get('publisher series', 0):
            self.series_count = F('series_count') + deltas['publisher series']
        if deltas.get('issues', 0):
            self.issue_count = F('issue_count') + deltas['issues']

    _update_stats = True

    def stat_counts(self):
        """
        Returns all count values relevant to this publisher.

        Includes a count for the publisher itself.
        """
        if self.deleted:
            return {}

        return {'publishers': 1}

    def get_absolute_url(self):
        return urlresolvers.reverse(
            'show_publisher',
            kwargs={'publisher_id': self.id})

    ############################
    # TODO related to OI functionality, to be re-factored

    def active_brand_emblems_no_pending(self):
        """
        Active brands, not including those with pending deletes.
        Used in some cases where we don't want someone to add to a brand
        that is in the process of being deleted.
        """
        # TODO: check for pending brand_use deletes
        return self.active_brand_emblems().exclude(
          revisions__deleted=True,
          revisions__changeset__state__in=states.ACTIVE).distinct()

    def active_indicia_publishers_no_pending(self):
        """
        Active indicia publishers, not including those with pending deletes.
        Used in some cases where we don't want someone to add to an ind pub
        that is in the process of being deleted.
        """
        return self.active_indicia_publishers().exclude(
          revisions__deleted=True,
          revisions__changeset__state__in=states.ACTIVE)


class IndiciaPublisher(BasePublisher):
    class Meta:
        db_table = 'gcd_indicia_publisher'
        ordering = ['name']
        app_label = 'gcd'

    parent = models.ForeignKey(Publisher, on_delete=models.CASCADE)
    is_surrogate = models.BooleanField(default=False, db_index=True)
    country = models.ForeignKey(Country, on_delete=models.CASCADE)

    issue_count = models.IntegerField(default=0)

    def has_dependents(self):
        return bool(self.issue_count or
                    self.issue_revisions.active_set().exists())

    def active_issues(self):
        return self.issue_set.exclude(deleted=True)

    def stat_counts(self):
        """
        Returns all count values relevant to this indicia publisher.

        Includes a count for the indicia publisher itself.
        """
        if self.deleted:
            return {}

        return {'indicia publishers': 1}

    def object_page_name(self):
        parent_url = self.parent.get_absolute_url()
        return mark_safe('<a href="%s">%s</a> : %s' % (parent_url,
                                                       self.parent.name,
                                                       self.name))

    def get_absolute_url(self):
        return urlresolvers.reverse(
            'show_indicia_publisher',
            kwargs={'indicia_publisher_id': self.id})


class BrandGroup(BasePublisher):
    class Meta:
        db_table = 'gcd_brand_group'
        ordering = ['name']
        app_label = 'gcd'

    parent = models.ForeignKey(Publisher, on_delete=models.CASCADE)

    issue_count = models.IntegerField(default=0)

    def has_dependents(self):
        return bool(self.issue_count or
                    self.active_emblems().exists() or
                    self.brand_revisions.active_set().exists())

    def active_emblems(self):
        return self.brand_set.exclude(deleted=True)

    def active_issues(self):
        from apps.gcd.models.issue import Issue
        emblems_id = list(self.active_emblems().values_list('id', flat=True))
        return Issue.objects.filter(brand__in=emblems_id,
                                    deleted=False)

    def stat_counts(self):
        """
        Returns all count values relevant to this brand group.

        Includes a count for the brand group itself.
        """
        if self.deleted:
            return {}

        return {'brands': 1}

    def object_markdown_name(self):
        return '%s : %s' % (self.parent.name, self.name)

    def object_page_name(self):
        parent_url = self.parent.get_absolute_url()
        return mark_safe('<a href="%s">%s</a> : %s' % (parent_url,
                                                       self.parent.name,
                                                       self.name))

    def get_absolute_url(self):
        return urlresolvers.reverse(
            'show_brand_group',
            kwargs={'brand_group_id': self.id})


class Brand(BasePublisher):
    class Meta:
        ordering = ['name']
        app_label = 'gcd'

    group = models.ManyToManyField(BrandGroup, blank=True,
                                   db_table='gcd_brand_emblem_group')
    issue_count = models.IntegerField(default=0)
    generic = models.BooleanField(default=False)
    image_resources = GenericRelation(Image)

    @property
    def emblem(self):
        img = Image.objects.filter(
          object_id=self.id, deleted=False,
          content_type=ContentType.objects.get_for_model(self), type__id=3)
        if img:
            return img.get()
        else:
            return None

    def has_dependents(self):
        return bool(self.issue_count or
                    self.use_revisions.active_set().exists() or
                    self.issue_revisions.active_set().exists())

    def active_issues(self):
        return self.issue_set.exclude(deleted=True)

    def group_parents(self):
        return self.group.values_list('parent', flat=True)

    def stat_counts(self):
        """
        Returns all count values relevant to this brand emblem.

        Brand emblems themselves are not currently counted.
        """
        if self.deleted:
            return {}

        return {'issues': self.issue_count}

    def get_absolute_url(self):
        return urlresolvers.reverse('show_brand',
                                    kwargs={'brand_id': self.id})

    def __str__(self):
        if self.generic:
            return "%s [generic]" % self.name
        return self.name


class BrandUse(GcdLink):
    class Meta:
        db_table = 'gcd_brand_use'
        app_label = 'gcd'
        ordering = ['emblem__name', 'year_began']

    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE)
    emblem = models.ForeignKey(Brand, on_delete=models.CASCADE,
                               related_name='in_use')

    year_began = models.IntegerField(db_index=True, null=True)
    year_ended = models.IntegerField(null=True)
    year_began_uncertain = models.BooleanField(default=False, db_index=True)
    year_ended_uncertain = models.BooleanField(default=False, db_index=True)

    notes = models.TextField()

    @property
    def deleted(self):
        return False

    def active_issues(self):
        return self.emblem.issue_set.exclude(deleted=True)\
          .filter(issue__series__publisher=self.publisher)

    def get_absolute_url(self):
        return urlresolvers.reverse('show_brand',
                                    kwargs={'brand_id': self.emblem.id})

    def __str__(self):
        return 'emblem %s was used from %s to %s by %s.' % (
          self.emblem,
          _display_year(self.year_began, self.year_began_uncertain),
          _display_year(self.year_ended, self.year_ended_uncertain),
          self.publisher)


class Printer(BasePublisher):
    class Meta:
        ordering = ['name']
        app_label = 'gcd'

    country = models.ForeignKey(Country, on_delete=models.CASCADE)

    # Cached counts.
    indicia_printer_count = models.IntegerField(default=0, db_index=True)
    issue_count = models.IntegerField(default=0)

    def active_indicia_printers(self):
        return self.indiciaprinter_set.exclude(deleted=True)

    def has_dependents(self):
        return bool(self.issue_count or
                    self.indicia_printer_revisions.active_set().exists())

    def update_cached_counts(self, deltas, negate=False):
        """
        Updates the database fields that cache child object counts.

        Expects a deltas object in the form returned by stat_counts()
        methods, and also expected by CountStats.update_all_counts().
        """
        if negate:
            deltas = deltas.copy()
            for k, v in deltas.items():
                deltas[k] = -v

        # Don't apply F() if delta is 0, because we don't want
        # a lazy evaluation F-object result in a count field
        # if we don't absolutely need it.
        if deltas.get('indicia printers', 0):
            self.indicia_printer_count = (F('indicia_printer_count') +
                                          deltas['indicia printers'])
        if deltas.get('issues', 0):
            self.issue_count = F('issue_count') + deltas['issues']

    def show_issue_count(self):
        from .issue import Issue
        return Issue.objects.filter(indicia_printer__parent=self,
                                    deleted=False).count()

    def get_absolute_url(self):
        return urlresolvers.reverse('show_printer',
                                    kwargs={'printer_id': self.id})


class IndiciaPrinter(BasePublisher):
    class Meta:
        db_table = 'gcd_indicia_printer'
        ordering = ['name']
        app_label = 'gcd'

    parent = models.ForeignKey(Printer, on_delete=models.CASCADE)
    country = models.ForeignKey(Country, on_delete=models.CASCADE)

    issue_count = models.IntegerField(default=0)

    def has_dependents(self):
        return bool(self.issue_count or
                    self.issue_revisions.active_set().exists())

    def active_issues(self):
        return self.issue_set.exclude(deleted=True)

    def update_cached_counts(self, deltas, negate=False):
        """
        Updates the database fields that cache child object counts.

        Expects a deltas object in the form returned by stat_counts()
        methods, and also expected by CountStats.update_all_counts().
        """
        if negate:
            deltas = deltas.copy()
            for k, v in deltas.items():
                deltas[k] = -v

        # Don't apply F() if delta is 0, because we don't want
        # a lazy evaluation F-object result in a count field
        # if we don't absolutely need it.
        if deltas.get('issues', 0):
            self.issue_count = F('issue_count') + deltas['issues']

        if deltas.get('issues', 0):
            self.parent.issue_count = F('issue_count') + deltas['issues']
            self.parent.save()

    def object_page_name(self):
        parent_url = self.parent.get_absolute_url()
        return mark_safe('<a href="%s">%s</a> : %s' % (parent_url,
                                                       self.parent.name,
                                                       self.name))

    def get_absolute_url(self):
        return urlresolvers.reverse(
          'show_indicia_printer', kwargs={'indicia_printer_id': self.id})


class PublisherBaseTable(tables.Table):
    name = tables.Column()
    year_began = tables.Column(verbose_name='Began')
    year_ended = tables.Column(verbose_name='Ended')
    issue_count = tables.Column(verbose_name='Issues',
                                initial_sort_descending=True,
                                attrs={'td': {'class':
                                              TW_COLUMN_ALIGN_RIGHT}})

    def order_name(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'name',
                                       'year_began',)
        return (query_set, True)

    def order_issue_count(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'issue_count',
                                       'name',
                                       'year_began',)
        return (query_set, True)

    def render_name(self, record):
        return render_publisher(record)

    def render_issue_count(self, value, record):
        return mark_safe('<a href="%sissues/">%d</a>' %
                         (record.get_absolute_url(), value))


class PublisherSearchTable(PublisherBaseTable):
    name = tables.Column(verbose_name='Publisher')
    series_count = tables.Column(verbose_name='Series',
                                 initial_sort_descending=True,
                                 attrs={'td': {'class':
                                               TW_COLUMN_ALIGN_RIGHT}})
    brand_count = tables.Column(verbose_name='Brands',
                                initial_sort_descending=True,
                                attrs={'td': {'class':
                                              TW_COLUMN_ALIGN_RIGHT}})
    indicia_publisher_count = tables.Column(
      verbose_name='Indicia / Colophon Publishers',
      initial_sort_descending=True,
      attrs={'td': {'class':
                    TW_COLUMN_ALIGN_RIGHT}})

    def render_brand_count(self, value, record):
        return mark_safe('<a href="%sbrands/">%d</a>' %
                         (record.get_absolute_url(), value))

    def render_indicia_publisher_count(self, value, record):
        return mark_safe('<a href="%sindicia_publishers/">%d</a>' %
                         (record.get_absolute_url(), value))

    def render_series_count(self, value, record):
        return mark_safe('<a href="%s">%d</a>' %
                         (record.get_absolute_url(), value))


class IndiciaPublisherSearchTable(PublisherBaseTable):
    name = tables.Column(verbose_name='Indicia / Colophon Publisher')
    parent = tables.Column(verbose_name='Parent Publisher')

    class Meta:
        fields = ('name', 'parent', 'year_began', 'year_ended', 'issue_count')

    def render_issue_count(self, value, record):
        return mark_safe('<a href="%s">%d</a>' %
                         (record.get_absolute_url(), value))

    def render_parent(self, value):
        return render_publisher(value)


class IndiciaPublisherPublisherTable(IndiciaPublisherSearchTable):
    parent = None
    surrogate = tables.Column(accessor='is_surrogate',
                              verbose_name='Surrogate',
                              empty_values=(False,))

    class Meta:
        fields = ('name', 'year_began', 'year_ended', 'surrogate',
                  'issue_count')

    def render_surrogate(self, value):
        return 'Yes' if value else ''


class BrandGroupSearchTable(IndiciaPublisherSearchTable):
    name = tables.Column(verbose_name="Publisher's Brand Group")

    class Meta:
        fields = ('name', 'parent', 'year_began', 'year_ended', 'issue_count')

    def render_name(self, value, record):
        return mark_safe('<a href="%s">%s</a>' %
                         (record.get_absolute_url(), value))


class BrandGroupEmblemTable(BrandGroupSearchTable):
    notes = tables.Column(orderable=False)


class BrandGroupPublisherTable(BrandGroupSearchTable):
    parent = None
    emblem_count = tables.Column(accessor='brand_emblem_count',
                                 verbose_name='Brand Emblems',
                                 initial_sort_descending=True,
                                 attrs={'td': {'class':
                                               TW_COLUMN_ALIGN_RIGHT}})

    class Meta:
        fields = ('name', 'year_began', 'year_ended', 'emblem_count',
                  'issue_count')

    def render_emblem_count(self, value, record):
        return mark_safe('<a href="%s">%s</a>' %
                         (record.get_absolute_url(), value))


class BrandEmblemSearchTable(PublisherBaseTable):
    name = tables.Column(verbose_name="Publisher's Brand Emblem")
    group = tables.Column(verbose_name="Publisher's Brand Group(s)",
                          orderable=False)
    emblem = tables.Column(verbose_name="Emblem", orderable=False)

    class Meta:
        fields = ('emblem', 'name', 'group', 'year_began', 'year_ended',
                  'issue_count')

    def render_group(self, value):
        return_value = ''
        for group in value.all():
            return_value += '<a href="%s">%s</a>' % (
              group.get_absolute_url(), group)
            return_value += ' (%s); ' % render_publisher(group.parent)
        return_value = return_value[:-2]
        return mark_safe(return_value)

    def render_emblem(self, value, record):
        if not settings.FAKE_IMAGES and value:
            return mark_safe(
              f'<a href="{record.get_absolute_url()}">'
              f'<img src="{value.thumbnail.url}"></a>')
        return ''

    def render_issue_count(self, value, record):
        return mark_safe('<a href="%s">%d</a>' %
                         (record.get_absolute_url(), value))

    def render_name(self, value, record):
        return mark_safe('<a href="%s">%s</a>' %
                         (record.get_absolute_url(), value))


class BrandEmblemPublisherTable(BrandEmblemSearchTable):
    name = tables.Column(accessor='emblem__name',
                         verbose_name="Publisher's Brand Emblem")
    group = tables.Column(accessor='emblem__group',
                          verbose_name="Publisher's Brand Group(s)",
                          orderable=False)
    notes = tables.Column(orderable=False)
    emblem = tables.Column(accessor='emblem__emblem',
                           verbose_name="Emblem",
                           orderable=False)

    class Meta:
        fields = ('emblem', 'name', 'group', 'year_began', 'year_ended',)

    def order_name(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'emblem__name',
                                       'year_began',)
        return (query_set, True)

    def order_issue_count(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'issue_count',
                                       'emblem__name',
                                       'year_began',)
        return (query_set, True)

    def render_group(self, value, record):
        return_value = ''
        for group in value.all():
            return_value += '<a href="%s">%s</a>' % (
              group.get_absolute_url(), group)
            if group.parent != record.publisher:
                return_value += ' (%s); ' % render_publisher(group.parent)
            else:
                return_value += '; '
        return_value = return_value[:-2]
        return mark_safe(return_value)


class BrandEmblemGroupTable(BrandEmblemSearchTable):
    group = None
    notes = tables.Column(orderable=False)

    class Meta:
        fields = ('emblem', 'name', 'year_began', 'year_ended', 'issue_count',
                  'notes')

    def render_name(self, value, record):
        return mark_safe('<a href="%s">%s</a>' %
                         (record.get_absolute_url(), value))


class PrinterSearchTable(PublisherBaseTable):
    pass
