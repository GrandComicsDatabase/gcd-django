# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import models
from django.db.models.fields import Field, related, FieldDoesNotExist
from django.contrib.auth.models import User
from django.contrib.contenttypes import models as content_models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import fields as generic_fields
from django.core.validators import RegexValidator

from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFit
from taggit.managers import TaggableManager

from apps.oi import states, relpath
from apps.oi.helpers import (
    update_count, remove_leading_article,
    validated_isbn, get_keywords, save_keywords, on_sale_date_as_string,
    on_sale_date_fields)

# We should just from apps.gcd import models as gcd_models, but that's
# a lot of little changes so for now tell flake8 noqa so it doesn't complain
from apps.gcd.models import *  # noqa
from apps.gcd.models.issue import INDEXED


# TODO: CTYPES and ACTION_* are going away at some point.
CTYPES = {
    'publisher': 1,
    'issue_add': 5,
    'issue_bulk': 8,
    'series': 4,
    'variant_add': 9,
    'two_issues': 10,
}


ACTION_ADD = 'add'
ACTION_DELETE = 'delete'
ACTION_MODIFY = 'modify'


class Changeset(models.Model):

    state = models.IntegerField(db_index=True)

    indexer = models.ForeignKey('auth.User', db_index=True,
                                related_name='changesets')
    along_with = models.ManyToManyField(User,
                                        related_name='changesets_assisting')
    on_behalf_of = models.ManyToManyField(User,
                                          related_name='changesets_source')

    # Changesets don't get an approver until late in the workflow,
    # and for legacy cases we don't know who they were.
    approver = models.ForeignKey('auth.User',  db_index=True,
                                 related_name='approved_%(class)s', null=True)

    # In production, change_type is a tinyint(2) due to the small value set.
    change_type = models.IntegerField(db_index=True)
    migrated = models.BooleanField(default=False, db_index=True)
    date_inferred = models.BooleanField(default=False)

    imps = models.IntegerField(default=0)

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)

    # TODO: This is just here so we can mock it in unit tests of old code.
    #       It will go away along with CTYPES.
    def changeset_action(self):
        raise NotImplementedError


class ChangesetComment(models.Model):
    """
    Comment class for revision management.

    We are not using Django's comments contrib package for several reasons:

    1.  Additional fields- we want to associate comments with state
        transitions, which also tells us who made the comment (since
        currently comments can only be made by the person changing the
        revision state, or by the indexer when saving intermediate edits.

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
    revision = generic_fields.GenericForeignKey('content_type', 'revision_id')

    old_state = models.IntegerField()
    new_state = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True, editable=False)


class RevisionLock(models.Model):
    """
    Indicates that a particular Changeset has a particular row locked.

    In order to have an active Revision for a given row, a Changeset
    must hold a lock on it.  Rows in this table represent locks,
    and the unique_together constraint on the content type and object id
    ensure that only one Changeset can hold an object's lock at a time.
    Locks are released by deleting the row.

    A lock with a NULL changeset is used to check that the object can
    be locked before creating a Changeset that would not be used
    if the lock fails.

    TODO: cron job to periodically scan for stale locks?
    """
    class Meta:
        db_table = 'oi_revision_lock'
        unique_together = ('content_type', 'object_id')

    changeset = models.ForeignKey(Changeset, null=True,
                                  related_name='revision_locks')

    content_type = models.ForeignKey(content_models.ContentType)
    object_id = models.IntegerField(db_index=True)
    locked_object = generic_fields.GenericForeignKey('content_type',
                                                     'object_id')


class RevisionManager(models.Manager):
    """
    Custom manager base class for revisions.
    """
    # We want to use these methods on reverse relation sets.
    use_for_related_fields = True

    def get_queryset(self):
        return RevisionQuerySet(self.model, using=self._db)

    def active(self):
        """
        Get the active revision, assuming that there is one.

        Throws the DoesNotExist or MultipleObjectsReturned exceptions on
        the appropriate Revision subclass, as it calls get() underneath.
        """
        return self.get(changeset__state__in=states.ACTIVE)

    def active_set(self):
        """
        Filter to only revisions on an active changeset.

        For use when the set being filtered can result in multiple
        active revisions, which raises an exception from active().
        """
        return self.filter(changeset__state__in=states.ACTIVE)

    def pending_deletions(self):
        """
        Filter to active revisions that are deleting their object.
        """
        return self.active_set().filter(deleted=True)

    def filter_pending_deletions(self, data_queryset):
        """
        Filter pending deletions out of a queryset of GcdBase-derived objects.

        Since this does not operate on Revision querysets, it should not be
        copied to the RevisionQuerySet class.
        """
        return data_queryset.exclude(
            revisions__deleted=True,
            revisions__changeset__state__in=states.ACTIVE).distinct()


class RevisionQuerySet(models.QuerySet):
    """
    Propagates the RevisionManager methods to further querysets.
    """
    def active(self):
        return self.get(changeset__state__in=states.ACTIVE)

    def active_set(self):
        return self.filter(changeset__state__in=states.ACTIVE)

    def pending_deletions(self):
        return self.active_set().filter(deleted=True)


class Revision(models.Model):
    """
    Abstract base class implementing the workflow of a revisable object.

    This holds the data while it is being edited, and remains in the table
    as a history of each given edit, including those that are discarded.

    A state column tracks the progress of the revision, which should
    eventually end in either the APPROVED or DISCARDED state.

    Various classmethods exist to get information about the revision fields
    so that they can be handled generically.  All of these method names
    start with _get and end with a suffix indicating the return value:

    fields:       a dictionary mapping field attribute names to field objects
    field_names:  a set of field attribute names
    field_tuples: a set of tuples of attribute names that may cross relations
    """
    class Meta:
        abstract = True

    objects = RevisionManager()

    changeset = models.ForeignKey(Changeset, related_name='%(class)ss')
    previous_revision = models.OneToOneField('self', null=True,
                                             related_name='next_revision')

    # If True, this revision deletes the object in question.  Other fields
    # should not contain changes but should instead be a record of the object
    # at the time of deletion and therefore match the previous revision.
    # If changes are present, then they were never actually published and
    # should be ignored in terms of history.
    deleted = models.BooleanField(default=False, db_index=True)

    # If True, this revision has been committed back to the display tables.
    # If False, this revision will never be committed.
    # If None, this revision is still active, and may or may not be committed
    # at some point in the future.
    committed = models.NullBooleanField(default=None, db_index=True)

    comments = generic_fields.GenericRelation(
        ChangesetComment,
        content_type_field='content_type',
        object_id_field='revision_id')

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)

    is_changed = False

    # These are initialized on first use- see the corresponding classmethods.
    # Set to None as an empty iterable is a valid possible value.
    _regular_fields = None
    _irregular_fields = None
    _single_value_fields = None
    _multi_value_fields = None
    _meta_fields = None

    # Child classes must set these properly.  Unlike source, they cannot be
    # instance properties because they are needed during revision construction.
    source_name = NotImplemented
    source_class = NotImplemented

    @property
    def source(self):
        """
        The thing of which this is a revision.
        Since this is different for each revision,
        the subclass must override this.
        """
        raise NotImplementedError

    @source.setter
    def source(self, value):
        """
        Used with source_class by base revision code to create new objects.
        """
        raise NotImplementedError

    # #####################################################################
    # Properties indicating the type of action this Revision is performing.
    @property
    def added(self):
        """
        True if this is an open or committed add.
        """
        return not self.previous_revision and not self.discarded

    @property
    def edited(self):
        """
        True if this open or committed and neither an add nor a delete.

        NOTE: This does not necessarily mean there have been any edits.
        """
        return bool(self.previous_revision and not
                    (self.deleted or self.discarded))

    @property
    def discarded(self):
        """
        For symmetry with committed and open.
        """
        return self.committed is False

    @property
    def open(self):
        """
        For symmetry with committed and discarded.
        """
        return self.committed is None

    # #####################################################################
    # Field declarations and classification.

    @classmethod
    def _classify_fields(cls):
        """
        Populates the regular and irregular field dictionaries.

        This should be called at most once during the life of the class.
        It relies on the excluded field set to filter out irrelevant fields.
        """
        if cls._regular_fields is not None:
            # Already classified.
            return

        # NOTE: As of Django 1.9, reverse relations show up in the list
        #       of fields, but are not actually Field instances.  Since
        #       we don't want them anyway, use this to filter them out.
        #
        #       In a future release of Django this will change, but should
        #       be covered in the release notes.  And presumably there
        #       will be a different reliable way to filter them out.
        excluded_names = cls._get_excluded_field_names()
        meta_names = cls._get_meta_field_names()
        data_fields = {
            f.get_attname(): f
            for f in cls.source_class._meta.get_fields()
            if isinstance(f, Field) and f.get_attname() not in excluded_names
        }
        rev_fields = {
            f.get_attname(): f
            for f in cls._meta.get_fields()
            if isinstance(f, Field) and f.get_attname() not in excluded_names
        }
        cls._regular_fields = {}
        cls._irregular_fields = {}
        cls._single_value_fields = {}
        cls._multi_value_fields = {}
        cls._meta_fields = {}

        for name, data_field in data_fields.iteritems():
            # Currently we do not have relations that are meta fields,
            # so just handle those here and move on to the next field.
            if name in meta_names:
                cls._meta_fields[name] = data_field
                continue

            # Note that ForeignKeys and OneToOneFields show up under the
            # attribute name for the actual key ('parent_id' instead of
            # 'parent'), so strip the _id off for more convenient use.
            # You can still pass the 'parent' form to _meta.get_field().
            # TODO: Is there a more reliable way to do this?  Cannot
            #       seem to find anything in the Django 1.9 API.
            key_name = name
            if ((data_field.many_to_one or data_field.one_to_one) and
                    name.endswith('_id')):
                # If these aren't the same we have no idea what's going
                # on, so an AssertionError is appropriate.
                assert cls.source_class._meta.get_field(key_name) == data_field
                key_name = name[:-len('_id')]

            if name not in rev_fields:
                # No corresponding revision field, so it can't be regular.
                cls._irregular_fields[key_name] = data_field
                continue

            # The internal type is the field type i.e. CharField or ForeignKey.
            rev_field = rev_fields[name]
            rev_ftype = rev_field.get_internal_type()
            data_ftype = data_field.get_internal_type()
            rev_target = (rev_field.target_field.get_attname()
                          if isinstance(rev_field, related.RelatedField)
                          else None)
            data_target = (data_field.target_field.get_attname()
                           if isinstance(data_field, related.RelatedField)
                           else None)

            if rev_ftype == data_ftype and rev_target == data_target:
                # Non-relational fields have a .rel of None.  While we should
                # never have identically named foreign keys that point to
                # different things, it's better to check than assume.
                #
                # Most of these fields can be copied, including ManyToMany
                # fields, although ManyToMany fields may need to be treated
                # differently in other ways, so we track them separately
                # as well.
                cls._regular_fields[key_name] = data_field

                if data_field.many_to_many or data_field.one_to_many:
                    cls._multi_value_fields[key_name] = data_field
                else:
                    cls._single_value_fields[key_name] = data_field

            elif isinstance(data_field,
                            TaggableManager) and name == 'keywords':
                # Keywords are regular but not assignable in the same way
                # as single- or multi-value fields as the keywords are
                # stored as a single string in revisions.
                cls._regular_fields[key_name] = data_field

            else:
                # There's some mismatch, so we don't know how to handle this.
                cls._irregular_fields[key_name] = data_field

    @classmethod
    def _get_excluded_field_names(cls):
        """
        Field names that appear to be regular fields but should be ignored.

        Any data object field that has a matching (name, type, and if
        relevant related type) field on the revision that should *NOT*
        be copied back and forth should be included here.

        It is not necessary to include non-matching fields here, whether
        they affect revision field values or not.

        Fields listed here may or may not be present on any given data object,
        but if they are present they should be omitted from automatic
        classification.

        Subclasses may add to this set, but should never remove fields from it.

        Deprecated fields should NOT be included, as they should continue
        to be copied back and forth until the data is all removed, at
        which point the field should be dropped from the data object.
        """
        # Not all data objects have all of these, but since this
        # is just used in set subtractions, that is safe to do.
        # All of these fields are common to multiple revision types.
        #
        # id, created, and modified are automatic columns
        # tagged_items is the reverse relation for 'keywords'
        # image_resources are handled through their own ImageRevisions
        return frozenset({
            'id',
            'created',
            'modified',
            'deleted',
            'reserved',
            'tagged_items',
            'image_resources',
        })

    @classmethod
    def _get_deprecated_field_names(cls):
        """
        The set of field names that should not be allowed in new objects.

        These fields are still present in both the data object and revision
        tables, and should therefore be copied out of the data objects in
        case old values are still present and need to be preserved until
        they can be migrated.  But new values should not be allowed.
        """
        return frozenset()

    @classmethod
    def _get_meta_field_names(cls):
        """
        Fields that are about other fields, and only copied from rev to data.

        These fields are not included in either the regular or irregular
        field sets, nor the single value or multi value sets.  They are
        handled completely separately.

        See also _get_meta_fields() for more information.
        """
        return frozenset()

    @classmethod
    def _get_regular_fields(cls):
        """
        Data fields that can be predictably transferred to and from revisions.

        For most fields, this just means copying the value.  For a few
        such as keywords, there is a different but standard way of transferring
        the values.  For ManyToManyFields, the add/remove/set/clear methods
        can be used.
        """
        cls._classify_fields()
        return cls._regular_fields

    @classmethod
    def _get_irregular_fields(cls):
        """
        Data object fields that cannot be handled by generic revision code.

        These fields either don't exist on the revision, or they do not
        match types and we do not understand the mismatch as a well-known
        special case (i.e. keywords as CharField vs TaggableManager).
        """
        cls._classify_fields()
        return cls._irregular_fields

    @classmethod
    def _get_single_value_fields(cls):
        """
        The subset of regular fields that have a single value.
        """
        cls._classify_fields()
        return cls._single_value_fields

    @classmethod
    def _get_multi_value_fields(cls):
        """
        The subset of regular fields that have a queryset value.
        """
        cls._classify_fields()
        return cls._multi_value_fields

    @classmethod
    def _get_meta_fields(cls):
        """
        Fields that are not managed as primary data.

        These fields are usually meta-data of some sort, such as flags
        indicating data that needs revisiting.  Alternatively, they
        may be additional information calculated from primary data
        but cached in database fields.

        These field values may be changed in the data object without
        using a Revision, and Revisions should not attempt to keep
        them in sync.

        When committing a revision, the field must be activley set
        correctly as it is not copied *from* the data object, but
        will be copied back *to* it.

        Note that fields that are calculated either entirely within
        the revision, or entirely within the data object, but are
        never copied in either direction should *not* be included
        here.  This classification is essentially for fields that
        are only copied from revision to data object.
        """
        cls._classify_fields()
        return cls._meta_fields

    @classmethod
    def _get_conditional_field_tuple_mapping(cls):
        """
        A dictionary of field names mapped to their conditions.

        The conditions are stored as a tuple of field names that can
        be applied to an instance to get the value.
        For example, ('series', 'has_isbn') would mean that you
        could get the value by looking at revision.series.has_isbn
        """
        return {}

    @classmethod
    def _get_parent_field_tuples(cls):
        """
        The set of parent-ish objects that this revision may need to update.

        This should include parent chains up to the root data object(s) that
        need updating, for instance an issue should include its publisher
        by way of the series foreign key (as opposed to publishers found
        through other links, which are either duplicate or should be
        ignored.

        Elements of the set are tuples to allow for multiple parent levels.
        ForeignKey, ManyToManyField, and OneToOneField are all valid
        field types for this method.

        Note that if multiple parents along a path require updating, then
        each level of parent must be included.  In the issue example,
        ('series',) and ('series', 'publisher') must both be included.

        This allows for the case where an intermediate object does not
        require updating.
        """
        return frozenset()

    @classmethod
    def _get_major_flag_field_tuples(cls):
        """
        The set of flags that require further processing upon commit.

        These are stored as tuples in the same way as
        _get_parent_field_tuples().
        """
        return frozenset()

    @classmethod
    def _get_stats_category_field_tuples(cls):
        """
        These fields, when present, determine CountStats categories to update.

        This implementation works for any class that does not have to get
        these fields from a parent object.
        """
        stats_tuples = set()
        for name in ('country', 'language'):
            try:
                # We just call get_field to see if it raises, so we
                # ignore the return value.
                cls._meta.get_field(name)
                stats_tuples.add((name,))
            except FieldDoesNotExist:
                pass

        return stats_tuples

    # #####################################################################
    # Methods for creating (cloning) a Revision from a data object,
    # including hook methods for use in customizing the cloning process.

    def _pre_initial_save(self, fork=False, fork_source=None,
                          exclude=frozenset()):
        """
        Called just before saving to the database to handle unusual fields.

        Note that if there is a source data object, it will already be set.

        See clone() for usage of fork, fork_source, and exclude.
        """
        pass

    def _post_m2m_add(self, fork=False, fork_source=None, exclude=frozenset()):
        """
        Called after initial save to database and m2m population.

        This is for handling unusual fields that require the revision to
        already exist in the database.

        See clone() for usage of fork, fork_source, and exclude.
        """
        pass

    @classmethod
    def clone(cls, data_object, changeset, fork=False, exclude=frozenset()):
        """
        Given an existing data object, create a new revision based on it.

        This new revision will be where the edits are made.

        'fork' may be set to true to create a revision for a new data
        object based on an existing data object.  The source and
        previous_revision fields will be left null in this case.  Due to
        this, the source issue will be passed separately to the customization
        methods as 'fork_source'.

        Entirely new data objects should be started by simply instantiating
        a new revision of the approparite type directly.

        A set (or set-like object) of field names to exclude from copying
        may be passed.  This is particularly useful for forking.
        """
        # We start with all assignable fields, since we want to copy
        # old values even for deprecated fields.
        rev_kwargs = {field: getattr(data_object, field)
                      for field
                      in cls._get_single_value_fields().viewkeys() - exclude}

        # Keywords are not assignable but behave the same way whenever
        # they are present, so handle them here.
        if 'keywords' in cls._get_regular_fields().viewkeys() - exclude:
            rev_kwargs['keywords'] = get_keywords(data_object)

        # Instantiate the revision.  Since we do not know the exact
        # field name for the data_object, set it through the source property.
        revision = cls(changeset=changeset, **rev_kwargs)

        if data_object and not fork:
            revision.source = data_object

            # Link to the previous revision for this data object.
            # It is an error not to have a previous revision for
            # a pre-existing data object.
            previous_revision = type(revision).objects.get(
                next_revision=None,
                changeset__state=states.APPROVED,
                **{revision.source_name: data_object})
            revision.previous_revision = previous_revision

        revision._pre_initial_save(fork=fork, fork_source=data_object,
                                   exclude=exclude)
        revision.save()

        # Populate all of the many to many relations that don't use
        # their own separate revision classes.
        for m2m in revision._get_multi_value_fields().viewkeys() - exclude:
            getattr(revision, m2m).add(*list(getattr(data_object, m2m).all()))
        revision._post_m2m_add(fork=fork, fork_source=data_object,
                               exclude=exclude)

        return revision

    # ##################################################################
    # Methods for inventorying significant changes to the fields,
    # an handling those changes and the resulting updates to cached
    # values and statistics.

    def _reset_values(self):
        pass

    def _check_major_change(self, attrs):
        """
        Fill out the changes structure for a single attribute tuple.
        """
        old, new = self.source, self
        changes = {}

        # The name of the last foreign key is the name used for
        # tracking changes.  Except 'parent' is tracked as 'publisher'
        # for historical reasons.  Eventually we will likely switch
        # the 'parent' database fields to 'publisher'.
        name = 'publisher' if attrs[-1] == 'parent' else attrs[-1]

        old_rp = relpath.RelPath(self.source_class, *attrs)
        new_rp = relpath.RelPath(type(self), *attrs)

        old_value = old_rp.get_value(old, empty=self.added)
        new_value = new_rp.get_value(new, empty=self.deleted)

        changed = '%s changed' % name
        if self.added or self.deleted:
            changes[changed] = True
        elif old_rp.multi_valued:
            # Different QuerySet objects are never equal, even if they
            # express the same queries and have the same evaluation state.
            # So use sets for determining changes.
            changes[changed] = set(old_value) != set(new_value)
        else:
            changes[changed] = old_value != new_value

        if old_rp.boolean_valued:
            # We only care about the direction of change for booleans.
            # At this time, it is sufficient to treat None for a NullBoolean
            # as False.  This can produce a "changed" (False to or from None)
            # in which both "to" and "from" are False.  Strange but OK.
            #
            # Without the bool(), if old_value (for from) or new_value
            # (for to) are None, then the changes would be set to None
            # instead of True or False.
            changes['to %s' % name] = bool((not old_value) and new_value)
            changes['from %s' % name] = bool(old_value and (not new_value))
        else:
            changes['old %s' % name] = old_value
            changes['new %s' % name] = new_value

        return changes

    def _get_major_changes(self, extra_field_tuples=frozenset()):
        """
        Returns a dictionary for deciding what additional actions are needed.

        Major changes are generally ones that require updating statistics
        and/or cached counts in the display tables.  They may also require
        other actions.

        This method bundles up all of the flags and old vs new values
        needed for easy conditionals and easy calls to update_all_counts().

        extra_field_tuples is a way for child classes to put additional fields
        into the changes dictionary through a super() call without having
        to put them in any of the sets that trigger special handling.
        This is useful for oddball fields that trigger custom code when
        changed, but don't fall into any of the usual patterns.
        """
        changes = {}
        for name_tuple in (self._get_parent_field_tuples() |
                           self._get_major_flag_field_tuples() |
                           self._get_stats_category_field_tuples() |
                           extra_field_tuples):
            changes.update(self._check_major_change(name_tuple))

        return changes

    def _adjust_stats(self, changes, old_counts, new_counts):
        """
        Handles universal statistics updating.

        Child classes should call this with super() before proceeding
        to adjust counts stored in their display objects.
        """
        if (old_counts != new_counts or
                changes.get('country changed', False) or
                changes.get('language changed', False)):
            CountStats.objects.update_all_counts(
                old_counts,
                country=changes.get('old country', None),
                language=changes.get('old language', None),
                negate=True)
            CountStats.objects.update_all_counts(
                new_counts,
                country=changes.get('new country', None),
                language=changes.get('new language', None))

        deltas = {
            k: new_counts.get(k, 0) - old_counts.get(k, 0)
            for k in old_counts.viewkeys() | new_counts.viewkeys()
        }

        if any(deltas.values()):
            for parent_tuple in self._get_parent_field_tuples():
                self._adjust_parent_counts(parent_tuple, changes, deltas,
                                           old_counts, new_counts)

            self.source.update_cached_counts(deltas)
            self.source.save()

    def _adjust_parent_counts(self, parent_tuple, changes, deltas,
                              old_counts, new_counts):
        """
        Handles the counts adjustment for a single parent.
        """
        # Always use the last attribute name for the parent name.
        # But switch 'parent' to 'publisher' (historical reasons).
        parent = (
            'publisher' if parent_tuple[-1] == 'parent' else parent_tuple[-1])

        changed = changes['%s changed' % parent]
        old_value = changes['old %s' % parent]
        new_value = changes['new %s' % parent]

        multi = relpath.RelPath(type(self), *parent_tuple).multi_valued
        if changed:
            if old_value:
                if multi:
                    for v in old_value:
                        v.update_cached_counts(old_counts, negate=True)
                        v.save()
                else:
                    old_value.update_cached_counts(old_counts, negate=True)
                    old_value.save()
            if new_value:
                if multi:
                    for v in new_value:
                        v.update_cached_counts(new_counts)
                        v.save()
                else:
                    new_value.update_cached_counts(new_counts)
                    new_value.save()

        elif old_counts != new_counts:
            # Doesn't matter whether we use old or new as they are the same.
            if multi:
                for v in new_value:
                    v.update_cached_counts(deltas)
                    v.save()
            else:
                new_value.update_cached_counts(deltas)
                new_value.save()

    # #####################################################################
    # Methods for saving the Revision back to the data object, including
    # hook methods for customizing that process.

    def _pre_commit_check(self):
        """
        Runs sanity checks before anything else in commit_to_display.

        This method must not attempt to change anything, and should raise
        an exception if the check fails.  For conditions that can be
        fixed, use _handle_prerequisites.
        """
        pass

    def _handle_prerequisites(self, changes):
        """
        Creates/commits related revisions before committing this revision.

        This is where a revision subclass should look for other revisions
        that must be committed before the commit of this revision can
        proceed.  It should create and/or commit those prerequisite
        revisions as needed, updating this revision with the results
        if appropriate.

        This method should take into account the possibility that multiple
        revisions in a given changeset may have the same prerequisites, and
        either only perform actions that can be safely repeated or verify
        that prior revisions have not already handled things.

        This runs before the old stat counts are collected so that any
        changes from the prerequisites are accounted for in the stats,
        any any count updates are not double-counted.

        Note that prerequisite revisions may attempt to handle this
        revision as a dependent revision, so care must be taken to
        avoid loops.
        """
        pass

    def _pre_delete(self, changes):
        """
        Runs just before the data object is deleted in a deletion revision.
        """
        pass

    def _post_create_for_add(self, changes):
        """
        Runs after a new object is created during an add.

        This is where things like adding many-to-many objects can be done.
        """
        pass

    def _post_assign_fields(self, changes):
        """
        Runs once the added or edited display object is set up.

        Fields that can't be copied directly are handled here.
        Not run for deletions.
        """
        pass

    def _pre_save_object(self, changes):
        """
        Runs just before the display object is saved.

        This is where additional processing related to the major changes,
        such as conditional field adjustments, can be done.
        """
        pass

    def _post_save_object(self, changes):
        """
        Runs just after the display object is saved.

        Typically used to handle many-to-many fields.
        """
        pass

    def _handle_dependents(self, changes):
        """
        Creates/commits related revisions after committing this revision.

        This is where a revision subclass should ensure that any revisions
        that depend on this revision get handled created and/or committed
        appropriately.

        This runs at the very end of commit_to_display(), after the new
        stats have been collected and handled.  Otherwise any counts
        adjusted in the revisions handled here would be double-counted
        by this revision's stats code as well.

        Note that dependent revisions may attempt to handle this revision
        as a prerequisite, so care must be taken to avoid loops.
        To help with this, self.committed will be set to True and this
        revision will be saved to the database by the time this method
        is called.
        """
        pass

    def _copy_fields_to(self, target):
        """
        Used to copy fields from a revision to a display object.

        At the time when this is called, the revision may not yet have
        the display object set as self.source (in the case of a newly
        added object), so the target of the copy is given as a parameter.
        """
        fields_to_copy = self._get_single_value_fields().copy()
        fields_to_copy.update(self._get_meta_fields())
        c = self._get_conditional_field_tuple_mapping()
        for name in fields_to_copy:
            # If conditional, apply getattr until we produce the flag
            # value and only assign the field if that flag is True.
            if (name not in c or reduce(getattr, c[name], self)):
                setattr(target, name, getattr(self, name))

    def commit_to_display(self, clear_reservation=True):
        """
        Writes the changes from the revision back to the display object.

        Revisions should handle their own dependencies on other revisions.
        """
        self._pre_commit_check()
        changes = self._get_major_changes()

        self._handle_prerequisites(changes)
        old_stats = {} if self.added else self.source.stat_counts()

        if self.deleted:
            self._pre_delete(changes)
            self._reset_values()
            self.source.delete()
        else:
            if self.added:
                self.source = self.source_class()
                self._post_create_for_add(changes)

            self._copy_fields_to(self.source)
            self._post_assign_fields(changes)

        if clear_reservation:
            self.source.reserved = False

        self._pre_save_object(changes)
        self.source.save()

        if self.added:
            # Reset the source because now it has a database id,
            # which we must save.  Just saving the added source while
            # it is attached does not update the revision with the newly
            # created source id from the database.
            #
            # We do this because it is easier for all other code if it
            # only works with self.source, no matter whether it is
            # an add, edit, or delete.
            self.source = self.source

        self.committed = True
        self.save()

        # Keywords must be handled post-save for added objects, and
        # are safe to handle here for other types of revisions.
        if 'keywords' in self._get_regular_fields():
            save_keywords(self, self.source)

        for multi in self._get_multi_value_fields():
            old_rp = relpath.RelPath(type(self), multi)
            new_rp = relpath.RelPath(type(self.source), multi)

            new_rp.set_value(self.source, old_rp.get_value(self))

        self._post_save_object(changes)

        new_stats = self.source.stat_counts()
        self._adjust_stats(changes, old_stats, new_stats)
        self._handle_dependents(changes)

    # #####################################################################
    # Methods not involved in the Revision lifecycle.

    def __unicode__(self):
        """
        String representation for debugging purposes only.

        No UI should rely on this representation being suitable for end users.
        """
        # It's possible to add and delete something at the same time,
        # although we don't currently allow it.  In theory one could
        # edit and delete, although we don't even have any way to indicate
        # that currently.
        action = []
        if self.added:
            action.append('adding')
        if self.edited:
            action.append('editing')
        if self.deleted:
            action.append('deleting')

        return '%r %s %s %r (%r) change %r' % (
            self.id,
            ' & '.join(action),
            self.source_class.__name__,
            self.source,
            None if self.source is None else self.source.id,
            None if self.changeset_id is None else self.changeset_id,
        )


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


class LinkRevision(Revision):
    """
    Revision base class for use with GcdLink data objects.

    Unlike regular data objects, these objects are truly deleted from
    the database when they are no longer needed, which requires additional
    handling in the revisions.
    """
    class Meta:
        abstract = True

    def _pre_delete(self, changes):
        for revision in self.source.revisions.all():
            # Unhook the revisions because the data link object
            # will be truly deleted, not just marked inactive.
            revision.series_bond_id = None
            revision.save()

        # The loop above does not affect us as an in-memory instance,
        # so update the id, but no need to save.
        self.series_bond_id = None


class PublisherRevisionBase(Revision):
    class Meta:
        abstract = True

    name = models.CharField(max_length=255)

    year_began = models.IntegerField(null=True, blank=True)
    year_ended = models.IntegerField(null=True, blank=True)
    year_began_uncertain = models.BooleanField(default=False)
    year_ended_uncertain = models.BooleanField(default=False)

    notes = models.TextField(blank=True)
    keywords = models.TextField(blank=True, default='')
    url = models.URLField(blank=True)


class PublisherRevision(PublisherRevisionBase):
    class Meta:
        db_table = 'oi_publisher_revision'
        ordering = ['-created', '-id']

    objects = RevisionManager()

    publisher = models.ForeignKey('gcd.Publisher', null=True,
                                  related_name='revisions')

    country = models.ForeignKey('gcd.Country', db_index=True)

    # Deprecated fields about relating publishers/imprints to each other
    is_master = models.BooleanField(default=True, db_index=True)
    parent = models.ForeignKey('gcd.Publisher', default=None,
                               null=True, blank=True, db_index=True,
                               related_name='imprint_revisions')

    date_inferred = models.BooleanField(default=False)

    source_name = 'publisher'
    source_class = Publisher

    @property
    def source(self):
        return self.publisher

    @source.setter
    def source(self, value):
        self.publisher = value


class IndiciaPublisherRevision(PublisherRevisionBase):
    class Meta:
        db_table = 'oi_indicia_publisher_revision'
        ordering = ['-created', '-id']

    objects = RevisionManager()

    indicia_publisher = models.ForeignKey('gcd.IndiciaPublisher', null=True,
                                          related_name='revisions')

    is_surrogate = models.BooleanField(default=False)

    country = models.ForeignKey('gcd.Country', db_index=True,
                                related_name='indicia_publishers_revisions')

    parent = models.ForeignKey('gcd.Publisher',
                               null=True, blank=True, db_index=True,
                               related_name='indicia_publisher_revisions')

    source_name = 'indicia_publisher'
    source_class = IndiciaPublisher

    @property
    def source(self):
        return self.indicia_publisher

    @source.setter
    def source(self, value):
        self.indicia_publisher = value

    @classmethod
    def _get_parent_field_tuples(cls):
        return frozenset({('parent',)})

    def _do_complete_added_revision(self, parent):
        """
        Do the necessary processing to complete the fields of a new
        indicia publisher revision for adding a record before it can be saved.
        """
        self.parent = parent


class BrandGroupRevision(PublisherRevisionBase):
    class Meta:
        db_table = 'oi_brand_group_revision'
        ordering = ['-created', '-id']

    objects = RevisionManager()

    brand_group = models.ForeignKey('gcd.BrandGroup', null=True,
                                    related_name='revisions')

    parent = models.ForeignKey('gcd.Publisher',
                               null=True, blank=True, db_index=True,
                               related_name='brand_group_revisions')

    source_name = 'brand_group'
    source_class = BrandGroup

    @property
    def source(self):
        return self.brand_group

    @source.setter
    def source(self, value):
        self.brand_group = value

    @classmethod
    def _get_parent_field_tuples(cls):
        return frozenset({('parent',)})

    def _do_complete_added_revision(self, parent):
        """
        Do the necessary processing to complete the fields of a new
        series revision for adding a record before it can be saved.
        """
        self.parent = parent

    def _handle_dependents(self, changes):
        if self.added:
            brand_revision = BrandRevision(
                changeset=self.changeset,
                name=self.name,
                year_began=self.year_began,
                year_ended=self.year_ended,
                year_began_uncertain=self.year_began_uncertain,
                year_ended_uncertain=self.year_ended_uncertain)
            brand_revision.save()
            brand_revision.group.add(self.brand_group)
            brand_revision.commit_to_display()


class BrandRevision(PublisherRevisionBase):
    class Meta:
        db_table = 'oi_brand_revision'
        ordering = ['-created', '-id']

    objects = RevisionManager()

    brand = models.ForeignKey('gcd.Brand', null=True, related_name='revisions')
    # parent needs to be kept for old revisions
    parent = models.ForeignKey('gcd.Publisher',
                               null=True, blank=True, db_index=True,
                               related_name='brand_revisions')
    group = models.ManyToManyField('gcd.BrandGroup', blank=False,
                                   related_name='brand_revisions')

    source_name = 'brand'
    source_class = Brand

    @property
    def source(self):
        return self.brand

    @source.setter
    def source(self, value):
        self.brand = value

    @property
    def issue_count(self):
        if self.brand is None:
            return 0
        return self.brand.issue_count

    def _handle_dependents(self, changes):
        if self.added:
            if self.brand.group.count() != 1:
                raise NotImplementedError

            group = self.brand.group.get()
            use = BrandUseRevision(
                changeset=self.changeset,
                emblem=self.brand,
                publisher=group.parent,
                year_began=self.year_began,
                year_began_uncertain=self.year_began_uncertain,
                year_ended=self.year_ended,
                year_ended_uncertain=self.year_ended_uncertain)
            use.save()
            use.commit_to_display()


class BrandUseRevision(Revision):
    class Meta:
        db_table = 'oi_brand_use_revision'
        ordering = ['-created', '-id']

    objects = RevisionManager()

    brand_use = models.ForeignKey('gcd.BrandUse', null=True,
                                  related_name='revisions')

    emblem = models.ForeignKey('gcd.Brand', null=True,
                               related_name='use_revisions')

    publisher = models.ForeignKey('gcd.Publisher', null=True, db_index=True,
                                  related_name='brand_use_revisions')

    year_began = models.IntegerField(db_index=True, null=True)
    year_ended = models.IntegerField(null=True)
    year_began_uncertain = models.BooleanField(default=False)
    year_ended_uncertain = models.BooleanField(default=False)
    notes = models.TextField(max_length=255, blank=True)

    source_name = 'brand_use'
    source_class = BrandUse

    @property
    def source(self):
        return self.brand_use

    @source.setter
    def source(self, value):
        self.brand_use = value

    def _do_complete_added_revision(self, emblem, publisher):
        """
        Do the necessary processing to complete the fields of a new
        BrandUse revision for adding a record before it can be saved.
        """
        self.publisher = publisher
        self.emblem = emblem


class CoverRevision(Revision):
    class Meta:
        db_table = 'oi_cover_revision'
        ordering = ['-created', '-id']

    objects = RevisionManager()

    cover = models.ForeignKey(Cover, null=True, related_name='revisions')
    issue = models.ForeignKey(Issue, related_name='cover_revisions')

    marked = models.BooleanField(default=False)
    is_replacement = models.BooleanField(default=False)
    is_wraparound = models.BooleanField(default=False)
    front_left = models.IntegerField(default=0, null=True)
    front_right = models.IntegerField(default=0, null=True)
    front_bottom = models.IntegerField(default=0, null=True)
    front_top = models.IntegerField(default=0, null=True)

    file_source = models.CharField(max_length=255, null=True)

    source_name = 'cover'
    source_class = Cover

    @property
    def source(self):
        return self.cover

    @source.setter
    def source(self, value):
        self.cover = value

    @classmethod
    def _get_excluded_field_names(cls):
        return frozenset(
            super(CoverRevision, cls)._get_excluded_field_names() |
            {
                'is_wraparound',
                'front_left',
                'front_right',
                'front_top',
                'front_bottom',
            }
        )

    @classmethod
    def _get_stats_category_field_tuples(cls):
        return frozenset({('issue', 'series', 'country',),
                          ('issue', 'series', 'language',)})

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
                self.issue = cover.issue
            else:
                raise NotImplementedError
            cover.save()
        elif self.deleted:
            cover.delete()
            cover.save()
            update_count('covers', -1,
                         language=cover.issue.series.language,
                         country=cover.issue.series.country)
            if cover.issue.series.scan_count() == 0:
                series = cover.issue.series
                series.has_gallery = False
                series.save()
            return

        if clear_reservation:
            cover.reserved = False

        if self.cover and self.is_replacement is False:
            # this is a move of a cover
            if self.changeset.change_type in [CTYPES['variant_add'],
                                              CTYPES['two_issues']]:
                old_issue = cover.issue
                issue_rev = self.changeset.issuerevisions\
                                          .exclude(issue=old_issue).get()
                cover.issue = issue_rev.issue
                cover.save()
                if issue_rev.series != old_issue.series:
                    if (issue_rev.series.language !=
                        old_issue.series.language) \
                       or (issue_rev.series.country !=
                           old_issue.series.country):
                        update_count('covers', -1,
                                     language=old_issue.series.language,
                                     country=old_issue.series.country)
                        update_count('covers', 1,
                                     language=issue_rev.series.language,
                                     country=issue_rev.series.country)
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
                update_count('covers', 1,
                             language=cover.issue.series.language,
                             country=cover.issue.series.country)
                if not cover.issue.series.has_gallery:
                    series = cover.issue.series
                    series.has_gallery = True
                    series.save()
            copy_approved_cover(self)
            cover.marked = self.marked
            cover.last_upload = self.changeset.comments \
                                    .latest('created').created
            cover.is_wraparound = self.is_wraparound
            cover.front_left = self.front_left
            cover.front_right = self.front_right
            cover.front_top = self.front_top
            cover.front_bottom = self.front_bottom
            cover.save()


class SeriesRevision(Revision):
    class Meta:
        db_table = 'oi_series_revision'
        ordering = ['-created', '-id']

    objects = RevisionManager()

    series = models.ForeignKey(Series, null=True, related_name='revisions')

    # When adding a series, this requests the ongoing reservation upon
    # approval of the new series.  The request will be granted unless the
    # indexer has reached their maximum number of ongoing reservations
    # at the time of approval.
    reservation_requested = models.BooleanField(default=False)

    name = models.CharField(max_length=255)
    leading_article = models.BooleanField(default=False)

    # The "format" field is a legacy field that is being split into
    # color, dimensions, paper_stock, binding, and publishing_format
    format = models.CharField(max_length=255, blank=True)
    color = models.CharField(max_length=255, blank=True)
    dimensions = models.CharField(max_length=255, blank=True)
    paper_stock = models.CharField(max_length=255, blank=True)
    binding = models.CharField(max_length=255, blank=True)
    publishing_format = models.CharField(max_length=255, blank=True)
    publication_type = models.ForeignKey(SeriesPublicationType,
                                         null=True, blank=True)

    year_began = models.IntegerField()
    year_ended = models.IntegerField(null=True, blank=True)
    year_began_uncertain = models.BooleanField(default=False)
    year_ended_uncertain = models.BooleanField(default=False)
    is_current = models.BooleanField(default=False)

    publication_notes = models.TextField(blank=True)

    # Fields for tracking relationships between series.
    # Crossref fields don't appear to really be used- nearly all null.
    # TODO: what's a crossref field?  Was that a field in the old DB?
    #       appears to be a stale comment of some sort.  The tracking
    #       notes field was definitely used plenty.
    tracking_notes = models.TextField(blank=True)

    # Fields for handling the presence of certain issue fields
    has_barcode = models.BooleanField(default=False)
    has_indicia_frequency = models.BooleanField(default=False)
    has_isbn = models.BooleanField(default=False, verbose_name='Has ISBN')
    has_issue_title = models.BooleanField(default=False)
    has_volume = models.BooleanField(default=False)
    has_rating = models.BooleanField(default=False)

    is_comics_publication = models.BooleanField(default=False)
    is_singleton = models.BooleanField(default=False)

    notes = models.TextField(blank=True)
    keywords = models.TextField(blank=True, default='')

    # Country and Language info.
    country = models.ForeignKey(Country, related_name='series_revisions')
    language = models.ForeignKey(Language, related_name='series_revisions')

    # Fields related to the publishers table.
    publisher = models.ForeignKey(Publisher, related_name='series_revisions')
    imprint = models.ForeignKey(Publisher, null=True, blank=True, default=None,
                                related_name='imprint_series_revisions')
    date_inferred = models.BooleanField(default=False)

    source_name = 'series'
    source_class = Series

    @property
    def source(self):
        return self.series

    @source.setter
    def source(self, value):
        self.series = value

    @classmethod
    def _get_excluded_field_names(cls):
        return frozenset(
            super(SeriesRevision, cls)._get_excluded_field_names() |
            {'open_reserve', 'publication_dates'}
        )

    @classmethod
    def _get_parent_field_tuples(cls):
        return frozenset({('publisher',)})

    @classmethod
    def _get_major_flag_field_tuples(self):
        return frozenset({
            ('is_comics_publication',),
            ('is_current',),
            ('is_singleton',),
        })

    @classmethod
    def _get_deprecated_field_names(cls):
        return frozenset({'format'})

    def _do_complete_added_revision(self, publisher):
        """
        Do the necessary processing to complete the fields of a new
        series revision for adding a record before it can be saved.
        """
        self.publisher = publisher

    def _handle_prerequisites(self, changes):
        # Handle deletion of the singleton issue before getting the
        # series stat counts to avoid double-counting the deletion.
        if self.deleted and self.series.is_singleton:
            issue_revision = IssueRevision.clone(
                instance=self.series.issue_set[0], changeset=self.changeset)
            issue_revision.deleted = True
            issue_revision.save()
            issue_revision.commit_to_display()

    def _post_assign_fields(self, changes):
        if self.leading_article:
            self.series.sort_name = remove_leading_article(self.name)
        else:
            self.series.sort_name = self.name

    def _pre_save_object(self, changes):
        if changes['from is_current']:
            reservation = self.series.get_ongoing_reservation()
            reservation.delete()

        if changes['to is_comics_publication']:
            # TODO: But don't we count covers for some non-comics?
            self.series.has_gallery = bool(self.series.scan_count())

    def _handle_dependents(self, changes):
        # Handle adding the singleton issue last, to avoid double-counting
        # the addition in statistics.
        if changes['to is_singleton'] and self.series.issue_count == 0:
            issue_revision = IssueRevision(changeset=self.changeset,
                                           series=self.series,
                                           after=None,
                                           number='[nn]',
                                           publication_date=self.year_began)
            # We assume that a non-four-digit year is a typo of some
            # sort, and do not propagate it.  The approval process
            # should catch that sort of thing.
            # TODO: Consider a validator on year_began?
            if len(unicode(self.year_began)) == 4:
                issue_revision.key_date = '%d-00-00' % self.year_began
            issue_revision.save()
            issue_revision.commit_to_display()


class SeriesBondRevision(LinkRevision):
    class Meta:
        db_table = 'oi_series_bond_revision'
        ordering = ['-created', '-id']
        get_latest_by = "created"

    objects = RevisionManager()

    series_bond = models.ForeignKey(SeriesBond, null=True,
                                    related_name='revisions')

    origin = models.ForeignKey(Series, null=True,
                               related_name='origin_bond_revisions')
    origin_issue = models.ForeignKey(
        Issue, null=True, related_name='origin_series_bond_revisions')
    target = models.ForeignKey(Series, null=True,
                               related_name='target_bond_revisions')
    target_issue = models.ForeignKey(
        Issue, null=True, related_name='target_series_bond_revisions')

    bond_type = models.ForeignKey(SeriesBondType, null=True,
                                  related_name='bond_revisions')
    notes = models.TextField(max_length=255, default='', blank=True)

    source_name = 'series_bond'
    source_class = SeriesBond

    @property
    def source(self):
        return self.series_bond

    @source.setter
    def source(self, value):
        self.series_bond = value


class IssueRevision(Revision):
    class Meta:
        db_table = 'oi_issue_revision'
        ordering = ['-created', '-id']

    objects = RevisionManager()

    issue = models.ForeignKey(Issue, null=True, related_name='revisions')

    # If not null, insert or move the issue after the given issue
    # when saving back the DB. If null, place at the beginning of
    # the series.
    after = models.ForeignKey(
        Issue, null=True, blank=True, related_name='after_revisions',
        verbose_name='Add this issue after')

    # This is used *only* for multiple issues within the same changeset.
    # It does NOT correspond directly to gcd_issue.sort_code, which must be
    # calculated at the time the revision is committed.
    revision_sort_code = models.IntegerField(null=True)

    # When adding an issue, this requests the reservation upon approval of
    # the new issue.  The request will be granted unless an ongoing reservation
    # is in place at the time of approval.
    reservation_requested = models.BooleanField(
        default=False, verbose_name='Request reservation')

    number = models.CharField(max_length=50)

    title = models.CharField(max_length=255, default='', blank=True)
    no_title = models.BooleanField(default=False)

    volume = models.CharField(max_length=50, blank=True, default='')
    no_volume = models.BooleanField(default=False)
    display_volume_with_number = models.BooleanField(default=False)
    variant_of = models.ForeignKey(Issue, null=True,
                                   related_name='variant_revisions')
    variant_name = models.CharField(max_length=255, blank=True, default='')

    publication_date = models.CharField(max_length=255, blank=True, default='')
    key_date = models.CharField(
        max_length=10, blank=True, default='',
        validators=[RegexValidator(
            r'^(17|18|19|20)\d{2}(\.|-)(0[0-9]|1[0-3])(\.|-)\d{2}$')])
    year_on_sale = models.IntegerField(db_index=True, null=True, blank=True)
    month_on_sale = models.IntegerField(db_index=True, null=True, blank=True)
    day_on_sale = models.IntegerField(db_index=True, null=True, blank=True)
    on_sale_date_uncertain = models.BooleanField(default=False)
    indicia_frequency = models.CharField(max_length=255, blank=True,
                                         default='')
    no_indicia_frequency = models.BooleanField(default=False)

    price = models.CharField(max_length=255, blank=True, default='')
    page_count = models.DecimalField(max_digits=10, decimal_places=3,
                                     null=True, blank=True, default=None)
    page_count_uncertain = models.BooleanField(default=False)

    editing = models.TextField(blank=True, default='')
    no_editing = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default='')
    keywords = models.TextField(blank=True, default='')

    series = models.ForeignKey(Series, related_name='issue_revisions')
    indicia_publisher = models.ForeignKey(
        IndiciaPublisher, null=True, blank=True, default=None,
        related_name='issue_revisions',
        verbose_name='indicia/colophon publisher')
    indicia_pub_not_printed = models.BooleanField(
        default=False,
        verbose_name='indicia/colophon pub. not printed')
    brand = models.ForeignKey(
        Brand, null=True, default=None, blank=True,
        related_name='issue_revisions', verbose_name='brand emblem')
    no_brand = models.BooleanField(default=False,
                                   verbose_name='no brand emblem')

    isbn = models.CharField(
        max_length=32, blank=True, default='', verbose_name='ISBN')
    no_isbn = models.BooleanField(default=False, verbose_name='No ISBN')

    barcode = models.CharField(max_length=38, blank=True, default='')
    no_barcode = models.BooleanField(default=False)

    rating = models.CharField(max_length=255, blank=True, default='',
                              verbose_name="Publisher's age guidelines")
    no_rating = models.BooleanField(
        default=False, verbose_name="No publisher's age guidelines")

    date_inferred = models.BooleanField(default=False)

    source_name = 'issue'
    source_class = Issue

    @property
    def source(self):
        return self.issue

    @source.setter
    def source(self, value):
        self.issue = value

    @property
    def series_changed(self):
        """ True if the series changed and this is neither add nor delete. """
        return ((not self.deleted) and
                (self.previous_revision is not None) and
                self.previous_revision.series != self.series)

    @classmethod
    def fork_variant(cls, issue, changeset,
                     variant_name, variant_cover_revision=None,
                     reservation_requested=False):
        current_variants = issue.variant_set.all().order_by('-sort_code')
        if current_variants:
            add_after = current_variants[0]
        else:
            add_after = issue

        variant_revision = IssueRevision.clone(
            issue, changeset, fork=True, exclude={
                'publication_date',
                'key_date',
                'on_sale_date',
                'on_sale_date_uncertain',
                'price',
                'brand',
                'no_brand',
                'isbn',
                'no_isbn',
                'barcode',
                'no_barcode',
                'keywords',
            })
        variant_revision.add_after = add_after
        variant_revision.variant_of = issue
        variant_revision.variant_name = variant_name
        variant_revision.reservation_requested = reservation_requested
        variant_revision.save()

        if variant_cover_revision:
            cover_sequence_revision = StoryRevision(
                changeset=changeset,
                type=StoryType.objects.get(name='cover'),
                no_script=True,
                pencils='?',
                inks='?',
                colors='?',
                no_letters=True,
                no_editing=True,
                sequence_number=0,
                page_count=2 if variant_cover_revision.is_wraparound else 1)
            cover_sequence_revision.save()
        else:
            cover_sequence_revision = None

        return variant_revision, cover_sequence_revision

    @classmethod
    def _get_stats_category_field_tuples(cls):
        return frozenset({('series', 'country',), ('series', 'language',)})

    @classmethod
    def _get_conditional_field_tuple_mapping(cls):
        has_title = ('series', 'has_issue_title')
        has_barcode = ('series', 'has_barcode')
        has_isbn = ('series', 'has_isbn')
        has_volume = ('series', 'has_volume')
        has_ind_freq = ('series', 'has_indicia_frequency')
        return {
            'title': has_title,
            'no_title': has_title,
            'barcode': has_barcode,
            'no_barcode': has_barcode,
            'isbn': has_isbn,
            'no_isbn': has_isbn,
            'valid_isbn': has_isbn,
            'volume': has_volume,
            'no_volume': has_volume,
            'display_volume_with_issue': has_volume,
            'indicia_frequency': has_ind_freq,
            'no_indicia_frequency': has_ind_freq,
        }

    @classmethod
    def _get_parent_field_tuples(cls):
        # There are several routes to a publisher object, but
        # if there are differences, it is the publisher of the series
        # that should get the count adjustments.
        return frozenset({
            ('series',),
            ('series', 'publisher'),
            ('indicia_publisher',),
            ('brand',),
            ('brand', 'group'),
        })

    def _pre_initial_save(self, fork=False, fork_source=None,
                          exclude=frozenset()):
        source = fork_source if fork_source else self.issue
        if source.on_sale_date and 'on_sale_date' not in exclude:
            (self.year_on_sale,
             self.month_on_sale,
             self.day_on_sale) = on_sale_date_fields(source.on_sale_date)

    def _do_complete_added_revision(self, series, variant_of=None):
        """
        Do the necessary processing to complete the fields of a new
        issue revision for adding a record before it can be saved.
        """
        self.series = series
        if variant_of:
            self.variant_of = variant_of

    def _same_series_revisions(self):
        return self.changeset.issuerevisions.filter(series=self.series)

    def _same_series_open_with_after(self):
        return self._same_series_revisions().filter(after__isnull=False,
                                                    committed=None)

    def _open_prereq_revisions(self):
        # Adds and moves go first to last, deletes last to first.
        sort = '-revision_sort_code' if self.deleted else 'revision_sort_code'
        return self._same_series_revisions().exclude(id=self.id) \
                                            .filter(committed=None) \
                                            .order_by(sort)

    def _committed_prereq_revisions(self):
        # We pop off of open prereqs and push onto committed, so reverse sort.
        sort = 'revision_sort_code' if self.deleted else '-revision_sort_code'
        return self._same_series_revisions().exclude(id=self.id) \
                                            .filter(committed=True) \
                                            .order_by(sort)

    def _pre_commit_check(self):
        # If any other issue from this series has been committed, we have
        # already gone through this logic, so skip it.
        if self._same_series_revisions().filter(committed=True).exists():
            return

        # Verify that we have at most one uncommitted revision with this
        # series that has a non-null 'after' field.  This means that for now
        # we can only support one contiguous run of added/moved issues per
        # series.
        #
        # TODO: This may need further tweaking for various cases of working
        #       with variants, moving covers, etc. but is sufficient for
        #       general single and bulk issue operations.
        after = self._same_series_open_with_after()
        if after.count() > 1:
            raise ValueError(
                ("%s, %s: Only one IssueRevision per series within a "
                 "changeset can have 'after' set.  All others are assumed "
                 "to follow it based on the 'revision_sort_code' field.") %
                (self.changeset, self))
        if after.exists() and (after.first() !=
                               self._same_series_revisions()
                                   .order_by('revision_sort_code')
                                   .first()):
            raise ValueError(
                ("%s, %s: The IssueRevision that specifies an 'after' must "
                 "have the lowest revision_sort_code.") %
                (self.changeset, after.first()))

    def _ensure_sort_code_space(self):
        first_rev = self._same_series_open_with_after().first()
        after_code = -1 if first_rev is None else first_rev.after.sort_code

        # Include deleted issues due to unique constraint on sort_code.
        later_issues = Issue.objects.filter(
            series=self.series,
            sort_code__gt=after_code).order_by('-sort_code')

        if not later_issues.exists():
            # We're appending to the series, no space needed.
            return

        num_issues = self._same_series_revisions().count()
        if later_issues.first().sort_code - after_code > num_issues:
            # Someone else already made space here.
            return

        for later_issue in later_issues:
            later_issue.sort_code += num_issues
            later_issue.save()

    def _handle_prerequisites(self, changes):
        if self.edited and not self.series_changed:
            # order of revision commit doesn't matter, as we do issue
            # sort_code reorderings separately from the main editing
            # workflow, at least for now.
            return

        if not self.deleted:
            self._ensure_sort_code_space()

        current_prereq_qs = self._open_prereq_revisions().all()
        current_prereq_count = current_prereq_qs.count()
        while current_prereq_count:
            current_prereq_qs.first().commit_to_display()
            # Always eval a new queryset as committing may cause other commits.
            # Calling all() produces an identical but unevaluated queryset.
            current_prereq_qs = current_prereq_qs.all()
            new_prereq_count = current_prereq_qs.count()

            if new_prereq_count >= current_prereq_count:
                # We should never *gain* revisions- even if we create
                # revisions during a commit, those newly created revisions
                # should themselves be committed before the other commit
                # completes.  Prevent infinite loops by raising.
                raise RuntimeError("Committing revisions did not reduce the "
                                   "number of uncommitted revisions!")

            current_prereq_count = new_prereq_count

    def _post_assign_fields(self, changes):
        self.issue.on_sale_date = on_sale_date_as_string(self)

        if self.series.has_isbn:
            self.issue.valid_isbn = validated_isbn(self.issue.isbn)

        # TODO: Support adding base + variant by adding a variant_of_rev
        #       field to IssueRevision and setting variant_of to the
        #       committed issue of the variant_of_rev field automatically,
        #       committing the variant_of_rev if necessary.
        #       Idea may be good for other new dependent object situations.
        if self.added or self.series_changed:
            if not self.after:
                # If we're handling a run of issues, this is the
                # previous issue in the run, if any.
                committed = self._committed_prereq_revisions().first()
                if committed:
                    self.after = committed.issue

            if self.after:
                self.issue.sort_code = self.after.sort_code + 1
            else:
                self.issue.sort_code = 0

    def _post_save_object(self, changes):
        self.series.set_first_last_issues()
        if self.series_changed:
            old_series = self.previous_revision.series
            old_series.set_first_last_issues()

            # new series might have gallery after move
            if not self.series.has_gallery and \
               self.issue.active_covers().count():
                self.series.has_gallery = True
                self.series.save()

            # old series might have lost gallery after move
            if old_series.scan_count() == 0:
                old_series.has_gallery = False
                old_series.save()

    def _handle_dependents(self, changes):
        # These story revisions will handle their own stats when committed.
        # They will also update the issue's is_indexed field.
        for story in self.changeset.storyrevisions.filter(issue=None):
            story.issue = self.issue
            story.save()

        if not self.deleted and self.issue.is_indexed != INDEXED['skeleton']:
            RecentIndexedIssue.objects.update_recents(self.issue)


class StoryRevision(Revision):
    class Meta:
        db_table = 'oi_story_revision'
        ordering = ['-created', '-id']

    objects = RevisionManager()

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
    keywords = models.TextField(blank=True, default='')

    issue = models.ForeignKey(Issue, null=True, related_name='story_revisions')
    date_inferred = models.BooleanField(default=False)

    source_name = 'story'
    source_class = Story

    @property
    def source(self):
        return self.story

    @source.setter
    def source(self, value):
        self.story = value

    @classmethod
    def _get_stats_category_field_tuples(cls):
        return frozenset({('issue', 'series', 'country',),
                          ('issue', 'series', 'language',)})

    def _get_major_changes(self, extra_field_tuples=frozenset()):
        # We need to look at issue for index status changes, but it does
        # not otherwise behave like a normal parent field, nor does it
        # fit into any of the other unusual field classifications.
        extras = {('issue',)}

        if extra_field_tuples:
            # extra_field_tuples might be a frozenset, so add to our new
            # set rather than the other way around.
            extras.add(extra_field_tuples)

        return super(StoryRevision, self)._get_major_changes(
            extra_field_tuples=extras)

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

    def _handle_dependents(self, changes):
        # While committing an issue is a prerequisite for the story,
        # accounting for index status changes is dependent upon the
        # story commit.
        issues = [] if self.added else [changes['old issue']]
        if changes['issue changed'] and not self.deleted:
            issues.append(changes['new issue'])

        # import pytest
        for issue in issues:
            delta = issue.set_indexed_status()
            if delta:
                if self.edited:
                    assert issue.series.country is not None
                    assert issue.series.language is not None
                CountStats.objects.update_all_counts(
                    {'issue indexes': delta},
                    country=issue.series.country,
                    language=issue.series.language)


class ReprintRevision(Revision):
    class Meta:
        db_table = 'oi_reprint_revision'
        ordering = ['-created', '-id']
        get_latest_by = "created"

    reprint = models.ForeignKey(Reprint, null=True,
                                related_name='revisions')

    origin = models.ForeignKey(Story, null=True,
                               related_name='origin_reprint_revisions')
    origin_revision = models.ForeignKey(
        StoryRevision, null=True, related_name='origin_reprint_revisions')
    origin_issue = models.ForeignKey(
        Issue, null=True, related_name='origin_reprint_revisions')

    target = models.ForeignKey(Story, null=True,
                               related_name='target_reprint_revisions')
    target_revision = models.ForeignKey(
        StoryRevision, null=True, related_name='target_reprint_revisions')
    target_issue = models.ForeignKey(Issue, null=True,
                                     related_name='target_reprint_revisions')

    notes = models.TextField(max_length=255, default='')

    source_name = 'reprint'
    source_class = Reprint

    @property
    def source(self):
        return self.reprint

    @source.setter
    def source(self, value):
        self.reprint = value

    def save(self, *args, **kwargs):
        # Ensure that we can't create a nonsense link.
        if self.origin:
            if self.origin_issue and self.origin_issue != self.origin.issue:
                raise ValueError(
                    "Reprint origin story and issue do not match.  Story "
                    "issue: '%s'; Issue: '%s'" % (self.origin.issue,
                                                  self.origin_issue))
            if not self.origin_issue:
                self.origin_issue = self.origin.issue

        if self.target:
            if self.target_issue and self.target_issue != self.target.issue:
                raise ValueError(
                    "Reprint target story and issue do not match.  Story "
                    "issue: '%s'; Issue: '%s'" % (self.target.issue,
                                                  self.target_issue))
            if not self.target_issue:
                self.target_issue = self.target.issue

        if self.origin_revision:
            if self.origin and self.origin_revision.story != self.origin:
                raise ValueError(
                    "Reprint origin story revision and origin story do not "
                    "agree.  Story from revision: '%s'; Story: '%s'" %
                    (self.origin_revision.story, self.origin))

            if (self.origin_issue and
                    self.origin_revision.issue != self.origin_issue):
                raise ValueError(
                    "Reprint origin story revision issue and origin issue "
                    "do not agree.  Issue from revision: '%s'; Issue: '%s'" %
                    (self.origin_revision.issue, self.origin_issue))
                self.target_issue = self.target.issue

        if self.target_revision:
            if self.target and self.target_revision.story != self.target:
                raise ValueError(
                    "Reprint target story revision and target story do not "
                    "agree.  Story from revision: '%s'; Story: '%s'" %
                    (self.target_revision.story, self.target))

            if (self.target_issue and
                    self.target_revision.issue != self.target_issue):
                raise ValueError(
                    "Reprint target story revision issue and target issue "
                    "do not agree.  Issue from revision: '%s'; Issue: '%s'" %
                    (self.target_revision.issue, self.target_issue))

        super(ReprintRevision, self).save(*args, **kwargs)

    def _handle_prerequisites(self, changes):
        # If we have StoryRevisions instead of Stories, commit them
        # first and set our Story fields so that our own commit can
        # be handled generically after this point.
        if self.origin_revision:
            self.origin_revision.commit_to_display()
            self.origin = self.origin_revision.source
            self.origin_issue = self.origin.issue

        if self.target_revision:
            self.target_revision.commit_to_display()
            self.target = self.target_revision.source
            self.target_issue = self.target.issue


class Download(models.Model):
    """
    Track downloads of bulk data.  Description may contain the filesystem
    paths or other information about what was downloaded.
    """
    user = models.ForeignKey(User)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)


class ImageRevision(Revision):
    """
    Manage uploading or replacing images attached to other objects.

    The ImageRevision class is unusual in that all non-delete operations
    must involve uploading an image file- either a new file or a replacement.

    We only ever keep one copy of the image on the filesystem, and therefore
    either the Image *or* the ImageRevision will have a field for that file,
    but never both.  Files are named after the id of the object to which
    they are attached.  Image and ImageRevision configure different
    directories in which to store their images, which avoids id conflicts.

    The lifecycle for images on the filesystem is as follows:

    Initial upload:  image temporarily stored under the revision,
        but deleted after being copied to the data object.

    Replacement:  old image copied from data object to the *previous*
        revision (which is the one where that image was uploaded),
        new image handled as with the initial upload.

    Deletion:  image left with data object, not copied to any revision.
    """
    class Meta:
        db_table = 'oi_image_revision'
        ordering = ['created']

    objects = RevisionManager()

    image = models.ForeignKey(Image, null=True, related_name='revisions')

    content_type = models.ForeignKey(content_models.ContentType, null=True)
    object_id = models.PositiveIntegerField(db_index=True, null=True)
    object = generic_fields.GenericForeignKey('content_type', 'object_id')

    type = models.ForeignKey(ImageType)

    image_file = models.ImageField(upload_to='%s/%%m_%%Y' %
                                             settings.NEW_GENERIC_IMAGE_DIR)
    scaled_image = ImageSpecField([ResizeToFit(width=400)],
                                  source='image_file',
                                  format='JPEG', options={'quality': 90})

    marked = models.BooleanField(default=False)
    is_replacement = models.BooleanField(default=False)

    source_name = 'image'
    source_class = Image

    @property
    def source(self):
        return self.image

    @source.setter
    def source(self, value):
        self.image = value

    @classmethod
    def _get_excluded_field_names(cls):
        return frozenset(
            super(ImageRevision, cls)._get_excluded_field_names() |
            {'image_file', 'scaled_image', 'thumbnail', 'icon'}
        )

    @classmethod
    def _get_meta_field_names(cls):
        return frozenset({'marked'})

    def _pre_commit_check(self):
        # This arrangement of if statements makes it easy to unit test
        # all conditions.
        if not self.edited:
            if self.is_replacement:
                raise ValueError("Can only replace during edit, not %s." %
                                 ("add" if self.added else "delete"))

            elif (self.added and self.type.unique and
                  Image.objects.filter(
                      content_type=ContentType.objects
                                              .get_for_model(self.object),
                      object_id=self.object.id,
                      type=self.type,
                      deleted=False).exists()):
                raise ValueError(
                    '%s has an %s. Additional images cannot be uploaded, '
                    'only replacements are possible.' %
                    (self.object, self.type.description))

    def _post_save_object(self, changes):
        if self.deleted:
            # We want to leave the image with the deleted data object
            # to support change history and examining deleted data.
            # So we don't do anything in this case.
            return

        # TODO: What happens if the database transaction fails and unrolls?
        #       Is there anything we can do to make sure the filesystem side
        #       doesn't end up in too bad of a state?
        if self.is_replacement:
            # Since we remove files from revisions when we copy them to
            # data objects, upon replacement we need to backfill a copy
            # of the image to the revision before we delete it from
            # the data object.
            self.previous_revision \
                .image_file.save('%d.jpg' % self.previous_revision.id,
                                 content=self.image.image_file)
            self.image.image_file.delete()

        # Copy to the data object and then remove from the revision
        # so that there is only one copy on the filesystem.
        self.image.image_file.save('%d.jpg' % self.image.id,
                                   content=self.image_file)
        self.image_file.delete()

    def __unicode__(self):
        uni = super(ImageRevision, self).__unicode__()
        if self.image_file:
            return '%s (%s)' % (uni, self.image_file.url)
        return '%s (no file)' % uni
