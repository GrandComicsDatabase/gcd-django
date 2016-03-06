# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from .gcddata import GcdLink
from .story import Story
from .issue import Issue
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc


class Reprint(GcdLink):
    class Meta:
        app_label = 'gcd'

    origin = models.ForeignKey(Story, related_name='to_reprints', null=True)
    target = models.ForeignKey(Story, related_name='from_reprints', null=True)

    # NOTE: These should be NOT NULL but that needs to be added after the first
    #       data migration.
    # "temp_" prefix on reverse relations is there only until the other three
    # reprint tables are deleted.  otherwise, these new fields clash with them.
    origin_issue = models.ForeignKey(Issue,
                                     related_name='temp_to_issue_reprints',
                                     null=True)
    target_issue = models.ForeignKey(Issue,
                                     related_name='temp_from_issue_reprints',
                                     null=True)

    notes = models.TextField(max_length=255)

    def save(self, update_fields=None, *args, **kwargs):
        """
        Ensure origin/target_issue are always in agreement with origin/target.

        This makes certain that origin_issue and target_issue are always set
        to the same thing as origin.issue or target.issue when origin or
        target are set.  This allows an easy query for all reprints related
        to an issue.  Finding only reprints that lack a story can be done
        by filtering on origin/target=None.

        NOTE: If origin_issue or target_issue are changed without changing
              or clearing origin or target, those changes will be silently
              dropped.  origin and target always overwrite any disagreeing
              origin_issue or target_issue.

        This method is not called for bulk updates or creates, so care should
        be taken not to violate this constraint when using those methods.
        """
        if ((update_fields is None or 'origin' in update_fields) and
                self.origin is not None):
            self.origin_issue = self.origin.issue
            if (update_fields is not None and
                    'origin_issue' not in update_fields):
                update_fields.append('origin_issue')

        if ((update_fields is None or 'target' in update_fields) and
                self.target is not None):
            self.target_issue = self.target.issue
            if (update_fields is not None and
                    'target_issue' not in update_fields):
                update_fields.append('target_issue')

        if update_fields is not None:
            kwargs['update_fields'] = update_fields
        super(Reprint, self).save(*args, **kwargs)

    @property
    def origin_sort(self):
        if self.origin_issue.key_date:
            sort = self.origin_issue.key_date
        else:
            sort = '9999-99-99'
        return "%s-%d-%d" % (sort,
                             self.origin_issue.series.year_began,
                             self.origin_issue.sort_code)

    @property
    def target_sort(self):
        if self.target_issue.key_date:
            sort = self.target_issue.key_date
        else:
            sort = '9999-99-99'
        return "%s-%d-%d" % (sort,
                             self.target_issue.series.year_began,
                             self.target_issue.sort_code)

    def get_compare_string(self, base_issue):
        if self.origin_issue == base_issue:
            direction = 'in'
            story = self.target
            issue = self.target_issue
        else:
            direction = 'from'
            story = self.origin
            issue = self.origin_issue

        if story:
            reprint = (('%s %s <i>sequence</i> '
                        '<a target="_blank" href="%s#%d">%s</a>') %
                       (direction,
                        esc(issue.full_name()),
                        issue.get_absolute_url(),
                        story.id,
                        esc(story)))
        else:
            reprint = ('%s <a target="_blank" href="%s">%s</a>' %
                       (direction,
                        issue.get_absolute_url(),
                        esc(issue.full_name())))

        if self.notes:
            reprint = '%s [%s]' % (reprint, esc(self.notes))
        return mark_safe(reprint)

    def __unicode__(self):
        if self.origin and self.target:
            return '%s of %s is reprinted in %s of %s' % (
                self.origin, self.origin_issue, self.target, self.target_issue)
        elif self.origin:
            return u'%s of %s is reprinted in %s' % (
                self.origin, self.origin_issue, self.target_issue)
        elif self.target:
            return u'material from %s is reprinted in %s of %s' % (
                self.origin_issue, self.target, self.target_issue)
        return u'material from %s is reprinted in %s' % (
            self.origin_issue, self.target_issue)
