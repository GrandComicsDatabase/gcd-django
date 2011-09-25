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
from apps.gcd.migration.history.issue import MigratoryIssueRevision, LogIssue

def main():
    logging.basicConfig(level=logging.NOTSET,
                        stream=sys.stdout,
                        format='%(asctime)s %(levelname)s: %(message)s')

    anon = Indexer.objects.filter(user__username='anon').select_related('user')[0]
    for log_class in (LogPublisher,
                      #LogSeries,
                      #LogIssue,
                     ):
        log_class.migrate(anon)

        # Commit the changes to the InnoDB tables for each object type.
        transaction.commit_unless_managed()

main()

