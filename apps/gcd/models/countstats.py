# -*- coding: utf-8 -*-
from django.db import models

class CountStats(models.Model):
    """
    Store stats from gcd database.
    """
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_count_stats'

    class Admin:
        pass

    name = models.CharField(primary_key=True, max_length=40, null=True)
    count = models.IntegerField()

    def __unicode__(self):
        return self.name + ": " + str(self.count)

