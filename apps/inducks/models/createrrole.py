from django.db import models

from .storyversion import StoryVersion

class CreatorRole(models.Model):
    class Meta:
        db_table = 'inducks_storyjob'
        app_label = 'coa'

    class Admin:
        pass

    id = models.CharField(max_length = 100, primary_key = True, 
                          db_column = 'personcode')

    story_version = models.ForeignKey(StoryVersion, 
                            db_column = 'storyversioncode', null = True)
    role = models.CharField(max_length = 100, primary_key = True, 
                            db_column = 'plotwritartink')
    creator = models.CharField(max_length = 100, primary_key = True, 
                                  db_column = 'personcode')
    indirect = models.BooleanField(default = False, db_column = 'indirect')
    notes = models.TextField(max_length = 1000, db_column = 'storyjobcomment',
                             null = True)
