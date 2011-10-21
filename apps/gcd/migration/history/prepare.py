import sys
import logging
import datetime
from django.db import models, transaction, connection
from django.contrib.auth.models import User
from apps.gcd.models.publisher import Publisher
from apps.gcd.models.indexer import Indexer
from apps.oi.models import *

#from apps.gcd.migration.history.publisher import MigratoryPublisherRevision, \
#                                                 LogPublisher
#from apps.gcd.migration.history.series import MigratorySeriesRevision, LogSeries
#from apps.gcd.migration.history.issue import MigratoryIssueRevision, LogIssue
#from apps.gcd.migration.history.story import MigratoryStoryRevision, LogStory
from apps.gcd.migration.history.publisher import LogPublisher
from apps.gcd.migration.history.series import LogSeries
from apps.gcd.migration.history.issue import LogIssue
from apps.gcd.migration.history.story import LogStory

def main():
    logging.basicConfig(level=logging.NOTSET,
                        stream=sys.stdout,
                        format='%(asctime)s %(levelname)s: %(message)s')

    anon = Indexer.objects.filter(user__username='anon').select_related('user')[0]
    unknown_country = Country.objects.get(name='(unknown)')
    try:
        undetermined_language = Language.objects.get(code='und')
    except Language.DoesNotExist:
        undetermined_language = Language(code='und', name='(undetermined)')
        undetermined_language.save()
    try:
        unknown_story_type = StoryType.objects.get(name='(unknown)')
    except StoryType.DoesNotExist:
        unknown_story_type = StoryType(name='(unknown)', sort_code=100)
        unknown_story_type.save()
        unknown_story_type.sort_code = models.F('id')
        unknown_story_type.save()

    cursor = connection.cursor()

    # Ray had two accounts which were merged in the original migration.
    fetch_indexer = "SELECT ID FROM GCDOnline.Indexers WHERE username='%s'"
    cursor.execute(fetch_indexer % 'rayb')
    ray1 = cursor.fetchone()[0]
    cursor.execute(fetch_indexer % 'RaySB')
    ray2 = cursor.fetchone()[0]
    cursor.close()

    for old_table, log_class in (#('LogPublishers', LogPublisher),
                                 #('LogSeries', LogSeries),
                                 ('LogIssues', LogIssue),
                                 ('LogStories', LogStory),
                                ):
        table_name = log_class._meta.db_table

        logging.info("Creating %s" % table_name)
        cursor = connection.cursor()
        cursor.execute("""
CREATE TABLE %s (PRIMARY KEY (id)) ENGINE=MyISAM
  SELECT * FROM GCDOnline.%s;
""" % (table_name, log_class.original_table()));

        logging.info("Altering table %s and loading data" % table_name)
        log_class.alter_table(anon)
        log_class.fix_values(anon, unknown_country, undetermined_language)

        logging.info("Deleting rows that don't match %s" %
                     log_class.display_table())
        cursor.execute("""
DELETE l FROM %s l LEFT OUTER JOIN %s d
               ON l.%s = d.id
    WHERE d.id IS NULL %s;
""" % (table_name, log_class.display_table(),
       log_class.source_id(), log_class.extra_delete_where()))

        # Set Ray's 2nd login to his first login, and set NULL users to anonymous.
        log_class.objects.filter(old_user_id=ray2).update(old_user_id=ray1)
        log_class.objects.filter(old_user_id__isnull=True)\
                         .update(old_user_id=anon.id)

        logging.info("Setting up sort codes for %s" % table_name)
        cursor.execute("""
SET @sort_old=1;
SET @sort_new=0;
UPDATE %s SET sort_old=@sort_old:=@sort_old + 1,
              sort_new=@sort_new:=@sort_new + 1
    ORDER BY %s, id;
""" % (table_name, log_class.source_id()))

        # Somehow afer this we can't execute further queries.  Close to clear
        # state.  There must be a better way to handle this...
        cursor.close()
        cursor = connection.cursor()

        # Left outer join with this table order because we want the pairing
        # where the counter for each publihser is smallest to have nothing
        # on the old side.  For the first object, there is no row
        # with "old" == 1.  For the rest of the objects, the
        # "AND old.<source_id>=new.<source_id> filters out the old side
        # of the two sort columns that would otherwise match across different
        # that just happen to sort next to each other.
        # Those first rows will have a NULL old ID, so set those to the
        # anonymous user at the dawn of time, and consider them all additions.
        logging.info("Fixing alignment of users and times for %s" % table_name)
        cursor.execute("""
SET @first_day='2002-01-01';
SET @first_time='00:00:00';
UPDATE %s new LEFT OUTER JOIN %s old
    ON old.sort_old=new.sort_new AND old.%s=new.%s
    SET new.userid_new=IF(old.id IS NULL, %d, old.UserID),
        new.modified_new=IF(old.id IS NULL, @first_day, old.Modified),
        new.modtime_new=IF(old.id IS NULL, @first_time, old.ModTime),
        new.is_add=IF(old.id IS NULL, 1, 0);
""" % (table_name, table_name, log_class.source_id(), log_class.source_id(),
       anon.id))

        # Somehow afer this we can't execute further queries.  Close to clear
        # state.  There must be a better way to handle this...
        cursor.close()
        cursor = connection.cursor()

        logging.info("Marking duplicate rows for %s" % table_name)
        # delete duplicate rows where it is a dupe if the "group by"
        # columns are the same.
        cursor.execute("""
CREATE TEMPORARY TABLE %s_helper (id int(11) PRIMARY KEY, is_add int)
    SELECT MIN(ID) AS id, MAX(is_add) AS is_add FROM %s
    GROUP BY %s;

UPDATE %s l LEFT OUTER JOIN %s_helper h ON l.ID=h.id
    SET l.is_duplicate=1 WHERE h.id IS NULL;
""" % (table_name, table_name, log_class.group_duplicate_fields(),
       table_name, table_name))

        # Close to tidy up.
        cursor.close()

        logging.info("Fixing blank timestamps")
        early = False
        if log_class is LogIssue:
            early = True
        log_class.add_times(log_class.objects.filter(ModTime__isnull=True), early)

        logging.info("Done with preparation for %s" % table_name)
        transaction.commit_unless_managed()

main()

