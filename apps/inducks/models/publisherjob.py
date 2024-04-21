from django.db import models

from .issue import Issue
from .publisher import Publisher

class PublisherJob(models.Model):
    class Meta:
        db_table = 'inducks_publishingjob'
        app_label = 'coa'

    class Admin:
        pass

    publisher = models.ForeignKey(Publisher, primary_key = True, 
                           db_column = 'publisherid')
    issue = models.ForeignKey(Issue, primary_key = True, 
                              db_column = 'issuecode')
    notes = models.TextField(db_column = 'publishingjobcomment', null = True)
