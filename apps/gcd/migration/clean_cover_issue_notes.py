import sys

from django.db import transaction, connection, settings
from django.contrib.auth.models import User

from apps.gcd.models import Issue, StoryType
from apps.gcd.migration import migrate_reserve, do_auto_approve

anon = User.objects.get(username=settings.ANON_USER_NAME)
cover_type = StoryType.objects.get(name='cover')

def cleanup_cover_notes(issues, clean_all=False):
    changes = []
    for i in issues[:450]:
        c = migrate_reserve(i, 'issue', 'to cleanup cover notes')
        if c:
            ir = c.issuerevisions.all()[0]
            cr = c.storyrevisions.get(type=cover_type, notes=ir.notes)
            cr.notes = ''
            cr.save()
            if clean_all:
                srs = c.storyrevisions.filter(notes=ir.notes)
                ir.notes=''
                ir.save()
                for sr in srs:
                    sr.notes=''
                    sr.save()
            changes.append((c, True))
        else:
            print "%d is reserved" % i
    do_auto_approve(changes, 'cleaning cover notes')

@transaction.commit_on_success
def main():
    text = 'Indexed with help from Alberto Becattini.'
    issues=Issue.objects.filter(notes=text).filter(story__notes=text, story__type=cover_type)
    cleanup_cover_notes(issues)
    text='nessuna'
    issues=Issue.objects.filter(notes=text).filter(story__notes=text, story__type=cover_type)
    cleanup_cover_notes(issues, clean_all=True)
    text='Printed in Norway by Aktietrykkeriet i Stavanger.'
    issues=Issue.objects.filter(notes=text).filter(story__notes=text, story__type=cover_type)
    cleanup_cover_notes(issues)
    text='Printed in Spain.'
    issues=Issue.objects.filter(notes=text).filter(story__notes=text, story__type=cover_type)
    cleanup_cover_notes(issues)

if __name__ == '__main__':
    main()

