import sys

from django.db import transaction, connection

from apps.gcd.models import Series
from apps.legacy.tools import migrate_reserve, do_auto_approve

@transaction.commit_on_success
def mark_as_singleton():
    changes = []

    series = Series.objects.filter(issue__number='[nn]', 
        issue__indicia_frequency='').filter(issue_count=1, is_singleton=False)

    for s in series[:200]:
        c = migrate_reserve(s, 'series', 'for marking as singleton')
        if c:
            sr = c.seriesrevisions.get()
            sr.is_singleton = True
            sr.save()
            changes.append((c, True))
    do_auto_approve(changes, 'marking of singleton')
    return True

@transaction.commit_on_success
def main():
    for i in range(100):
        mark_as_singleton()

if __name__ == '__main__':
    main()

