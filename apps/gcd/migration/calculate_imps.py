# -*- coding: utf-8 -*-
import sys
import logging
from django.db import transaction
from django.db.models import Q
from django.contrib.auth.models import User
from apps.gcd.models.indexer import Indexer, IMPS_FOR_APPROVAL
from apps.oi import states
from apps.oi.models import Changeset

@transaction.commit_on_success
def main():

    logging.basicConfig(level=logging.NOTSET,
                        stream=sys.stdout,
                        format='%(asctime)s %(levelname)s: %(message)s')

    anon = User.objects.get(username='anon')
    n = 1
    for c in Changeset.objects.filter(Q(approver__isnull=False) |
                                      Q(state=states.PENDING))\
                              .exclude(Q(indexer=anon) & Q(approver=anon))\
                              .filter(migrated=False):
        if n % 500 == 1:
            logging.info("Calculating changeset %d" % n)
        c.calculate_imps()
        c.save()
        if c.state == states.APPROVED:
            c.indexer.indexer.add_imps(c.total_imps())
        if c.approver is not None and \
           c.state in (states.APPROVED, states.DISCARDED):
            c.approver.indexer.add_imps(IMPS_FOR_APPROVAL)
        n += 1

main()

