import sys
import logging
from datetime import datetime, timedelta
from django.db import models, transaction, connection
from django.contrib.auth.models import User
from apps.gcd.models.publisher import Publisher
from apps.gcd.models.indexer import Indexer
from apps.oi.models import *
from apps.gcd.migration.history import MigratoryTable, LogRecord

class MigratoryStoryRevision(MigratoryTable):
    class Meta(MigratoryTable.Meta):
        db_table = 'oi_story_revision'
        managed = False

class LogStory(LogRecord):
    class Meta(LogRecord.Meta):
        db_table = 'log_story'
        app_label = 'gcd'

    StoryID = models.BigIntegerField()
    DisplayStory = models.ForeignKey('gcd.Story', db_column='StoryID')
    IssueID = models.IntegerField()
    DisplayIssue = models.ForeignKey('gcd.Issue', db_column='IssueID')

    Seq_No = models.IntegerField()
    Title = models.CharField(max_length=255)
    Feature = models.CharField(max_length=255)
    Type = models.CharField(max_length=255)
    StoryType = models.ForeignKey('gcd.StoryType', db_column='type_id')
    Pg_Cnt = models.IntegerField()

    Script = models.CharField(max_length=255)
    Pencils = models.CharField(max_length=255)
    Inks = models.CharField(max_length=255)
    Colors = models.CharField(max_length=255)
    Letters = models.CharField(max_length=255)
    Editing = models.CharField(max_length=255)

    Genre = models.CharField(max_length=255)
    Char_App = models.CharField(max_length=255)
    Synopsis = models.TextField(blank=True)
    Reprints = models.TextField(blank=True)
    JobNo = models.CharField(max_length=25)
    Notes = models.TextField(blank=True)

    ctype = CTYPES['issue']
    ctype_add = ctype
    migratory_class = MigratoryStoryRevision

    @classmethod
    def original_table(klass):
        return 'LogStories'

    @classmethod
    def display_table(klass):
        return 'gcd_story'

    @classmethod
    def source_id(klass):
        return 'StoryID'

    @classmethod
    def group_duplicate_fields(klass):
        return ('Seq_No, Title collate utf8_bin, Feature collate utf8_bin, '
                'Type collate utf8_bin, Pg_Cnt, Script collate utf8_bin, '
                'Pencils collate utf8_bin, Inks collate utf8_bin, '
                'Colors collate utf8_bin, Letters collate utf8_bin, '
                'Editing collate utf8_bin, Genre collate utf8_bin, '
                'Char_App collate utf8_bin, Synopsis collate utf8_bin, '
                'Reprints collate utf8_bin, JobNo collate utf8_bin, '
                'Notes collate utf8_bin')

    @classmethod
    def alter_table(klass, anon):
        cursor = connection.cursor()
        cursor.execute("""
ALTER TABLE log_story
    MODIFY COLUMN Script longtext,
    MODIFY COLUMN Pencils longtext,
    MODIFY COLUMN Inks longtext,
    MODIFY COLUMN Colors longtext,
    MODIFY COLUMN Letters longtext,
    MODIFY COLUMN Editing longtext,
    MODIFY COLUMN Char_App longtext,
    MODIFY COLUMN Synopsis longtext,
    MODIFY COLUMN Reprints longtext,
    MODIFY COLUMN Notes longtext,
    ADD INDEX (Type),
    ADD COLUMN type_id int(11) default NULL,
    %s,
    ADD INDEX (IssueID),
    ADD INDEX (StoryID);
""" % klass._common_alter_clauses())

        logging.info("Table altered, inserting data.")
        cursor.execute("""
INSERT INTO log_story
        (StoryID, IssueID, Seq_No, Title, Feature, Type, Pg_Cnt,
         Script, Pencils, Inks, Colors, Letters, Editing,
         Genre, Char_App, Synopsis, Reprints, JobNo, Notes,
         UserID)
    SELECT
        s.id, s.issue_id, s.sequence_number, s.title, s.feature, t.name,
        s.page_count, s.script, s.pencils, s.inks, s.colors, s.letters, s.editing,
        s.genre, s.characters, s.synopsis, s.reprint_notes, s.job_number, s.notes,
        %d
    FROM
        migrated.gcd_story s INNER JOIN migrated.gcd_story_type t ON s.type_id=t.id;
""" % anon.id)

    @classmethod
    def fix_values(klass, anon, unknown_country, undetermined_language):
        cursor = connection.cursor()

        # Remove orphaned stories- no sensible "unknown" issue for them.
        cursor.execute("""
DELETE ls FROM log_story ls LEFT OUTER JOIN gcd_issue gi ON ls.IssueID = gi.id
    WHERE gi.id IS NULL;
""")
        cursor.close()

        # Fix types, setting up join field.
        klass.objects.filter(Type='activity').update(
            StoryType=StoryType.objects.get(name='activity'))
        klass.objects.filter(Type__in=('advertisement', 'ad')).update(
            StoryType=StoryType.objects.get(name='advertisement'))
        klass.objects.filter(Type__in=('backcovers',
                                       'backcover',
                                       'back cover')).update(
            StoryType=StoryType.objects.get(
              name='(backcovers) *do not use* / *please fix*'))
        klass.objects.filter(Type__in=('biography', 'bio',
                                       'biography (nonfictional)')).update(
            StoryType=StoryType.objects.get(name='biography (nonfictional)'))
        klass.objects.filter(Type__in=('cartoon', 'cartoons')).update(
            StoryType=StoryType.objects.get(name='cartoon'))
        klass.objects.filter(Type__in=('cover', 'front cover')).update(
            StoryType=StoryType.objects.get(name='cover'))
        klass.objects.filter(Type__in=('cover reprint', 'cover reprints',
                                'cover reprint (on interior page)')).update(
            StoryType=StoryType.objects.get(
              name='cover reprint (on interior page)'))
        klass.objects.filter(Type='credits').update(
            StoryType=StoryType.objects.get(name='credits'))
        klass.objects.filter(Type='filler').update(
            StoryType=StoryType.objects.get(name='filler'))
        klass.objects.filter(Type__in=('foreword', 'foreward', 'intro',
          'introduction', 'foreword, introduction, preface, afterword')).update(
            StoryType=StoryType.objects.get(
              name='foreword, introduction, preface, afterword'))
        klass.objects.filter(Type__in=('insert', 'dust jacket',
                                       'insert or dust jacket')).update(
            StoryType=StoryType.objects.get(name='insert or dust jacket'))
        klass.objects.filter(Type__in=('letter', 'letter page',
                                       'letters page', 'letters')).update(
            StoryType=StoryType.objects.get(name='letters page'))
        klass.objects.filter(Type='photo story').update(
            StoryType=StoryType.objects.get(name='photo story'))
        klass.objects.filter(Type__in=('pinup', 'illustration', 'illustrations',
                                       'pin-up', 'pin up')).update(
            StoryType=StoryType.objects.get(name='illustration'))
        klass.objects.filter(Type='profile', 'character profile').update(
            StoryType=StoryType.objects.get(name='character profile'))
        klass.objects.filter(Type__in=('promo', 'house ad', 'house ads',
                                       'promo (ad from the publisher)')).update(
            StoryType=StoryType.objects.get(name='promo (ad from the publisher)'))
        klass.objects.filter(Type__in=('psa', 'public service',
                                       'public service announcement')).update(
            StoryType=StoryType.objects.get(name='public service announcement'))
        klass.objects.filter(Type='recap').update(
            StoryType=StoryType.objects.get(name='recap'))
        klass.objects.filter(Type='story').update(
            StoryType=StoryType.objects.get(name='comic story'))
        klass.objects.filter(Type='text article').update(
            StoryType=StoryType.objects.get(name='text article'))
        klass.objects.filter(Type='text story').update(
            StoryType=StoryType.objects.get(name='text story'))
        klass.objects.filter(Type='statement of ownership').update(
            StoryType=StoryType.objects.get(name='statement of ownership'))

        # Anything that didn't get set is unknown.  Sadly this will obscure the
        # history of a lot of the type clean-up and conversion to English of
        # some translated types, but no obvious solution to that at this time.
        # We'll still have the old data if we ever really need it.
        klass.objects.filter(StoryType__isnull=True).update(
            StoryType=StoryType.objects.get(name='(unknown)'))


        # Fix null values in other fields.
        klass.objects.filter(Seq_No__isnull=True).update(Seq_No=9999)
        klass.objects.filter(Title__isnull=True).update(Title='')
        klass.objects.filter(Feature__isnull=True).update(Feature='')

        klass.objects.filter(Script__isnull=True).update(Script='')
        klass.objects.filter(Pencils__isnull=True).update(Pencils='')
        klass.objects.filter(Inks__isnull=True).update(Inks='')
        klass.objects.filter(Colors__isnull=True).update(Colors='')
        klass.objects.filter(Letters__isnull=True).update(Letters='')
        klass.objects.filter(Editing__isnull=True).update(Editing='')

        klass.objects.filter(Genre__isnull=True).update(Genre='')
        klass.objects.filter(Char_App__isnull=True).update(Char_App='')
        klass.objects.filter(Synopsis__isnull=True).update(Synopsis='')
        klass.objects.filter(Reprints__isnull=True).update(Reprints='')
        klass.objects.filter(JobNo__isnull=True).update(JobNo='')
        klass.objects.filter(Notes__isnull=True).update(Notes='')

    @classmethod
    def get_related(klass):
        return ('DisplayStory', 'DisplayIssue', 'User__user')

    @classmethod
    def add_times(klass, no_times, early=False):
        """
        None of the shortcuts work with the log_story table, so it just
        has to be brute force ordered by time.  However, it does have the
        nice property that Modified and ModTime are always either both NULL
        or both not NULL.
        """
        # "Dawn of time" for the previous site.
        dawn_of_time = datetime(2002, 1, 1, 0, 0, 0)
        delta = timedelta(0, 1, 0)

        # There is no story zero, this saves us from "is None" checks.
        last_story_id = 0
        last_dt = dawn_of_time

        stories = klass.objects.filter(is_duplicate=False)
        total = stories.count()
        counter = 1
        for story in stories.order_by('StoryID', 'ID').iterator():
            if counter % 5000 == 1:
                logging.info("Setting times for row %d out of %d" %
                             (counter, total))
            if story.Modified is None:
                if story.StoryID != last_story_id:
                    story.dt = dawn_of_time
                else:
                    this_dt = last_dt + delta
                    story.dt = this_dt
                story.dt_inferred = True
            else:
                story.dt = datetime.combine(story.Modified, story.ModTime)
            story.save()
            last_dt = story.dt
            last_story_id = story.StoryID
            counter += 1

    def convert(self, changeset):
        revision = StoryRevision(changeset=changeset,
                                 story_id=self.StoryID,
                                 issue_id=self.IssueID,
                                 sequence_number=self.Seq_No,
                                 title=self.Title,
                                 feature=self.Feature,
                                 type=self.StoryType,
                                 page_count=self.Pg_Cnt,
                                 script=self.Script,
                                 pencils=self.Pencils,
                                 inks=self.Inks,
                                 colors=self.Colors,
                                 letters=self.Letters,
                                 editing=self.Editing,
                                 genre=self.Genre,
                                 characters=self.Char_App,
                                 synopsis=self.Synopsis,
                                 reprint_notes=self.Reprints,
                                 job_number=self.JobNo,
                                 notes=self.Notes,
                                 date_inferred=changeset.date_inferred)
        revision.save()
        return revision

