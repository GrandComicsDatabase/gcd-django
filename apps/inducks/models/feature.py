from django.db import models

from .basestory import BaseStory
from .character import Character

class Feature(models.Model):
    class Meta:
        db_table = 'inducks_herocharacter'
        app_label = 'coa'

    class Admin:
        pass

    feature = models.ForeignKey(Character, primary_key = True, 
                                db_column = 'charactercode')


    base_story = models.ForeignKey(BaseStory, 
                            db_column = 'storycode', null = True)
