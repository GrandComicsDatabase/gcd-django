# -*- coding: utf-8 -*-
from django.db import models
from django.core import urlresolvers
from django.db.models import Sum, Count

from publisher import IndiciaPublisher, Brand
from series import Series

# TODO: should not be importing oi app into gcd app, dependency should be
# the other way around.  Probably.
from apps.oi import states

class Issue(models.Model):
    class Meta:
        app_label = 'gcd'
        ordering = ['series', 'sort_code']

    # Issue identification
    number = models.CharField(max_length=50, db_index=True)
    volume = models.CharField(max_length=50, db_index=True)
    no_volume = models.BooleanField(default=0)
    display_volume_with_number = models.BooleanField(default=False)
    isbn = models.CharField(max_length=32)
    valid_isbn = models.CharField(max_length=13)
    variant_of = models.ForeignKey('self', null=True,
                                   related_name='variant_set')
    variant_name = models.CharField(max_length=255)
    
    # Dates and sorting
    publication_date = models.CharField(max_length=255)
    key_date = models.CharField(max_length=10)
    sort_code = models.IntegerField(db_index=True)
    indicia_frequency = models.CharField(max_length=255)

    # Price, page count and format fields
    price = models.CharField(max_length=255)
    page_count = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    page_count_uncertain = models.BooleanField(default=0)

    editing = models.TextField()
    no_editing = models.BooleanField(default=0)
    notes = models.TextField()


    # Series and publisher links
    series = models.ForeignKey(Series)
    indicia_publisher = models.ForeignKey(IndiciaPublisher, null=True)
    indicia_pub_not_printed = models.BooleanField(default=0)
    brand = models.ForeignKey(Brand, null=True)
    no_brand = models.BooleanField(default=0, db_index=True)

    is_indexed = models.BooleanField(default=0, db_index=True)

    # Fields related to change management.
    reserved = models.BooleanField(default=0, db_index=True)

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)

    deleted = models.BooleanField(default=0, db_index=True)

    def active_stories(self):
        return self.story_set.exclude(deleted=True)

    def shown_stories(self):
        """ returns cover sequence and story sequences """
        if self.variant_of:
            stories_from = self.variant_of
        else:
            stories_from = self
        stories = list(stories_from.active_stories()
                                   .order_by('sequence_number')
                                   .select_related('type'))

        if (len(stories) > 0):
            cover_story = stories.pop(0)
            if self.variant_of:
                # can have only one sequence, the variant cover
                if self.active_stories().count():
                    cover_story = self.active_stories()[0]
        else: 
            cover_story = None
        return cover_story, stories

    def active_covers(self, variants=False):
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
        return Cover.objects.filter(issue__id__in=variant_issues)\
                            .exclude(deleted=True)

    def all_covers(self):
        return self.active_covers() | self.variant_covers()
        
    def shown_covers(self):
        return self.active_covers(), self.variant_covers()

    def has_covers(self, variants=False):
        if variants:
            return self.all_covers().count() > 0
        else:
            return self.active_covers().count() > 0

    def _display_number(self):
        if self.display_volume_with_number:
            return u'v%s#%s' % (self.volume, self.number)
        return self.number
    display_number = property(_display_number)

    # determine and set whether something has been indexed at all or not
    def set_indexed_status(self):
        from story import StoryType
        if self.active_stories().filter(type=StoryType.objects.get(name='story'))\
                                .count() > 0:
            is_indexed = True
        else:
            total_count = self.active_stories()\
                              .aggregate(Sum('page_count'))['page_count__sum']
            if (total_count is not None and self.page_count is not None and
                    total_count * 2 > self.page_count):
                is_indexed = True
            else:
                is_indexed = False
        if self.is_indexed != is_indexed:
            self.is_indexed = is_indexed
            self.save()
        return self.is_indexed

    def index_status_name(self):
        """
        Text form of status.  If clauses arranged in order of most
        likely case to least.
        """
        if self.reserved:
            active =  self.revisions.get(changeset__state__in=states.ACTIVE)
            return states.CSS_NAME[active.changeset.state]
        elif self.is_indexed:
            return 'approved'
        else:
            return 'available'

    def get_prev_next_issue(self):
        """
        Find the issues immediately before and after the given issue.
        """

        prev_issue = None
        next_issue = None

        earlier_issues = \
          self.series.active_issues().filter(sort_code__lt=self.sort_code)
        earlier_issues = earlier_issues.order_by('-sort_code')
        if earlier_issues:
            prev_issue = earlier_issues[0]     
        
        later_issues = self.series.active_issues()\
                           .filter(sort_code__gt=self.sort_code)
        later_issues = later_issues.order_by('sort_code')
        if later_issues:
            next_issue = later_issues[0]

        return [prev_issue, next_issue]

    def delete(self):
        self.deleted = True
        self.reserved = False
        self.save()

    def deletable(self):
        return self.cover_revisions.filter(changeset__state__in=states.ACTIVE)\
                                   .count() == 0

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

    def full_name(self):
        return u'%s #%s' % (self.series.full_name(), self.display_number)

    def __unicode__(self):
        return u'%s #%s' % (self.series, self.display_number)

