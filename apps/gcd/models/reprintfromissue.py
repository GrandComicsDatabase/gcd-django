# -*- coding: utf-8 -*-
from django.db import models
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from .gcddata import GcdLink
from .story import Story
from .issue import Issue

class ReprintFromIssue(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_reprint_from_issue'

    origin_issue = models.ForeignKey(Issue, related_name='to_reprints')
    target = models.ForeignKey(Story, related_name='from_issue_reprints')
    notes = models.TextField(max_length = 255)

    # Fields related to change management.
    reserved = models.BooleanField(default=False, db_index=True)

    @property
    def origin_sort(self):
        if self.origin_issue.key_date:
            sort = self.origin_issue.key_date
        else:
            sort = '9999-99-99'
        return "%s-%d-%d" % (sort, self.origin_issue.series.year_began,
                             self.origin_issue.sort_code)

    @property
    def target_sort(self):
        if self.target.issue.key_date:
            sort = self.target.issue.key_date
        else:
            sort = '9999-99-99'
        return "%s-%d-%d" % (sort, self.target.issue.series.year_began,
                             self.target.issue.sort_code)

    def get_compare_string(self, base_issue):
        if self.origin_issue == base_issue:
            reprint = 'in %s <i>sequence</i> <a target="_blank" href="%s#%d">%s</a>' % \
                        (self.target.issue.get_absolute_url(),
                         esc(self.target.issue.full_name()),
                         self.target.id, esc(self.target))
        else:
            reprint = 'from <a target="_blank" href="%s">%s</a>' % \
                        (self.origin_issue.get_absolute_url(),
                         esc(self.origin_issue.full_name()))
        if self.notes:
            reprint = '%s [%s]' % (reprint, esc(self.notes))
        return mark_safe(reprint)

    def __unicode__(self):
        return '%s reprinted in %s of %s' % (self.origin_issue, self.target,
                                              self.target.issue)
