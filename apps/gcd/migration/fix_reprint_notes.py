import sys

from django.db import transaction, connection, settings
from django.contrib.auth.models import User

from apps.gcd.models import Issue
from apps.gcd.migration import migrate_reserve, do_auto_approve

anon = User.objects.get(username=settings.ANON_USER_NAME)

def fix_reprint_notes(issues, old_reprint_note, new_reprint_note):
    changes = []
    for i in issues[:450]:
        c = migrate_reserve(i, 'issue', 'to fix reprint notes')
        if c:
            ir = c.issuerevisions.all()[0]
            crs = c.storyrevisions.filter(reprint_notes__icontains=old_reprint_note)
            for cr in crs:
                cr.reprint_notes = cr.reprint_notes.replace(old_reprint_note,
                                                            new_reprint_note)
                cr.save()
            changes.append((c, True))
        else:
            print "%s is reserved" % i
    do_auto_approve(changes, 'fixing reprint notes')

@transaction.commit_on_success
def main():
    old_reprint_note = '100 Bullets: A Foregone Tomorrow (DC, 2002 series) #nn'
    new_reprint_note = '100 Bullets (DC, 2000 series) #4 - A Foregone Tomorrow'
    issues=Issue.objects.filter(story__reprint_notes__icontains=old_reprint_note,
                                story__deleted=False).filter(deleted=False).distinct()
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note)

    old_reprint_note = '100 Bullets: Decayed (DC, 2006 series) #[nn]'
    new_reprint_note = '100 Bullets (DC, 2000 series) #10 - Decayed'
    issues=Issue.objects.filter(story__reprint_notes__icontains=old_reprint_note,
                                story__deleted=False).filter(deleted=False).distinct()
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note)

    old_reprint_note = '100 Bullets: Once Upon a Crime (DC, 2007 series) #[nn]'
    new_reprint_note = '100 Bullets (DC, 2000 series) #11 - Once Upon a Crime'
    issues=Issue.objects.filter(story__reprint_notes__icontains=old_reprint_note,
                                story__deleted=False).filter(deleted=False).distinct()
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note)

    old_reprint_note = '100 Bullets: Dirty (DC, 2008 series) #[nn]'
    new_reprint_note = '100 Bullets (DC, 2000 series) #12 - Dirty'
    issues=Issue.objects.filter(story__reprint_notes__icontains=old_reprint_note,
                                story__deleted=False).filter(deleted=False).distinct()
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note)

    old_reprint_note = '100 Bullets: Wilt (DC, 2008 series) #[nn]'
    new_reprint_note = '100 Bullets (DC, 2000 series) #13 - Wilt'
    issues=Issue.objects.filter(story__reprint_notes__icontains=old_reprint_note,
                                story__deleted=False).filter(deleted=False).distinct()
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note)

    old_reprint_note = 'Starman: Sins of the Father (DC, 1995 series) #[nn]'
    new_reprint_note = 'Starman (DC, 1995 series) #1 - Sins of the Father'
    issues=Issue.objects.filter(story__reprint_notes__icontains=old_reprint_note,
                                story__deleted=False).filter(deleted=False).distinct()
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note)

    old_reprint_note = 'American Century: Scars and Stripes (DC, 2001 series) #[nn]'
    new_reprint_note = 'American Century (DC, 2001 series) #1 - Scars and Stripes'
    issues=Issue.objects.filter(story__reprint_notes__icontains=old_reprint_note,
                                story__deleted=False).filter(deleted=False).distinct()
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note)

    old_reprint_note = 'American Century: Hollywood Babylon (DC, 2002 series) #[nn]'
    new_reprint_note = 'American Century (DC, 2001 series) #2 - Hollywood Babylon'
    issues=Issue.objects.filter(story__reprint_notes__icontains=old_reprint_note,
                                story__deleted=False).filter(deleted=False).distinct()
    fix_reprint_notes(issues, old_reprint_note, new_reprint_note)


if __name__ == '__main__':
    main()

