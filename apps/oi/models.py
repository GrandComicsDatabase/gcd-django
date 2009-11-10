from datetime import datetime

from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import User
from django.contrib.contenttypes import models as content_models
from django.contrib.contenttypes import generic

from apps.oi import states
from apps.gcd.models import *

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
    class Meta:
        ordering = ['created']

    commenter = models.ForeignKey(User)
    text = models.TextField()

    content_type = models.ForeignKey(content_models.ContentType)
    revision_id = models.PositiveIntegerField(db_index=True)
    revision = generic.GenericForeignKey('content_type', 'revision_id')

    old_state = models.IntegerField()
    new_state = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True, editable=False)

    def display_old_state(self):
        return states.DISPLAY_NAME[self.old_state]

    def display_new_state(self):
        return states.DISPLAY_NAME[self.new_state]

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

        revision = self._do_create_revision(instance,
                                            indexer=indexer,
                                            state=state)
        revision.comments.create(commenter=indexer,
                                 text='Editing',
                                 old_state=states.UNRESERVED,
                                 new_state=revision.state)

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
    along_with = models.ManyToManyField(User,
                                        related_name='%(class)s_assisting')
    on_behalf_of = models.ManyToManyField(User, related_name='%(class)s_source')

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

    def _source(self):
        """
        The thing of which this is a revision.
        Since this is different for each revision, the subclass must override this.
        """
        raise NotImplementedError

    # Note: lambda required so that polymorphism works.
    source = property(lambda self: self._source())

    def queue_name(self):
        """
        Long name form to display in queues.
        This allows revision objects to use their linked object's __unicode__
        method for compatibility in preview pages, but display a more
        verbose form in places like queues that need them.

        Derived classes should override _queue_name to supply a base string
        other than the standard unicode representation.
        """
        uni = self._queue_name()
        if self.source is None:
            uni += u' [ADDED]'
        if self.deleted:
            uni += u' [DELETED]'
        return uni

    def _queue_name(self):
        return unicode(self)

    def display_state(self):
        """
        Return the display text for the state.
        Makes it much easier to display state information in templates.
        """
        return states.DISPLAY_NAME[self.state]

    def save_added_revision(self, indexer, comments, **kwargs):
        """
        Add the remaining arguments and many to many relations for an unsaved
        added revision produced by a model form.  The general workflow should be:

        revision = form.save(commit=False)
        revision.save_added_revision(indexer=request.user) # optionally with kwargs

        Since this prevents the form from adding any many to many relationships,
        the _do_save_added_revision method on each concrete revision class
        needs be certain to save any such relations that come from the form.
        """
        if not isinstance(indexer, User):
            raise TypeError, "Please supply a valid indexer."

        self.indexer = indexer
        self.state = states.OPEN
        self.created = datetime.now()
        self.modified = self.created
        self._do_complete_added_revision(**kwargs)
        self.save()
        self.comments.create(commenter=indexer,
                             text=comments,
                             old_state=states.UNRESERVED,
                             new_state=self.state)

    def _do_complete_added_revision(self, **kwargs):
        """
        Hook for indiividual revisions to process additional parameters
        necessary to create a new revision representing an added record.
        By default no additional processing is done, so subclasses are
        free to override this method without calling it on the parent class.
        """
        pass

    def _check_approver(self):
        """
        Check for a mentor, set to approver if necessary, and return the
        appropriate state for a submitted change.
        """
        if self.approver is None and self.indexer.indexer.is_new and \
           self.indexer.mentor is not None:
            self.approver = self.indexer.mentor

        new_state = states.PENDING
        if self.approver is not None:
            new_state = states.REVIEWING
        return new_state
        
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

        new_state = self._check_approver()

        self.comments.create(commenter=self.indexer,
                             text=notes,
                             old_state=self.state,
                             new_state=new_state)
        self.state = new_state
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
        if self.state not in (states.OPEN, states.REVIEWING):
            raise ValueError, "Only OPEN or REVIEWING changes may be discarded."

        self.comments.create(commenter=discarder,
                             text=notes,
                             old_state=self.state,
                             new_state=states.DISCARDED)

        self.state = states.DISCARDED
        self.save()
        self._do_unreserve()

    def assign(self, approver, notes=''):
        """
        Set an approver who will examine the changes in this pending revision.

        This causes the revision to move out of the general queue and into
        the examiner's approval queue.
        """
        if self.state != states.PENDING:
            raise ValueError, "Only PENDING changes can be reviewed."

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

class OngoingReservation(models.Model):
    """
    Represents the ongoing revision on all new issues in a series.

    Whenever an issue is added to a series, if there is an ongoing reservation
    for that series the issue is immediately reserved to the ongoing
    reservation holder.
    """
    class Meta:
        db_table = 'oi_ongoing_reservation'

    indexer = models.ForeignKey(User, related_name='ongoing_reservations')
    series = models.OneToOneField(Series, related_name='ongoing_reservation')
    along_with = models.ManyToManyField(User, related_name='ongoing_assisting')
    on_behalf_of = models.ManyToManyField(User, related_name='ongoing_source')

    """
    The creation timestamp for this reservation.
    """
    created = models.DateTimeField(auto_now_add=True, db_index=True, null=True)

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
    notes = models.TextField(null=True, blank=True,
      help_text='Anything that doesn\'t fit in other fields.  These notes '
                'are part of the regular display.')
    url = models.URLField(null=True, blank=True,
      help_text='The official web site of the publisher.')

    # Fields about relating publishers/imprints to each other.
    is_master = models.BooleanField(default=0, db_index=True,
      help_text='Check if this is a top-level publisher that may contain '
                'imprints.')
    parent = models.ForeignKey('gcd.Publisher',
                               null=True, blank=True, db_index=True,
                               related_name='imprint_revisions')

    def _source(self):
        return self.publisher

    # Fake an imprint set for the preview page.
    def _imprint_set(self):
        if self.publisher is None:
            return Publisher.object.filter(pk__isnull=True)
        return self.publisher.imprint_set
    imprint_set = property(_imprint_set)

    def _series_set(self):
        if self.publisher is None:
            return Series.objects.filter(pk__isnull=True)
        return self.publisher.series_set
    series_set = property(_series_set)

    def _imprint_series_set(self):
        if self.publisher is None:
            return Series.objects.filter(pk__isnull=True)
        return self.publisher.imprint_series_set
    imprint_series_set = property(_imprint_series_set)



    def __unicode__(self):
        if self.publisher is None:
            return self.name
        return unicode(self.publisher)

    def _queue_name(self):
        return u'%s (%s, %s)' % (self.name, self.year_began,
                                 self.country.code.upper())
    def commit_to_display(self, clear_reservation=True):
        pub = self.publisher
        if pub is None:
            pub = Publisher(imprint_count=0,
                            series_count=0,
                            issue_count=0)
            if self.parent:
                self.parent.imprint_count += 1
        elif self.deleted:
            if self.parent:
                self.parent.imprint_count -= 1
            pub.delete()
            return

        pub.name = self.name
        pub.year_began = self.year_began
        pub.year_ended = self.year_ended
        pub.country = self.country
        pub.notes = self.notes
        pub.url = self.url
        pub.is_master = self.is_master
        pub.parent = self.parent

        if clear_reservation:
            pub.reserved = False

        pub.save()
        if self.publisher is None:
            self.publisher = pub

    def _do_unreserve(self):
        if self.publisher is not None:
            self.publisher.reserved = False
            self.publisher.save()

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

    def _do_complete_added_revision(self, parent=None):
        """
        Do the necessary processing to complete the fields of a new
        series revision for adding a record before it can be saved.
        """
        self.parent = parent
        if self.parent is None:
            self.is_master = True

        # Publishers go straight into PENDING or REVIEWING
        self.state = self._check_approver()


class SeriesRevisionManager(RevisionManager):
    """
    Custom manager allowing the cloning of revisions from existing rows.
    """

    def clone_revision(self, series, indexer, check=True, state=states.OPEN):
        """
        Given an existing Series instance, create a new revision based on it.

        This new revision will be where the edits are made.
        If there are no revisions, first save a baseline so that the pre-edit
        values are preserved.
        Entirely new series should be started by simply instantiating
        a new SeriesRevision directly.
        """
        return RevisionManager.clone_revision(self,
                                              instance=series,
                                              instance_class=Series,
                                              instance_name='series',
                                              indexer=indexer,
                                              check=check,
                                              state=state)

    def _do_create_revision(self, series, indexer, state):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        kwargs = {}
        if (state == states.BASELINE):
            kwargs['created'] = series.created
            kwargs['modified'] = series.modified
        else:
            kwargs['created'] = datetime.now()
            kwargs['modified'] = kwargs['created']

        revision = SeriesRevision(
          # revision-specific fields:
          series=series,
          state=state,
          indexer=indexer,

          # copied fields:
          name=series.name,
          format=series.format,
          notes=series.notes,
          year_began=series.year_began,
          year_ended=series.year_ended,
          is_current=series.is_current,

          publication_notes=series.publication_notes,
          tracking_notes=series.tracking_notes,

          country=series.country,
          language=series.language,
          publisher=series.publisher,
          imprint=series.imprint,
          **kwargs)

        revision.save()
        return revision

class SeriesRevision(Revision):
    class Meta:
        db_table = 'oi_series_revision'
        ordering = ['-created', '-id']

    objects=SeriesRevisionManager()

    series = models.ForeignKey(Series, null=True, related_name='revisions')

    name = models.CharField(max_length=255, null=True, blank=True)
    format = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    year_began = models.IntegerField(null=True, blank=True)
    year_ended = models.IntegerField(null=True, blank=True)
    is_current = models.BooleanField()

    # Publication notes are not displayed in the current UI but may
    # be accessed in the OI.
    publication_notes = models.TextField(null=True, blank=True)

    # Fields for tracking relationships between series.
    # Crossref fields don't appear to really be used- nearly all null.
    tracking_notes = models.TextField(null=True, blank=True)

    # Country and Language info.
    country = models.ForeignKey(Country, null=True, blank=True,
                                related_name='series_revisions')
    language = models.ForeignKey(Language, null=True, blank=True,
                                 related_name='series_revisions')

    # Fields related to the publishers table.
    publisher = models.ForeignKey(Publisher, null=True, blank=True,
                                  related_name='series_revisions')
    imprint = models.ForeignKey(Publisher,
                                related_name='imprint_series_revisions',
                                null=True)

    def _source(self):
        return self.series

    # Fake the issue and cover sets and a few other fields for the preview page.
    def _issue_set(self):
        if self.series is None:
            return Issue.objects.filter(pk__isnull=True)
        return self.series.issue_set
    issue_set = property(_issue_set)

    def _cover_set(self):
        if self.series is None:
            return Cover.objects.filter(pk__isnull=True)
        return self.series.cover_set
    cover_set = property(_cover_set)

    def _has_gallery(self):
        if self.series is None:
            return False
        return self.series.has_gallery
    has_gallery = property(_has_gallery)

    def _do_complete_added_revision(self, publisher, imprint=None):
        """
        Do the necessary processing to complete the fields of a new
        series revision for adding a record before it can be saved.
        """
        self.is_master = True
        if imprint is not None:
            self.is_master = False

        self.publisher = publisher
        self.imprint = imprint

        # Series go straight into PENDING or REVIEWING
        self.state = self._check_approver()

    def commit_to_display(self, clear_reservation=True):
        series = self.series
        if series is None:
            series = Series(issue_count=0)
            self.publisher.series_count += 1
        elif self.deleted:
            self.publisher.series_count -= 1
            self.publisher.issue_count -= series.issue_count
            series.delete()
            return

        series.name = self.name
        series.format = self.format
        series.notes = self.notes
        series.year_began = self.year_began
        series.year_ended = self.year_ended
        series.is_current = self.is_current

        series.publication_notes = self.publication_notes
        series.tracking_notes = self.tracking_notes

        series.country = self.country
        series.language = self.language
        series.publisher = self.publisher
        series.imprint = self.imprint

        if clear_reservation:
            series.reserved = False

        series.save()
        if self.series is None:
            self.series = series

    def _do_unreserve(self):
        if self.series is not None:
            self.series.reserved = False
            self.series.save()

    def __unicode__(self):
        if self.series is None:
            return u'%s (%s series)' % (self.name, self.year_began)
        return unicode(self.series)

class IssueRevisionManager(RevisionManager):

    def clone_revision(self, issue, indexer, check=True, state=states.OPEN):
        """
        Given an existing Issue instance, create a new revision based on it.

        This new revision will be where the edits are made.
        If there are no revisions, first save a baseline so that the pre-edit
        values are preserved.
        Entirely new issues should be started by simply instantiating
        a new IssueRevision directly.
        """
        return RevisionManager.clone_revision(self,
                                              instance=issue,
                                              instance_class=Issue,
                                              instance_name='issue',
                                              indexer=indexer,
                                              check=check,
                                              state=state)

    def _do_create_revision(self, issue, indexer, state):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        kwargs = {}
        if (state == states.BASELINE):
            kwargs['created'] = issue.created
            kwargs['modified'] = issue.modified
        else:
            kwargs['created'] = datetime.now()
            kwargs['modified'] = kwargs['created']

        revision = IssueRevision(
          # revision-specific fields:
          issue=issue,
          state=state,
          indexer=indexer,

          # copied fields:
          volume=issue.volume,
          number=issue.number,
          publication_date=issue.publication_date,
          price=issue.price,
          key_date=issue.key_date,
          sort_code=issue.sort_code,
          series=issue.series,
          **kwargs)

        revision.save()
        return revision

class IssueRevision(Revision):
    class Meta:
        db_table = 'oi_issue_revision'
        ordering = ['-created', '-id']

    objects = IssueRevisionManager()

    issue = models.ForeignKey(Issue, null=True, related_name='revisions')

    volume = models.IntegerField(max_length=255, null=True)
    number = models.CharField(max_length=25, null=True)

    publication_date = models.CharField(max_length=255, null=True)
    price = models.CharField(max_length=25, null=True)
    key_date = models.CharField(max_length=10, null=True)
    sort_code = models.IntegerField()

    series = models.ForeignKey(Series)

    def commit_to_display(self, clear_reservation=True):
        issue = self.issue
        if issue is None:
            issue = Issue()
        issue.number = self.number
        issue.volume = self.volume
        issue.publication_date = self.publication_date
        issue.price = self.price
        issue.key_date = self.key_date,
        issue.sort_code = self.sort_code,
        issue.series = self.series

        if clear_reservation:
            issue.reserved = False

        issue.save()

    def __unicode__(self):
        return unicode(self.issue)

class StoryRevisionManager(RevisionManager):

    def clone_revision(self, story, indexer, issue_revision,
                       check=True, state=states.OPEN):
        """
        Given an existing Story instance, create a new revision based on it.

        This new revision will be where the edits are made.
        If there are no revisions, first save a baseline so that the pre-edit
        values are preserved.
        Entirely new stories should be started by simply instantiating
        a new StoryRevision directly.
        """
        return RevisionManager.clone_revision(self,
                                              instance=story,
                                              instance_class=Story,
                                              instance_name='story',
                                              indexer=indexer,
                                              check=check,
                                              state=state,
                                              issue_revision=issue_revision)

    def _do_create_revision(self, story, issue_revision, indexer, state):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        kwargs = {}
        if (state == states.BASELINE):
            kwargs['created'] = issue.created
            kwargs['modified'] = issue.modified
        else:
            kwargs['created'] = datetime.now()
            kwargs['modified'] = kwargs['created']

        revision = StoryRevision(
          # revision-specific fields:
          story=story,
          issue_revision=issue_revision,
          state=state,
          indexer=indexer,

          # copied fields:
          title=story.title,
          feature=story.feature,
          page_count=story.page_count,
          page_count_uncertain=story.page_count_uncertain,

          script=story.script,
          pencils=story.pencils,
          inks=story.inks,
          colors=story.colors,
          letters=story.letters,

          no_script=story.no_script,
          no_pencils=story.no_pencils,
          no_inks=story.no_inks,
          no_colors=story.no_colors,
          no_letters=story.no_letters,

          editor=story.editor,
          notes=story.notes,
          synopsis=story.synopsis,
          reprints=story.reprints,
          genre=story.genre,
          type=story.type,
          job_number=story.job_number,
          sequence_number=story.sequence_number,

          issue=story.issue,
          **kwargs)

class StoryRevision(Revision):
    class Meta:
        db_table = 'oi_story_revision'
        ordering = ['-created', '-id']

    story = models.ForeignKey(Story, null=True, related_name='revisions')
    issue_revision = models.ForeignKey('oi.IssueRevision',
                                       related_name='story_revisions')

    title = models.CharField(max_length=255, db_column='Title', null=True)
    feature = models.CharField(max_length=255, db_column='Feature',
                               null=True)
    page_count = models.FloatField(db_column='Pg_Cnt', null=True)
    page_count_uncertain = models.BooleanField(default=0)

    characters = models.TextField(db_column='Char_App', null = True)

    script = models.TextField(max_length=255, db_column='Script', null=True)
    pencils = models.TextField(max_length=255, db_column='Pencils', null=True)
    inks = models.TextField(max_length=255, db_column='Inks', null=True)
    colors = models.TextField(max_length=255, db_column='Colors', null=True)
    letters = models.TextField(max_length=255, db_column='Letters', null=True)

    no_script = models.BooleanField(default=0)
    no_pencils = models.BooleanField(default=0)
    no_inks = models.BooleanField(default=0)
    no_colors = models.BooleanField(default=0)
    no_letters = models.BooleanField(default=0)

    editor = models.TextField(max_length=255, db_column='Editing', null=True)
    notes = models.TextField(max_length=255, db_column='Notes', null=True)
    synopsis = models.TextField(max_length=255, db_column='Synopsis', null=True)
    reprints = models.TextField(max_length=255, db_column='Reprints', null=True)
    genre = models.CharField(max_length=255, db_column='Genre', null=True)
    type = models.CharField(max_length=255, db_column='Type', null=True)
    sequence_number = models.IntegerField(db_column='Seq_No', null=True)
    job_number = models.CharField(max_length=25, db_column='JobNo', null=True)

    issue = models.ForeignKey(Issue, null=True, related_name='story_revisions')

    def commit_to_display(self, clear_reservation=True):
        story = self.story
        if story is None:
            story = Story()

        story.title = self.title
        story.feature = self.feature
        story.page_count = self.page_count
        story.page_count_uncertain = self.page_count_uncertain

        story.script = self.script
        story.pencils = self.pencils
        story.inks = self.inks
        story.colors = self.colors
        story.letters = self.letters

        story.no_script = self.no_script
        story.no_pencils = self.no_pencils
        story.no_inks = self.no_inks
        story.no_colors = self.no_colors
        story.no_letters = self.no_letters

        story.editor = self.editor
        story.notes = self.notes
        story.synopsis = self.synopsis
        story.reprints = self.reprints
        story.genre = self.genre
        story.type = self.type
        story.job_number = self.job_number
        story.sequence_number = self.sequence_number

        if clear_reservation:
            story.reserved = False

        story.save()

    def __unicode__(self):
        return unicode(self.story)

