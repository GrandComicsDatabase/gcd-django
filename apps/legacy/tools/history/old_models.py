# -*- coding: utf-8 -*-
from decimal import Decimal

from django.db import models

from .series import Series
from .issue import Issue
from .story import Story
from apps.oi.models import IssueRevision, StoryRevision, StoryType
from apps.legacy.tools.history.story import MigratoryStoryRevision
from apps.legacy.tools.history.issue import MigratoryIssueRevision

class OldIssue(models.Model):
    class Meta:
        app_label = 'old_gcd_data'
        #ordering = ['series', 'sort_code']
        db_table='issues'

    # Issue identification
    number = models.CharField(db_column='Issue', max_length=50, db_index=True)
    volume = models.IntegerField(db_column='VolumeNum', db_index=True)
    book_name = models.CharField(db_column='Bk_Name', max_length=50)
    pub_name = models.CharField(db_column='Pub_Name', max_length=50)

    story_count = models.IntegerField(db_column='storycount')
    is_updated = models.IntegerField(db_column='isUpdated')
    # Dates and sorting
    publication_date = models.CharField(db_column='Pub_Date', max_length=255)
    key_date = models.CharField(db_column='Key_Date', max_length=10, db_index=True)

    # Price, page count and format fields
    price = models.CharField(db_column='Price', max_length=255)
    page_count = models.DecimalField(db_column='Pg_Cnt', max_digits=10, decimal_places=3, null=True)

    editing = models.TextField(db_column='Editing', )
    notes = models.TextField(db_column='Notes', )

    series_id = models.IntegerField(db_column='SeriesID')

    modified = models.DateField(db_column='Modified')
    last_change = models.DateField(db_column='LstChang')
    modified_time = models.TimeField(db_column='ModTime')
    created = models.DateField(db_column='created')

    migratory_class = MigratoryIssueRevision

    def convert(self, changeset):
        if self.volume is None:
            volume = ''
        else:
            volume = '%s' % self.volume

        display_series = Series.objects.get(id=self.series_id)

        if display_series.year_ended and display_series.year_ended < 1970:
            no_isbn = True
        else:
            no_isbn = False

        if display_series.year_ended and display_series.year_ended < 1974:
            no_barcode = True
        else:
            no_barcode = False

        issue = Issue.objects.get(id=self.id)

        if not self.publication_date:
            self.publication_date = ''

        if not self.key_date:
            self.key_date = ''

        if not self.price:
            self.price = ''

        revision = IssueRevision(changeset=changeset,
                                 issue=issue,
                                 number=self.number,
                                 volume=volume,
                                 series=display_series,
                                 publication_date=self.publication_date,
                                 key_date=self.key_date.replace('.', '-'),
                                 price=self.price,
                                 no_barcode=no_barcode,
                                 no_isbn=no_isbn,
                                 date_inferred=changeset.date_inferred)
        revision.save()
        return revision

class OldStory(models.Model):
    class Meta:
        app_label = 'old_gcd_data'
        db_table='stories'

    title = models.CharField(db_column='Title', max_length=255)
    feature = models.CharField(db_column='Feature', max_length=255)
    type = models.CharField(db_column='Type')
    sequence_number = models.IntegerField(db_column='Seq_No')

    page_count = models.DecimalField(db_column='Pg_Cnt', max_digits=10, decimal_places=3, null=True)
#models.IntegerField(db_column='Pg_Cnt')
    script = models.TextField(db_column='Script')
    pencils = models.TextField(db_column='Pencils')
    inks = models.TextField(db_column='Inks')
    colors = models.TextField(db_column='Colors')
    letters = models.TextField(db_column='Letters')
    editing = models.TextField(db_column='Editing')

    job_number = models.CharField(db_column='JobNo')
    genre = models.CharField(db_column='Genre')
    characters = models.TextField(db_column='Char_App')
    synopsis = models.TextField(db_column='Synopsis')
    reprint_notes = models.TextField(db_column='Reprints')
    notes = models.TextField(db_column='Notes')

    # Fields from issue.
    issue = models.ForeignKey(OldIssue, db_column='IssueId')

    # Fields related to change management.
    created = models.DateField(db_column='Created')
    modified = models.DateField(db_column='Modified')
    modified_time = models.TimeField(db_column='Modtime')
    migratory_class = MigratoryStoryRevision

    def convert(self, changeset):
        from apps.gcd.migration.history.migrate_status import convert_story_type
        # Fix types
        story_type = convert_story_type(self)

        if Story.objects.filter(id=self.id).exists():
            story_id = self.id
        else:
            story_id = None

        try:
            page_count = float(self.page_count)
        except:
            page_count = None

        revision = StoryRevision(changeset=changeset,
                                 story_id=story_id,
                                 issue_id=self.issue_id,
                                 sequence_number=self.sequence_number,
                                 title=self.title,
                                 feature=self.feature,
                                 type=story_type,
                                 page_count=page_count,
                                 script=self.script,
                                 pencils=self.pencils,
                                 inks=self.inks,
                                 colors=self.colors,
                                 letters=self.letters,
                                 editing=self.editing,
                                 genre=self.genre,
                                 characters=self.characters,
                                 synopsis=self.synopsis,
                                 reprint_notes=self.reprint_notes,
                                 job_number=self.job_number,
                                 notes=self.notes)
        revision.save()
        return revision

