from django.db import transaction
from django.db.models import F
from apps.gcd.models import *
from apps.oi.models import *

def _do_reserve(indexer, display_obj, model_name):
    """
    Copied from apps.oi.views because I did not want to edit it at this late date
    and I wanted a custom changset creation message.
    """
    changeset = Changeset(indexer=indexer, state=states.OPEN)
    changeset.save()
    changeset.comments.create(commenter=indexer,
                              text='Migrated from the previous OI.  The compare '
                                   'page for this change will not highlight '
                                   'changes made before the migration, '
                                   'so please verify all fields.',
                              old_state=states.UNRESERVED,
                              new_state=changeset.state)

    revision = IssueRevision.objects.clone_revision(
      display_obj, changeset=changeset)
    for story in revision.issue.story_set.all():
       StoryRevision.objects.clone_revision(story=story, changeset=changeset)
    return changeset

@transaction.commit_on_success
def migrate():
    reserved_issues = Issue.objects.filter(index_status__in=(1, 2))
    total = reserved_issues.count()
    counter = 0
    for issue in reserved_issues:
        if counter % 100 == 0:
            print "Migrating %d out of %d" % (counter, total)
        counter += 1

        reservations = issue.reservation_set.filter(status=F('issue__index_status'))
        if reservations.count() > 0:
            reservation = reservations.order_by('-created')[0]
            changeset = _do_reserve(reservation.indexer.user, issue, 'issue')
            if issue.index_status == 2:
                changeset.submit('Migrated from the pending queue of the '
                                 'previous OI.')
    print "Migration complete!"
    return True

migrate()


