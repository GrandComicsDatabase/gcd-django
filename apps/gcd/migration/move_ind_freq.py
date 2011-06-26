import sys

from django.db import transaction, connection, settings
from django.contrib.auth.models import User

from apps.gcd.models import Issue
from apps.gcd.migration import migrate_reserve, do_auto_approve
from apps.gcd.templatetags.display import valid_barcode

anon = User.objects.get(username=settings.ANON_USER_NAME)

def migrate_if(issues):
    changes = []    
    for i in issues[:250]:
        c = migrate_reserve(i, 'issue', 'to set the no_indicia_frequency flag')
        if c:
            ir = c.issuerevisions.all()[0]
            ir.indicia_frequency = u''
            ir.no_indicia_frequency = True
            ir.save()
            changes.append((c, True))

    do_auto_approve(changes, 'moving of indicia_frequency information')

@transaction.commit_on_success
def main():
    issues = Issue.objects.filter(indicia_frequency='[none]', deleted=False)
    migrate_if(issues)
    issues = Issue.objects.filter(indicia_frequency='[none listed]', deleted=False)
    migrate_if(issues)
    issues = Issue.objects.filter(indicia_frequency='none', deleted=False)
    migrate_if(issues)
    issues = Issue.objects.filter(indicia_frequency='None listed', deleted=False)
    migrate_if(issues)
    issues = Issue.objects.filter(indicia_frequency='[not listed]', deleted=False)
    migrate_if(issues)
    issues = Issue.objects.filter(indicia_frequency='[not applicable]', deleted=False)
    migrate_if(issues)
    issues = Issue.objects.filter(indicia_frequency='[not indicated]', deleted=False)
    migrate_if(issues)


if __name__ == '__main__':
    main()

