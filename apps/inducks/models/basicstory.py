from django.db import models

from .series import Series
from .issue import Issue

class BaseStory(models.Model):
    class Meta:
        db_table = 'inducks_story'
        app_label = 'coa'

    class Admin:
        pass

    id = models.CharField(max_length = 100, primary_key = True, 
                          db_column = 'storycode')

    first_publication_date = models.CharField(max_length = 10, 
                                       db_column = 'firstpublicationdate', 
                                       null = True)
    notes = models.TextField(max_length = 255, db_column = 'storycomment',
                             null = True)
    error_message = models.TextField(db_column = 'errormessage', null = True)

    def __str__(self):
        return self.id

