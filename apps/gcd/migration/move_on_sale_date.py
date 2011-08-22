import sys

from django.db import transaction, connection, settings
from django.contrib.auth.models import User

from apps.gcd.models import Issue
from apps.gcd.migration import migrate_reserve, do_auto_approve

anon = User.objects.get(username=settings.ANON_USER_NAME)
length = len("U.S. on sale date: ")

def migrate_osd(issues):
    changes = []
    for i in issues[:450]:
        c = None
        try:
            date = i.notes[length:length+10]
            year = int(date[:4])
            month = int(date[5:7])
            day = int(date[8:10])
            c = migrate_reserve(i, 'issue', 'to move the on-sale date')
        except ValueError:
            print "on-sale date not used", i, i.notes
        if c:
            ir = c.issuerevisions.all()[0]
            ir.notes = ir.notes[length+10:].lstrip('.').strip()
            if ir.notes:
                print 'new:', ir.notes
            print 'old:', ir.issue.notes
            ir.year_on_sale = year
            ir.month_on_sale = month
            ir.day_on_sale = day
            ir.save()
            changes.append((c, True))

    do_auto_approve(changes, 'moving of on-sale date information')

@transaction.commit_on_success
def main():
    issues = Issue.objects.filter(notes__istartswith="U.S. on sale date: 1999-", deleted=False)
    migrate_osd(issues)
    issues = Issue.objects.filter(notes__istartswith="U.S. on sale date: 20", deleted=False)
    migrate_osd(issues)

if __name__ == '__main__':
    main()

