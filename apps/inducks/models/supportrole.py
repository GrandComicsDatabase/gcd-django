from django.db import models

from .story import Story
from .creator import Creator

class SupportRole(models.Model):
    class Meta:
        db_table = 'inducks_entryjob'
        app_label = 'coa'

    class Admin:
        pass

    story = models.ForeignKey(Story, primary_key = True,
                            db_column = 'entrycode', null = True)
    role = models.CharField(max_length = 100, 
                            db_column = 'transletcol')
    creator = models.ForeignKey(Creator, primary_key = True, 
                                db_column = 'personcode')
    notes = models.TextField(max_length = 1000, db_column = 'entryjobcomment',
                             null = True)
