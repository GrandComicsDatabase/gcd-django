from datetime import datetime

from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import User
from django.contrib.contenttypes import models as content_models
from django.contrib.contenttypes import generic

from apps.oi import states
from apps.gcd.models import Publisher, Country

class RevisionComment(models.Model):
    """
    Comment class for revision management.

    We are not using Django's comments contrib package for several reasons:

    1.  Additional fields- we want to associate comments with state transitions,
        which also tells us who made the comment (since currently comments can
        only be made by the person changing the revision state, or by the
        indexer when saving intermediate edits.

        TODO: The whole bit where the indexer can end up tacking on a bunch
        of comments rather than having just one that they build up and edit
        and send in with the submission is not quite right.  Needs work still.

    2.  We don't need the anti-spam measures as these will not be accessible
        by the general public.  If we get a spammer with an account we'll have
        bigger problems than comments, and other ways to deal with them.

    3.  Unneeded fields.  This isn't really an obstacle to use, but the
        django comments system copies over a number of fields that we would
        not want copied in case they change (email, for instance).
    """

    commenter = models.ForeignKey(User)
    text = models.TextField()

    content_type = models.ForeignKey(content_models.ContentType)
    revision_id = models.PositiveIntegerField(db_index=True)
    revision = generic.GenericForeignKey('content_type', 'revision_id')

    old_state = models.IntegerField()
    new_state = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True, editable=False)

class RevisionManager(models.Manager):
    """
    Custom manager base class for revisions.
    """

    def clone_revision(self, instance, instance_class, instance_name,
                       indexer, check=True, state=states.OPEN):
        """
        Given an existing instance, create a new revision based on it.

        This new revision will be where the edits are made.
        If there are no revisions, first save a baseline so that the pre-edit
        values are preserved.
        Entirely new publishers should be started by simply instantiating
        a new PublisherRevision directly.
        """

        if not isinstance(indexer, User):
            raise TypeError, "Please supply a valid indexer."
        if not isinstance(instance, instance_class):
            raise TypeError, "Please supply a valid %s." % instance_class

        if check:
            prior_revisions = self.filter(
              **{instance_name: instance})

            if prior_revisions.count() == 0:
                # Establish a baseline revision for this publisher before
                # creating the new about-to-be-edited revision.
                # TODO: technically it's wrong to set the indexer like this,
                # but since baseline revisions have a special state it's
                # easy to find and fix later when we migrate the Log tables.
                # And this way we can avoid yet another NULLable field.
                self.clone_revision(instance,
                                    check=False,
                                    indexer=indexer,
                                    state=states.BASELINE)

        # TODO: Use transaction for the rest if we go to InnoDB.
        revision = self._do_create_revision(instance,
                                            indexer=indexer,
                                            state=state)
        revision.comments.create(commenter=indexer,
                                 text='Reserved',
                                 old_state=states.UNRESERVED,
                                 new_state=states.OPEN)

        # Mark as reserved *after* cloning the revision in order to avoid
        # overwriting the modified timestamp in the case of a BASELINE
        # revision.
        instance.reserved = True
        instance.save()
        return revision

class Revision(models.Model):
    """
    Mixin abstract base class implementing the workflow of a revisable object.

    This holds the data while it is being edited, and remains in the table
    as a history of each given edit, including those that are discarded.

    A state column trackes the progress of the revision, which should eventually
    end in either the APPROVED or DISCARDED state.  A special case is the
    BASELINE state which is a marker for future database migration work
    during the New Fun release.
    """
    class Meta:
        abstract = True

    state = models.IntegerField(db_index=True)

    indexer = models.ForeignKey('auth.User', db_index=True,
                                related_name='reserved_%(class)s')

    # Revisions don't get an approver until late in the workflow,
    # and for legacy cases we don't know who they were.
    approver = models.ForeignKey('auth.User',  db_index=True,
                                 related_name='approved_%(class)s', null=True)

    comments = generic.GenericRelation(RevisionComment,
                                       content_type_field='content_type',
                                       object_id_field='revision_id')

    """
    If true, this revision deletes the object in question.  Other fields
    should not contain changes but should instead be a record of the object
    at the time of deletion and therefore match the previous revision.
    If changes are present, then they were never actually published and
    should be ignored in terms of history.
    """
    deleted = models.BooleanField(default=0)

    """
    The creation timestamp for this revision.
    Not automatic so we can handle baseline revisions.
    """
    created = models.DateTimeField(db_index=True, null=True)

    """
    The modification timestamp for this revision.
    Not automatic so we can handle baseline revisions.
    """
    modified = models.DateTimeField(db_index=True, null=True)

    def submit(self, notes=''):
        """
        Submit changes for approval.
        If this is the first such submission or if the prior approver released
        the changes back to the general queue, then the changes go into the
        general approval queue.  If it is an edit in reply to a disapproval,
        then the changes go directly back into the approver's queue.
        """

        if self.state != states.OPEN:
            raise ValueError, "Only OPEN changes can be submitted for approval."

        self.comments.create(commenter=self.indexer,
                             text=notes,
                             old_state=self.state,
                             new_state=states.PENDING)
        self.state = states.PENDING
        self.save()

    def retract(self, notes=''):
        """
        Retract a submitted change.

        This can only be done if the change is not being examined.  Users
        should contact the examiner if they would like to further edit
        a change that is under examination.
        """

        if self.state != states.PENDING:
            raise ValueError, "Only PENDING changes my be retracted."
        if self.approver is not None:
            raise ValueError, "Only changes with no approver may be retracted."

        self.comments.create(commenter=self.indexer,
                             text=notes,
                             old_state=self.state,
                             new_state=states.OPEN)
        self.state = states.OPEN
        self.save()

    def discard(self, discarder, notes=''):
        """
        Discard a change without comitting it back to the data tables.

        This may be done either by the indexer, effectively releasign the
        reservation, or by an approver, effectively canceling it.
        """
        if self.state not in (states.OPEN, states.PENDING):
            raise ValueError, "Only OPEN or PENDING changes may be discarded."

        self.comments.create(commenter=discarder,
                             text=notes,
                             old_state=self.state,
                             new_state=states.DISCARDED)

        self.state = states.DISCARDED
        self.save()
        self.publisher.reserved = False
        self.publisher.save()

    def examine(self, approver, notes=''):
        """
        Set an approver who will examine the changes in this pending revision.

        This causes the revision to move out of the general queue and into
        the examiner's approval queue.
        """
        if self.state != states.PENDING:
            raise ValueError, "Only PENDING changes can be approved."

        # TODO: check that the approver has approval priviliges.
        if not isinstance(approver, User):
            raise TypeError, "Please supply a valid approver."

        self.comments.create(commenter=approver,
                             text=notes,
                             old_state=self.state,
                             new_state=states.REVIEWING)
        self.approver = approver
        self.state=states.REVIEWING
        self.save()

    def release(self, notes=''):
        if self.state != states.REVIEWING:
            raise ValueError, "Only REVIEWING changes my change approver."

        self.comments.create(commenter=self.approver,
                             text=notes,
                             old_state=self.state,
                             new_state=states.PENDING)
        self.approver = None
        self.state = states.PENDING
        self.save()

    def approve(self, notes=''):
        """
        Approve a pending index from an approver's queue into production.

        This moves the revision to approved and copies its data back to the
        production display table.
        """

        if self.state != states.REVIEWING or self.approver is None:
            raise ValueError, \
                  "Only REVIEWING changes with an approver can be approved."

        self.comments.create(commenter=self.approver,
                             text=notes,
                             old_state=self.state,
                             new_state=states.APPROVED)
        self.commit_to_display()
        self.state = states.APPROVED
        self.save()

    def disapprove(self, notes=''):
        """
        Send the change back to the indexer for more work.
        """
        # TODO: Should we validate that a non-empty reason is supplied
        # through the approver_notes field here or in the view layer?
        # Where should validation go in general?

        if self.state != states.REVIEWING or self.approver is None:
            raise ValueError, \
                  "Only REVIEWING changes with an approver can be disapproved."
        self.comments.create(commenter=self.approver,
                             text=notes,
                             old_state=self.state,
                             new_state=states.OPEN)
        self.state = states.OPEN
        self.save()

    def mark_deleted(self, notes=''):
        """
        Mark this revision as deleted, meaning that instead of copying it
        back to the display table, the display table entry will be removed
        when the revision is committed.

        Deletion moves the revision directly into PENDING as further edits
        are pointless.
        """
        if self.state != states.OPEN:
            raise ValueError, \
                "Objects may be deleted only through OPEN reservations."

        self.comments.create(commenter=self.indexer,
                             text=notes,
                             old_state=self.state,
                             new_state=states.PENDING)
        self.state = states.PENDING
        self.deleted = True
        self.save()

class PublisherRevisionManager(RevisionManager):
    """
    Custom manager allowing the cloning of revisions from existing rows.
    """

    def clone_revision(self, publisher, indexer, check=True, state=states.OPEN):
        """
        Given an existing Publisher instance, create a new revision based on it.

        This new revision will be where the edits are made.
        If there are no revisions, first save a baseline so that the pre-edit
        values are preserved.
        Entirely new publishers should be started by simply instantiating
        a new PublisherRevision directly.
        """
        return RevisionManager.clone_revision(self,
                                              instance=publisher,
                                              instance_class=Publisher,
                                              instance_name='publisher',
                                              indexer=indexer,
                                              check=check,
                                              state=state)

    def _do_create_revision(self, publisher, indexer, state):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        kwargs = {}
        if (state == states.BASELINE):
            kwargs['created'] = publisher.created
            kwargs['modified'] = publisher.modified
        else:
            kwargs['created'] = datetime.now()
            kwargs['modified'] = kwargs['created']

        revision = PublisherRevision(
          # revision-specific fields:
          publisher=publisher,
          state=state,
          indexer=indexer,

          # copied fields:
          name=publisher.name,
          year_began=publisher.year_began,
          year_ended=publisher.year_ended,
          country=publisher.country,
          notes=publisher.notes,
          url=publisher.url,
          is_master=publisher.is_master,
          parent=publisher.parent,
          **kwargs)

        revision.save()
        return revision

class PublisherRevision(Revision):
    class Meta:
        db_table = 'oi_publisher_revision'
        ordering = ['-created', '-id']
        permissions = (
            ('can_reserve', 'can reserve a record for add, edit or delete'),
            ('can_approve', 'can approve a change to a record'),
            ('can_cancel', 'can cancel a pending change they did not open'),
        )

    objects=PublisherRevisionManager()

    # Can be null in the case of adding an entirely new publisher.
    publisher=models.ForeignKey('gcd.Publisher', null=True,
                                related_name='revisions')

    # Core publisher fields.
    name = models.CharField(max_length=255, null=True, blank=True,
                            db_index=True,
      help_text="The publisher's name.  For master publishers, use the most "
                'common form of the name, i.e. "DC" rather than '
                '"D.C. Comics, Inc." or "DC Comics".  For imprints, use the '
                'name exactly as it appears (in the indicia for indicia '
                'publishers, in the logo for cover imprints).')

    year_began = models.IntegerField(null=True, blank=True, db_index=True,
      help_text='The first year in which the publisher was active.')
    year_ended = models.IntegerField(null=True, blank=True,
      help_text='The last year in which the publisher was active. '
                'Leave blank if the publisher is still active.')
    country = models.ForeignKey('gcd.Country',
                                null=True, blank=True, db_index=True)
    notes = models.TextField(null=True, blank=True)
    url = models.URLField(null=True, blank=True,
      help_text='The official web site of the publisher.')

    # Fields about relating publishers/imprints to each other.
    is_master = models.BooleanField(default=0, db_index=True,
      help_text='Check if this is a top-level publisher that may contain '
                'imprints.')
    parent = models.ForeignKey('gcd.Publisher',
                               null=True, blank=True, db_index=True,
                               related_name='imprint_revisions')

    def __unicode__(self):
        return self.name

    def commit_to_display(self):
        pub = self.publisher
        pub.name = self.name
        pub.year_began = self.year_began
        pub.year_ended = self.year_ended
        pub.country = self.country
        pub.notes = self.notes
        pub.url = self.url
        pub.is_master = self.is_master
        pub.parent = self.parent

        pub.save()

    def has_imprints(self):
        return self.imprint_set.count() > 0

    def is_imprint(self):
        return self.parent_id is not None and self.parent_id != 0

    def get_absolute_url(self):
        if self.is_imprint():
            return "/imprint/%i/" % self.id
        else:
            return "/publisher/%i/" % self.id

    def get_official_url(self):
        try:
            if not self.url.lower().startswith("http://"):
                self.url = "http://" + self.url
                #TODO: auto fix urls ?
                #self.save()
        except:
            return ""

        return self.url

class SeriesRevision:
    pass

