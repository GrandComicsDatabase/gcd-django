from datetime import datetime
import itertools
import operator

from django.db import models
from django.db.models import F, Count
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import User
from django.contrib.contenttypes import models as content_models
from django.contrib.contenttypes import generic

from apps.oi import states
from apps.gcd.models import *

class Changeset(models.Model):

    state = models.IntegerField(db_index=True)

    indexer = models.ForeignKey('auth.User', db_index=True,
                                related_name='changesets')
    along_with = models.ManyToManyField(User,
                                        related_name='changesets_assisting')
    on_behalf_of = models.ManyToManyField(User, related_name='changesets_source')

    # Changesets don't get an approver until late in the workflow,
    # and for legacy cases we don't know who they were.
    approver = models.ForeignKey('auth.User',  db_index=True,
                                 related_name='approved_%(class)s', null=True)

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)

    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)
        self._is_inline = None
        self._inline_revision = None

    def _revision_sets(self):
        return (self.publisherrevisions.all(),
                self.indiciapublisherrevisions.all(),
                self.brandrevisions.all(),
                self.seriesrevisions.all(),
                self.issuerevisions.all(),
                self.storyrevisions.all())

    def _revisions(self):
        """
        Fake up an iterable (not actually a list) of all revisions,
        in canonical order.
        TODO: This is probably too database-intensive, unless chain doesn't
        evalate each queryset until it needs to.  Which it might.
        """
        return itertools.chain(*self._revision_sets())
    revisions = property(_revisions)

    def revision_count(self):
        return reduce(operator.add,
                      map(lambda rs: rs.count(), self._revision_sets()))

    def inline(self):
        """
        If true, edit the revisions of the changeset inline in the changeset page.
        Otherwise, render a page for the changeset that links to a separate edit
        page for each revision.
        """
        if self._is_inline is None:
            if (self.revision_count() == 1 and
                self.issuerevisions.count() == 0):
                self._is_inline = True
            else:
                self._is_inline = False
        return self._is_inline

    def inline_revision(self):
        if self.inline():
            if self._inline_revision is None:
                self._inline_revision = self.revisions.next()
        return self._inline_revision

    def singular(self):
        """
        Used for conditionals in templates, as bulk issue adds are treated 
        differently.
        """
        return self.inline() or self.issuerevisions.count() == 1

    def ordered_issue_revisions(self):
        """
        Used in the display.  Natural revision order must be by timestamp.
        """
        return self.issuerevisions.order_by('revision_sort_code', 'id')

    def queue_name(self):
        if self.inline():
            return self.revisions.next().queue_name()
        if self.issuerevisions.count() == 1:
            return self.issuerevisions.all()[0].queue_name()
        return unicode(self)

    def display_state(self):
        """
        Return the display text for the state.
        Makes it much easier to display state information in templates.
        """
        return states.DISPLAY_NAME[self.state]

    def _check_approver(self):
        """
        Check for a mentor, set to approver if necessary, and return the
        appropriate state for a submitted change.

        Set last issue even if we are part of a current series, because
        the is_current flag denotes that already and we may want to use the
        last issue to date sometimes.
        """
        if self.approver is None and self.indexer.indexer.is_new and \
           self.indexer.indexer.mentor is not None:
            self.approver = self.indexer.indexer.mentor

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
        for revision in self.revisions:
            if revision.source is not None:
                revision.source.reserved = False
                revision.source.save()

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

        issue_revision_count = self.issuerevisions.count() 
        if issue_revision_count > 1:
            # Bulk add of skeletons is relatively complicated.
            # The first issue will have the "after" field set.  Later
            # issues will need the "after" field set to the issue that was
            # just created by the previous save.
            previous_revision = None
            for revision in self.issuerevisions.order_by('revision_sort_code'):
                if previous_revision is None:
                    revision.commit_to_display(space_count=issue_revision_count)
                else:
                    revision.after = previous_revision.issue
                    revision.commit_to_display(space_count=0)
                previous_revision = revision
        else:
            for revision in self.revisions:
                revision.commit_to_display()

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
        for revision in self.revisions:
            revision.mark_deleted()

        self.save()

    def __unicode__(self):
        if self.inline():
            return  unicode(self.inline_revision())
        ir_count = self.issuerevisions.count() 
        if ir_count == 1:
            return unicode(self.issuerevisions.all()[0])
        if ir_count > 1:
            first = self.issuerevisions.order_by('revision_sort_code')[0]
            last = self.issuerevisions.order_by('-revision_sort_code')[0]
            return '%s #%s - %s' % (first.series, first.display_number,
                                                  last.display_number)
        return 'Changeset: %d' % self.id

class ChangesetComment(models.Model):
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
        db_table = 'oi_changeset_comment'
        ordering = ['created']

    commenter = models.ForeignKey(User)
    text = models.TextField()

    changeset = models.ForeignKey(Changeset, related_name='comments')

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

    def clone_revision(self, instance, instance_class,
                       changeset, check=True, **kwargs):
        """
        Given an existing instance, create a new revision based on it.

        This new revision will be where the edits are made.
        If there are no revisions, first save a baseline so that the pre-edit
        values are preserved.
        Entirely new publishers should be started by simply instantiating
        a new PublisherRevision directly.
        """
        if not isinstance(instance, instance_class):
            raise TypeError, "Please supply a valid %s." % instance_class

        revision = self._do_create_revision(instance,
                                            changeset=changeset,
                                            **kwargs)
        # Mark as reserved *after* cloning the revision in order to avoid
        # overwriting the modified timestamp in the case of a BASELINE
        # revision.
        instance.reserved = True
        instance.save()
        return revision

    def active(self):
        """
        For use on the revisions relation from display objects
        where reserved == True.
        Throws the DoesNotExist or MultipleObjectsReturned exceptions on
        the appropriate Revision subclass, as it calls get() underneath.
        """
        return self.get(changeset__state__in=states.ACTIVE)

class Revision(models.Model):
    """
    Abstract base class implementing the workflow of a revisable object.

    This holds the data while it is being edited, and remains in the table
    as a history of each given edit, including those that are discarded.

    A state column trackes the progress of the revision, which should eventually
    end in either the APPROVED or DISCARDED state.  A special case is the
    BASELINE state which is a marker for future database migration work
    during the New Fun release.
    """
    class Meta:
        abstract = True

    changeset = models.ForeignKey(Changeset, related_name='%(class)ss')

    """
    If true, this revision deletes the object in question.  Other fields
    should not contain changes but should instead be a record of the object
    at the time of deletion and therefore match the previous revision.
    If changes are present, then they were never actually published and
    should be ignored in terms of history.
    """
    deleted = models.BooleanField(default=0)

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)

    def _source(self):
        """
        The thing of which this is a revision.
        Since this is different for each revision, the subclass must override this.
        """
        raise NotImplementedError

    # Note: lambda required so that polymorphism works.
    source = property(lambda self: self._source())

    def _source_name(self):
        """
        Used to key lookups in various shared view methods.
        """
        raise NotImplementedError

    # Note: lambda required so that polymorphism works.
    source_name = property(lambda self: self._source_name())

    def mark_deleted(self, notes=''):
        """
        Mark this revision as deleted, meaning that instead of copying it
        back to the display table, the display table entry will be removed
        when the revision is committed.
        """
        self.deleted = True
        self.save()

    def compare_changes(self):
        """
        Set up the 'changed' property so that it can be accessed conveniently
        from a template.  Template calling limitations prevent just
        using a parameter to compare one field at a time.
        """
        self.changed = {}
        for field_name in self._field_list():
            new = getattr(self, field_name)
            if self.source is None:
                if new:
                    self.changed[field_name] = True
                else:
                    self.changed[field_name] = False
            elif new != getattr(self.source, field_name):
                self.changed[field_name] = True
            else:
                self.changed[field_name] = False

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

    def save_added_revision(self, changeset, **kwargs):
        """
        Add the remaining arguments and many to many relations for an unsaved
        added revision produced by a model form.  The general workflow should be:

        revision = form.save(commit=False)
        revision.save_added_revision() # optionally with kwargs

        Since this prevents the form from adding any many to many relationships,
        the _do_save_added_revision method on each concrete revision class
        needs be certain to save any such relations that come from the form.
        """
        self.changeset = changeset
        self._do_complete_added_revision(**kwargs)
        self.save()

    def _do_complete_added_revision(self, **kwargs):
        """
        Hook for indiividual revisions to process additional parameters
        necessary to create a new revision representing an added record.
        By default no additional processing is done, so subclasses are
        free to override this method without calling it on the parent class.
        """
        pass

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
    created = models.DateTimeField(auto_now_add=True, db_index=True)

class PublisherRevisionManagerBase(RevisionManager):
    def _base_field_kwargs(self, instance):
        return {
          'name': instance.name,
          'year_began': instance.year_began,
          'year_ended': instance.year_ended,
          'notes': instance.notes,
          'url': instance.url,
        }

class PublisherRevisionBase(Revision):
    class Meta:
        abstract = True

    name = models.CharField(max_length=255, db_index=True)

    year_began = models.IntegerField(null=True, blank=True, db_index=True,
      help_text='The first year in which the publisher was active.')
    year_ended = models.IntegerField(null=True, blank=True,
      help_text='The last year in which the publisher was active. '
                'Leave blank if the publisher is still active.')
    notes = models.TextField(blank=True,
      help_text='Anything that doesn\'t fit in other fields.  These notes '
                'are part of the regular display.')
    url = models.URLField(blank=True,
      help_text='The official web site of the publisher.')

    def _assign_base_fields(self, target):
        target.name = self.name
        target.year_began = self.year_began
        target.year_ended = self.year_ended
        target.notes = self.notes
        target.url = self.url

    def _field_list(self):
        return ('name', 'year_began', 'year_ended', 'notes', 'url')

    def __unicode__(self):
        if self.source is None:
            return self.name
        return unicode(self.source)

class PublisherRevisionManager(PublisherRevisionManagerBase):
    """
    Custom manager allowing the cloning of revisions from existing rows.
    """

    def clone_revision(self, publisher, changeset):
        """
        Given an existing Publisher instance, create a new revision based on it.

        This new revision will be where the edits are made.
        Entirely new publishers should be started by simply instantiating
        a new PublisherRevision directly.
        """
        return PublisherRevisionManagerBase.clone_revision(self,
                                              instance=publisher,
                                              instance_class=Publisher,
                                              changeset=changeset)

    def _do_create_revision(self, publisher, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        kwargs = self._base_field_kwargs(publisher)

        revision = PublisherRevision(
          publisher=publisher,
          changeset=changeset,

          country=publisher.country,
          is_master=publisher.is_master,
          parent=publisher.parent,
          **kwargs)

        revision.save()
        return revision

class PublisherRevision(PublisherRevisionBase):
    class Meta:
        db_table = 'oi_publisher_revision'
        ordering = ['-created', '-id']

    objects=PublisherRevisionManager()

    publisher=models.ForeignKey('gcd.Publisher', null=True,
                                related_name='revisions')

    country = models.ForeignKey('gcd.Country', db_index=True)

    is_master = models.BooleanField(default=0, db_index=True,
      help_text='Check if this is a top-level publisher that may contain '
                'imprints.')
    parent = models.ForeignKey('gcd.Publisher',
                               null=True, blank=True, db_index=True,
                               related_name='imprint_revisions')

    def _source(self):
        return self.publisher

    def _source_name(self):
        return 'publisher'

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

    def _queue_name(self):
        return u'%s (%s, %s)' % (self.name, self.year_began,
                                 self.country.code.upper())

    def _field_list(self):
        fields = []
        fields.extend(PublisherRevisionBase._field_list(self))
        fields.extend(('country', 'is_master', 'parent'))
        return fields

    def commit_to_display(self, clear_reservation=True):
        pub = self.publisher
        if pub is None:
            pub = Publisher(imprint_count=0,
                            series_count=0,
                            issue_count=0)
            if self.parent:
                self.parent.imprint_count += 1
                self.parent.save()
            else:
                publisher_count = CountStats.objects.get(name='publishers')
                publisher_count.count += 1
                publisher_count.save()
        elif self.deleted:
            if self.parent:
                self.parent.imprint_count -= 1
                self.parent.save()
            else:
                publisher_count = CountStats.objects.get(name='publishers')
                publisher_count.count -= 1
                publisher_count.save()
            pub.delete()
            return

        self._assign_base_fields(pub)
        pub.country = self.country
        pub.is_master = self.is_master
        pub.parent = self.parent

        if clear_reservation:
            pub.reserved = False

        pub.save()
        if self.publisher is None:
            self.publisher = pub
            self.save()

    def _indicia_publisher_count(self):
        if self.source is None:
            return 0
        return self.source.indicia_publisher_count
    indicia_publisher_count = property(_indicia_publisher_count)

    def _brand_count(self):
        if self.source is None:
            return 0
        return self.source.brand_count
    brand_count = property(_brand_count)

    def has_imprints(self):
        return self.imprint_set.count() > 0

    def is_imprint(self):
        return self.parent_id is not None and self.parent_id != 0

    def get_absolute_url(self):
        if self.publisher is None:
            return "/publisher/revision/%i/preview" % self.id
        return self.publisher.get_absolute_url()

    def get_official_url(self):
        """
        TODO: See the apps.gcd.models.Publisher class for plans for removal
        of this method.
        """
        if self.url is None:
            return ''
        return self.url

    def _do_complete_added_revision(self, parent=None):
        """
        Do the necessary processing to complete the fields of a new
        series revision for adding a record before it can be saved.
        """
        self.parent = parent
        if self.parent is None:
            self.is_master = True

class IndiciaPublisherRevisionManager(PublisherRevisionManagerBase):

    def clone_revision(self, indicia_publisher, changeset):
        """
        Given an existing Publisher instance, create a new revision based on it.

        This new revision will be where the edits are made.
        Entirely new publishers should be started by simply instantiating
        a new PublisherRevision directly.
        """
        return PublisherRevisionManagerBase.clone_revision(self,
                                              instance=indicia_publisher,
                                              instance_class=IndiciaPublisher,
                                              changeset=changeset)

    def _do_create_revision(self, indicia_publisher, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        kwargs = self._base_field_kwargs(indicia_publisher)

        revision = IndiciaPublisherRevision(
          indicia_publisher=indicia_publisher,
          changeset=changeset,

          is_surrogate=indicia_publisher.is_surrogate,
          country=indicia_publisher.country,
          parent=indicia_publisher.parent,
          **kwargs)

        revision.save()
        return revision

class IndiciaPublisherRevision(PublisherRevisionBase):
    class Meta:
        db_table = 'oi_indicia_publisher_revision'
        ordering = ['-created', '-id']

    objects = IndiciaPublisherRevisionManager()

    indicia_publisher = models.ForeignKey('gcd.IndiciaPublisher', null=True,
                                           related_name='revisions')

    is_surrogate = models.BooleanField(db_index=True)

    country = models.ForeignKey('gcd.Country', db_index=True,
                                related_name='indicia_publishers_revisions')

    parent = models.ForeignKey('gcd.Publisher',
                               null=True, blank=True, db_index=True,
                               related_name='indicia_publisher_revisions')

    def _source(self):
        return self.indicia_publisher

    def _source_name(self):
        return 'indicia_publisher'

    def _field_list(self):
        fields = []
        fields.extend(PublisherRevisionBase._field_list(self))
        fields.extend(('is_surrogate', 'country', 'parent'))
        return fields

    def _queue_name(self):
        return u'%s (%s, %s)' % (self.name, self.year_began,
                                 self.country.code.upper())

    def _issue_set(self):
        if self.indicia_publisher is None:
            return Issue.objects.filter(pk__isnull=True)
        return self.indicia_publisher.series_set
    issue_set = property(_issue_set)

    def _issue_count(self):
        if self.indicia_publisher is None:
            return 0
        return self.indicia_publisher.issue_count
    issue_count = property(_issue_count)

    def _do_complete_added_revision(self, parent):
        """
        Do the necessary processing to complete the fields of a new
        series revision for adding a record before it can be saved.
        """
        self.parent = parent

    def commit_to_display(self, clear_reservation=True):
        ipub = self.indicia_publisher
        if ipub is None:
            ipub = IndiciaPublisher()
            self.parent.indicia_publisher_count += 1
            self.parent.save()
            publisher_count = CountStats.objects.get(name='indicia publishers')
            publisher_count.count += 1
            publisher_count.save()

        elif self.deleted:
            self.parent.indicia_publisher_count -= 1
            self.parent.save()
            publisher_count = CountStats.objects.get(name='indicia publishers')
            publisher_count.count -= 1
            publisher_count.save()
            ipub.delete()
            return

        self._assign_base_fields(ipub)
        ipub.is_surrogate = self.is_surrogate
        ipub.country = self.country
        ipub.parent = self.parent

        if clear_reservation:
            ipub.reserved = False

        ipub.save()
        if self.indicia_publisher is None:
            self.indicia_publisher = ipub
            self.save()

    def get_absolute_url(self):
        if self.indicia_publisher is None:
            return "/indicia_publisher/revision/%i/preview" % self.id
        return self.indicia_publisher.get_absolute_url()

class BrandRevisionManager(PublisherRevisionManagerBase):

    def clone_revision(self, brand, changeset):
        """
        Given an existing Publisher instance, create a new revision based on it.

        This new revision will be where the edits are made.
        Entirely new publishers should be started by simply instantiating
        a new PublisherRevision directly.
        """
        return PublisherRevisionManagerBase.clone_revision(self,
                                                           instance=brand,
                                                           instance_class=Brand,
                                                           changeset=changeset)

    def _do_create_revision(self, brand, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        kwargs = self._base_field_kwargs(brand)

        revision = BrandRevision(
          brand=brand,
          changeset=changeset,

          parent=brand.parent,
          **kwargs)

        revision.save()
        return revision

class BrandRevision(PublisherRevisionBase):
    class Meta:
        db_table = 'oi_brand_revision'
        ordering = ['-created', '-id']

    objects = BrandRevisionManager()

    brand = models.ForeignKey('gcd.Brand', null=True, related_name='revisions')

    parent = models.ForeignKey('gcd.Publisher',
                               null=True, blank=True, db_index=True,
                               related_name='brand_revisions')

    def _source(self):
        return self.brand

    def _source_name(self):
        return 'brand'

    def _field_list(self):
        fields = []
        fields.extend(PublisherRevisionBase._field_list(self))
        fields.append('parent')
        return fields

    def _queue_name(self):
        return u'%s (%s)' % (self.name, self.year_began)

    def _issue_set(self):
        if self.brand is None:
            return Issue.objects.filter(pk__isnull=True)
        return self.brand.series_set
    issue_set = property(_issue_set)

    def _issue_count(self):
        if self.brand is None:
            return 0
        return self.brand.issue_count
    issue_count = property(_issue_count)

    def _do_complete_added_revision(self, parent):
        """
        Do the necessary processing to complete the fields of a new
        series revision for adding a record before it can be saved.
        """
        self.parent = parent

    def commit_to_display(self, clear_reservation=True):
        brand = self.brand
        if brand is None:
            brand = Brand()
            self.parent.brand_count += 1
            self.parent.save()
            publisher_count = CountStats.objects.get(name='brands')
            publisher_count.count += 1
            publisher_count.save()

        elif self.deleted:
            self.parent.brand_count -= 1
            self.parent.save()
            publisher_count = CountStats.objects.get(name='brands')
            publisher_count.count -= 1
            publisher_count.save()
            brand.delete()
            return

        self._assign_base_fields(brand)
        brand.parent = self.parent

        if clear_reservation:
            brand.reserved = False

        brand.save()
        if self.brand is None:
            self.brand = brand
            self.save()

    def get_absolute_url(self):
        if self.brand is None:
            return "/brand/revision/%i/preview" % self.id
        return self.brand.get_absolute_url()

class SeriesRevisionManager(RevisionManager):
    """
    Custom manager allowing the cloning of revisions from existing rows.
    """

    def clone_revision(self, series, changeset):
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
                                              changeset=changeset)

    def _do_create_revision(self, series, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        revision = SeriesRevision(
          # revision-specific fields:
          series=series,
          changeset=changeset,

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
          imprint=series.imprint)

        revision.save()
        return revision

class SeriesRevision(Revision):
    class Meta:
        db_table = 'oi_series_revision'
        ordering = ['-created', '-id']

    objects=SeriesRevisionManager()

    series = models.ForeignKey(Series, null=True, related_name='revisions')

    # When adding a series, this requests the ongoing reservation upon approval of
    # the new series.  The request will be granted unless the indexer has reached
    # their maximum number of ongoing reservations at the time of approval.
    reservation_requested = models.BooleanField(default=0)

    name = models.CharField(max_length=255, blank=True)
    format = models.CharField(max_length=255, blank=True)
    year_began = models.IntegerField(blank=True)
    year_ended = models.IntegerField(null=True, blank=True)
    is_current = models.BooleanField()

    # Publication notes are not displayed in the current UI but may
    # be accessed in the OI.
    publication_notes = models.TextField(blank=True)

    # Fields for tracking relationships between series.
    # Crossref fields don't appear to really be used- nearly all null.
    tracking_notes = models.TextField(blank=True)

    notes = models.TextField(blank=True)

    # Country and Language info.
    country = models.ForeignKey(Country, related_name='series_revisions')
    language = models.ForeignKey(Language, related_name='series_revisions')

    # Fields related to the publishers table.
    publisher = models.ForeignKey(Publisher,
                                  related_name='series_revisions')
    imprint = models.ForeignKey(Publisher, null=True, blank=True,
                                related_name='imprint_series_revisions')

    def _source(self):
        return self.series

    def _source_name(self):
        return 'series'

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

    def get_ongoing_revision(self):
        if self.series is None:
            return None
        return self.series.get_ongoing_revision()

    def _field_list(self):
        return ('name',
                'format',
                'year_began',
                'year_ended',
                'is_current',
                'publisher',
                'imprint',
                'country',
                'language',
                'publication_notes',
                'tracking_notes',
                'notes',)

    def _do_complete_added_revision(self, publisher, imprint=None):
        """
        Do the necessary processing to complete the fields of a new
        series revision for adding a record before it can be saved.
        """
        self.publisher = publisher
        self.imprint = imprint

    def commit_to_display(self, clear_reservation=True):
        series = self.series
        if series is None:
            series = Series(issue_count=0)
            self.publisher.series_count += 1
            self.publisher.save()
            if self.imprint:
                self.imprint.series_count += 1
                self.imprint.save()       
            series_count = CountStats.objects.get(name='series')
            series_count.count += 1
            series_count.save()
        elif self.deleted:
            self.publisher.series_count -= 1
            self.publisher.issue_count -= series.issue_count
            self.publisher.save()
            if self.imprint:
                self.imprint.series_count -= 1
                self.imprint.save()       
            series.delete()
            series_count = CountStats.objects.get(name='series')
            series_count.count -= 1
            series_count.save()
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
            self.save()

    def get_absolute_url(self):
        if self.series is None:
            return "/series/revision/%i/preview" % self.id
        return self.series.get_absolute_url()

    def __unicode__(self):
        if self.series is None:
            return u'%s (%s series)' % (self.name, self.year_began)
        return unicode(self.series)

class IssueRevisionManager(RevisionManager):

    def clone_revision(self, issue, changeset):
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
                                              changeset=changeset)

    def _do_create_revision(self, issue, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        revision = IssueRevision(
          # revision-specific fields:
          issue=issue,
          changeset=changeset,

          # copied fields:
          number=issue.number,
          volume=issue.volume,
          no_volume=issue.no_volume,
          display_volume_with_number=issue.display_volume_with_number,
          publication_date=issue.publication_date,
          price=issue.price,
          key_date=issue.key_date,
          indicia_frequency=issue.indicia_frequency,
          series=issue.series,
          indicia_publisher=issue.indicia_publisher,
          brand=issue.brand,
          page_count=issue.page_count,
          page_count_uncertain=issue.page_count_uncertain,
          editing=issue.editing,
          no_editing=issue.no_editing,
          notes=issue.notes)

        revision.save()
        return revision

class IssueRevision(Revision):
    class Meta:
        db_table = 'oi_issue_revision'
        ordering = ['-created', '-id']

    objects = IssueRevisionManager()

    issue = models.ForeignKey(Issue, null=True, related_name='revisions')

    # If not null, insert or move the issue after the given issue
    # when saving back the the DB. If null, place at the beginning of
    # the series.
    after = models.ForeignKey(Issue, null=True, related_name='after_revisions')

    # This is used *only* for multiple issues within the same changeset.
    # It does NOT correspond directly to gcd_issue.sort_code, which must be
    # calculated at the time the revision is committed.
    revision_sort_code = models.IntegerField(null=True)

    # When adding an issue, this requests the reservation upon approval of
    # the new issue.  The request will be granted unless an ongoing reservation
    # is in place at the time of approval.
    reservation_requested = models.BooleanField(default=0)

    number = models.CharField(max_length=50)
    volume = models.IntegerField(max_length=255, null=True, blank=True)
    no_volume = models.BooleanField(default=0)
    display_volume_with_number = models.BooleanField(default=0)

    publication_date = models.CharField(max_length=255, blank=True)
    indicia_frequency = models.CharField(max_length=255, blank=True)
    key_date = models.CharField(max_length=10, blank=True)

    price = models.CharField(max_length=255, blank=True)
    page_count = models.DecimalField(max_digits=10, decimal_places=3,
                                     null=True, blank=True)
    page_count_uncertain = models.BooleanField(default=0)

    editing = models.TextField(blank=True)
    no_editing = models.BooleanField(default=0)
    notes = models.TextField(blank=True)

    series = models.ForeignKey(Series, related_name='issue_revisions')
    indicia_publisher = models.ForeignKey(IndiciaPublisher, null=True,
                                          related_name='issue_revisions')
    brand = models.ForeignKey(Brand, null=True, related_name='issue_revisions')

    def _display_number(self):
        """
        Implemented separately because it needs to use the revision's
        display field and not the source's.  Although the actual contstruction
        of the string should really be factored out somewhere for consistency.
        """
        if self.display_volume_with_number:
            return u'v%s#%s' % (self.volume, self.number)
        return self.number
    display_number = property(_display_number)

    def _sort_code(self):
        if self.issue is None:
            return 0
        return self.issue.sort_code
    sort_code = property(_sort_code)

    def _story_set(self):
        return self.ordered_story_revisions()
    story_set = property(_story_set)

    def _cover(self):
        if self.issue is None:
            # TODO: This is a problem as there should always be a cover.
            # TODO: Deal with after reorganized covers table is done.
            # TODO: How do we initialize cover on add anyway?  Add not working
            # TODO: yet so it doesn't matter until we get there.
            return None
        return self.issue.cover
    cover = property(_cover)

    def _reservation_set(self):
        # Just totally fake this for now.
        return Reservation.objects.filter(pk__isnull=True)
    reservation_set = property(_reservation_set)

    def get_prev_next_issue(self):
        if self.issue is not None:
            return self.issue.get_prev_next_issue()
        if self.after is not None:
            [p, n] = self.after.get_prev_next_issue()
            return [self.after, n]
        return [None, None]

    def _field_list(self):
        return ('volume', 'number', 'no_volume', 'display_volume_with_number',
                'publication_date', 'key_date', 'indicia_frequency',
                'price', 'page_count', 'page_count_uncertain',
                'editing', 'no_editing', 'notes',
                'series', 'indicia_publisher', 'brand')

    def _source(self):
        return self.issue

    def _source_name(self):
        return 'issue'

    def _do_complete_added_revision(self, series):
        """
        Do the necessary processing to complete the fields of a new
        issue revision for adding a record before it can be saved.
        """
        self.series = series

    def _story_revisions(self):
        if self.source is None:
            return self.changeset.storyrevisions.filter(issue__isnull=True)
        return self.changeset.storyrevisions.filter(issue=self.source)

    def ordered_story_revisions(self):
        return self._story_revisions().order_by('sequence_number')

    def next_sequence_number(self):
        stories = self._story_revisions()
        if stories.count():
            return stories.order_by('-sequence_number')[0].sequence_number + 1
        return 0

    def commit_to_display(self, clear_reservation=True, space_count=1):
        issue = self.issue

        if issue is None:
            if self.after is None:
                after_code = -1
            else:
                after_code = self.after.sort_code

            # sort_codes tend to be sequential, so just always increment them
            # out of the way.
            later_issues = Issue.objects.filter(
              series=self.series,
              sort_code__gt=after_code).order_by('-sort_code')

            # Make space for the issue(s) being added.  The changeset will
            # pass a larger number or zero in order to make all necessary
            # space for a multiple add on the first pass, and then not
            # have to update this for the remaining issues.
            if space_count > 0:
                # Unique constraint prevents us from doing this:
                # later_issues.update(sort_code=F('sort_code') + space_count)
                # which is vastly more efficient.  TODO: revisit.
                for later_issue in later_issues:
                    later_issue.sort_code += space_count
                    later_issue.save()

            issue = Issue(sort_code=after_code + 1)

            self.series.issue_count += 1
            self.series.publisher.issue_count += 1
            self.series.publisher.save()
            if self.brand:
                self.brand.issue_count += 1
                self.brand.save()
            if self.indicia_publisher:
                self.indicia_publisher.issue_count += 1
                self.indicia_publisher.save()
            if self.series.imprint:
                self.series.imprint.issue_count += 1
                self.series.imprint.save()       
            issue_count = CountStats.objects.get(name='issues')
            issue_count.count += 1
            issue_count.save()

        elif self.deleted:
            self.series.issue_count -= 1
            self.series.publisher.issue_count -= 1
            self.series.publisher.save()
            if self.brand:
                self.brand.issue_count -= 1
                self.brand.save()
            if self.indicia_publisher:
                self.indicia_publisher.issue_count -= 1
                self.indicia_publisher.save()
            if self.series.imprint:
                self.series.imprint.issue_count -= 1
                self.series.imprint.save()       
            issue_count = CountStats.objects.get(name='issues')
            issue_count.count -= 1
            issue_count.save()
            issue.delete()
            self._check_first_last()
            return

        issue.number = self.number
        issue.volume = self.volume
        issue.no_volume = self.no_volume
        issue.display_volume_with_number = self.display_volume_with_number

        issue.publication_date = self.publication_date
        issue.indicia_frequency = self.indicia_frequency
        issue.key_date = self.key_date

        issue.price = self.price
        issue.page_count = self.page_count
        issue.page_count_uncertain = self.page_count_uncertain

        issue.editing = self.editing
        issue.no_editing = self.no_editing
        issue.notes = self.notes

        issue.series = self.series
        issue.indicia_publisher = self.indicia_publisher
        issue.brand = self.brand

        if clear_reservation:
            issue.reserved = False

        issue.save()
        if self.issue is None:
            # TODO: Remove cover code (and maybe series?) when we can.
            issue.cover_set.create(code='000', series=self.series,
                                   modified=datetime.now())

            self.issue = issue
            self.save()

        # TODO: Currently can't change sort code here so really only need
        # TODO: to call when issue added (deleted covered above).
        # TODO: But this may change?  Just call for now.
        self._check_first_last()

    def _check_first_last(self):
        issues = self.series.issue_set.order_by('sort_code')
        if issues.count() == 0:
            self.series.first_issue = None
            self.series.last_issue = None
        else:
            self.series.first_issue = issues[0]
            self.series.last_issue = issues[len(issues) - 1]
        self.series.save()

    def __unicode__(self):
        """
        Re-implement locally instead of using self.issue because it may change.
        """
        return u'%s #%s' % (self.series, self.display_number)

class StoryRevisionManager(RevisionManager):

    def clone_revision(self, story, changeset):
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
                                              changeset=changeset)

    def _do_create_revision(self, story, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        revision = StoryRevision(
          # revision-specific fields:
          story=story,
          changeset=changeset,

          # copied fields:
          title=story.title,
          title_inferred=story.title_inferred,
          feature=story.feature,
          page_count=story.page_count,
          page_count_uncertain=story.page_count_uncertain,

          script=story.script,
          pencils=story.pencils,
          inks=story.inks,
          colors=story.colors,
          letters=story.letters,
          editing=story.editing,

          no_script=story.no_script,
          no_pencils=story.no_pencils,
          no_inks=story.no_inks,
          no_colors=story.no_colors,
          no_letters=story.no_letters,
          no_editing=story.no_editing,

          notes=story.notes,
          synopsis=story.synopsis,
          characters=story.characters,
          reprint_notes=story.reprint_notes,
          genre=story.genre,
          type=story.type,
          job_number=story.job_number,
          sequence_number=story.sequence_number,

          issue=story.issue)

        revision.save()
        return revision

class StoryRevision(Revision):
    class Meta:
        db_table = 'oi_story_revision'
        ordering = ['-created', '-id']

    objects = StoryRevisionManager()

    story = models.ForeignKey(Story, null=True,
                              related_name='revisions')

    title = models.CharField(max_length=255, blank=True)
    title_inferred = models.BooleanField(default=0, db_index=True)
    feature = models.CharField(max_length=255, blank=True)
    type = models.ForeignKey(StoryType)
    sequence_number = models.IntegerField()

    page_count = models.DecimalField(max_digits=10, decimal_places=3,
                                     null=True, blank=True)
    page_count_uncertain = models.BooleanField(default=0)

    script = models.TextField(blank=True)
    pencils = models.TextField(blank=True)
    inks = models.TextField(blank=True)
    colors = models.TextField(blank=True)
    letters = models.TextField(blank=True)
    editing = models.TextField(blank=True)

    no_script = models.BooleanField(default=0)
    no_pencils = models.BooleanField(default=0)
    no_inks = models.BooleanField(default=0)
    no_colors = models.BooleanField(default=0)
    no_letters = models.BooleanField(default=0)
    no_editing = models.BooleanField(default=0)

    job_number = models.CharField(max_length=25, blank=True)
    genre = models.CharField(max_length=255, blank=True)
    characters = models.TextField(blank=True)
    synopsis = models.TextField(blank=True)
    reprint_notes = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    issue = models.ForeignKey(Issue, related_name='story_revisions')

    def _field_list(self):
        return (
          'title',
          'title_inferred',
          'feature',
          'page_count',
          'page_count_uncertain',
          'characters',
          'script',
          'pencils',
          'inks',
          'colors',
          'letters',
          'editing',
          'no_script',
          'no_pencils',
          'no_inks',
          'no_colors',
          'no_letters',
          'no_editing',
          'notes',
          'synopsis',
          'reprint_notes',
          'genre',
          'type',
          'sequence_number',
          'job_number',
          'issue',
        )

    def _source(self):
        return self.story

    def _source_name(self):
        return 'story'

    def _do_complete_added_revision(self, issue):
        """
        Do the necessary processing to complete the fields of a new
        story revision for adding a record before it can be saved.
        """
        self.issue = issue

    def commit_to_display(self, clear_reservation=True):
        story = self.story
        if story is None:
            story = Story()
            if self.type.name == 'story':
                self.issue.story_type_count +=1
                self.issue.save()
                if self.issue.story_type_count == 1:
                    issue_count = CountStats.objects.get(name='issue indexes')
                    issue_count.count += 1
                    issue_count.save()
            story_count = CountStats.objects.get(name='stories')
            story_count.count += 1
            story_count.save()
        elif self.deleted:
            if story.type.name == 'story':
                self.issue.story_type_count -=1
                self.issue.save()
                if self.issue.story_type_count == 0:
                    issue_count = CountStats.objects.get(name='issue indexes')
                    issue_count.count -= 1
                    issue_count.save()
            story_count = CountStats.objects.get(name='stories')
            story_count.count -= 1
            story_count.save()
            story.delete()
            return

        elif self.type.name == 'story' and story.type.name != 'story':
            self.issue.story_type_count += 1
            self.issue.save()
            if self.issue.story_type_count == 1:
                issue_count = CountStats.objects.get(name='issue indexes')
                issue_count.count += 1
                issue_count.save()
        elif self.type.name != 'story' and story.type.name == 'story':
            self.issue.story_type_count -= 1
            self.issue.save()
            if self.issue.story_type_count == 0:
                issue_count = CountStats.objects.get(name='issue indexes')
                issue_count.count -= 1
                issue_count.save()

        story.title = self.title
        story.title_inferred = self.title_inferred
        story.feature = self.feature
        story.issue = self.issue
        story.page_count = self.page_count
        story.page_count_uncertain = self.page_count_uncertain

        story.script = self.script
        story.pencils = self.pencils
        story.inks = self.inks
        story.colors = self.colors
        story.letters = self.letters
        story.editing = self.editing

        story.no_script = self.no_script
        story.no_pencils = self.no_pencils
        story.no_inks = self.no_inks
        story.no_colors = self.no_colors
        story.no_letters = self.no_letters
        story.no_editing = self.no_editing

        story.notes = self.notes
        story.synopsis = self.synopsis
        story.reprint_notes = self.reprint_notes
        story.characters = self.characters
        story.genre = self.genre
        story.type = self.type
        story.job_number = self.job_number
        story.sequence_number = self.sequence_number

        if clear_reservation:
            story.reserved = False

        story.save()

        if self.story is None:
            self.story = story
            self.save()

    def has_credits(self):
        return self.script or \
               self.pencils or \
               self.inks or \
               self.colors or \
               self.letters or \
               self.editing
               
    def has_content(self):
        return self.genre or \
               self.characters or \
               self.synopsis or \
               self.reprint_notes or \
               self.job_number

    def has_data(self):
        return self.has_credits() or self.has_content() or self.notes

    def __unicode__(self):    
        """
        Re-implement locally instead of using self.story because it may change.
        """
        return u'%s (%s: %s)' % (self.feature, self.type, self.page_count)

