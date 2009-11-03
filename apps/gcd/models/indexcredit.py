from django.db import models

from indexer import Indexer
from series import Series

class IndexCredit(models.Model):
    """
    Series-level indexing credits from gcd database.
    No longer updated, but used for historical crediting.
    """

    class Meta:
        db_table = 'gcd_series_indexers'
        app_label = 'gcd'

    class Admin:
        pass

    indexer = models.ForeignKey(Indexer, related_name='index_credit_set')
    series = models.ForeignKey(Series, related_name='index_credit_set')
    run = models.CharField(max_length=255, null=True)
    notes = models.TextField(null=True)

    modified = models.DateTimeField(auto_now=True)

