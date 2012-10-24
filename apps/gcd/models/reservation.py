from django.db import models

from indexer import Indexer
from issue import Issue

class Reservation(models.Model):
    """
    Issue-level reservations in the OI.
    No longer updated, used for historical crediting and migration.
    """
    class Meta:
        app_label = 'gcd'

    class Admin:
        pass

    indexer = models.ForeignKey(Indexer, related_name='reservation_set')
    issue = models.ForeignKey(Issue, related_name='reservation_set')
    status = models.IntegerField(db_index=True)

    expires = models.DateField(null=True, blank=True)
    created = models.DateTimeField(auto_now=True, editable=False)

