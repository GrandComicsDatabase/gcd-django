# -*- coding: utf-8 -*-
from django.db import models

class Error(models.Model):
    """
    Store errors from gcd database.
    """
    class Meta:
        app_label = 'gcd'

    class Admin:
        pass

    error_key = models.CharField(primary_key=True, max_length=40, null=True,
                                 editable=False)
    error_text = models.TextField(null=True, blank=True)

    is_safe = models.BooleanField()

    def __unicode__(self):
        return self.error_text

