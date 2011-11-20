# -*- coding: utf-8 -*-
from django.db import models
from story import Story, Issue

class ReprintToIssue(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_reprint_to_issue'

    id = models.AutoField(primary_key = True)
    source = models.ForeignKey(Story, related_name = 'to_issue_reprints')
    target_issue = models.ForeignKey(Issue, related_name = 'from_reprints')
    notes = models.TextField(max_length = 255)

    # Fields related to change management.
    reserved = models.BooleanField(default=False, db_index=True)

    def get_compare_string(self, base_issue):
        if self.target_issue == base_issue:
            reprint = u'from <a target="_blank" href="%s#%d">%s</a> of %s' % \
                        (self.source.issue.get_absolute_url(),
                        self.source.id, esc(self.source), esc(self.source.issue))
        else:
            reprint = u'in <a target="_blank" href="%s">%s</a>' % \
                        (self.target_issue.get_absolute_url(),
                         esc(self.target_issue))
        if self.notes:
            reprint = u'%s [%s]' % (reprint, esc(self.notes))
        return mark_safe(reprint)

    def __unicode__(self):
        return u'%s of %s reprinted in %s' % (self.source, self.source.issue,
                                             self.target_issue)
