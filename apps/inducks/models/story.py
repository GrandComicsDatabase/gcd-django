from django.db import models

from .series import Series
from .issue import Issue
from .storyversion import StoryVersion
from .language import Language

class Story(models.Model):
    class Meta:
        db_table = 'inducks_entry'
        app_label = 'coa'

    class Admin:
        pass

    id = models.CharField(max_length = 20, primary_key = True, 
                          db_column = 'entrycode')

    reprints = models.TextField(max_length = 100, db_column = 'alsoreprint',
                                null = True)
    reprint_notes = models.TextField(max_length = 1000, db_column = 'changes', null = True)
    news_start_date = models.CharField(max_length = 10, 
                                       db_column = 'startdate', null = True)
    news_end_date = models.CharField(max_length = 10, 
                                    db_column = 'enddate', null = True)
    included_in_story = models.CharField(max_length = 20,
                          db_column = 'includedinentrycode')

    notes = models.TextField(max_length = 255, db_column = 'entrycomment',
                             null = True)
    error_message = models.TextField(db_column = 'errormessage', null = True)
    job_number = models.CharField(max_length = 25, db_column = 'printedcode',
                                  null = True)
    inducks_number = models.CharField(max_length = 25, db_column = 'guessedcode',
                                  null = True)
    sequence_number = models.CharField(max_length = 100, db_column = 'position', null = True)

    title = models.CharField(max_length = 255, db_column = 'title',
                             null = True)
    issue = models.ForeignKey(Issue,
                              db_column = 'issuecode',
                              null = True)
    story_version = models.ForeignKey(StoryVersion, 
                            db_column = 'storyversioncode', null = True)
    language = models.ForeignKey(Language, primary_key = True, 
                                 db_column = 'languagecode')

    def __str__(self):
        return self.id

