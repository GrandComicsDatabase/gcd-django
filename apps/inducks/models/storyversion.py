from django.db import models

from .series import Series
from .issue import Issue
from .basestory import BaseStory

class StoryVersion(models.Model):
    class Meta:
        db_table = 'inducks_storyversion'
        app_label = 'coa'

    class Admin:
        pass

    id = models.CharField(max_length = 20, primary_key = True, 
                          db_column = 'storyversioncode')

    plot = models.TextField(db_column = 'plotsummary',
                            null = True)
    script = models.TextField(db_column = 'writsummary',
                              null = True)
    pencils = models.TextField(max_length = 255, db_column = 'artsummary',
                               null = True)
    inks = models.TextField(db_column = 'inksummary',
                            null = True)

    page_count = models.IntegerField(db_column = 'entirepages', null = True)
    page_numerator = models.IntegerField(db_column = 'brokenpagenumerator', null = True)
    page_denominator = models.IntegerField(db_column = 'brokenpagedenominator', null = True)
    no_broken_page = models.BooleanField(default = False, db_column = 'brokenpageunspecified')
    type = models.CharField(max_length = 100, db_column = 'kind',
                            null = True)
    base_story = models.ForeignKey(BaseStory, 
                            db_column = 'storycode', null = False)


    def __unicode__(self):
        return self.id

