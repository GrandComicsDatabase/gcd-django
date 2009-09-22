from django.db import models

from series import Series
from issue import Issue

class Story(models.Model):
    class Meta:
        db_table = 'stories'
        app_label = 'gcd'

    class Admin:
        pass


    id = models.AutoField(primary_key=True, db_column='ID')

    # Core story fields.
    feature = models.CharField(max_length=255, db_column='Feature',
                               null=True)
    page_count = models.FloatField(db_column='Pg_Cnt', null=True)
    page_count_uncertain = models.BooleanField(default=0)

    characters = models.TextField(db_column='Char_App', null = True)

    script = models.TextField(max_length=255, db_column='Script', null=True)
    pencils = models.TextField(max_length=255, db_column='Pencils', null=True)
    inks = models.TextField(max_length=255, db_column='Inks', null=True)
    colors = models.TextField(max_length=255, db_column='Colors', null=True)
    letters = models.TextField(max_length=255, db_column='Letters', null=True)

    no_script = models.BooleanField(default=0)
    no_pencils = models.BooleanField(default=0)
    no_inks = models.BooleanField(default=0)
    no_colors = models.BooleanField(default=0)
    no_letters = models.BooleanField(default=0)

    title = models.CharField(max_length=255, db_column='Title', null=True)
    editor = models.TextField(max_length=255, db_column='Editing', null=True)
    notes = models.TextField(max_length=255, db_column='Notes', null=True)
    synopsis = models.TextField(max_length=255, db_column='Synopsis', null=True)
    reprints = models.TextField(max_length=255, db_column='Reprints', null=True)
    genre = models.CharField(max_length=255, db_column='Genre', null=True)
    type = models.CharField(max_length=255, db_column='Type', null=True)
    sequence_number = models.IntegerField(db_column='Seq_No', null=True)
    job_number = models.CharField(max_length=25, db_column='JobNo', null=True)

    # I believe this counts issues this appears in (i.e. reprints)
    issue_count = models.IntegerField(db_column = 'IssueCount', null = True)


    # Fields from issue (foreign key plus duplicates/caches).
    issue = models.ForeignKey(Issue,
                              db_column = 'IssueID',
                              null = True)

    # Fields from series.  Should be a foreign key but apparently somtimes
    # violates that constraint so kept only as an integer.  Needs work.
    series = models.IntegerField(db_column = 'SeriesID', null = True)

    # Fields related to change management.
    reserved = models.BooleanField(default=0)
    created = models.DateTimeField(auto_now_add = True, null = True)
    modified = models.DateTimeField(db_column = 'Modified',
                                    auto_now = True, null = True)

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

