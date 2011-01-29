import sys
from stdnum import isbn
from django.conf import settings
from apps.oi.models import *
from apps.oi.views import _do_reserve

anon = User.objects.get(username=settings.ANON_USER_NAME)

def migrate_reserve(issue, comment):
    if issue.reserved == False:
        changeset=_do_reserve(anon, issue, 'issue')
        if changeset == None:
            raise ValueError
        changeset.state=states.OPEN
        changeset.save()
        comment = changeset.comments.create(commenter=anon,
          text='This is an automatically generated changeset %s.' % comment,
          old_state=states.UNRESERVED, new_state=states.OPEN)
        # not really race conflict save, but we cannot do a double click anyway
        issue.reserved=True 
        issue.save()
        return changeset
    else:
        return "Issue %s is reserved" % issue

def do_auto_approve(liste, comment):
   for (issue, is_approvable) in liste:
        if type(issue) == Changeset:
            # in principle another approver could take this change
            # if already approved, this gets another comment, not a problem
            # if not approved till now, this gets approved, not really a problem
            # if rejected, this gets approved, overrriding the approver
            if is_approvable:
                issue.approver = anon
                issue.state = states.REVIEWING
                issue.approve(notes='Automatically approved %s.' % comment)
                print "change is auto-approved:", issue

def migrate_isbn(change):
    ''' two return values: change valid, can be autoapproved '''
    issue_rev = change.issuerevisions.get()
    cand_isbn = issue_rev.notes[4:].strip(':# ').split()[0].strip('.;')
    if isbn.is_valid(cand_isbn):
        issue_rev.isbn = cand_isbn
        pos = issue_rev.notes.find(cand_isbn) + len(cand_isbn)
        new_notes = issue_rev.notes[pos:].lstrip(' ;.\r\n')
        if change.storyrevisions.count():
            cover_rev = change.storyrevisions.get(sequence_number=0)
            if cover_rev.notes == issue_rev.notes:
                cover_rev.notes = new_notes
            cover_rev.save()
        issue_rev.notes = new_notes
        issue_rev.save()
        change.submit()
        if issue_rev.notes == '':
            return True, True
        else:
            return True, False
    else:
        # no valid isbn, no reason to keep changeset in db
        change.discard(anon) # to cleanup issue reserved state
        change.delete() 
        return False, False

def print_issues(liste):
    for (issue, auto_approve) in liste:
        if type(issue) == Changeset:
            if auto_approve:
                info = "migrated, can be auto-approved:"
            else:
                info = "migrated:"
            print info, issue, issue.issuerevisions.get().notes
        else:
            print issue

if __name__ == "__main__":
    issue_list = Issue.objects.filter(notes__istartswith="ISBN", deleted=False)

    cnt = 0
    liste = []
    MAX_PER_TURN = 10
    for issue in issue_list:
        cnt += 1
        change = migrate_reserve(issue, 'for the migration of ISBNs')
        if type(change) == Changeset:
            success, auto_approve = migrate_isbn(change)
            if success:
                liste.append((change, auto_approve))
            else:
                liste.append((u"ISBN not valid for %s: %s" % (issue, issue.notes), False))
        else:
            liste.append((change, False))
        if cnt == MAX_PER_TURN:
            print_issues(liste)
            answer = raw_input('Auto-approve the marked issues (y/n):')
            if answer.startswith('y'):
                do_auto_approve(liste, 'migration of ISBNs')
            cnt = 0
            liste = [] 

    print_issues(liste)
    answer = raw_input('Auto-approve the marked issues (y/n):')
    if answer.startswith('y'):
        do_auto_approve(liste, 'migration of ISBNs')
