from django.db import models

from apps.gcd.models import Indexer, Series, Issue, Story


class IndexCredit(models.Model):
    """
    Series-level indexing credits from gcd database.
    No longer updated, but used for historical crediting.
    """

    class Meta:
        db_table = 'legacy_series_indexers'

    class Admin:
        pass

    indexer = models.ForeignKey(Indexer, related_name='index_credit_set')
    series = models.ForeignKey(Series, related_name='index_credit_set')
    run = models.CharField(max_length=255, null=True)
    notes = models.TextField(null=True)

    modified = models.DateTimeField(auto_now=True)


class Reservation(models.Model):
    """
    Issue-level reservations in the OI.
    No longer updated, used for historical crediting and migration.
    """
    class Admin:
        pass

    indexer = models.ForeignKey(Indexer, related_name='reservation_set')
    issue = models.ForeignKey(Issue, related_name='reservation_set')
    status = models.IntegerField(db_index=True)

    expires = models.DateField(null=True, blank=True)
    created = models.DateTimeField(auto_now=True, editable=False)


class MigrationStoryStatus(models.Model):
    """
    Storing information for the migration of story data.
    """

    class Meta:
        db_table = 'legacy_migration_story_status'

    story = models.OneToOneField(Story, related_name='migration_status')
    reprint_needs_inspection = models.BooleanField(default=False, db_index=True)
    reprint_confirmed = models.BooleanField(default=False, db_index=True)

    # In production, this field is indexed for the first 255 characters,
    # but Django cannot produce a length-limited index and MySQL
    # cannot fully index a longtext, so it does not appear here.
    reprint_original_notes = models.TextField(null=True)

    modified = models.DateTimeField(auto_now=True)
