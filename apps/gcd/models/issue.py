# -*- coding: utf-8 -*-


from decimal import Decimal

from django.db import models, NotSupportedError
import django.urls as urlresolvers
from django.db.models import Sum, F
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

import django_tables2 as tables

from taggit.managers import TaggableManager

from .gcddata import GcdData
from .publisher import IndiciaPublisher, Brand, IndiciaPrinter
from .image import Image
from .story import StoryType, STORY_TYPES, CreditType
from .creator import CreatorNameDetail
from .award import ReceivedAward
from .datasource import ExternalLink

INDEXED = {
    'skeleton': 0,
    'full': 1,
    'partial': 2,
    'ten_percent': 3,
}

# 1: variant with cover artwork and cover image identical to base
# 2: variant with different scan, but cover artwork identical to base
# 3: variant with cover artwork different to base
VARIANT_COVER_STATUS = {
    1: 'No Difference',
    2: 'Only Scan Difference',
    3: 'Artwork Difference'
}


class VCS_Codes(models.IntegerChoices):
    NO_DIFFERENCE = 1
    ONLY_SCAN_DIFFERENCE = 2
    ARTWORK_DIFFERENCE = 3


def issue_descriptor(issue):
    if issue.number == '[nn]' and issue.series.is_singleton:
        return ''
    if issue.title and issue.series.has_issue_title:
        title = ' - ' + issue.title
    else:
        title = ''
    if issue.display_volume_with_number:
        if issue.volume_not_printed:
            volume = '[v%s]' % issue.volume
        else:
            volume = 'v%s' % issue.volume
        return '%s#%s%s' % (volume, issue.number, title)
    return issue.number + title


class CodeNumberType(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_code_number_type'
        ordering = ['name']

    name = models.CharField(max_length=50, db_index=True, unique=True)

    def __str__(self):
        return self.name


class PublisherCodeNumber(GcdData):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_issue_code_number'

    number = models.CharField(max_length=50, db_index=True)
    number_type = models.ForeignKey(CodeNumberType, on_delete=models.CASCADE)
    issue = models.ForeignKey('Issue', on_delete=models.CASCADE,
                              related_name='code_number')

    def __str__(self):
        return "%s: %s (%s)" % (self.issue, self.number,
                                self.number_type)


class IssueCredit(GcdData):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_issue_credit'

    creator = models.ForeignKey(CreatorNameDetail, on_delete=models.CASCADE)
    credit_type = models.ForeignKey(CreditType, on_delete=models.CASCADE)
    issue = models.ForeignKey('Issue', on_delete=models.CASCADE,
                              related_name='credits')

    is_credited = models.BooleanField(default=False, db_index=True)

    uncertain = models.BooleanField(default=False, db_index=True)

    credited_as = models.CharField(max_length=255)

    # record for a wider range of work types, or how it is credited
    credit_name = models.CharField(max_length=255)

    is_sourced = models.BooleanField(default=False, db_index=True)
    sourced_by = models.CharField(max_length=255)

    def __str__(self):
        return "%s: %s (%s)" % (self.issue, self.creator, self.credit_type)


class Issue(GcdData):
    class Meta:
        app_label = 'gcd'
        ordering = ['series', 'sort_code']
        unique_together = ('series', 'sort_code')

    # Issue identification
    number = models.CharField(max_length=50, db_index=True)
    title = models.CharField(max_length=255, db_index=True)
    no_title = models.BooleanField(default=False, db_index=True)
    volume = models.CharField(max_length=50, db_index=True)
    no_volume = models.BooleanField(default=False, db_index=True)
    volume_not_printed = models.BooleanField(default=False)
    display_volume_with_number = models.BooleanField(default=False,
                                                     db_index=True)
    isbn = models.CharField(max_length=32, db_index=True)
    no_isbn = models.BooleanField(default=False, db_index=True)
    valid_isbn = models.CharField(max_length=13, db_index=True)
    variant_of = models.ForeignKey('self', on_delete=models.CASCADE, null=True,
                                   related_name='variant_set')
    variant_name = models.CharField(max_length=255)
    variant_cover_status = models.IntegerField(choices=VCS_Codes.choices,
                                               default=3, db_index=True)
    barcode = models.CharField(max_length=38, db_index=True)
    no_barcode = models.BooleanField(default=False)
    rating = models.CharField(max_length=255, default='', db_index=True)
    no_rating = models.BooleanField(default=False, db_index=True)

    # Dates and sorting
    publication_date = models.CharField(max_length=255)
    key_date = models.CharField(max_length=10, db_index=True)
    on_sale_date = models.CharField(max_length=10, db_index=True)
    on_sale_date_uncertain = models.BooleanField(default=False)
    sort_code = models.IntegerField(db_index=True)
    indicia_frequency = models.CharField(max_length=255)
    no_indicia_frequency = models.BooleanField(default=False, db_index=True)

    # Price, page count and format fields
    price = models.CharField(max_length=255)
    page_count = models.DecimalField(max_digits=10, decimal_places=3,
                                     null=True)
    page_count_uncertain = models.BooleanField(default=False)

    editing = models.TextField()
    no_editing = models.BooleanField(default=False, db_index=True)
    notes = models.TextField()
    external_link = models.ManyToManyField(ExternalLink)

    keywords = TaggableManager()

    # Series and publisher links
    series = models.ForeignKey('Series', on_delete=models.CASCADE)
    indicia_publisher = models.ForeignKey(IndiciaPublisher,
                                          on_delete=models.CASCADE, null=True)
    indicia_pub_not_printed = models.BooleanField(default=False)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, null=True)
    no_brand = models.BooleanField(default=False, db_index=True)
    indicia_printer = models.ManyToManyField(IndiciaPrinter)
    no_indicia_printer = models.BooleanField(default=False)
    image_resources = GenericRelation(Image)

    awards = GenericRelation(ReceivedAward)

    # In production, this is a tinyint(1) because the set of numbers
    # is very small.  But syncdb produces an int(11).
    is_indexed = models.IntegerField(default=0, db_index=True)

    @property
    def indicia_image(self):
        img = Image.objects.filter(
          object_id=self.id,
          deleted=False,
          content_type=ContentType.objects.get_for_model(self),
          type__id=1)
        if img:
            return img.get()
        else:
            return None

    @property
    def soo_image(self):
        img = Image.objects.filter(
          object_id=self.id,
          deleted=False,
          content_type=ContentType.objects.get_for_model(self),
          type__id=2)
        if img:
            return img.get()
        else:
            return None

    @property
    def from_reprints(self):
        return self.from_all_reprints.filter(target=None)

    @property
    def from_story_reprints(self):
        return self.from_reprints.exclude(origin=None)

    @property
    def from_issue_reprints(self):
        return self.from_reprints.filter(origin=None)

    @property
    def to_reprints(self):
        return self.to_all_reprints.filter(origin=None)

    @property
    def to_story_reprints(self):
        return self.to_reprints.exclude(target=None)

    @property
    def to_issue_reprints(self):
        return self.to_reprints.filter(target=None)

    @property
    def active_credits(self):
        return self.credits.exclude(deleted=True)

    def active_stories(self):
        return self.story_set.exclude(deleted=True)

    def _active_variants(self):
        return self.variant_set.exclude(deleted=True)

    def active_variants(self):
        return self._active_variants()

    def active_awards(self):
        return self.awards.exclude(deleted=True)

    def active_printers(self):
        return self.indicia_printer.all()

    def active_code_numbers(self):
        return self.code_number.all()

    def get_cover_sequence(self):
        if not self.variant_of or self.variant_cover_status == 3:
            cover = self.active_stories().filter(type=STORY_TYPES['cover'])\
                        .prefetch_related('credits__creator__creator')
        else:
            cover = self.variant_of.active_stories()\
                        .filter(type=STORY_TYPES['cover'])\
                        .prefetch_related('credits__creator__creator')
        if cover:
            return cover[0]
        else:
            return None

    def shown_stories(self):
        """ returns cover sequence and story sequences """
        if self.variant_of:
            stories_from = self.variant_of
        else:
            stories_from = self
        stories = list(stories_from.active_stories()
                                   .order_by('sequence_number')
                                   .select_related('type', 'migration_status')
                                   .prefetch_related(
                                     'feature_object',
                                     'feature_logo__feature',
                                     'credits__creator__creator',
                                     'credits__creator__type'))
        cover_story = None
        if self.series.is_comics_publication or (
          self.series.has_about_comics is True and
          self.is_indexed == INDEXED['full']):
            if (len(stories) > 0) and stories[0].type_id == 6:
                cover_story = stories.pop(0)
            if self.variant_of:
                if self.variant_cover_status == 3:
                    if self.active_stories().count():
                        cover_story = self.active_stories()[0]
                    else:
                        cover_story = None
        return cover_story, stories

    def _active_covers(self):
        if self.can_have_cover():
            return self.cover_set.exclude(deleted=True)
        else:
            return self.cover_set.none()

    def active_covers(self, stats=False):
        # check for variant with no image difference
        if self.variant_of and self.variant_cover_status == 1 and not stats:
            return self.variant_of.active_covers()
        return self._active_covers()

    def variant_covers(self):
        """ returns the images from the variant issues """
        from .cover import Cover
        if self.variant_of:
            # check for variant with no image difference
            if self.variant_cover_status == 1:
                return self.variant_of.variant_covers()
            else:
                variant_issues = list(self.variant_of.active_variants()
                                          .exclude(id=self.id)
                                          .values_list('id', flat=True))
        else:
            variant_issues = list(self.active_variants()
                                      .values_list('id', flat=True))
        variant_covers = Cover.objects.filter(issue__id__in=variant_issues)\
                                      .exclude(deleted=True)
        if self.variant_of:
            variant_covers |= self.variant_of.active_covers()
        return variant_covers

    def shown_covers(self):
        return self.active_covers(), self.variant_covers()

    def show_printer(self):
        first = True
        printers = ''
        for printer in self.active_printers():
            if first:
                first = False
            else:
                printers += '; '
            printers += '<a href="%s">%s</a>' % (printer.get_absolute_url(),
                                                 esc(printer.name))
        return mark_safe(printers)

    def has_keywords(self):
        if self.series.is_singleton:
            return self.keywords.exists() or self.series.has_keywords()
        return self.keywords.exists()

    def has_content(self):
        """
        Simplifies UI checks for conditionals.  Content fields
        """
        return self.notes or \
            self.variant_of or \
            self.other_variants() or \
            self.has_keywords() or \
            self.has_reprints() or \
            self.active_awards().count()

    def has_covers(self):
        return self.can_have_cover() and self.active_covers().exists()

    def can_have_cover(self):
        if self.series.is_comics_publication:
            return True
        if self.is_indexed in [INDEXED['full'], INDEXED['ten_percent']]:
            return True
        else:
            return False

    def other_variants(self):
        if self.variant_of:
            variants = self.variant_of.active_variants().exclude(id=self.id)
        else:
            variants = self.active_variants()
        return list(variants)

    def _get_prev_next_issue(self):
        """
        Find the issues immediately before and after the given issue.
        """

        prev_issue = None
        next_issue = None

        earlier_issues = self.series.active_base_issues()\
                             .filter(sort_code__lt=self.sort_code)\
                             .exclude(id=self.variant_of_id)
        earlier_issues = earlier_issues.order_by('-sort_code')
        if earlier_issues:
            prev_issue = earlier_issues[0]

        later_issues = self.series.active_base_issues()\
                           .filter(sort_code__gt=self.sort_code)
        later_issues = later_issues.order_by('sort_code')
        if later_issues:
            next_issue = later_issues[0]

        return [prev_issue, next_issue]

    def get_prev_next_issue(self):
        return self._get_prev_next_issue()

    def has_reprints(self, ignore=STORY_TYPES['preview']):
        """Simplifies UI checks for conditionals, notes and reprint fields"""
        return self.from_reprints.count() or \
            self.to_reprints.exclude(target__type__id=ignore).count()

    def has_variants(self):
        return self.active_variants().exists()

    def has_dependents(self):
        # what about award_revisions ?
        has_non_story_deps = (
            self.has_variants() or
            self.has_reprints(ignore=None) or
            self.cover_revisions.active_set().exists() or
            self.variant_revisions.active_set().exists() or
            self.origin_reprint_revisions.active_set().exists() or
            self.target_reprint_revisions.active_set().exists())
        if has_non_story_deps:
            return True

        for story in self.active_stories():
            has_story_deps = (
                story.has_reprints(notes=False) or
                story.origin_reprint_revisions.active_set().exists() or
                story.target_reprint_revisions.active_set().exists())
            if has_story_deps:
                return True

        return False

    def can_upload_variants(self):
        if self.has_covers():
            currently_deleting = self.revisions.active_set() \
                                               .filter(deleted=True).exists()
            return not currently_deleting
        else:
            return False

    def set_indexed_status(self):
        """
        Sets the index status and returns the resulting stat change value.

        The return value of this method is intended for use in adjusting
        the "issue indexes" stat count.  GCD model modules cannot import
        CountStats and set them directly due to circular dependencies.
        """
        was_indexed = self.is_indexed

        if not self.variant_of:
            is_indexed = INDEXED['skeleton']
            if Decimal(self.page_count or 0) > 0:
                total_count = self.active_stories()\
                              .aggregate(Sum('page_count'))['page_count__sum']
                if total_count is None:
                    total_count = 0
                if (total_count > 0 and
                        total_count >= Decimal('0.4') * self.page_count):
                    is_indexed = INDEXED['full']
                elif (total_count > 0 and
                        total_count >= Decimal('0.1') * self.page_count):
                    is_indexed = INDEXED['ten_percent']

            if (is_indexed not in [INDEXED['full'], INDEXED['ten_percent']] and
                self.active_stories()
                    .filter(type=StoryType.objects.get(name='comic story'))
                    .exists()):
                is_indexed = INDEXED['partial']

            if is_indexed == INDEXED['full']:
                if self.page_count_uncertain or self.active_stories()\
                       .filter(page_count_uncertain=True).exists():
                    is_indexed = INDEXED['partial']

            if self.is_indexed != is_indexed:
                self.is_indexed = is_indexed
                self.save()
                if self.active_variants():
                    for variant in self.active_variants():
                        variant.is_indexed = is_indexed
                        variant.save()

        index_delta = 0
        if self.series.is_comics_publication:
            if not was_indexed and self.is_indexed:
                index_delta = 1
            elif was_indexed and not self.is_indexed:
                index_delta = -1
        return index_delta

    _update_stats = True

    def stat_counts(self):
        """
        Returns all count values relevant to this issue.

        Includes counts for the issue itself.

        Non-comics publications return statistics only for stories and covers,
        as non-comics issues do not count towards stats.

        Note that we have a special value "series issues", because non-variant
        issues are counted differently with respect to series than in general.
        A series always counts its own non-variant issues, even when the series
        is not a comics publication.
        """
        if self.deleted:
            return {}

        counts = {
            'stories': self.active_stories().count(),
            'covers': self.active_covers(stats=True).count(),
        }

        if not self.variant_of_id:
            counts['series issues'] = 1

        if self.series.is_comics_publication:
            if self.variant_of_id:
                counts['variant issues'] = 1
            else:
                counts['issues'] = 1
                if self.is_indexed != INDEXED['skeleton']:
                    counts['issue indexes'] = 1
        return counts

    def get_absolute_url(self):
        return urlresolvers.reverse(
            'show_issue',
            kwargs={'issue_id': self.id})

    @property
    def full_descriptor(self):
        if self.variant_name:
            return "%s [%s]" % (self.issue_descriptor, self.variant_name)
        if self.active_code_numbers().filter(number_type__id=1):
            return "%s (%s)" % (self.issue_descriptor,
                                self.active_code_numbers()
                                .get(number_type__id=1).number)
        return self.issue_descriptor

    @property
    def issue_descriptor(self):
        return issue_descriptor(self)

    @property
    def display_full_descriptor(self):
        number = self.full_descriptor
        if number:
            return '#' + number
        else:
            return ''

    @property
    def display_number(self):
        number = self.issue_descriptor
        if number:
            return '#' + number
        else:
            return ''

    def full_name(self, variant_name=True):
        if variant_name and self.variant_name:
            return '%s %s [%s]' % (self.series.full_name(),
                                   self.display_number,
                                   self.variant_name)
        if self.active_code_numbers().filter(number_type__id=1):
            return "%s %s (%s)" % (
              self.series.full_name(),
              self.display_number,
              self.active_code_numbers().get(number_type__id=1).number)
        return '%s %s' % (self.series.full_name(), self.display_number)

    def full_name_with_link(self, publisher=False):
        name_link = self.series.full_name_with_link(publisher)
        return mark_safe('%s <a href="%s">%s</a>' % (name_link,
                                                     self.get_absolute_url(),
                                                     esc(self.display_number)))

    def show_series_and_issue_link(self):
        if self.display_number:
            issue_number = '%s' % (esc(self.display_number))
        else:
            issue_number = ''
        if self.variant_name:
            issue_number = '%s [%s]' % (issue_number, esc(self.variant_name))
        if issue_number:
            issue_number = '<a href="%s">%s</a>' % (self.get_absolute_url(),
                                                    issue_number)
        return mark_safe('<a href="%s">%s</a> (%s series) %s' %
                         (self.series.get_absolute_url(),
                          esc(self.series.name),
                          esc(self.series.year_began),
                          issue_number))

    def short_name(self):
        if self.variant_name:
            return '%s %s [%s]' % (self.series.name,
                                   self.display_number,
                                   self.variant_name)
        else:
            return '%s %s' % (self.series.name, self.display_number)

    def __str__(self):
        if self.variant_name:
            return '%s %s [%s]' % (self.series, self.display_number,
                                   self.variant_name)
        else:
            return '%s %s' % (self.series, self.display_number)

##############################################################################
# Tables with Sorting
##############################################################################


class IssueColumn(tables.TemplateColumn):
    def value(self, record):
        return str(record)

    def order(self, query_set, is_descending):
        try:
            query_set = query_set.annotate(series_name=F('series__sort_name'))
        except NotSupportedError:
            # it fails for joined querysets, but there we did the annotation
            # beforehand !
            pass
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'series_name',
                                       'series__year_began',
                                       'series__id',
                                       direction + 'sort_code')
        return (query_set, True)


class IssueTable(tables.Table):
    issue = IssueColumn(accessor='id', verbose_name='Issue',
                        template_name='gcd/bits/sortable_issue_entry.html',
                        )
    publication_date = tables.Column(verbose_name='Publication Date')
    on_sale_date = tables.Column(verbose_name='On-sale Date')

    class Meta:
        model = Issue
        fields = ('issue', 'publication_date', 'on_sale_date')
        attrs = {'th': {'class': "non_visited"}}

    def order_publication_date(self, query_set, is_descending):
        try:
            query_set = query_set.annotate(series_name=F('series__sort_name'))
        except NotSupportedError:
            # it fails for joined querysets, but there we did the annotation
            # beforehand !
            pass
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'key_date',
                                       direction + 'series_name',
                                       direction + 'sort_code')
        return (query_set, True)

    def order_on_sale_date(self, query_set, is_descending):
        try:
            query_set = query_set.annotate(series_name=F('series__sort_name'))
        except NotSupportedError:
            # it fails for joined querysets, but there we did the annotation
            # beforehand !
            pass
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'on_sale_date',
                                       direction + 'key_date',
                                       direction + 'series_name',
                                       direction + 'sort_code')
        return (query_set, True)


class IssuePublisherTable(IssueTable):
    publisher = tables.Column(accessor='series__publisher',
                              verbose_name='Publisher')

    class Meta:
        model = Issue
        fields = ('publisher', 'issue', 'publication_date', 'on_sale_date')
        attrs = {'th': {'class': "non_visited"}}

    def order_publisher(self, query_set, is_descending):
        try:
            query_set = query_set.annotate(
              publisher_name=F('series__publisher__name'))
            query_set = query_set.annotate(series_name=F('series__sort_name'))
        except NotSupportedError:
            # it fails for joined querysets, but there we did the annotation
            # beforehand !
            pass
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'publisher_name',
                                       direction + 'series_name',
                                       direction + 'sort_code')
        return (query_set, True)

    def render_publisher(self, value):
        from apps.gcd.templatetags.display import absolute_url
        from apps.gcd.templatetags.credits import show_country_info
        display_publisher = "<img %s>" % (show_country_info(value.country))
        return mark_safe(display_publisher) + absolute_url(value)

    def value_publisher(self, value):
        return str(value)


class IndiciaPublisherIssueTable(IssueTable):
    brand = tables.Column(accessor='brand',
                          verbose_name='Brand')

    class Meta:
        model = Issue
        fields = ('issue', 'publication_date', 'on_sale_date', 'brand')
        attrs = {'th': {'class': "non_visited"}}

    def order_brand(self, query_set, is_descending):
        query_set = query_set.annotate(series_name=F('series__sort_name'))
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'brand__name',
                                       direction + 'series_name',
                                       direction + 'sort_code')
        return (query_set, True)

    def render_brand(self, value):
        from apps.gcd.templatetags.display import absolute_url
        return absolute_url(value)

    def value_brand(self, value):
        return str(value)


class BrandEmblemIssueTable(IssueTable):
    indicia_publisher = tables.Column(accessor='indicia_publisher',
                                      verbose_name='Indicia Publisher',
                                      empty_values=())

    class Meta:
        model = Issue
        fields = ('issue', 'publication_date', 'on_sale_date',
                  'indicia_publisher')
        attrs = {'th': {'class': "non_visited"}}

    def order_indicia_publisher(self, query_set, is_descending):
        query_set = query_set.annotate(series_name=F('series__sort_name'))
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'indicia_publisher',
                                       direction + 'series_name',
                                       direction + 'sort_code')
        return (query_set, True)

    def render_indicia_publisher(self, record):
        from apps.gcd.templatetags.display import absolute_url,\
                                                  show_indicia_pub
        from apps.gcd.templatetags.credits import get_country_flag
        return_val = show_indicia_pub(record)
        if record.series.publisher_id not in record.brand.group_parents():
            return_val += " (%s%s)" % (get_country_flag(record.series.publisher
                                                                     .country),
                                       absolute_url(record.series.publisher))
        return mark_safe(return_val)

    def value_indicia_publisher(self, value):
        return str(value)


class BrandGroupIssueTable(IndiciaPublisherIssueTable, BrandEmblemIssueTable):
    def __init__(self, *args, **kwargs):
        self.brand = kwargs.pop('brand')
        super(BrandEmblemIssueTable, self).__init__(*args, **kwargs)

    def render_indicia_publisher(self, record):
        from apps.gcd.templatetags.display import absolute_url,\
                                                  show_indicia_pub
        from apps.gcd.templatetags.credits import get_country_flag
        return_val = show_indicia_pub(record)
        if record.series.publisher != self.brand.parent:
            return_val += " (%s%s)" % (get_country_flag(record.series.publisher
                                                                     .country),
                                       absolute_url(record.series.publisher))
        return mark_safe(return_val)

    def value_indicia_publisher(self, value):
        return str(value)


class PublisherIssueTable(IndiciaPublisherIssueTable, BrandEmblemIssueTable):
    def render_indicia_publisher(self, record):
        from apps.gcd.templatetags.display import show_indicia_pub
        return_val = show_indicia_pub(record)
        return mark_safe(return_val)

    def value_indicia_publisher(self, value):
        return str(value)
