import sys

from django.db import transaction, connection, settings
from django.contrib.auth.models import User

from apps.gcd.models import Series
from apps.gcd.migration import migrate_reserve, do_auto_approve

from stdnum import isbn

anon = User.objects.get(username=settings.ANON_USER_NAME)

def migrate_isbn_series_issue(change_series, change_issue):
    ''' two return values: change valid, can be autoapproved '''
    series_rev = change_series.seriesrevisions.get()
    issue_rev = change_issue.issuerevisions.get()
    if series_rev.notes.startswith('ISBN-10'):
        if series_rev.notes.find('ISBN-13') < 0:
            cand_isbn = series_rev.notes[7:].strip(':# ').split()[0].strip('.;')
        else:    
            return False, False, False
    elif series_rev.notes.startswith('ISBN-13'):
        if series_rev.notes.find('ISBN-10') < 0:
            cand_isbn = series_rev.notes[7:].strip(':# ').split()[0].strip('.;')
        else:    
            return False, False, False
    else:
        cand_isbn = series_rev.notes[4:].strip(':# ').split()[0].strip('.;')
    if isbn.is_valid(cand_isbn):
        issue_rev.isbn = cand_isbn
        pos = series_rev.notes.find(cand_isbn) + len(cand_isbn)
        new_notes = series_rev.notes[pos:].lstrip(' ;.\r\n')
        series_rev.notes = new_notes
        series_rev.save()
        issue_rev.save()
        change_series.submit()
        change_issue.submit()
        if series_rev.notes == '':
            return True, True, True
        else:
            return True, False, True
    else:
        return False, False, False

def migrate_isbn():
    series_set = Series.objects.filter(notes__istartswith="ISBN", deleted=False, issue_count=1, issue__isbn='')

    changes = []
    for series in series_set[:200]:
        change_series = migrate_reserve(series, 'series', 'for the migration of ISBNs')
        if change_series:
            issue = series.active_issues().get()
            change_issue = migrate_reserve(issue, 'issue', 'for the migration of ISBNs')
            if change_issue is None:
                # could not reserve issue, no reason to keep changeset in db
                change_series.discard(anon) # to cleanup reserved state
                change_series.delete() 
            else:
                success, auto_approve_series, auto_approve_issue = migrate_isbn_series_issue(change_series, change_issue)
                if success:
                    changes.append((change_series, auto_approve_series))
                    changes.append((change_issue, auto_approve_issue))
                else:
                    print u"ISBN not valid for %s: %s" % (series, series.notes)
                    # no valid isbn, no reason to keep changeset in db
                    change_series.discard(anon) # to cleanup reserved state
                    change_series.delete() 
                    change_issue.discard(anon) # to cleanup reserved state
                    change_issue.delete() 
    do_auto_approve(changes, 'migration of ISBNs')

@transaction.commit_on_success
def main():
    migrate_isbn()

if __name__ == '__main__':
    main()

