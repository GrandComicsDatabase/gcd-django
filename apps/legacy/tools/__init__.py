from django.conf import settings
from django.contrib.auth.models import User

from apps.oi.models import Changeset
from apps.oi.views import _do_reserve
from apps.oi import states
from apps.oi.templatetags.editing import is_locked

ANON_USER = User.objects.get(username=settings.ANON_USER_NAME)

def migrate_reserve(display, label, comment=''):
    if is_locked(display) == None:
        changeset=_do_reserve(ANON_USER, display, label)
        if changeset == None:
            raise ValueError(display)
        changeset.state=states.OPEN
        changeset.save()
        comment = changeset.comments.create(commenter=ANON_USER,
          text='This is an automatically generated changeset %s.' % comment,
          old_state=states.UNRESERVED, new_state=states.OPEN)
        return changeset
    else:
        print("%s %s is reserved" % (label.capitalize(), display))
        return None

def do_auto_approve(liste, comment):
   for (change, is_approvable) in liste:
        if type(change) == Changeset:
            # in principle another approver could take this change
            # if already approved, this gets another comment, not a problem
            # if not approved till now, this gets approved, not really a problem
            # if rejected, this gets approved, overrriding the approver
            if is_approvable:
                change.approver = ANON_USER
                change.state = states.REVIEWING
                change.approve(notes='Automatically approved %s.' % comment)
                print("change is auto-approved:", change)

