from django.db import models

from indexer import Indexer
from issue import Issue

class Reservation(models.Model):
    """
    Issue-level reservations in the OI.
    """

    class Meta:
        db_table = 'Reservations'
        app_label = 'gcd'

    class Admin:
        pass

    id = models.AutoField(primary_key=True, db_column='ID')

    indexer = models.ForeignKey(Indexer, db_column='IndexerID',
                                related_name='reservation_set')
    issue = models.ForeignKey(Issue, db_column='IssueID',
                               related_name='reservation_set')
    status = models.IntegerField(null=True, blank=True, db_column='Status')

    # NOTE: there are two rows with a non-null but 0000-00-00 date
    # which will need to be fixed or else python date objects won't work.
    expires = models.DateField(null=True, blank=True, db_column='Expires')

    created = models.DateField(auto_now=True, null=True, editable=False,
                               db_column='Created')

    # NOTE: this appears to always be 1.
    index_type = models.IntegerField(null=True, blank=True,
                                     db_column='IndexType')

