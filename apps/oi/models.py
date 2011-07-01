# -*- coding: utf-8 -*-
import itertools
import operator
import re
from stdnum import isbn

from django.db import models, settings
from django.db.models import Q, F, Count, Max
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import User
from django.contrib.contenttypes import models as content_models
from django.contrib.contenttypes import generic
from django.utils.safestring import mark_safe
from django.core.validators import RegexValidator

from apps.oi import states
from apps.gcd.models import *

LANGUAGE_STATS = ['de',]

# Changeset type "constants"
CTYPES = {
    'unknown': 0,
    'publisher': 1,
    'brand': 2,
    'indicia_publisher': 3,
    'series': 4,
    'issue_add': 5,
    'issue': 6,
    'cover': 7,
    'issue_bulk': 8,
    'variant_add': 9
}

CTYPES_INLINE = frozenset((CTYPES['publisher'],
                           CTYPES['brand'],
                           CTYPES['indicia_publisher'],
                           CTYPES['series'],
                           CTYPES['cover']))

# Change types that *might* be bulk changes.  But might just have one revision.
CTYPES_BULK = frozenset((CTYPES['issue_bulk'],
                         CTYPES['issue_add']))

ACTION_ADD = 'add'
ACTION_DELETE = 'delete'
ACTION_MODIFY = 'modify'

IMP_BONUS_ADD = 10
IMP_COVER_VALUE = 5
IMP_APPROVER_VALUE = 3
IMP_DELETE = 1


def check_delete_imprint(imprint):
    '''
    Check an imprints for deletion and delete if possible.
    Note that imprints cannot be reserved by users.
    Need to re-fetch the imprint from the db since we did an F()-update before
    '''
    imprint = Publisher.objects.get(id=imprint.id)
    if imprint.deletable():
        from apps.oi.views import _do_reserve
        anon = User.objects.get(username=settings.ANON_USER_NAME)
        changeset=_do_reserve(anon, imprint, 'publisher', delete=True)
        if changeset == None: # something is wrong
            raise ValueError
        changeset.state=states.REVIEWING
        changeset.approver = anon
        changeset.save()
        comment = changeset.comments.create(commenter=anon,
          text='Automatically generated changeset for the deletion of an imprint.',
          old_state=states.UNRESERVED, new_state=states.PENDING)
        changeset.approve(notes='Automatically approved deletion.')
        return True
    else:
        return False


def update_count(field, delta, language=None):
    '''
    updates statistics, for all and per language
    CountStats with language=None is for all languages
    '''
    stat = CountStats.objects.get(name=field, language=None)
    stat.count = F('count') + delta
    stat.save()

    if language:
        stat = CountStats.objects.filter(name=field, language=language)
        if stat.count():
            stat = stat[0]
            stat.count = F('count') + delta
            stat.save()
        else:
            CountStats.objects.init_stats(language)

def set_series_first_last(series):
    '''
    set first_issue and last_issue for given series
    '''
    issues = series.active_issues().order_by('sort_code')
    if issues.count() == 0:
        series.first_issue = None
        series.last_issue = None
    else:
        series.first_issue = issues[0]
        series.last_issue = issues[len(issues) - 1]
    series.save()

def validated_isbn(entered_isbn):
    '''
    returns ISBN10 or ISBN13 if valid ISBN, empty string otherwiese
    '''
    isbns = entered_isbn.split(';')
    valid_isbns = True
    for num in isbns:
        valid_isbns &= isbn.is_valid(num)
    if valid_isbns and len(isbns) == 1:
        return isbn.compact(isbns[0])
    elif valid_isbns and len(isbns) == 2:
        compacted_isbns = [isbn.compact(isbn.to_isbn13(i)) for i in isbns]
        # if two ISBNs it must be corresponding ISBN10 and ISBN13
        if compacted_isbns[0] == compacted_isbns[1]:
            # always store ISBN13 if both exist
            return compacted_isbns[0]
    return ''

def remove_leading_article(name):
    '''
    returns the name with the leading article (separated by "'"
    or whitespace) removed
    '''
    article_match = re.match(r"\w+['\s]\s*(.*)$", name, re.UNICODE)
    if article_match:
        return article_match.group(1)
    else:
        return name

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

    change_type = models.IntegerField(db_index=True)
    migrated = models.BooleanField(default=False, db_index=True, blank=True)
    date_inferred = models.BooleanField(default=False, blank=True)

    imps = models.IntegerField(default=0)

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)

    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)
        self._inline_revision = None

    def _revision_sets(self):
        if self.change_type in [CTYPES['issue'], CTYPES['variant_add']]:
            return (self.issuerevisions.all().select_related('issue', 'series'),
                    self.storyrevisions.all(), self.coverrevisions.all())

        if self.change_type in [CTYPES['issue_add'], CTYPES['issue_bulk']]:
            return (self.issuerevisions.all().select_related('issue', 'series'),)

        if self.change_type == CTYPES['cover']:
            return (self.coverrevisions.all().select_related('issue__series'),)

        if self.change_type == CTYPES['series']:
            return (self.seriesrevisions.all(),)

        if self.change_type == CTYPES['publisher']:
            return (self.publisherrevisions.all(), self.brandrevisions.all(),
                    self.indiciapublisherrevisions.all())

        if self.change_type == CTYPES['brand']:
            return (self.brandrevisions.all(),)

        if self.change_type == CTYPES['indicia_publisher']:
            return (self.indiciapublisherrevisions.all(),)

    def _revisions(self):
        """
        Fake up an iterable (not actually a list) of all revisions,
        in canonical order.
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
        return self.change_type in CTYPES_INLINE

    def inline_revision(self):
        if self.inline():
            if self._inline_revision is None:
                if self.change_type == CTYPES['publisher']:
                    # to filter out all the imprints in a publisher deletion
                    # changeset
                    if self.publisherrevisions.count() > 1:
                        self._inline_revision = \
                          self.publisherrevisions.filter(is_master=True)[0]
                    else:
                        self._inline_revision = \
                           self.publisherrevisions.get()
                else:
                    self._inline_revision = self.revisions.next()
        return self._inline_revision

    def deleted(self):
        if self.inline():
            # everything but issues
            return self.inline_revision().deleted
        elif self.issuerevisions.count() == 1:
            # single issue deletions
            return self.issuerevisions.all()[0].deleted
        else:
            # bulk issue deletions not supported
            return False

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
        if self.change_type in CTYPES_BULK:
            return unicode(self)
        elif self.change_type == CTYPES['issue']:
            return self.revisions.next().queue_name()
        elif self.change_type == CTYPES['variant_add']:
            return self.issuerevisions.get(variant_of__isnull=False).queue_name()
        else:
            return self.inline_revision().queue_name()

    def queue_descriptor(self):
        if self.change_type == CTYPES['issue_add']:
            return u'[ADDED]'
        elif self.change_type == CTYPES['variant_add']:
            return u'[VARIANT]'
        return self.revisions.next().queue_descriptor()

    def changeset_action(self):
        """
        Produce a human-readable description of whether we're adding, removing
        or modifying data with this changeset.
        """
        if self.change_type in [CTYPES['issue_add'], CTYPES['variant_add']]:
            return ACTION_ADD
        elif self.change_type == CTYPES['issue_bulk']:
            return ACTION_MODIFY

        revision = self.revisions.next()
        if revision.deleted:
            return ACTION_DELETE
        elif revision.source is None or revision.previous() is None:
            return ACTION_ADD
        return ACTION_MODIFY

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
        if self.approver is None and (self.indexer.indexer.is_new and \
           self.indexer.indexer.mentor is not None and \
           self.change_type != CTYPES['cover']):
            self.approver = self.indexer.indexer.mentor

        new_state = states.PENDING
        if self.approver is not None:
            new_state = states.REVIEWING
        return new_state

    def submit(self, notes='', delete=False):
        """
        Submit changes for approval.
        If this is the first such submission or if the prior approver released
        the changes back to the general queue, then the changes go into the
        general approval queue.  If it is an edit in reply to a disapproval,
        then the changes go directly back into the approver's queue.
        """

        if (self.state != states.OPEN) and \
           not (delete and self.state == states.UNRESERVED):
            raise ValueError, "Only OPEN changes can be submitted for approval."

        new_state = self._check_approver()

        self.comments.create(commenter=self.indexer,
                             text=notes,
                             old_state=self.state,
                             new_state=new_state)
        self.state = new_state

        # Since a submission is what puts the changeset in a non-editable state,
        # calculate the imps now.
        self.calculate_imps()
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
        if self.state not in states.ACTIVE:
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
        if self.approver:
            self.approver.indexer.add_imps(IMP_APPROVER_VALUE)

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
        if self.state not in states.ACTIVE or \
           self.approver is None:
            raise ValueError, "Only changes with an approver may be unassigned."

        if self.state == states.REVIEWING:
            new_state = states.PENDING
        else:
            new_state = self.state

        self.comments.create(commenter=self.approver,
                             text=notes,
                             old_state=self.state,
                             new_state=new_state)
        self.approver = None
        self.state = new_state
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
        if self.change_type == CTYPES['issue_add'] and issue_revision_count > 1:
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
        self.indexer.indexer.add_imps(self.total_imps())
        self.approver.indexer.add_imps(IMP_APPROVER_VALUE)

        for revision in self.revisions:
            revision._post_commit_to_display()

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

    def calculate_imps(self):
        """
        Go through and add up the imps from the revisions, but don't commit
        to the database.
        """
        self.imps = 0
        if self.change_type in CTYPES_BULK:
            # Currently, bulk changes are only allowed when the changes
            # are uniform across all revisions in the change.  When we
            # allow non-uniform changes we may need to calculate all of
            # the imp revisions and take the maximum value or something.
            self.imps += self.revisions.next().calculate_imps()
        else:
            for revision in self.revisions:
                # Deletions are a bit strange.  Essentially, you get one
                # point per button you press, however many objects that
                # button deletes.  Similar to bulk adds counting the same
                # as a single add.  Story objects are deleted one at a time,
                # and multiple of them can be deleted in a single changeset
                # without deleting the entire issue.  Issue and other objects,
                # however, are only deleted when the entire action of the
                # changeset is a deletion.  So they get one IMP_DELETE no
                # matter what else was in the changeset.

                if revision.deleted:
                    if isinstance(revision, StoryRevision):
                        self.imps += IMP_DELETE
                    else:
                        self.imps = IMP_DELETE
                        return
                else:
                    self.imps += revision.calculate_imps()

    def magnitude(self):
        """
        A rough guide to the size of the change.  Currently implemented by
        examining the calculated imps, but may be switched to a changed field
        count of some sort if we change how imps work or decide that a different
        metric will work better as a size estimate.  For instance number of
        characters (as in letters, not the characters field) changed.
        """
        return self.imps

    def total_imps(self):
        """
        The total number of imps awarded for this changeset, including both
        field-calculated imps and bonuses such as the add bonus.
        """
        calculated = self.imps
        if self.change_type != CTYPES['cover'] and \
           self.changeset_action() == ACTION_ADD:
            return calculated + IMP_BONUS_ADD
        return calculated

    def __unicode__(self):
        if self.inline():
            return  unicode(self.inline_revision())
        ir_count = self.issuerevisions.count()
        if ir_count == 1:
            return unicode(self.issuerevisions.all()[0])
        if self.change_type == CTYPES['variant_add']:
            return unicode(self.issuerevisions.get(variant_of__isnull=False)) \
              + ' [Variant]'
        if ir_count > 1 and self.change_type == CTYPES['issue_add']:
            first = self.issuerevisions.order_by('revision_sort_code')[0]
            last = self.issuerevisions.order_by('-revision_sort_code')[0]
            return u'%s #%s - %s' % (first.series, first.display_number,
                                                  last.display_number)
        if self.change_type == CTYPES['issue_bulk']:
            return unicode(u'%s and %d other issues' %
                           (self.issuerevisions.all()[0], ir_count - 1))
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

    content_type = models.ForeignKey(content_models.ContentType, null=True)
    revision_id = models.IntegerField(db_index=True, null=True)
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
    end in either the APPROVED or DISCARDED state.
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

    comments = generic.GenericRelation(ChangesetComment,
                                       content_type_field='content_type',
                                       object_id_field='revision_id')

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)

    is_changed = False

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

    def _changed(self):
        """
        The dictionary of change information between this revision and the
        previous revision of the same source object.
        """
        pass

    def field_list(self):
        """
        Public field list interface, in case we ever decide we want
        to process child class field lists before returning them.
        """
        return self._field_list()

    def _field_list(self):
        """
        Default implementation for objects that have no fields (like covers).
        """
        return []

    def _get_blank_values(self):
        """
        Create a dictionary with the "blank" values for all of the fields
        of this type of revision.  This is used to determine the change
        value of newly added objects.  Blank values are often not allowed
        in the database (i.e. NOT NULL columns) so this cannot be done
        with a revision instance.  Blank values should be set.
        """
        raise NotImplementedError

    def previous(self):
        # We never spontaneously gain a previous revision during normal operation,
        # so it's safe to cache this.
        if hasattr(self, '_prev_rev'):
            return self._prev_rev

        # prev_rev stays None for additions
        self._prev_rev = None

        if self.source is not None:
            prev_revs = self.source.revisions \
              .exclude(changeset__state=states.DISCARDED) \
              .filter(Q(modified__lt=self.modified) |
                      (Q(modified=self.modified) & Q(id__lt=self.id))) \
              .order_by('-modified', '-id')
            if prev_revs.count() > 0:
                self._prev_rev = prev_revs[0]
        return self._prev_rev


    def posterior(self):
        # This would be in the db cache anyway, but this way we
        # save db-calls in some cases.
        # Inside a transaction we cannot gain a new revision, so it's safe
        if hasattr(self, '_post_rev'):
            return self._post_rev

        # post_rev stays None if no newer revision is found
        self._post_rev = None

        if self.changeset.state == states.APPROVED:
            post_revs = self.source.revisions \
              .filter(changeset__state=states.APPROVED) \
              .filter(Q(modified__gt=self.modified) |
                      (Q(modified=self.modified) & Q(id__gt=self.id))) \
              .order_by('modified', 'id')
            if post_revs.count() > 0:
                self._post_rev = post_revs[0]
        return self._post_rev


    def compare_changes(self):
        """
        Set up the 'changed' property so that it can be accessed conveniently
        from a template.  Template calling limitations prevent just
        using a parameter to compare one field at a time.
        """
        self.changed = {}
        self.is_changed = False

        if self.deleted:
            # deletion counts as changed to ease conditional for
            # collapsing sequences in bits/compare.html
            self.is_changed = True
            return

        prev_rev = self.previous()
        if prev_rev is None:
            self.is_changed = True
            prev_values = self._get_blank_values()
            get_prev_value = lambda field: prev_values[field]
        else:
            get_prev_value = lambda field: getattr(prev_rev, field)

        for field_name in self.field_list():
            old = get_prev_value(field_name)
            new = getattr(self, field_name)
            if type(new) == unicode:
                field_changed = old.strip() != new.strip()
            else:
                field_changed = old != new
            self.changed[field_name] = field_changed
            self.is_changed |= field_changed

    def _start_imp_sum(self):
        """
        Hook for subclasses to initialize state for an IMP calculation.
        For instance, if a subclass is keeping track of whether either of a
        pair of fields that together represent an IMP have been seen, this
        hook can be used to clear that state before a new calculation begins.
        """
        pass

    def _imps_for(self, field_name):
        """
        Each revision subclass should override this and have it return the number
        of IMPs that a field should add to the total.  Note that this may be
        stateful as a change in one field may have already been accounted for due
        to a change in a related field.  Child classes may maintain state for this
        sort of tracking, and the _start_imp_sum hook should be overridden to
        clear any such state.
        """
        raise NotImplementedError

    def calculate_imps(self):
        """
        Calculate and return the number of Index Measurment Points that this
        revision is worth.  Relies on self.changed being set.
        """
        imps = 0
        self.compare_changes()
        if self.deleted or not self.is_changed:
            return imps

        self._start_imp_sum()
        for field_name in self.field_list():
            if field_name in self.changed and self.changed[field_name]:
                imps += self._imps_for(field_name)
        return imps

    def queue_name(self):
        """
        Long name form to display in queues.
        This allows revision objects to use their linked object's __unicode__
        method for compatibility in preview pages, but display a more
        verbose form in places like queues that need them.

        Derived classes should override _queue_name to supply a base string
        other than the standard unicode representation.
        """
        return self._queue_name()

    def _queue_name(self):
        return unicode(self)

    def queue_descriptor(self):
        """
        Display descriptor for queue name
        """
        if self.source is None:
            return u'[ADDED]'
        if self.deleted:
            return u'[DELETED]'
        return u''

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

    def _post_commit_to_display(self):
        """
        Hook for individual revisions to perform additional processing
        after it and all other revisions in the same changeset have been
        committed to the display.  For instance, this allows an issue to
        perform actions based on all attched stories having been committed.
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

    def __unicode__(self):
        return u'%s reserved by %s' % (self.series, self.indexer.indexer)

class PublisherRevisionManagerBase(RevisionManager):
    def _base_field_kwargs(self, instance):
        return {
          'name': instance.name,
          'year_began': instance.year_began,
          'year_ended': instance.year_ended,
          'year_began_uncertain': instance.year_began_uncertain,
          'year_ended_uncertain': instance.year_ended_uncertain,
          'notes': instance.notes,
          'url': instance.url,
        }

class PublisherRevisionBase(Revision):
    class Meta:
        abstract = True

    name = models.CharField(max_length=255)

    year_began = models.IntegerField(null=True, blank=True,
      help_text='The first year in which the publisher was active.')
    year_ended = models.IntegerField(null=True, blank=True,
      help_text='The last year in which the publisher was active. '
                'Leave blank if the publisher is still active.')
    year_began_uncertain = models.BooleanField(blank=True,
      help_text='Check if you are not certain of the beginning year.')
    year_ended_uncertain = models.BooleanField(blank=True,
      help_text='Check if you are not certain of the ending year, or if you '
                'are not certain whether the publisher is still active.')

    notes = models.TextField(blank=True,
      help_text='Anything that doesn\'t fit in other fields.  These notes '
                'are part of the regular display.')
    url = models.URLField(blank=True,
      help_text='The official web site of the publisher.')

    # order exactly as desired in compare page
    # use list instead of set to control order
    _base_field_list = ['name',
                        'year_began',
                        'year_began_uncertain',
                        'year_ended',
                        'year_ended_uncertain',
                        'url',
                        'notes']

    def _assign_base_fields(self, target):
        target.name = self.name
        target.year_began = self.year_began
        target.year_ended = self.year_ended
        target.year_began_uncertain = self.year_began_uncertain
        target.year_ended_uncertain = self.year_ended_uncertain
        target.notes = self.notes
        target.url = self.url

    def _field_list(self):
        return self._base_field_list

    def _start_imp_sum(self):
        self._seen_year_began = False
        self._seen_year_ended = False

    def _imps_for(self, field_name):
        if field_name in ('year_began', 'year_began_uncertain'):
           if not self._seen_year_began:
                self._seen_year_began = True
                return 1
        elif field_name in ('year_ended', 'year_ended_uncertain'):
           if not self._seen_year_ended:
                self._seen_year_ended = True
                return 1
        elif field_name in self._base_field_list:
            return 1
        return 0

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
    date_inferred = models.BooleanField(default=False, blank=True)

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

    def active_series(self):
        return self.series_set.exclude(deleted=True)

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
        fields.insert(fields.index('url'), 'country')
        fields.extend(('is_master', 'parent'))
        return fields

    def _get_blank_values(self):
        return {
            'name': '',
            'country': None,
            'year_began': None,
            'year_ended': None,
            'year_began_uncertain': None,
            'year_ended_uncertain': None,
            'url': '',
            'notes': '',
            'is_master': True,
            'parent': None,
        }

    def _imps_for(self, field_name):
        # We don't actually ever change parent and is_master since imprint
        # objects are hidden from direct access by the indexer.
        if field_name == 'country':
            return 1
        return PublisherRevisionBase._imps_for(self, field_name)

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
                update_count('publishers', 1)
        elif self.deleted:
            if self.parent:
                self.parent.imprint_count -= 1
                self.parent.save()
            else:
                update_count('publishers', -1)
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

    def _imprint_count(self):
        if self.source is None:
            return 0
        return self.source.imprint_count
    imprint_count = property(_imprint_count)

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

    def _series_count(self):
        if self.source is None:
            return 0
        return self.source.series_count
    series_count = property(_series_count)

    def _issue_count(self):
        if self.source is None:
            return 0
        return self.source.issue_count
    issue_count = property(_issue_count)

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

    is_surrogate = models.BooleanField()

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
        fields.insert(fields.index('url'), 'is_surrogate')
        fields.insert(fields.index('url'), 'country')
        fields.append(('parent'))
        return fields

    def _get_blank_values(self):
        return {
            'name': '',
            'country': None,
            'year_began': None,
            'year_ended': None,
            'year_began_uncertain': None,
            'year_ended_uncertain': None,
            'is_surrogate': None,
            'url': '',
            'notes': '',
            'parent': None,
        }

    def _imps_for(self, field_name):
        if field_name in ['is_surrogate', 'parent', 'country']:
            return 1
        return PublisherRevisionBase._imps_for(self, field_name)

    def _queue_name(self):
        return u'%s: %s (%s, %s)' % (self.parent.name,
                                     self.name,
                                     self.year_began,
                                     self.country.code.upper())

    def active_issues(self):
        return self.issue_set.exclude(deleted=True)

    # Fake the issue sets for the preview page.
    def _issue_set(self):
        if self.indicia_publisher is None:
            return Issue.objects.filter(pk__isnull=True)
        return self.indicia_publisher.issue_set
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
            update_count('indicia publishers', 1)

        elif self.deleted:
            self.parent.indicia_publisher_count -= 1
            self.parent.save()
            update_count('indicia publishers', -1)
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

    def _get_blank_values(self):
        return {
            'name': '',
            'year_began': None,
            'year_ended': None,
            'year_began_uncertain': None,
            'year_ended_uncertain': None,
            'url': '',
            'notes': '',
            'parent': None,
        }

    def _imps_for(self, field_name):
        if field_name == 'parent':
            return 1
        return PublisherRevisionBase._imps_for(self, field_name)

    def _queue_name(self):
        return u'%s: %s (%s)' % (self.parent.name, self.name, self.year_began)

    def active_issues(self):
        return self.issue_set.exclude(deleted=True)

    # Fake the issue sets for the preview page.
    def _issue_set(self):
        if self.brand is None:
            return Issue.objects.filter(pk__isnull=True)
        return self.brand.issue_set
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
            update_count('brands', 1)

        elif self.deleted:
            self.parent.brand_count -= 1
            self.parent.save()
            update_count('brands', -1)
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

class CoverRevisionManager(RevisionManager):
    """
    Custom manager allowing the cloning of revisions from existing rows.
    """

    def clone_revision(self, cover, changeset):
        """
        Given an existing Cover instance, create a new revision based on it.

        This new revision will be where the replacement is stored.
        """
        return RevisionManager.clone_revision(self,
                                              instance=cover,
                                              instance_class=Cover,
                                              changeset=changeset)

    def _do_create_revision(self, cover, changeset, **ignore):
        """
        Helper delegate to do the class-specific work of clone_revision.
        """
        revision = CoverRevision(
          # revision-specific fields:
          cover=cover,
          changeset=changeset,

          # copied fields:
          issue=cover.issue)

        revision.save()
        return revision


class CoverRevision(Revision):
    class Meta:
        db_table = 'oi_cover_revision'
        ordering = ['-created', '-id']

    objects=CoverRevisionManager()

    cover = models.ForeignKey(Cover, null=True, related_name='revisions')
    issue = models.ForeignKey(Issue, related_name='cover_revisions')

    marked = models.BooleanField(default=False)
    is_replacement = models.BooleanField(default=False)
    is_wraparound = models.BooleanField(default=False)
    front_left = models.IntegerField(default=0)
    front_right = models.IntegerField(default=0)
    front_bottom = models.IntegerField(default=0)
    front_top = models.IntegerField(default=0)

    file_source = models.CharField(max_length=255)

    def _source(self):
        return self.cover

    def _source_name(self):
        return 'cover'

    def _get_blank_values(self):
        """
        Covers don't do field comparisons, so just return an empty
        dictionary so we don't throw an exception if code calls this.
        """
        return {}

    def calculate_imps(self, prev_rev=None):
        return IMP_COVER_VALUE

    def _imps_for(self, field_name):
        """
        Covers are done purely on a flat point model and don't really have fields.
        We shouldn't get here, but just in case, return 0 to be safe.
        """
        return 0

    def commit_to_display(self, clear_reservation=True):
        # the file handling is in the view/covers code
        cover = self.cover

        if cover is None:
            # check for variants having added issue records
            issue_revisions = self.changeset.issuerevisions.all()
            if len(issue_revisions) == 0:
                cover = Cover(issue=self.issue)
            elif len(issue_revisions) == 1:
                if not issue_revisions[0].issue:
                    issue_revisions[0].commit_to_display()
                cover = Cover(issue=issue_revisions[0].issue)
            else:
                raise NotImplementedError
            cover.save()
        elif self.deleted:
            cover.delete()
            cover.save()
            update_count('covers', -1, language=cover.issue.series.language)
            if cover.issue.series.scan_count() == 0:
                series = cover.issue.series
                series.has_gallery = False
                series.save()
            return

        if self.cover and self.is_replacement==False:
            # this is a move of a cover
            if self.changeset.change_type == CTYPES['variant_add']:
                old_issue = cover.issue
                issue_rev = self.changeset.issuerevisions\
                                          .exclude(issue=old_issue).get()
                cover.issue = issue_rev.issue
                cover.save()
                if issue_rev.series != old_issue.series:
                    if issue_rev.series.language != old_issue.series.language:
                        update_count('covers', -1,
                                     language=old_issue.series.language)
                        update_count('covers', 1,
                                     language=issue_rev.series.language)
                    if not issue_rev.series.has_gallery:
                        issue_rev.series.has_gallery = True
                        issue_rev.series.save()
                    if old_issue.series.scan_count() == 0:
                        old_issue.series.has_gallery = False
                        old_issue.series.save()
            else:
                # implement in case we do different kind if cover moves
                raise NotImplementedError
        else:
            from apps.oi.covers import copy_approved_cover
            if self.cover is None:
                self.cover = cover
                self.save()
                update_count('covers', 1, language=cover.issue.series.language)
                if not cover.issue.series.has_gallery:
                    series = cover.issue.series
                    series.has_gallery = True
                    series.save()
            copy_approved_cover(self)
            cover.marked = self.marked
            cover.last_upload = self.changeset.comments.latest('created').created
            cover.is_wraparound = self.is_wraparound
            cover.front_left = self.front_left
            cover.front_right = self.front_right
            cover.front_top = self.front_top
            cover.front_bottom = self.front_bottom
            cover.save()

    def base_dir(self):
        return settings.MEDIA_ROOT + settings.NEW_COVERS_DIR + \
                 self.changeset.created.strftime('%B_%Y/').lower()

    def get_absolute_url(self):
        if self.cover is None:
            return "/cover/revision/%i/preview" % self.id
        return self.cover.get_absolute_url()

    def __unicode__(self):
        return unicode(self.issue)

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
          leading_article=series.name != series.sort_name,
          classification=series.classification,
          format=series.format,
          notes=series.notes,
          year_began=series.year_began,
          year_ended=series.year_ended,
          year_began_uncertain=series.year_began_uncertain,
          year_ended_uncertain=series.year_ended_uncertain,
          is_current=series.is_current,

          publication_notes=series.publication_notes,
          tracking_notes=series.tracking_notes,

          has_barcode=series.has_barcode,
          has_indicia_frequency=series.has_indicia_frequency,
          has_isbn=series.has_isbn,
          has_issue_title=series.has_issue_title,

          country=series.country,
          language=series.language,
          publisher=series.publisher,
          imprint=series.imprint)

        revision.save()
        return revision

def get_series_field_list():
    return ['name', 'leading_article', 'imprint', 'format', 'year_began',
            'year_began_uncertain', 'year_ended', 'year_ended_uncertain',
            'is_current', 'publisher', 'country', 'language', 'has_barcode',
            'has_indicia_frequency', 'has_isbn', 'has_issue_title',
            'tracking_notes', 'publication_notes', 'notes']

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

    name = models.CharField(max_length=255,
      help_text='Series name as it appears in the indicia (or cover only '
                'if there is no indicia).')
    leading_article = models.BooleanField(default=False, blank=True,
      help_text='Check if the name starts with an article.')
    classification = models.ForeignKey(Classification, null=True, blank=True)
    format = models.CharField(max_length=255, blank=True,
      help_text='This is a compound field that holds size, binding, '
                'paper stock and other information, separated by '
                'semi-colons.  Consult the wiki for specifics.')
    year_began = models.IntegerField(help_text='Year first issue published.')
    year_ended = models.IntegerField(null=True, blank=True,
      help_text='Leave blank if the series is still producing new issues.')
    year_began_uncertain = models.BooleanField(blank=True,
      help_text='Check if you are not certain of the beginning year.')
    year_ended_uncertain = models.BooleanField(blank=True,
      help_text='Check if you are not certain of the ending year.')
    is_current = models.BooleanField(
      help_text='Check if new issues are still being produced for this '
                'series. Only uncheck after the last issue is approved '
                'and in our database.')

    publication_notes = models.TextField(blank=True)

    # Fields for tracking relationships between series.
    # Crossref fields don't appear to really be used- nearly all null.
    tracking_notes = models.TextField(blank=True,
      help_text='Field to track numbering from one series to another.')

    # Fields for handling the presence of certain issue fields
    has_barcode = models.BooleanField(
      help_text="Barcodes are present for issues of this series.")
    has_indicia_frequency = models.BooleanField(
      help_text="Indicia frequencies are present for issues of this series.")
    has_isbn = models.BooleanField(verbose_name='Has ISBN',
      help_text="ISBNs are present for issues of this series.")
    has_issue_title = models.BooleanField(
      help_text="Titles are present for issues of this series.")

    notes = models.TextField(blank=True)

    # Country and Language info.
    country = models.ForeignKey(Country, related_name='series_revisions')
    language = models.ForeignKey(Language, related_name='series_revisions')

    # Fields related to the publishers table.
    publisher = models.ForeignKey(Publisher,
                                  related_name='series_revisions')
    imprint = models.ForeignKey(Publisher, null=True, blank=True,
                                related_name='imprint_series_revisions')
    date_inferred = models.BooleanField(default=False, blank=True)

    def _first_issue(self):
        if self.series is None:
            return None
        return self.series.first_issue
    first_issue = property(_first_issue)

    def _last_issue(self):
        if self.series is None:
            return None
        return self.series.last_issue
    last_issue = property(_last_issue)

    def _issue_count(self):
        if self.series is None:
            return 0
        return self.series.issue_count
    issue_count = property(_issue_count)

    def display_publication_dates(self):
        if self.series is None:
            return unicode(self.year_began)
        else:
            return self.series.display_publication_dates()

    def ordered_brands(self):
        if self.series is None:
            return []
        return self.series.ordered_brands()

    def brand_info_counts(self):
        if self.series is None:
            return { 'unknown': 0, 'no_brand': 0 }
        return self.series.brand_info_counts()

    def ordered_indicia_publishers(self):
        if self.series is None:
            return []
        return self.series.ordered_indicia_publishers()

    def indicia_publisher_info_counts(self):
        if self.series is None:
            return { 'unknown': 0 }
        return self.series.indicia_publisher_info_counts()

    def _source(self):
        return self.series

    def _source_name(self):
        return 'series'

    def active_issues(self):
        return self.issue_set.exclude(deleted=True)

    # Fake the issue and cover sets and a few other fields for the preview page.
    def _issue_set(self):
        if self.series is None:
            return Issue.objects.filter(pk__isnull=True)
        return self.series.active_issues()
    issue_set = property(_issue_set)

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
        return get_series_field_list()

    def _get_blank_values(self):
        return {
            'name': '',
            'leading_article': False,
            'classification': None,
            'format': '',
            'notes': '',
            'year_began': None,
            'year_ended': None,
            'year_began_uncertain': None,
            'year_ended_uncertain': None,
            'is_current': None,
            'publication_notes': '',
            'tracking_notes': '',
            'country': None,
            'language': None,
            'publisher': None,
            'imprint': None,
            'has_barcode': True,
            'has_indicia_frequency': True,
            'has_isbn': True,
            'has_issue_title': False
        }

    def _imps_for(self, field_name):
        """
        All current series fields are simple one point fields.
        """
        return 1

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
            self.publisher.series_count = F('series_count') + 1
            self.publisher.save()
            update_count('series', 1, language=self.language)
        elif self.deleted:
            self.publisher.series_count = F('series_count') - 1
            # TODO: implement when/if we allow series deletions along
            # with all their issues
            #self.publisher.issue_count -= series.issue_count
            self.publisher.save()
            if self.imprint:
                self.imprint.series_count = F('series_count') - 1
                self.imprint.save()
                check_delete_imprint(self.imprint)
            series.delete()
            update_count('series', -1, language=series.language)
            reservation = self.source.get_ongoing_reservation()
            if reservation:
                reservation.delete()
            return
        else:
            if self.imprint != self.series.imprint:
                if self.imprint:
                    self.imprint.issue_count = F('issue_count') + \
                                                 series.issue_count
                    self.imprint.series_count = F('series_count') + 1
                    self.imprint.save()
                if self.series.imprint:
                    self.series.imprint.issue_count = F('issue_count') - \
                                                        series.issue_count
                    self.series.imprint.series_count = F('series_count') - 1
                    self.series.imprint.save()
                    check_delete_imprint(self.series.imprint)

        series.name = self.name
        if self.leading_article:
            series.sort_name = remove_leading_article(self.name)
        else:
            series.sort_name = self.name
        series.classification = self.classification
        series.format = self.format
        series.notes = self.notes
        series.year_began = self.year_began
        series.year_ended = self.year_ended
        series.year_began_uncertain = self.year_began_uncertain
        series.year_ended_uncertain = self.year_ended_uncertain
        series.is_current = self.is_current
        series.has_barcode = self.has_barcode
        series.has_indicia_frequency = self.has_indicia_frequency
        series.has_isbn = self.has_isbn
        series.has_issue_title = self.has_issue_title

        reservation = series.get_ongoing_reservation()
        if not self.is_current and reservation and self.previous() and \
          self.previous().is_current:
            reservation.delete()

        series.publication_notes = self.publication_notes
        series.tracking_notes = self.tracking_notes

        series.country = self.country

        if series.language_id is None:
            update_count('series', 1, language=self.language)
            if series.issue_count:
                raise NotImplementedError("New series can't have issues!")

        elif series.language != self.language:
            update_count('series', -1, language=series.language)
            update_count('series', 1, language=self.language)
            if series.issue_count:
                update_count('issues', -series.issue_count,
                             language=series.language)
                update_count('issues', series.issue_count,
                             language=self.language)
                variant_issues = Issue.objects.filter(series=series,
                  deleted=False).exclude(variant_of=None).count()
                update_count('variant_issues', -issue_indexes,
                             language=series.language)
                update_count('variant_issues', issue_indexes,
                             language=self.language)
                issue_indexes = Issue.objects.filter(series=series,
                                  is_indexed=True, deleted=False).count()
                update_count('issue indexes', -issue_indexes,
                             language=series.language)
                update_count('issue indexes', issue_indexes,
                             language=self.language)
                story_count = Story.objects.filter(issue__series=series,
                                                   deleted=False).count()
                update_count('stories', -story_count,
                             language=series.language)
                update_count('stories', story_count,
                                 language=self.language)
                update_count('covers', -series.scan_count(),
                             language=series.language)
                update_count('covers', series.scan_count(),
                             language=self.language)
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


def get_issue_field_list():
    return ['number', 'title', 'no_title', 
            'volume', 'no_volume', 'display_volume_with_number', 
            'indicia_publisher', 'indicia_pub_not_printed',
            'brand', 'no_brand', 'publication_date', 'key_date', 
            'indicia_frequency', 'no_indicia_frequency', 'price',
            'page_count', 'page_count_uncertain', 'editing', 'no_editing',
            'isbn', 'no_isbn', 'barcode', 'no_barcode', 'notes']
            
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
          title=issue.title,
          no_title=issue.no_title,
          volume=issue.volume,
          no_volume=issue.no_volume,
          display_volume_with_number=issue.display_volume_with_number,
          publication_date=issue.publication_date,
          price=issue.price,
          key_date=issue.key_date,
          indicia_frequency=issue.indicia_frequency,
          no_indicia_frequency=issue.no_indicia_frequency,
          series=issue.series,
          indicia_publisher=issue.indicia_publisher,
          indicia_pub_not_printed=issue.indicia_pub_not_printed,
          brand=issue.brand,
          no_brand=issue.no_brand,
          page_count=issue.page_count,
          page_count_uncertain=issue.page_count_uncertain,
          editing=issue.editing,
          no_editing=issue.no_editing,
          barcode=issue.barcode,
          no_barcode=issue.no_barcode,
          isbn=issue.isbn,
          no_isbn=issue.no_isbn,
          variant_of=issue.variant_of,
          variant_name=issue.variant_name,
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
    after = models.ForeignKey(Issue, null=True, related_name='after_revisions',
      verbose_name='Add this issue after')

    # This is used *only* for multiple issues within the same changeset.
    # It does NOT correspond directly to gcd_issue.sort_code, which must be
    # calculated at the time the revision is committed.
    revision_sort_code = models.IntegerField(null=True)

    # When adding an issue, this requests the reservation upon approval of
    # the new issue.  The request will be granted unless an ongoing reservation
    # is in place at the time of approval.
    reservation_requested = models.BooleanField(default=False,
      verbose_name = 'Request reservation',
      help_text='Check this box to have this issue reserved to you '
                'automatically when it is approved, unless someone '
                'has acquired the series\' ongoing reservation before '
                'then.')

    number = models.CharField(max_length=50,
      help_text='The issue number (or other label) as it appears in the indicia. '
                'If there is no indicia the cover number may be used. '
                'Series that number by year (mosty European series) should write '
                'the year after a slash: "4/2009" for issue #4 in publication '
                'year 2009.  Place brackets around an issue number if there is an '
                'indicia but the number does not appear in it.  Use "[nn]" or the '
                'next logical number in brackets like "[2]" if '
                'there is no number printed anywhere on the issue.')

    title = models.CharField(max_length=255, default='', blank=True,
      help_text='The title of the issue. Refer to the wiki for the '
                'cases when an issue can have a title.')
    no_title = models.BooleanField(default=False,
      help_text='Check if there is no title.')

    volume = models.CharField(max_length=50, blank=True, default='',
      help_text='Volume number (only if listed on the item). For collections '
                'or other items that only have a volume or book number, '
                'put the same number in both this field and the issue number '
                'and do *not* check "Display volume with number". ')
    no_volume = models.BooleanField(default=False,
      help_text='If there is no volume, check this box and leave the volume field '
                'blank. This lets us distinguish between confirmed no-volume '
                'issues and issues indexed before we started tracking volume.')
    display_volume_with_number = models.BooleanField(default=False,
      help_text='Check to cause the site to display the volume as part of the '
                'issue number.  For example with a volume of "2" and an issue '
                'number of "1", checking this box will display "v2#1" instead '
                'of just "1" in the status grids and issues lists for the series.')
    variant_of = models.ForeignKey(Issue, null=True,
                                   related_name='variant_revisions')
    variant_name = models.CharField(max_length=255, blank=True, default='',
      help_text='Name of this variant. Examples are: "Cover A" (if listed as '
        'such in the issue), "2nd printing", "newsstand", "direct", or the '
        'name of the artist if different from the base issue.')

    publication_date = models.CharField(max_length=255, blank=True, default='',
      help_text='The publicaton date as printed on the comic, except with the '
                'name of the month (if any) spelled out.  Any part of the date '
                'that is not printed on the comic but is known should be put '
                'in square brackets, such as "[January] 2009".  Do NOT use the '
                'shipping date in this field, only the publication date.')
    indicia_frequency = models.CharField(max_length=255, blank=True, default='',
      help_text='If relevant, the frequency of publication specified in the '
                'indicia, which may not match the actual publication schedule. '
                'This is most often found on U.S. ongoing series.')
    no_indicia_frequency = models.BooleanField(default=False,
      help_text='Check this box if there is no publication frequency printed '
                'on the comic.')
    key_date = models.CharField(max_length=10, blank=True, default='',
      validators=[RegexValidator(r'^(17|18|19|20)\d{2}\.(0[0-9]|1[0-3])\.\d{2}$')],
      help_text='Keydate is a translation of the publication date into numeric '
                'form for chronological ordering and searches. It is in the '
                'format YYYY.MM.DD, where the parts of the date not given are '
                'filled up with 00. For comics dated only by year, the keydate '
                'is YYYY.00.00. For comics only dated by month the day (DD) '
                'is 00, and arbitrary numbers such as 10, 20, 30 are used to '
                'indicate an "early", "mid", or "late" month cover date. For '
                'the month (MM) on quarterlies, use 04 for Spring, 07 for '
                'Summer, 10 for Fall and 01 or 12 for Winter (in the northern '
                'hemisphere, shift accordingly in the southern).')

    price = models.CharField(max_length=255, blank=True, default='',
      help_text='Price in ISO format ("0.50 USD" for 50 cents (U.S.), '
                '"2.99 CAD" for $2.99 Canadian.  Use a format like '
                '"2/6 [0-2-6 GBP]" for pre-decimal British pounds. '
                'Use "0.00 FREE" for free issues. '
                'Separate multiple prices with a semicolon.  Use parentheses '
                'after the currency code for notes: "2.99 USD; 3.99 USD '
                '(newsstand)" Use country codes after the currency code if more '
                'than one price uses the same currency: '
                '"3.99 EUR DE; 3.50 EUR AT; 1.50 EUR FR"')
    page_count = models.DecimalField(max_digits=10, decimal_places=3,
                                     null=True, blank=True, default=None,
      help_text="Count of all pages in the issue, including the covers but "
                "excluding dust jackets and inserts.  A single sheet of paper "
                "folded in half would count as 4 pages.")
    page_count_uncertain = models.BooleanField(default=False,
      help_text="Check if you do not know or aren't sure about the page count.")

    editing = models.TextField(blank=True, default='',
      help_text='The editor and any similar credits for the whole issue.  If no '
                'overall editor is known put a question mark in the field.')
    no_editing = models.BooleanField(default=False,
      help_text='Check if there is no editor or similar credit (such as '
                'publisher) for the issue as a whole.')
    notes = models.TextField(blank=True, default='')

    series = models.ForeignKey(Series, related_name='issue_revisions')
    indicia_publisher = models.ForeignKey(IndiciaPublisher, null=True, blank=True,
      default=None, related_name='issue_revisions',
      help_text='The exact corporation listed as the publisher in the '
                'indicia, if any.  If there is none, the copyright holder '
                '(if any) may be used, with a comment in the notes field'                                          )
    indicia_pub_not_printed = models.BooleanField(default=False,
      help_text="Check this box if no indicia publisher name is "
                "listed in the indicia.")
    brand = models.ForeignKey(Brand, null=True, default=None, blank=True,
      related_name='issue_revisions',
      help_text="The publisher's logo or tagline on the cover of the comic, "
                "if any. Some U.S. golden age publishers did not put any "
                "identifiable brand marks on their comics."                )
    no_brand = models.BooleanField(default=False,
      help_text="Check this box if there is no publisher's logo or tagline.")

    isbn = models.CharField(max_length=32, blank=True, default='',
      verbose_name='ISBN',
      help_text='The ISBN as printed on the item. Do not use this field for '
                'numbering systems other than ISBN. If both ISBN 10 and '
                'ISBN 13 are listed, separate them with a semi-colon. '
                ' Example: "978-0-307-29063-2; 0-307-29063-8".'  )
    no_isbn = models.BooleanField(default=False, verbose_name='No ISBN',
      help_text="Check this box if there is no ISBN.")

    barcode = models.CharField(max_length=38, blank=True, default='',
      help_text='The barcode as printed on the item with no spaces. In case '
                'two barcodes are present, separate them with a semi-colon.')
    no_barcode = models.BooleanField(default=False,
      help_text='Check if there is no barcode.')

    date_inferred = models.BooleanField(default=False, blank=True)

    def _valid_isbn(self):
        return validated_isbn(self.isbn)
    valid_isbn = property(_valid_isbn)

    def _display_number(self):
        """
        Implemented separately because it needs to use the revision's
        display field and not the source's.  Although the actual construction
        of the string should really be factored out somewhere for consistency.
        """
        if self.title and self.series.has_issue_title:
            title = " - " + self.title
        else:
            title = ""
        if self.display_volume_with_number:
            return u'v%s#%s%s' % (self.volume, self.number, title)
        return self.number + title
    display_number = property(_display_number)

    def _sort_code(self):
        if self.issue is None:
            return 0
        return self.issue.sort_code
    sort_code = property(_sort_code)

    def active_covers(self):
        raise NotImplementedError

    def shown_covers(self):
        raise NotImplementedError

    def variant_covers(self):
        image_set = Cover.objects.none()
        if self.issue:
            # maybe a cover move from the base issue (only move allowed)
            ids = list(self.changeset.coverrevisions.all()\
                                     .values_list('cover__id', flat=True))
            image_set |= Cover.objects.filter(id__in=ids)

            image_set |= self.issue.variant_covers()
        elif self.variant_of:
            image_set |= self.variant_of.variant_covers()
            if self.changeset.change_type == CTYPES['variant_add'] \
              and self.changeset.coverrevisions.count():
                # maybe a cover move from the base issue (only move allowed)
                exclude_ids = list(self.changeset.coverrevisions\
                  .exclude(issue=self.issue).values_list('cover__id', flat=True))
                image_set |= self.variant_of.active_covers()\
                                            .exclude(id__in=exclude_ids)
            else:
                image_set |= self.variant_of.active_covers()
        return image_set

    def has_covers(self):
        if self.issue is None:
            return False
        return self.issue.has_covers()

    def other_variants(self):
        if self.variant_of:
            variants = self.variant_of.variant_set.all()
            if self.issue:
                variants = variants.exclude(id=self.issue.id)
        else:
            variants = self.variant_set.all()
        variants = list(variants.exclude(deleted=True))

        if self.changeset.change_type == CTYPES['variant_add'] \
          and not self.variant_of:
            variants.extend(self.changeset.issuerevisions.exclude(issue=self.issue))

        return variants

    def _variant_set(self):
        if self.issue is None:
            return Issue.objects.none()
        return self.issue.variant_set.all()
    variant_set = property(_variant_set)

    def active_stories(self):
        return self.story_set.exclude(deleted=True)

    def shown_stories(self):
        if self.variant_of:
            if self.changeset.issuerevisions.filter(issue=self.variant_of)\
                                            .count():
                # if base_issue is part of the changeset use the storyrevisions
                base_issue = self.changeset.issuerevisions\
                                        .filter(issue=self.variant_of).get()
            else:
                base_issue = self.variant_of
            stories = list(base_issue.active_stories()\
                                     .order_by('sequence_number')\
                                     .select_related('type'))
        else:
            stories = list(self.active_stories().order_by('sequence_number')\
                                                .select_related('type'))
        if (len(stories) > 0):
            cover_story = stories.pop(0)
            if self.variant_of:
                # can have only one sequence, the variant cover
                own_stories = list(self.active_stories())
                if own_stories:
                    cover_story = own_stories[0]
        else:
            cover_story = None
        return cover_story, stories

    def _story_set(self):
        return self.ordered_story_revisions()
    story_set = property(_story_set)

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
        fields = get_issue_field_list() 
        if self.changeset.change_type == CTYPES['issue_add']:
            fields = ['after'] + fields
        if not self.series.has_barcode and \
          self.changeset.change_type != CTYPES['issue_bulk']:
            fields.remove('barcode')
            fields.remove('no_barcode')
        if not self.series.has_indicia_frequency and \
          self.changeset.change_type != CTYPES['issue_bulk']:
            fields.remove('indicia_frequency')
            fields.remove('no_indicia_frequency')
        if not self.series.has_isbn and \
          self.changeset.change_type != CTYPES['issue_bulk']:
            fields.remove('isbn')
            fields.remove('no_isbn')
        if not self.series.has_issue_title and \
          self.changeset.change_type != CTYPES['issue_bulk']:
            fields.remove('title')
            fields.remove('no_title')
        if self.variant_of:
            fields = ['variant_name'] + fields
        return fields

    def _get_blank_values(self):
        return {
            'number': '',
            'title': '',
            'no_title': None,
            'volume': '',
            'no_volume': None,
            'display_volume_with_number': None,
            'publication_date': '',
            'price': '',
            'key_date': '',
            'indicia_frequency': '',
            'no_indicia_frequency': None,
            'series': None,
            'indicia_publisher': None,
            'indicia_pub_not_printed': None,
            'brand': None,
            'no_brand': None,
            'page_count': None,
            'page_count_uncertain': None,
            'editing': '',
            'no_editing': None,
            'isbn': '',
            'no_isbn': None,
            'barcode': '',
            'no_barcode': None,
            'notes': '',
            'sort_code': None,
            'after': None,
            'variant_name': '',
        }

    def _start_imp_sum(self):
        self._seen_volume = False
        self._seen_indicia_publisher = False
        self._seen_indicia_frequency = False
        self._seen_brand = False
        self._seen_page_count = False
        self._seen_editing = False
        self._seen_isbn = False

    def _imps_for(self, field_name):
        if field_name in ('number', 'publication_date', 'key_date',
                          'price', 'notes'):
            return 1
        if not self._seen_volume and \
           field_name in ('volume', 'no_volume', 'display_volume_with_number'):
            self._seen_volume = True
            return 1
        if not self._seen_indicia_publisher and \
           field_name in ('indicia_publisher', 'indicia_pub_not_printed'):
            self._seen_indicia_publisher = True
            return 1
        if not self._seen_indicia_frequency and \
           field_name in ('indicia_frequency', 'no_indicia_frequency'):
            self._seen_indicia_frequency = True
            return 1
        if not self._seen_brand and field_name in ('brand', 'no_brand'):
            self._seen_brand = True
            return 1
        if not self._seen_page_count and \
           field_name in ('page_count', 'page_count_uncertain'):
            self._seen_page_count = True
            return 1
        if not self._seen_editing and field_name in ('editing', 'no_editing'):
            self._seen_editing = True
            return 1
        if not self._seen_isbn and field_name in ('isbn', 'no_isbn'):
            self._seen_isbn = True
            return 1
        # Note, the "after" field does not directly contribute IMPs.
        return 0

    def _source(self):
        return self.issue

    def _source_name(self):
        return 'issue'

    def _do_complete_added_revision(self, series, variant_of=None):
        """
        Do the necessary processing to complete the fields of a new
        issue revision for adding a record before it can be saved.
        """
        self.series = series
        if variant_of:
            self.variant_of = variant_of
            # in case of same series sort after base issue
            if series == variant_of.series:
                self.after = variant_of
                max_sort = variant_of.variant_set.aggregate(Max('sort_code'))
                if max_sort['sort_code__max']:
                    self.after = variant_of.variant_set.get(
                                   sort_code=max_sort['sort_code__max'])


    def _post_commit_to_display(self):
        if self.changeset.changeset_action() == ACTION_MODIFY and \
           self.issue.is_indexed:
            RecentIndexedIssue.objects.update_recents(self.issue)

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
            if self.variant_of:
                update_count('variant issues', 1, language=self.series.language)
            else:
                self.series.issue_count = F('issue_count') + 1
                # do NOT save the series here, it gets saved later in
                # self._check_first_last(), if we save here as well
                # the issue_count goes up by 2
                self.series.publisher.issue_count = F('issue_count') + 1
                self.series.publisher.save()
                if self.brand:
                    self.brand.issue_count = F('issue_count') + 1
                    self.brand.save()
                if self.indicia_publisher:
                    self.indicia_publisher.issue_count = F('issue_count') + 1
                    self.indicia_publisher.save()
                if self.series.imprint:
                    self.series.imprint.issue_count = F('issue_count') + 1
                    self.series.imprint.save()
                update_count('issues', 1, language=self.series.language)

        elif self.deleted:
            if self.variant_of:
                update_count('variant issues', -1, language=self.series.language)
            else:
                self.series.issue_count = F('issue_count') - 1
                # do NOT save the series here, it gets saved later in
                # self._check_first_last(), if we save here as well
                # the issue_count goes down by 2
                self.series.publisher.issue_count = F('issue_count') - 1
                self.series.publisher.save()
                if self.brand:
                    self.brand.issue_count = F('issue_count') - 1
                    self.brand.save()
                if self.indicia_publisher:
                    self.indicia_publisher.issue_count = F('issue_count') - 1
                    self.indicia_publisher.save()
                if self.series.imprint:
                    self.series.imprint.issue_count = F('issue_count') - 1
                    self.series.imprint.save()
                update_count('issues', -1, language=issue.series.language)
            issue.delete()
            self._check_first_last()
            return

        else:
            if not self.variant_of:
                if self.brand != issue.brand:
                    if self.brand:
                        self.brand.issue_count = F('issue_count') + 1
                        self.brand.save()
                    if issue.brand:
                        issue.brand.issue_count = F('issue_count') - 1
                        issue.brand.save()
                if self.indicia_publisher != issue.indicia_publisher:
                    if self.indicia_publisher:
                        self.indicia_publisher.issue_count = F('issue_count') + 1
                        self.indicia_publisher.save()
                    if issue.indicia_publisher:
                        issue.indicia_publisher.issue_count = F('issue_count') - 1
                        issue.indicia_publisher.save()

        issue.number = self.number
        # only if the series has_field is True write to issue
        if self.series.has_issue_title:
            issue.title = self.title
            issue.no_title = self.no_title
        else: # handle case when series has_field changes during lifetime
              # of issue changeset, then changeset resets to issue data
            self.title = issue.title
            self.no_title = issue.no_title
            self.save()

        issue.volume = self.volume
        issue.no_volume = self.no_volume
        issue.display_volume_with_number = self.display_volume_with_number
        issue.variant_of = self.variant_of
        issue.variant_name = self.variant_name

        issue.publication_date = self.publication_date
        if self.series.has_indicia_frequency:
            issue.indicia_frequency = self.indicia_frequency
            issue.no_indicia_frequency = self.no_indicia_frequency
        else:
            self.indicia_frequency = issue.indicia_frequency
            self.no_indicia_frequency = issue.no_indicia_frequency
            self.save()

        issue.key_date = self.key_date

        issue.price = self.price
        issue.page_count = self.page_count
        issue.page_count_uncertain = self.page_count_uncertain

        issue.editing = self.editing
        issue.no_editing = self.no_editing
        issue.notes = self.notes

        issue.series = self.series
        issue.indicia_publisher = self.indicia_publisher
        issue.indicia_pub_not_printed = self.indicia_pub_not_printed
        issue.brand = self.brand
        issue.no_brand = self.no_brand

        if self.series.has_isbn:
            issue.isbn = self.isbn
            issue.no_isbn = self.no_isbn
            issue.valid_isbn = validated_isbn(issue.isbn)
        else:
            self.isbn = issue.isbn
            self.no_isbn = issue.no_isbn
            self.save()

        if self.series.has_barcode:
            issue.barcode = self.barcode
            issue.no_barcode = self.no_barcode
        else:
            self.barcode = issue.barcode
            self.no_barcode = issue.no_barcode
            self.save()

        if clear_reservation:
            issue.reserved = False

        issue.save()
        if self.issue is None:
            self.issue = issue
            self.save()
            self._check_first_last()
            for story in self.changeset.storyrevisions.filter(issue=None):
                story.issue = issue
                story.save()

    def _check_first_last(self):
        set_series_first_last(self.series)

    def get_absolute_url(self):
        if self.issue is None:
            return "/issue/revision/%i/preview" % self.id
        return self.issue.get_absolute_url()

    def full_name(self):
        return u'%s #%s' % (self.series.full_name(), self.display_number)

    def __unicode__(self):
        """
        Re-implement locally instead of using self.issue because it may change.
        """
        return u'%s #%s' % (self.series, self.display_number)

def get_story_field_list():
    return ['sequence_number', 'type', 'title', 'title_inferred',
            'feature', 'genre', 'job_number', 
            'script', 'no_script', 'pencils', 'no_pencils', 'inks',
            'no_inks', 'colors', 'no_colors', 'letters', 'no_letters',
            'editing', 'no_editing', 'page_count', 'page_count_uncertain',
            'characters', 'synopsis', 'reprint_notes', 'notes']

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
    title_inferred = models.BooleanField(default=False)
    feature = models.CharField(max_length=255, blank=True)
    type = models.ForeignKey(StoryType)
    sequence_number = models.IntegerField()

    page_count = models.DecimalField(max_digits=10, decimal_places=3,
                                     null=True, blank=True)
    page_count_uncertain = models.BooleanField(default=False)

    script = models.TextField(blank=True)
    pencils = models.TextField(blank=True)
    inks = models.TextField(blank=True)
    colors = models.TextField(blank=True)
    letters = models.TextField(blank=True)
    editing = models.TextField(blank=True)

    no_script = models.BooleanField(default=False)
    no_pencils = models.BooleanField(default=False)
    no_inks = models.BooleanField(default=False)
    no_colors = models.BooleanField(default=False)
    no_letters = models.BooleanField(default=False)
    no_editing = models.BooleanField(default=False)

    job_number = models.CharField(max_length=25, blank=True)
    genre = models.CharField(max_length=255, blank=True)
    characters = models.TextField(blank=True)
    synopsis = models.TextField(blank=True)
    reprint_notes = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    issue = models.ForeignKey(Issue, null=True, related_name='story_revisions')
    date_inferred = models.BooleanField(default=False, blank=True)

    def toggle_deleted(self):
        """
        Mark this revision as deleted, meaning that instead of copying it
        back to the display table, the display table entry will be removed
        when the revision is committed.
        """
        self.deleted = not self.deleted
        self.save()

    def moveable(self):
        """
        A story revision is moveable
        a) if it is not currently attached to an issue and is a revision of a
           previously existing story. Therefore it is a story which was moved
           to the version issue, this way it can be moved back.
        b) an issue version of mine in this changeset has no story attached and
           it is a cover sequence. Therefore one cover sequence can be moved
           from the base to the version issue.

        These conditions work for our current only case of a story move: i.e.
        issue versions.
        """
        if self.changeset.change_type == CTYPES['variant_add']:
            if self.issue == None:
                if self.story == None:
                    return False
                return True

            if self.deleted:
                return False

            if (self.changeset.storyrevisions.exclude(issue=self.issue).count() and
              self.changeset.issuerevisions.filter(variant_of=self.issue).count()) \
              or self.type != StoryType.objects.get(name='Cover'):
                return False
            return True
        else:
            raise False

    def _field_list(self):
        return get_story_field_list()
        
    def _get_blank_values(self):
        return {
            'title': '',
            'title_inferred': '',
            'feature': '',
            'page_count': None,
            'page_count_uncertain': None,
            'script': '',
            'pencils': '',
            'inks': '',
            'colors': '',
            'letters': '',
            'editing': '',
            'no_script': None,
            'no_pencils': None,
            'no_inks': None,
            'no_colors': None,
            'no_letters': None,
            'no_editing': None,
            'notes': '',
            'synopsis': '',
            'characters': '',
            'reprint_notes': '',
            'genre': '',
            'type': None,
            'job_number': '',
            'sequence_number': None,
            'issue': None,
        }

    def _start_imp_sum(self):
        self._seen_script = False
        self._seen_pencils = False
        self._seen_inks = False
        self._seen_colors = False
        self._seen_letters = False
        self._seen_editing = False
        self._seen_page_count = False
        self._seen_title = False

    def _imps_for(self, field_name):
        if field_name in ('sequence_number', 'type', 'feature', 'genre',
                          'characters', 'synopsis', 'job_number', 'reprint_notes',
                          'notes'):
            return 1
        if not self._seen_title and field_name in ('title', 'title_inferred'):
            self._seen_title = True
            return 1

        if not self._seen_page_count:
            self._seen_page_count = True
            if field_name == 'page_count':
                return 1

            # checking the 'uncertain' box  without also at least guessing the page
            # count itself doesn't count as IMP-worthy information.
            if field_name == 'page_count_uncertain' and \
               self.page_count is not None:
                return 1

        for name in ('script', 'pencils', 'inks', 'colors', 'letters', 'editing'):
            attr = '_seen_%s' % name
            no_name = 'no_%s' % name
            if not getattr(self, attr) and field_name in (name, no_name):
                setattr(self, attr, True)

                # Just putting in a question mark isn't worth an IMP.
                # Note that the input data is already whitespace-stripped.
                if field_name == name and getattr(self, field_name) == '?':
                    return 0
                return 1
        return 0

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

    def _reset_values(self):
        if self.deleted:
            # users can edit story revisions before deleting them.
            # ensure that the final deleted revision matches the
            # final state of the story.
            self.title = self.story.title
            self.title_inferred = self.story.title_inferred
            self.feature = self.story.feature
            self.page_count = self.story.page_count
            self.page_count_uncertain = self.story.page_count_uncertain

            self.script = self.story.script
            self.pencils = self.story.pencils
            self.inks = self.story.inks
            self.colors = self.story.colors
            self.letters = self.story.letters
            self.editing = self.story.editing

            self.no_script = self.story.no_script
            self.no_pencils = self.story.no_pencils
            self.no_inks = self.story.no_inks
            self.no_colors = self.story.no_colors
            self.no_letters = self.story.no_letters
            self.no_editing = self.story.no_editing

            self.notes = self.story.notes
            self.synopsis = self.story.synopsis
            self.characters = self.story.characters
            self.reprint_notes = self.story.reprint_notes
            self.genre = self.story.genre
            self.type = self.story.type
            self.job_number = self.story.job_number
            self.sequence_number = self.story.sequence_number
            self.save()

    def commit_to_display(self, clear_reservation=True):
        story = self.story
        if story is None:
            story = Story()
            update_count('stories', 1, language=self.issue.series.language)
        elif self.deleted:
            if self.issue.is_indexed == True:
                if self.issue.set_indexed_status() == False:
                    update_count('issue indexes', -1,
                                 language=story.issue.series.language)
            update_count('stories', -1, language=story.issue.series.language)
            self._reset_values()
            story.delete()
            return

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

        if self.issue.is_indexed == False:
            if self.issue.set_indexed_status():
                update_count('issue indexes', 1,
                             language=self.issue.series.language)
        else:
            if self.issue.set_indexed_status() == False:
                update_count('issue indexes', -1,
                             language=self.issue.series.language)

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

class Download(models.Model):
    """
    Track downloads of bulk data.  Description may contain the filesystem
    paths or other information about what was downloaded.
    """
    user = models.ForeignKey(User)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

