import sys
import logging
import datetime
import django
from django.db import models, transaction, connection
from django.contrib.auth.models import User
from apps.gcd.models.publisher import Publisher
from apps.indexer.models import Indexer
from apps.oi.models import *

django.setup()
from apps.legacy.tools.history.publisher import MigratoryPublisherRevision, \
                                                 LogPublisher
from apps.legacy.tools.history.series import MigratorySeriesRevision, LogSeries
#from apps.gcd.migration.history.issue_use_earliest import MigratoryIssueRevision, LogIssue
from apps.legacy.tools.history.issue import MigratoryIssueRevision, LogIssue

def main(use_earlier_data=False):
    logging.basicConfig(level=logging.NOTSET,
                        stream=sys.stdout,
                        format='%(asctime)s %(levelname)s: %(message)s')

    anon = Indexer.objects.filter(user__username='anon').select_related('user')[0]
    for log_class in (#LogPublisher,
                      #LogSeries,
                      LogIssue,
                     ):
        log_class.migrate(anon, use_earlier_data)

        # Commit the changes to the InnoDB tables for each object type.
        transaction.commit_unless_managed()

if __name__ == "__main__":
    django.setup()
    if len(sys.argv) != 2:
        print("give 1 (earliest) / 2 latest")
        sys.exit()
    if sys.argv[1] == '1':
        main(use_earlier_data=False)
    elif sys.argv[1] == '2':
        main(use_earlier_data=True)
    else:
        print("not valid: %s" % sys.argv[1])
