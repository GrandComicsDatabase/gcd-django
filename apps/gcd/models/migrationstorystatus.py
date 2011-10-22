from django.db import models

from story import Story

class MigrationStoryStatus(models.Model):
    """
    Storing information for the migration of story data.
    """

    class Meta:
        app_label = 'gcd'
        db_table = 'migration_story_status'

    story = models.OneToOneField(Story, related_name='migration_status')
    reprint_needs_inspection = models.BooleanField(default=0)
    reprint_confirmed = models.BooleanField(default=0)
    reprint_original_notes = models.TextField(null=True)

