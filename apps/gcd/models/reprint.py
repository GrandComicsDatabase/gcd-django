# -*- coding: utf-8 -*-
from django.db import models
from story import Story
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

class Reprint(models.Model):
    class Meta:
        app_label = 'gcd'

    id = models.AutoField(primary_key = True)
    source = models.ForeignKey(Story, related_name = 'to_reprints')
    target = models.ForeignKey(Story, related_name = 'from_reprints')
    notes = models.TextField(max_length = 255)

    # Fields related to change management.
    reserved = models.BooleanField(default=False, db_index=True)

    def get_compare_string(self, base_issue):
        if self.source.issue == base_issue:
            direction = 'in'
            story = self.target
        else:
            direction = 'from'
            story = self.source
        reprint = u'%s <a target="_blank" href="%s#%d">%s</a> of %s' % \
                    (direction, story.issue.get_absolute_url(),
                    story.id, esc(story), esc(story.issue))
        if self.notes:
            reprint = u'%s [%s]' % (reprint, esc(self.notes))
        return mark_safe(reprint)

    def __unicode__(self):
        return u'%s of %s is reprinted in %s of %s' % (self.source,
          self.source.issue, self.target, self.target.issue)
