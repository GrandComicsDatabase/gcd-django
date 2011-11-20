# -*- coding: utf-8 -*-
from django.db import models
from story import Story, Issue
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

class ReprintFromIssue(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_reprint_from_issue'

    id = models.AutoField(primary_key = True)
    source_issue = models.ForeignKey(Issue, related_name = 'to_reprints')
    target = models.ForeignKey(Story, related_name = 'from_issue_reprints')
    notes = models.TextField(max_length = 255)

    # Fields related to change management.
    reserved = models.BooleanField(default=False, db_index=True)

    def get_compare_string(self, base_issue):
        if self.source_issue == base_issue:
            reprint = u'in <a target="_blank" href="%s#%d">%s</a> of %s' % \
                        (self.target.issue.get_absolute_url(),
                         self.target.id, esc(self.target), esc(self.target.issue))
        else:
            reprint = u'from <a target="_blank" href="%s">%s</a>' % \
                        (self.source_issue.get_absolute_url(),
                         esc(self.source_issue))
        if self.notes:
            reprint = u'%s [%s]' % (reprint, esc(self.notes))
        return mark_safe(reprint)

    def __unicode__(self):
        return u'%s reprinted in %s of %s' % (self.source_issue, self.target,
                                             self.target.issue)
