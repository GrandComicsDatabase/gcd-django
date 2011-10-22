# -*- coding: utf-8 -*-
from django.db import models
from story import Story

class Reprint(models.Model):
    class Meta:
        app_label = 'gcd'

    id = models.AutoField(primary_key = True)
    source = models.ForeignKey(Story, related_name = 'to_reprints')
    target = models.ForeignKey(Story, related_name = 'from_reprints')
    notes = models.TextField(max_length = 255)

    # Fields related to change management.
    reserved = models.BooleanField(default=False, db_index=True)

    def __unicode__(self):
        return "from %s reprint in %s" % (self.source, self.target)