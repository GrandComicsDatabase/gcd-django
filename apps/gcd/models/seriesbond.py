# -*- coding: utf-8 -*-
from django.db import models
from series import Series
from issue import Issue

BOND_TRACKING = {1, 2, 3}

class SeriesBondType(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_series_bond_type'

    # technical name, not to be changed
    name = models.CharField(max_length=255, db_index=True)
    # short description, e.g. shown in selection boxes
    description = models.TextField()
    notes = models.TextField(blank=True)

    def __unicode__(self):
        return self.description

class SeriesBond(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_series_bond'

    origin = models.ForeignKey(Series, related_name='to_series_bond')
    target = models.ForeignKey(Series, related_name='from_series_bond')
    origin_issue = models.ForeignKey(Issue, null=True,
                                     related_name='to_series_issue_bond')
    target_issue = models.ForeignKey(Issue, null=True,
                                     related_name='from_series_issue_bond')
    bond_type = models.ForeignKey(SeriesBondType)
    # we don't use modelforms to edit seriesbonds, no blank=True needed
    notes = models.TextField(max_length=255)

    # Fields related to change management.
    reserved = models.BooleanField(default=False, db_index=True)

    def _modified(self):
        return self.revisions.filter(changeset__state=5).latest().modified
    modified = property(_modified)
    
    # we check for deleted in the oi for models, so set to False
    deleted = False
    def deletable(self):
        return True

    def __unicode__(self):
        if self.origin_issue:
            object_string = u'%s' % self.origin_issue
        else:
            object_string = u'%s' % self.origin
        if self.target_issue:
            object_string += u' continues at %s' % self.target_issue
        else:
            object_string += u' continues at %s' % self.target
        return object_string
