# -*- coding: utf-8 -*-
from django.db import models
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from .gcddata import GcdLink
from .story import Story
from .issue import Issue

class ReprintToIssue(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_reprint_to_issue'

    origin = models.ForeignKey(Story, related_name='to_issue_reprints')
    target_issue = models.ForeignKey(Issue, related_name='from_reprints')
    notes = models.TextField(max_length=255)

    # Fields related to change management.
    reserved = models.BooleanField(default=False, db_index=True)

    @property
    def origin_sort(self):
        if self.origin.issue.key_date:
            sort = self.origin.issue.key_date
        else:
            sort = '9999-99-99'
        return "%s-%d-%d" % (sort, self.origin.issue.series.year_began,
                             self.origin.issue.sort_code)
    
    @property
    def target_sort(self):
        if self.target_issue.key_date:
            sort = self.target_issue.key_date
        else:
            sort = '9999-99-99'
        return "%s-%d-%d" % (sort, self.target_issue.series.year_began,
                             self.target_issue.sort_code)

    def get_compare_string(self, base_issue):
        if self.target_issue == base_issue:
            reprint = 'from %s <i>sequence</i> <a target="_blank" href="%s#%d">%s</a>' % \
                        (self.origin.issue.get_absolute_url(), 
                         esc(self.origin.issue.full_name()),
                         self.origin.id, esc(self.origin))
        else:
            reprint = 'in <a target="_blank" href="%s">%s</a>' % \
                        (self.target_issue.get_absolute_url(),
                         esc(self.target_issue.full_name()))
        if self.notes:
            reprint = '%s [%s]' % (reprint, esc(self.notes))
        return mark_safe(reprint)

    def __unicode__(self):
        return '%s of %s reprinted in %s' % (self.origin, self.origin.issue,
                                              self.target_issue)
