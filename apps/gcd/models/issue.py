# -*- coding: utf-8 -*-
from decimal import Decimal

from django.db import models
from django.core import urlresolvers
from django.db.models import Sum, Count
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from taggit.managers import TaggableManager

from publisher import IndiciaPublisher, Brand
from series import Series
from image import Image

# TODO: should not be importing oi app into gcd app, dependency should be
# the other way around.  Probably.
from apps.oi import states

INDEXED = {
    'skeleton': 0,
    'full': 1,
    'partial': 2,
    'ten_percent': 3,
}

def issue_descriptor(issue):
    if issue.number == '[nn]' and issue.series.is_singleton:
        return u''
    if issue.title and issue.series.has_issue_title:
        title = u' - ' + issue.title
    else:
        title = u''
    if issue.display_volume_with_number:
        if issue.volume_not_printed:
            volume = u'[v%s]' % issue.volume
        else:
            volume = u'v%s' % issue.volume
        return u'%s#%s%s' % (volume, issue.number, title)
    return issue.number + title

class Issue(models.Model):
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
    display_volume_with_number = models.BooleanField(default=False, db_index=True)
    isbn = models.CharField(max_length=32, db_index=True)
    no_isbn = models.BooleanField(default=False, db_index=True)
    valid_isbn = models.CharField(max_length=13, db_index=True)
    variant_of = models.ForeignKey('self', null=True,
                                   related_name='variant_set')
    variant_name = models.CharField(max_length=255)
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
    page_count = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    page_count_uncertain = models.BooleanField(default=False)

    editing = models.TextField()
    no_editing = models.BooleanField(default=False, db_index=True)
    notes = models.TextField()

    keywords = TaggableManager()

    # Series and publisher links
    series = models.ForeignKey(Series)
    indicia_publisher = models.ForeignKey(IndiciaPublisher, null=True)
    indicia_pub_not_printed = models.BooleanField(default=False)
    image_resources = GenericRelation(Image)

    @property
    def indicia_image(self):
        img = Image.objects.filter(object_id=self.id, deleted=False,
          content_type = ContentType.objects.get_for_model(self), type__id=1)
        if img:
            return img.get()
        else:
            return None

    brand = models.ForeignKey(Brand, null=True)
    no_brand = models.BooleanField(default=False, db_index=True)

    @property
    def soo_image(self):
        img = Image.objects.filter(object_id=self.id, deleted=False,
          content_type = ContentType.objects.get_for_model(self), type__id=2)
        if img:
            return img.get()
        else:
            return None

    # In production, this is a tinyint(1) because the set of numbers
    # is very small.  But syncdb produces an int(11).
    is_indexed = models.IntegerField(default=0, db_index=True)

    # Fields related to change management.
    reserved = models.BooleanField(default=False, db_index=True)

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)

    deleted = models.BooleanField(default=False, db_index=True)

    def active_stories(self):
        return self.story_set.exclude(deleted=True)

    def active_variants(self):
        return self.variant_set.exclude(deleted=True)

    def shown_stories(self):
        """ returns cover sequence and story sequences """
        if self.variant_of:
            stories_from = self.variant_of
        else:
            stories_from = self
        stories = list(stories_from.active_stories()
                                   .order_by('sequence_number')
                                   .select_related('type', 'migration_status'))
        if self.series.is_comics_publication:
            if (len(stories) > 0):
                cover_story = stories.pop(0)
                if self.variant_of:
                    # can have only one sequence, the variant cover
                    if self.active_stories().count():
                        cover_story = self.active_stories()[0]
            elif self.variant_of and len(list(self.active_stories())):
                cover_story = self.active_stories()[0]
            else:
                cover_story = None
        else:
            cover_story = None
        return cover_story, stories

    def active_covers(self):
        return self.cover_set.exclude(deleted=True)

    def variant_covers(self):
        """ returns the images from the variant issues """
        from cover import Cover
        if self.variant_of:
            variant_issues = list(self.variant_of.variant_set\
                                      .exclude(id=self.id)\
                                      .exclude(deleted=True)\
                                      .values_list('id', flat=True))
        else:
            variant_issues = list(self.variant_set.exclude(deleted=True)\
                                      .values_list('id', flat=True))
        variant_covers = Cover.objects.filter(issue__id__in=variant_issues)\
                                      .exclude(deleted=True)
        if self.variant_of:
            variant_covers |= self.variant_of.active_covers()
        return variant_covers

    def shown_covers(self):
        return self.active_covers(), self.variant_covers()

    def has_covers(self):
        return self.can_have_cover() and self.active_covers().count() > 0

    def can_have_cover(self):
        if self.series.is_comics_publication:
            return True
        if self.is_indexed in [INDEXED['full'], INDEXED['ten_percent']]:
            return True
        else:
            return False
        
    def has_keywords(self):
        return self.keywords.exists()

    def other_variants(self):
        if self.variant_of:
            variants = self.variant_of.variant_set.exclude(id=self.id)
        else:
            variants = self.variant_set.all()
        return list(variants.exclude(deleted=True))

    def issue_descriptor(self):
        return issue_descriptor(self)

    @property
    def display_number(self):
        number = self.issue_descriptor()
        if number:
            return u'#' + number
        else:
            return u''

    # determine and set whether something has been indexed at all or not
    def set_indexed_status(self):
        from story import StoryType
        if not self.variant_of:
            is_indexed = INDEXED['skeleton']
            if self.page_count > 0:
                total_count = self.active_stories()\
                              .aggregate(Sum('page_count'))['page_count__sum']
                if total_count > 0 and \
                   total_count >= Decimal('0.4') * self.page_count:
                    is_indexed = INDEXED['full']
                elif total_count > 0 and \
                   total_count >= Decimal('0.1') * self.page_count:
                    is_indexed = INDEXED['ten_percent']
            if is_indexed not in [INDEXED['full'], INDEXED['ten_percent']] and \
              self.active_stories()\
              .filter(type=StoryType.objects.get(name='comic story')).count() > 0:
                is_indexed = INDEXED['partial']

            if is_indexed == INDEXED['full']:
                if self.page_count_uncertain or self.active_stories()\
                  .filter(page_count_uncertain=True).count() > 0:
                    is_indexed = INDEXED['partial']

            if self.is_indexed != is_indexed:
                self.is_indexed = is_indexed
                self.save()
                if self.active_variants():
                    for variant in self.active_variants():
                        variant.is_indexed = is_indexed
                        variant.save()
        return self.is_indexed

    def get_prev_next_issue(self):
        """
        Find the issues immediately before and after the given issue.
        """

        prev_issue = None
        next_issue = None

        earlier_issues = self.series.active_base_issues()\
                             .filter(sort_code__lt=self.sort_code)
        earlier_issues = earlier_issues.order_by('-sort_code')
        if earlier_issues:
            prev_issue = earlier_issues[0]

        later_issues = self.series.active_base_issues()\
                           .filter(sort_code__gt=self.sort_code)
        later_issues = later_issues.order_by('sort_code')
        if later_issues:
            next_issue = later_issues[0]

        return [prev_issue, next_issue]

    def delete(self):
        self.deleted = True
        self.reserved = False
        self.save()

    def has_reprints(self):
        from story import STORY_TYPES
        """Simplifies UI checks for conditionals.  notes and reprint fields"""
        return self.from_reprints.count() or \
               self.to_reprints.exclude(target__type__id=STORY_TYPES['promo']).count() or \
               self.from_issue_reprints.count() or \
               self.to_issue_reprints.count()

    def deletable(self):
        if self.cover_revisions.filter(changeset__state__in=states.ACTIVE)\
                                   .count() > 0:
            return False
        if self.variant_set.filter(deleted=False).count() > 0:
            return False
        if self.has_reprints():
            return False
        for story in self.active_stories():
            if story.has_reprints(notes=False):
                return False
        return True

    def can_upload_variants(self):
        if self.has_covers():
            return self.revisions.filter(changeset__state__in=states.ACTIVE,
                                         deleted=True).count() == 0
        else:
            return False

    def get_absolute_url(self):
        return urlresolvers.reverse(
            'show_issue',
            kwargs={'issue_id': self.id } )

    def full_name(self, variant_name=True):
        if variant_name and self.variant_name:
            return u'%s %s [%s]' % (self.series.full_name(),
                                    self.display_number,
                                    self.variant_name)
        else:
            return u'%s %s' % (self.series.full_name(), self.display_number)

    def full_name_with_link(self, publisher=False):
        name_link = self.series.full_name_with_link(publisher)
        return mark_safe('%s <a href="%s">%s</a>' % (name_link,
          self.get_absolute_url(), esc(self.display_number)))

    def short_name(self):
        if self.variant_name:
            return u'%s %s [%s]' % (self.series.name,
                                    self.display_number,
                                    self.variant_name)
        else:
            return u'%s %s' % (self.series.name, self.display_number)

    def __unicode__(self):
        if self.variant_name:
            return u'%s %s [%s]' % (self.series, self.display_number,
                                    self.variant_name)
        else:
            return u'%s %s' % (self.series, self.display_number)

