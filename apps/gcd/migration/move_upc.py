import sys

from django.db import transaction, connection, settings
from django.contrib.auth.models import User

from apps.gcd.models import Issue
from apps.gcd.migration import migrate_reserve, do_auto_approve
from apps.gcd.templatetags.display import valid_barcode

anon = User.objects.get(username=settings.ANON_USER_NAME)

def migrate_upc(issues):
    changes = []    
    for i in issues[:200]:
        c = migrate_reserve(i, 'issue', 'to move UPC from notes to barcode')
        if c:
            ir = c.issuerevisions.all()[0]
            cand_upc = ir.notes[3:].strip(':# ').split()[0].strip('.;')
            if valid_barcode(cand_upc):            
                ir.barcode = cand_upc
                pos = ir.notes.find(cand_upc) + len(cand_upc)
                new_notes = ir.notes[pos:].lstrip(' ;.\r\n')
                ir.notes = new_notes
                ir.save()
                changes.append((c, True))
                c.submit()
            else:
                # no valid barcode, no reason to keep changeset in db
                c.discard(anon) # to cleanup issue reserved state
                c.delete() 
                print u"barcode not valid for %s: %s" % (i, i.notes)
                
    do_auto_approve(changes, 'moving of UPC from notes to barcode')

@transaction.commit_on_success
def main():
    # treat Marvel and DC extra
    issues = Issue.objects.filter(notes__istartswith='upc', deleted=False).exclude(series__publisher__id=78).exclude(series__publisher__id=54)
    migrate_upc(issues)
    # before 1987 Marvel didn't use the check digit, but added two numbers for the issue, so some by chance validate as EAN-13
    # take them out
    issues = Issue.objects.filter(notes__istartswith='upc', deleted=False).filter(series__publisher__id=78, key_date__gte='1987')
    migrate_upc(issues)
    # before July 1988 DC didn't use the check digit, but added two numbers for the issue, so some by chance validate as EAN-13
    # take them out
    issues = Issue.objects.filter(notes__istartswith='upc', deleted=False).filter(series__publisher__id=54, key_date__gte='1988.07')
    migrate_upc(issues)

if __name__ == '__main__':
    main()

