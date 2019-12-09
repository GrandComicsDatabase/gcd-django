import sys
import logging
import datetime
from datetime import timedelta
from django.db import models, transaction, connection
from django.contrib.auth.models import User
from apps.gcd.models.publisher import Publisher
from apps.indexer.models import Indexer
from apps.oi.models import *
from apps.legacy.tools.history import MigratoryTable, LogRecord, \
                       EARLIEST_OLD_SITE, LATEST_OLD_SITE, EARLIEST_DATA_DATE
from apps.legacy.tools.history.story import MigratoryStoryRevision, LogStory
from functools import reduce

EPSILON = timedelta(5, 0, 0) # Five days

class MigratoryIssueRevision(MigratoryTable):
    class Meta(MigratoryTable.Meta):
        db_table = 'oi_issue_revision'
        managed = False

class LogIssue(LogRecord):
    class Meta(LogRecord.Meta):
        db_table = 'log_issue'
        app_label = 'gcd'

    IssueID = models.BigIntegerField()
    DisplayIssue = models.ForeignKey('gcd.Issue', db_column='IssueID')
    Issue = models.CharField(max_length=25)
    VolumeNum = models.IntegerField()
    SeriesID = models.IntegerField()
    DisplaySeries = models.ForeignKey('gcd.Series', db_column='SeriesID')

    Pub_Date = models.CharField(max_length=255)
    Key_Date = models.CharField(max_length=10)
    Price = models.CharField(max_length=25)

    ctype = CTYPES['issue']
    ctype_add = CTYPES['issue_add']
    migratory_class = MigratoryIssueRevision

    @classmethod
    def original_table(klass):
        return 'LogIssues'

    @classmethod
    def display_table(klass):
        return 'gcd_issue'

    @classmethod
    def source_id(klass):
        return 'IssueID'

    @classmethod
    def group_duplicate_fields(klass):
        return ('VolumeNum, SeriesID, Pub_Date collate utf8_bin, '
                'Price collate utf8_bin, Key_Date, Issue collate utf8_bin, IssueID')

    @classmethod
    def alter_table(klass, anon, database):
        if database == EARLIEST_OLD_SITE:
            cursor = connection.cursor()
            cursor.execute("""
ALTER TABLE log_issue
    %s,
    ADD INDEX (IssueID);
""" % klass._common_alter_clauses())
        else:
            cursor = connection.cursor()
            cursor.execute("""
ALTER TABLE log_issue
    DROP COLUMN IP,
    %s,
    ADD INDEX (IssueID);
""" % klass._common_alter_clauses())

        logging.info("Table altered, inserting data")
        cursor.execute("""
INSERT INTO log_issue
        (VolumeNum, SeriesID, Pub_Date, Price, Key_Date, Issue, IssueID, UserID)
    SELECT
        VolumeNum, SeriesID, Pub_Date, Price, Key_Date, Issue, ID, %d
    FROM %s.issues;
""" % (anon.id, database))

    @classmethod
    def fix_values(klass, anon, unknown_country, undetermined_language):
        cursor = connection.cursor()

        # For series attached to unrecognizable publishers, we set them
        # to the "unknown" publisher.  Adding an "unknown" series to every
        # publisher is impractical, so just delete orphaned issue records.
        cursor.execute("""
DELETE li.* FROM log_issue li LEFT OUTER JOIN gcd_series gs ON li.SeriesID = gs.id
    WHERE gs.id IS NULL;
UPDATE log_issue SET key_date = REPLACE(key_date, '.', '-');
""")
        cursor.close()
        klass.objects.filter(Pub_Date__isnull=True).update(Pub_Date='')
        klass.objects.filter(Key_Date__isnull=True).update(Key_Date='')
        klass.objects.filter(Price__isnull=True).update(Price='')

    @classmethod
    def get_related(klass):
        return ('DisplaySeries', 'DisplayIssue', 'User__user')

    @classmethod
    def add_special_times(klass):
        # Note that there are several rows in the log_issue table where the
        # timestamps exist and are slightly out of order w.r.t. the ID ordering.
        # These rows have the following IDs:
        # 53683, 53684, 58586, 60429, 64811, 73206, 108701, 109111, 145736,
        # 146347, 184169, 189359, 220502, 505125

        # Update the one date that can't be set to either the beginning or end
        # time of the old site.  Slot it in with the other two similarly-numbered
        # updates on that same day.
        klass.objects.filter(ID=289288)\
                     .update(Modified=datetime.datetime(2004, 7, 6, 0, 0, 3),
                             dt_inferred=True)

    @classmethod
    def migrate(klass, anon, use_earlier_data=False):
        from apps.legacy.tools.history.old_models import OldIssue, OldStory
        issue_history = klass.objects.order_by('IssueID', 'dt')
        related = klass.get_related()

        #issue_history = issue_history.filter(IssueID=174591)#541088)#205)

        if related is not None:
            issue_history = issue_history.filter(is_duplicate=False)\
                                         .select_related(*related)

        story_related = LogStory.get_related()

        last_i = None
        attached_stories = {}
        last_user = None
        last_dt = None
        adding_user = None
        icounter = 1
        scounter = 1
        for i in issue_history.iterator():
            if icounter % 1000 == 1:
                logging.info("Issue record %d" % icounter)
            icounter += 1

            # Find the stories, if any, that precede this issue.  We will
            # process them first, then the issue.  This allows us to properly
            # handle the case of stories that predate the first associated
            # issue object (a blank issue is constructed for this case inside
            # of gather_changeset()
            story_set = LogStory.objects.filter(is_duplicate=False)\
                                        .filter(DisplayIssue=i.DisplayIssue)\
                                        .filter(dt__lt=i.dt)
            if not use_earlier_data:
                if last_i is not None and last_i.IssueID == i.IssueID:
                    story_set = story_set.filter(dt__gte=last_i.dt)
            else:
                if last_i is not None and last_i.IssueID == i.IssueID:
                    story_set = story_set.filter(dt__gte=last_i.dt)
                else:
                    # issue with stories exists in dump from 2004-08
                    # do this once per issue
                    story_existed = OldStory.objects.using('earliest_old_site').filter(\
                        issue_id=i.IssueID).exists()
                    revision_exists = IssueRevision.objects.filter(issue_id=i.IssueID, created__lt=EARLIEST_DATA_DATE).exists()
                if not story_existed and story_set.exists() and not revision_exists:
                    # stories created after 2004-08, make assumption on indexer
                    # i.e. assume anon-stories with no time belong to 
                    # first actual indexer, determined from the issue-logs
                    anon_story_set = story_set.filter(UserID=anon.id, Modified__lt=datetime.date(2002,1,2))
                    for s in anon_story_set.order_by('dt').select_related(*story_related):
                        attached_stories[s.StoryID] = s
                        last_dt = s.dt
                    objects = klass.objects.order_by('IssueID', 'dt').filter(IssueID=i.IssueID).exclude(UserID=anon.id)
                    if objects.exists():
                        adding_user = objects[0].UserID
                    story_set = story_set.exclude(UserID=anon.id, Modified__lt=datetime.date(2002,1,2))
                else:
                    adding_user = None
            for s in story_set.order_by('dt').select_related(*story_related):
                if scounter % 5000 == 1:
                    logging.info("Story set loop %d" % scounter)
                scounter += 1

                # Check to see if we need to save based on this new story record.
                if last_user is not None and  s.UserID != last_user:
                    # Same story, but a different user, and at least one of
                    # the current objects needs saving.  So save under the old
                    # user and mark all stories as clean.
                    if not use_earlier_data:
                        klass.gather_changeset(last_i, attached_stories, anon)
                    else:
                        klass.gather_changeset(last_i, attached_stories, anon, 
                                               adding_user)
                        adding_user = None
                elif last_dt is not None and s.dt > last_dt + EPSILON:
                    # Same story, same user, but there's a large gap, so treat
                    # it as a new change.
                    if not use_earlier_data:
                        klass.gather_changeset(last_i, attached_stories, anon)
                    else:
                        klass.gather_changeset(last_i, attached_stories, anon, 
                                               adding_user)
                        adding_user = None

                # Either there was no old story, or we saved it, or
                # we determined that it can be supplanted by this one
                # because they were close enough together.  So track this new one.
                attached_stories[s.StoryID] = s
                last_user = s.UserID
                last_dt = s.dt

            # Now handle the issue record
            if last_i is not None and  i.IssueID != last_i.IssueID:
                # We have found a new issue, save the last state of the
                # previous issue and clear the tracked stories.

                # Look for stories after last issues datetime
                later_story_set = LogStory.objects.filter(is_duplicate=False)\
                                        .filter(DisplayIssue=last_i.DisplayIssue)\
                                        .filter(dt__gte=last_i.dt)
                for s in later_story_set.order_by('dt').select_related(*story_related):
                    if scounter % 5000 == 1:
                        logging.info("Story set loop %d" % scounter)
                    scounter += 1

                    # Check to see if we need to save based on this new story record.
                    if last_user is not None and  s.UserID != last_user:
                        # Same story, but a different user, and at least one of
                        # the current objects needs saving.  So save under the old
                        # user and mark all stories as clean.
                        if not use_earlier_data:
                            klass.gather_changeset(last_i, attached_stories, anon)
                        else:
                            klass.gather_changeset(last_i, attached_stories, anon, 
                                                   adding_user)
                            adding_user = None

                    elif last_dt is not None and s.dt > last_dt + EPSILON:
                        # Same story, same user, but there's a large gap, so treat
                        # it as a new change.
                        if not use_earlier_data:
                            klass.gather_changeset(last_i, attached_stories, anon)
                        else:
                            klass.gather_changeset(last_i, attached_stories, anon, 
                                                   adding_user)
                            adding_user = None

                    # Either there was no old story, or we saved it, or
                    # we determined that it can be supplanted by this one
                    # because they were close enough together.  So track this new one.
                    attached_stories[s.StoryID] = s
                    last_user = s.UserID
                    last_dt = s.dt

                if not use_earlier_data:
                    klass.gather_changeset(last_i, attached_stories, anon)
                else:
                    klass.gather_changeset(last_i, attached_stories, anon, 
                                           adding_user)
                    adding_user = None
                attached_stories = {}

            elif last_user is not None and i.UserID != last_user:
                # Same issue, but a different user.
                if not use_earlier_data:
                    klass.gather_changeset(last_i, attached_stories, anon)
                else:
                    klass.gather_changeset(last_i, attached_stories, anon, 
                                           adding_user)
                    adding_user = None

            elif last_dt is not None and i.dt > last_dt + EPSILON:
                # Same issue, same user, but there's a large gap.
                if not use_earlier_data:
                    klass.gather_changeset(last_i, attached_stories, anon)
                else:
                    klass.gather_changeset(last_i, attached_stories, anon, 
                                           adding_user)
                    adding_user = None

            last_i = i
            last_user = i.UserID
            last_dt = i.dt

        # And save anything left over at the end because we always
        # rely on a later object to trigger saves, and at this point
        # there aren't any more objects.

        # Look for stories after this issues datetime
        later_story_set = LogStory.objects.filter(is_duplicate=False)\
                                .filter(DisplayIssue=last_i.DisplayIssue)\
                                .filter(dt__gte=last_i.dt)
        for s in later_story_set.order_by('dt').select_related(*story_related):
            if scounter % 5000 == 1:
                logging.info("Story set loop %d" % scounter)
            scounter += 1

            # Check to see if we need to save based on this new story record.
            if last_user is not None and  s.UserID != last_user:
                # Same story, but a different user, and at least one of
                # the current objects needs saving.  So save under the old
                # user and mark all stories as clean.
                if not use_earlier_data:
                    klass.gather_changeset(last_i, attached_stories, anon)
                else:
                    klass.gather_changeset(last_i, attached_stories, anon, 
                                           adding_user)
                    adding_user = None

            elif last_dt is not None and s.dt > last_dt + EPSILON:
                # Same story, same user, but there's a large gap, so treat
                # it as a new change.
                if not use_earlier_data:
                    klass.gather_changeset(last_i, attached_stories, anon)
                else:
                    klass.gather_changeset(last_i, attached_stories, anon, 
                                           adding_user)
                    adding_user = None

            # Either there was no old story, or we saved it, or
            # we determined that it can be supplanted by this one
            # because they were close enough together.  So track this new one.
            attached_stories[s.StoryID] = s
            last_user = s.UserID
            last_dt = s.dt

        if not use_earlier_data:
            klass.gather_changeset(last_i, attached_stories, anon)
        else:
            klass.gather_changeset(last_i, attached_stories, anon, 
                                   adding_user)
            adding_user = None

    @classmethod
    def gather_changeset(klass, issue_record, attached_stories, anon, user=None):
        records = list(attached_stories.values())
        if issue_record is not None:
            records.append(issue_record)
        # We want to use the most recent revision for the changeset date+time.
        use_for_changeset = reduce(lambda a, b: a if a.dt >= b.dt else b, records)

        changeset = use_for_changeset.create_changeset(anon, user)
        if issue_record is None:
            # If there was no issue then there will always be at least one story.
            example_story = records[0]
            ir = IssueRevision(number=example_story.DisplayIssue.number,
                               issue=example_story.DisplayIssue,
                               series=example_story.DisplayIssue.series,
                               changeset=changeset,
                               date_inferred=changeset.date_inferred)
            ir.save()
            mr = klass.migratory_class.objects.get(id=ir.id)
            mr.created = changeset.created
            mr.modified = changeset.created
            mr.save()
        else:
            issue_record.create_revision(changeset, anon)

        for attached_story in attached_stories.values():
            attached_story.create_revision(changeset, anon)

    def convert(self, changeset):
        if self.VolumeNum is None:
            volume = ''
        else:
            volume = '%s' % self.VolumeNum

        if self.DisplaySeries.year_ended and self.DisplaySeries.year_ended < 1970:
            no_isbn = True
        else:
            no_isbn = False

        if self.DisplaySeries.year_ended and self.DisplaySeries.year_ended < 1974:
            no_barcode = True
        else:
            no_barcode = False

        revision = IssueRevision(changeset=changeset,
                                 issue=self.DisplayIssue,
                                 number=self.Issue,
                                 volume=volume,
                                 series=self.DisplaySeries,
                                 publication_date=self.Pub_Date,
                                 key_date=self.Key_Date,
                                 price=self.Price,
                                 no_barcode=no_barcode,
                                 no_isbn=no_isbn,
                                 date_inferred=changeset.date_inferred)
        revision.save()
        return revision

