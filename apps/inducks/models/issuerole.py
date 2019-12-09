from django.db import models

from .issue import Issue
from .creator import Creator

class IssueRole(models.Model):
    class Meta:
        db_table = 'inducks_issuejob'
        app_label = 'coa'

    class Admin:
        pass

    issue = models.ForeignKey(Issue, primary_key = True,
                            db_column = 'issuecode', null = True)
    role = models.CharField(max_length = 100, 
                            db_column = 'inxtransletcol')
    creator = models.ForeignKey(Creator, primary_key = True, 
                                db_column = 'personcode')
    notes = models.TextField(max_length = 1000, db_column = 'issuejobcomment',
                             null = True)
