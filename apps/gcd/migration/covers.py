from django.contrib.auth.models import User
from apps.gcd.models import *
from apps.oi.models import *

def create_cover_revision(cover, anon):
    changeset=Changeset(indexer=anon, approver=anon, state=states.APPROVED)
    changeset.save()
    changeset.created=cover.modified
    changeset.save()
    changeset.comments.create(commenter=anon, 
                              text='This is an automatically generated change '
                                   'for the cover scan present at the time of '
                                   'the cover migration.', 
                              old_state=states.APPROVED, new_state=states.APPROVED)
    comment = changeset.comments.all()[0]
    comment.created = cover.modified
    comment.save()
    revision=CoverRevision(changeset=changeset, 
                           cover=cover, issue=cover.issue, 
                           file_source=cover.contributor)
    revision.save()
    revision.created=cover.modified
    revision.save()

def convert_covers():
    anon = User.objects.get(id=381)
    covers=Cover.objects.filter(has_image=True)
    for cover in covers.iterator():
        create_cover_revision(cover, anon)

convert_covers()
