from django.db import models

from indexer import Indexer
from series import Series

class IndexCredit(models.Model):
    """ indexing credits from gcd database"""

    class Meta:
        db_table = 'IndexCredit'
        app_label = 'gcd'

    class Admin:
        pass

    id = models.AutoField(primary_key = True, db_column = 'ID')

    indexer = models.ForeignKey(Indexer, db_column = 'IndexerID',
                                related_name = 'index_credit_set')
    series = models.ForeignKey(Series, db_column = 'SeriesID',
                               related_name = 'index_credit_set')
    run = models.CharField(max_length = 255, db_column = 'Run', null = True)
    notes = models.TextField(db_column = 'Notes', null = True)
    comment = models.TextField(db_column = 'Comment', null = True)

    modified = models.DateField(db_column = 'DateMod',
                                auto_now = True, null = True)

