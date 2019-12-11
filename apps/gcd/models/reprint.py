# -*- coding: utf-8 -*-
from django.db import models
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from .story import Story

class Reprint(models.Model):
    class Meta:
        app_label = 'gcd'
                    
    origin = models.ForeignKey(Story, related_name='to_reprints')
    target = models.ForeignKey(Story, related_name='from_reprints')
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
        if self.target.issue.key_date:
            sort = self.target.issue.key_date
        else:
            sort = '9999-99-99'
        return "%s-%d-%d" % (sort, self.target.issue.series.year_began,
                             self.target.issue.sort_code)

    def get_compare_string(self, base_issue):
        if self.origin.issue == base_issue:
            direction = 'in'
            story = self.target
        else:
            direction = 'from'
            story = self.origin
        reprint = '%s %s <i>sequence</i> <a target="_blank" href="%s#%d">%s</a>' % \
                    (direction, story.issue.get_absolute_url(), 
                    esc(story.issue.full_name()), story.id, esc(story))
        if self.notes:
            reprint = '%s [%s]' % (reprint, esc(self.notes))
        return mark_safe(reprint)

    def __str__(self):
        return '%s of %s is reprinted in %s of %s' % (self.origin,
          self.origin.issue, self.target, self.target.issue)
