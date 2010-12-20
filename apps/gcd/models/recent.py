# -*- coding: utf-8 -*-
from django.db import models
from django.conf import settings

class RecentIndexedIssueManager(models.Manager):
    """
    Custom manager to allow specialized object creation.
    """

    def update_recents(self, issue):
        self.create(issue=issue, language=None)
        international = self.filter(language__isnull=True)
        count = international.count()
        if count > settings.RECENTS_COUNT:
            for recent in international.order_by('created')\
                            [:count - settings.RECENTS_COUNT]:
                recent.delete()

        self.create(issue=issue, language=issue.series.language)
        local = self.filter(language=issue.series.language)
        count = local.count()
        if count > settings.RECENTS_COUNT:
            for recent in local.order_by('created')\
                            [:count - settings.RECENTS_COUNT]:
                recent.delete()         

class RecentIndexedIssue(models.Model):
    """
    Cache the most recently indexed issues to avoid really expensive
    scans of the very large oi_changeset and oi_issue_revision tables.
    """
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_recent_indexed_issue'

    objects = RecentIndexedIssueManager()

    issue = models.ForeignKey('Issue')
    language = models.ForeignKey('Language', null=True, db_index=True)
    created = models.DateTimeField(auto_now_add=True, db_index=True)

