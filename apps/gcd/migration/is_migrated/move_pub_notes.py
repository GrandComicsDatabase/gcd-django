import sys

from django.db import transaction, connection

from apps.gcd.models import Series
from apps.gcd.migration import migrate_reserve, do_auto_approve

def move_pub_notes():
    changes = []

    series = Series.objects.filter(notes="", deleted=False).exclude(publication_notes="")

    for s in series[:250]:
        c = migrate_reserve(s, 'series', 'for moving publication notes to notes')
        if c:
            sr = c.seriesrevisions.all()[0]
            sr.notes = sr.publication_notes
            sr.publication_notes = ""
            sr.save()
            changes.append((c, True))
    do_auto_approve(changes, 'move of publication notes')
    return True

@transaction.commit_on_success
def main():
    move_pub_notes()

if __name__ == '__main__':
    main()

