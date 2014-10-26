# -*- coding: utf-8 -*-
from django.db import models
from django.conf import settings

class RecentIndexedIssueManager(models.Manager):
    """
    Custom manager to allow specialized object creation.
    """

    def update_recents(self, issue):
        international = self.filter(language__isnull=True)
        if issue.id not in international.values_list('issue', flat=True):
            self.create(issue=issue, language=None)
            count = international.count()
            if count > settings.RECENTS_COUNT:
                for recent in international.order_by('created')\
                                [:count - settings.RECENTS_COUNT]:
                    recent.delete()

        local = self.filter(language=issue.series.language)
        if issue.id not in local.values_list('issue', flat=True):
            self.create(issue=issue, language=issue.series.language)
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

