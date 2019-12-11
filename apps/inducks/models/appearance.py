from django.db import models

from .character import Character
from .storyversion import StoryVersion

class Appearance(models.Model):
    class Meta:
        db_table = 'inducks_appearance'
        app_label = 'coa'

    class Admin:
        pass

    character = models.ForeignKey(Character, primary_key = True, 
                                  db_column = 'charactercode')
    character_code = models.CharField(max_length = 20, 
                                  db_column = 'charactercode')
    story_version = models.ForeignKey(StoryVersion, 
                            db_column = 'storyversioncode', null = True)
    #def __str__(self):
        #return str(self.character) + str(self.story_version)
