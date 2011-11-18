# -*- coding: utf-8 -*-
from django.db import models
from issue import Issue

class IssueReprint(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'issue_reprint'

    id = models.AutoField(primary_key = True)
    source_issue = models.ForeignKey(Issue, related_name = 'to_issue_reprints')
    target_issue = models.ForeignKey(Issue, related_name = 'from_issue_reprints')
    notes = models.TextField(max_length = 255)

    # Fields related to change management.
    reserved = models.BooleanField(default=False, db_index=True)

    def get_compare_string(self, base_issue):
        if self.source.issue == base_issue:
            direction = 'in'
            issue = self.target_issue
        else:
            direction = 'from'
            issue = self.source_issue
        reprint = u'%s <a target="_blank" href="%s">%s</a>' % \
                    (direction, issue.get_absolute_url(), esc(story.issue))
        if self.notes:
            reprint = '%s [%s]' % (reprint, esc(self.notes))
        return mark_safe(reprint)

    def __unicode__(self):
        return "from %s reprint in %s" % (self.source_issue, self.target_issue)