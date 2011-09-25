import sys
import logging
import datetime
from django.db import models, transaction, connection, settings
from django.contrib.auth.models import User
from apps.gcd.models.publisher import Publisher
from apps.oi.models import *

def main(file, object_type):
    old_id = 0
    for line in file:
        id = int(line.strip())
        if old_id != id:
            checked = object_type.objects.get(id=id)
            revisions = checked.revisions.filter(changeset__comments__text__contains='2002-11-13')
            if revisions.count() > 1: # there are two revisions with the same comment about being the first
                # the correct migrated changes have date 2002-01-01
                baseline = revisions.exclude(created=datetime.datetime(2002,01,01,00,00,00)).get()
                oldest = revisions.filter(created=datetime.datetime(2002,01,01,00,00,00)).get()
                is_changed = False
                # some safety checks
                for field_name in baseline.field_list():
                    old = getattr(baseline, field_name)
                    new = getattr(oldest, field_name)
                    if type(new) == unicode:
                        field_changed = old.strip() != new.strip()
                    else:
                        field_changed = old != new
                    is_changed |= field_changed
                if is_changed:
                    # some more safety checks
                    newest = checked.revisions.filter(created__lt=settings.NEW_SITE_CREATION_DATE).latest('created')
                    is_changed = False
                    for field_name in baseline.field_list():
                        old = getattr(newest, field_name)
                        new = getattr(baseline, field_name)
                        if type(new) == unicode:
                            field_changed = old.strip() != new.strip()
                        else:
                            field_changed = old != new
                        is_changed |= field_changed
                    if is_changed: # this shouldn't happen
                        for revision in revisions:
                            print revision.created, revision.id
                        print newest.created
                        print id
                        print checked.revisions.count()
                    else:
                        baseline.changeset.delete()
                        print id, 'one deleted'
                else:
                    baseline.changeset.delete()
                    print id, 'one deleted'
        old_id = id
        file.next()

main(open('series_with_log_fixes'), Series)
main(open('publisher_with_log_fixes'), Publisher)