from django.db import models

from series import Series
from issue import Issue

class Story(models.Model):
    class Meta:
        db_table = 'stories'
        app_label = 'gcd'

    class Admin:
        pass


    id = models.AutoField(primary_key = True, db_column = 'ID')

    # Core story fields.
    feature = models.CharField(max_length = 255, db_column = 'Feature',
                               null = True, core = True)
    page_count = models.IntegerField(db_column = 'Pg_Cnt', null = True)
    characters = models.TextField(db_column = 'Char_App',
                                  null = True)
    script = models.TextField(max_length = 255, db_column = 'Script',
                              null = True)
    pencils = models.TextField(max_length = 255, db_column = 'Pencils',
                               null = True)
    inks = models.TextField(max_length = 255, db_column = 'Inks',
                            null = True)
    colors = models.TextField(max_length = 255, db_column = 'Colors',
                              null = True)
    letters = models.TextField(max_length = 255, db_column = 'Letters',
                               null = True)
    title = models.CharField(max_length = 255, db_column = 'Title',
                             null = True)
    editor = models.TextField(max_length = 255, db_column = 'Editing',
                              null = True)
    notes = models.TextField(max_length = 255, db_column = 'Notes', null = True)
    synopsis = models.TextField(max_length = 255, db_column = 'Synopsis',
                                null = True)
    reprints = models.TextField(max_length = 255, db_column = 'Reprints',
                                null = True)
    genre = models.CharField(max_length = 255, db_column = 'Genre',
                             null = True)
    type = models.CharField(max_length = 255, db_column = 'Type',
                            null = True)
    sequence_number = models.IntegerField(db_column = 'Seq_No', null = True)

    # I believe this counts issues this appears in (i.e. reprints)
    issue_count = models.IntegerField(db_column = 'IssueCount', null = True)

    # I'm not sure what this is- indexing artifact or story attribute?
    job_number = models.CharField(max_length = 25, db_column = 'JobNo',
                                  null = True)

    # Fields having to do with the old files.  I think.
    initial_distribution = models.IntegerField(db_column = 'InitDist',
                                               null = True)

    # Fields from issue (foreign key plus duplicates/caches).
    issue = models.ForeignKey(Issue,
                              db_column = 'IssueID',
                              null = True,
                              edit_inline = models.STACKED,
                              raw_id_admin = True,
                              num_in_admin = 3)
    issue_number = models.CharField(max_length = 50, db_column = 'Issue',
                                    null = True)
    publication_date = models.CharField(max_length = 50, db_column = 'Pub_Date',
                                        null = True)
    key_date = models.CharField(max_length = 10, db_column = 'Key_Date',
                                null = True)
    price = models.FloatField(db_column = 'Price', null = True)
    rel_year = models.IntegerField(null = True)

    # Fields from series (foreign key plus duplicates/caches).
    # Technically, foreign key is a dup/cache, as issue already has it.
    # series = models.ForeignKey(Series, db_column = 'SeriesID', null = True,
                               # raw_id_admin = True)
    series = models.IntegerField(db_column = 'SeriesID', null = True)
    year_began = models.IntegerField(db_column = 'Yr_Began', null = True)

    # Fields from publishers (duplicate/cache), no foreign key.
    publisher_name = models.CharField(max_length = 255, db_column = 'Pub_Name',
                                      null = True)

    # Fields related to change management.
    created = models.DateField(auto_now_add = True, null = True)
    modified = models.DateField(db_column = 'Modified',
                                auto_now = True, null = True)
    modification_time = models.TimeField(db_column = 'ModTime',
                                         auto_now = True, null = True)
    # Not sure about this one.  May have to do with file dists?
    last_change = models.DateField(db_column = 'LstChang', null = True)

    def has_credits(self):
        """Simplifies UI checks for conditionals.  Credit fields.
        Note that the editor field does not apply to the special cover story."""
        return self.script or \
               self.pencils or \
               self.inks or \
               self.colors or \
               self.letters or \
               (self.editor and (self.sequence_number > 0)) or \
               self.job_number

    def has_content(self):
        """Simplifies UI checks for conditionals.  Content fields"""
        return self.genre or \
               self.characters or \
               self.synopsis or \
               self.reprints

    def has_data(self):
        """Simplifies UI checks for conditionals.  All non-heading fields"""
        return self.has_credits() or self.has_content() or self.notes

    def __unicode__(self):
        return self.feature + "(" + self.type + ":" + self.page_count + ")"

