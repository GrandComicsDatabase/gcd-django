# -*- coding: utf-8 -*-
from django.db import models
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from .issue import Issue

class IssueReprint(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_issue_reprint'

    origin_issue = models.ForeignKey(Issue, related_name='to_issue_reprints')
    target_issue = models.ForeignKey(Issue, related_name='from_issue_reprints')
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
        if self.target_issue.key_date:
            sort = self.target_issue.key_date
        else:
            sort = '9999-99-99'
        return "%s-%d-%d" % (sort, self.target_issue.series.year_began,
                             self.target_issue.sort_code)

    def get_compare_string(self, base_issue):
        if self.origin_issue == base_issue:
            direction = 'in'
            issue = self.target_issue
        else:
            direction = 'from'
            issue = self.origin_issue
        reprint = '%s <a target="_blank" href="%s">%s</a>' % \
                    (direction, issue.get_absolute_url(), esc(issue.full_name()))
        if self.notes:
            reprint = '%s [%s]' % (reprint, esc(self.notes))
        return mark_safe(reprint)

    def __str__(self):
        return 'from %s reprint in %s' % (self.origin_issue, self.target_issue)
