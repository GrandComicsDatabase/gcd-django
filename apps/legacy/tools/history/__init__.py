import sys
import logging
import datetime
from django.db import models, transaction, connection
from django.contrib.auth.models import User
from apps.gcd.models.publisher import Publisher
from apps.indexer.models import Indexer
from apps.oi.models import *

LATEST_OLD_SITE = 'latest_old_site'
EARLIEST_OLD_SITE = 'earliest_old_site'

EARLIEST_DATA_DATE = datetime.datetime(2004,9,1,0,0)

COMMENT_TEXT = """This change history was migrated from the old site."""
COMMENT_TEXT_FOR_ADD = """
This is the oldest change we have for this object, so it shows as the addition.
However, it may just be the state of the object at the time when the data was first imported into the old site circa %s.
""" % settings.OLD_SITE_CREATION_DATE
COMMENT_TEXT_FOR_ADD_LATER = """
This is the oldest change we have for this object, so it shows as the addition.
It was added sometime after %s, and is likely close in time to the next change with an actual date.
The assignment of an indexer to this changeset is based on a heuristic, which in some rare situations results in wrong results.
"""  % EARLIEST_DATA_DATE

class MigratoryTable(models.Model):
    class Meta:
        abstract = True
        app_label = 'gcd'
    created = models.DateTimeField()
    modified = models.DateTimeField()

class MigratoryChangeset(MigratoryTable):
    class Meta(MigratoryTable.Meta):
        db_table = 'oi_changeset'
        managed = False

class LogRecord(models.Model):
    class Meta:
        abstract = True
        app_label = 'gcd'

    ID = models.BigIntegerField(primary_key=True)
    Modified = models.DateField(db_column='modified_new', db_index=True)
    ModTime = models.TimeField(db_column='modtime_new', db_index=True)
    UserID = models.IntegerField(db_column='userid_new')
    User = models.ForeignKey('indexer.Indexer', db_column='userid_new')
    is_add = models.BooleanField(default=False, db_index=True)
    is_duplicate = models.BooleanField(default=False, db_index=True)
    old_user_id = models.IntegerField(db_column='UserID')

    # Ultimately, it's easier to work with a DateTime field.
    # modified_new and modtime_new are used as an intermediate step.
    dt = models.DateTimeField(null=True, db_index=True)
    dt_inferred = models.BooleanField(default=False, db_index=True)

    @classmethod
    def original_table(klass):
        raise NotImplementedError

    @classmethod
    def display_table(klass):
        raise NotImplementedError

    @classmethod
    def source_id(klass):
        raise NotImplementedError

    @classmethod
    def extra_delete_where(klass):
        return ''

    @classmethod
    def group_duplicate_fields(klass):
        raise NotImplementedError

    @classmethod
    def _common_alter_clauses(klass):
        return """
    DROP COLUMN ActionType,
    ADD COLUMN sort_old int(11) default NULL,
    ADD COLUMN sort_new int(11) default NULL,
    ADD COLUMN userid_new int(11) default NULL,
    ADD COLUMN modified_new date default NULL,
    ADD COLUMN modtime_new time default NULL,
    ADD COLUMN is_add tinyint(1) NOT NULL default 0,
    ADD COLUMN is_duplicate tinyint(1) NOT NULL default 0,
    ADD COLUMN dt datetime,
    ADD COLUMN dt_inferred tinyint(1),
    CONVERT TO CHARACTER SET utf8,
    ADD INDEX (sort_old),
    ADD INDEX (sort_new),
    ADD INDEX (modified_new),
    ADD INDEX (modtime_new),
    ADD INDEX (is_add),
    ADD INDEX (is_duplicate),
    ADD INDEX (dt),
    ADD INDEX (dt_inferred),
    MODIFY COLUMN ID bigint(11) unsigned NOT NULL auto_increment
"""

    @classmethod
    def fix_values(klass, anon, unknown_country, undetermined_language):
        pass

    @classmethod
    def add_special_times(klass):
        pass

    @classmethod
    def add_times(klass, no_times, early=False):
        # dt_inferred is set to True whenever the *date* portion is inferred.
        # January 1, 2002 is earlier than anything currently in the DB.
        if early:
            klass.objects.filter(Modified__isnull=True)\
                         .update(Modified=datetime.date(2002, 1, 1),
                                 dt_inferred=True)
        else:
            klass.objects.filter(Modified__isnull=True, is_add=True)\
                         .update(Modified=datetime.date(2002, 1, 1),
                                 dt_inferred=True)
            klass.objects.filter(Modified__isnull=True, is_add=False)\
                         .update(Modified=datetime.date(2009, 11, 1),
                                 dt_inferred=True)
        klass.add_special_times()

        # fill in all the null modifiedtimes, making sure that if there are
        # multiple records for an object the time for the first is
        # 00:00:01, the next is 00:00:02, etc. (additions are pre-set to 00:00:00).
        source_id = klass.source_id()
        no_times = no_times.order_by(source_id, 'ID')
        try:
            id = getattr(no_times[0], source_id)
            logging.info("Fixing times on %d rows" % no_times.count())
        except IndexError:
            logging.info("No times to fix.")
            return

        seconds = 1
        for change in no_times:
            new_id = getattr(change, source_id)
            if id != new_id:
                seconds = 1
                id = new_id
            new_time = datetime.time(0, 0, seconds)
            change.ModTime = new_time
            change.save()
            seconds += 1

        # ADDTIME won't work unless all dates and times are not NULL.
        cursor = connection.cursor()
        cursor.execute("""UPDATE %s SET dt=ADDTIME(modified_new, modtime_new);""" %
                       klass._meta.db_table)
        cursor.close()

    @classmethod
    def get_related(klass):
        return None

    @classmethod
    def migrate(klass, anon, use_earlier_data=False):
        table_name = klass._meta.db_table

        # Migrate in order so that IMPs can be calculated- for any change,
        # the previous change, if any, must be migrated in order for IMPs
        # to be correct.
        counter = 1
        log_history = klass.objects.filter(is_duplicate=False)\
                                   .order_by(klass.source_id(), 'dt')
        related = klass.get_related()

        if related is not None:
            log_history = log_history.select_related(*related)

        for change in log_history.iterator():
            if counter % 1000 == 1:
                logging.info("Converting %s row %d" % (table_name, counter))
            counter += 1
            changeset = change.create_changeset(anon)
            change.create_revision(changeset, anon)

            #if not change.revision_exists():
                # temporary change for series history fixes
                #if counter % 1000 == 1:
                    #logging.info("Converting %s row %d" % (table_name, counter))
                #print change.SeriesID
                #print counter, change.DisplaySeries, change.Bk_Name, change.dt
                #print change.PublisherID
                #print change.DisplayPublisher, change.PubName, change.dt
                #counter += 1
                #changeset = change.create_changeset(anon)
                #change.create_revision(changeset, anon)

    def create_changeset(self, anon, user=None):
        # create changeset
        if user:
            indexer_user=Indexer.objects.get(id=user).user
        else:
            indexer_user=self.User.user
        ctype = self.ctype

        # self.dt_inferred may be None so we can't just assign it as is.
        date_inferred = False
        if self.dt_inferred is True:
            date_inferred = True

        changeset = Changeset(indexer=indexer_user, approver=anon.user,
                              state=states.APPROVED, change_type=ctype,
                              migrated=True, date_inferred=date_inferred)
        changeset.save()

        # Circumvent automatic field behavior.
        # all dates and times guaranteed to be valid
        mc = MigratoryChangeset.objects.get(id=changeset.id)
#        if user: # use_earlier_data
#            if self.dt < EARLIEST_DATA_DATE:
#                mc.created = EARLIEST_DATA_DATE
#            else:
#                mc.created = self.dt
#        else:
        mc.created = self.dt
        mc.modified = mc.created
        mc.save()
        changeset = Changeset.objects.get(id=changeset.id)

        comment_text = COMMENT_TEXT
        if self.is_add:
            if user:
                comment_text += COMMENT_TEXT_FOR_ADD_LATER
            else:
                comment_text += COMMENT_TEXT_FOR_ADD

        changeset.comments.create(commenter=indexer_user,
                                  text=comment_text,
                                  old_state=states.APPROVED,
                                  new_state=states.APPROVED)
        comment = changeset.comments.all()[0]
        comment.created = changeset.created
        comment.save()

        return changeset

    def create_revision(self, changeset, anon):
        revision = self.convert(changeset)

        # Circumvent automatic field behavior.
        mr = self.migratory_class.objects.get(id=revision.id)
        mr.created = changeset.created
        mr.modified = changeset.created
        mr.save()

