import sys
import logging
import datetime
from django.db import models, transaction, connection
from django.contrib.auth.models import User
from apps.gcd.models.publisher import Publisher
from apps.gcd.models.indexer import Indexer
from apps.oi.models import *

from apps.gcd.migration.history.publisher import MigratoryPublisherRevision, \
                                                 LogPublisher
from apps.gcd.migration.history.series import MigratorySeriesRevision, LogSeries
# from apps.gcd.migration.history.issue import MigratoryIssueRevision, LogIssue
# from apps.gcd.migration.history.story import MigratoryStoryRevision, LogStory

def main():
    logging.basicConfig(level=logging.NOTSET,
                        stream=sys.stdout,
                        format='%(asctime)s %(levelname)s: %(message)s')

    anon = Indexer.objects.filter(user__username='anon').select_related('user')[0]
    for log_class in (LogPublisher,
                      LogSeries,
                      # LogIssue,
                     ):
        table_name = log_class._meta.db_table
        counter = 1
        log_history = log_class.objects.filter(is_duplicate=False)
        related = log_class.get_related()

        if related is not None:
            log_history = log_history.select_related(*related)

        for change in log_history.iterator():
            if counter % 1000 == 1:
                logging.info("Converting %s row %d" % (table_name, counter))
            counter += 1
            changeset = change.create_changeset(anon)
            change.create_revision(changeset, anon)

        # Commit the changes to the InnoDB tables for each object type.
        transaction.commit_unless_managed()

main()

