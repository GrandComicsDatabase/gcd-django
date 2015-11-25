# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models

from .story import Story

class MigrationStoryStatus(models.Model):
    """
    Storing information for the migration of story data.
    """

    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_migration_story_status'

    story = models.OneToOneField(Story, related_name='migration_status')
    reprint_needs_inspection = models.BooleanField(default=False, db_index=True)
    reprint_confirmed = models.BooleanField(default=False, db_index=True)

    # In production, this field is indexed for the first 255 characters,
    # but Django cannot produce a length-limited index and MySQL
    # cannot fully index a longtext, so it does not appear here.
    reprint_original_notes = models.TextField(null=True)

    modified = models.DateTimeField(auto_now=True)
