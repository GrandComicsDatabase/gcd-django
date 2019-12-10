# -*- coding: utf-8 -*-


from django.db import models


class GcdBase(models.Model):
    """
    Base class for base classes.  Ensures consistent interface.
    """
    class Meta:
        app_label = 'gcd'
        abstract = True

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)

    def deletable(self):
        return not (self.revisions.active_set().exists() or
                    self.has_dependents())

    def has_dependents(self):
        """
        Checks for objects that depend on this object in database terms.

        This should include checks for open revisions of child objects,
        but not for revisions of this object, which can already be
        easily checked and are automatically included in the deletable()
        implementation.
        """
        return False

    def pending_deletion(self):
        return bool(self.revisions.pending_deletions().exists())

    # Indicates if the global stats are updated for this data object.
    _update_stats = False

    def stat_counts(self):
        """
        Returns all count values relevant to this data object.

        Includes a count for the data object itself.

        Objects that are not involved in statistics need not override
        this method.

        Non-comics publications must not return series and issue
        counts as they do not contribute those types of statistics.
        All other types of statistics are tracked in all cases.

        The return format must be a dictionary with keys that correspond
        to valid CountStats.name values, and values indicating the relevant
        numerical count for that name that this object (and its children)
        represent.
        """
        return {}

    def update_cached_counts(self, deltas, negate=False):
        """
        Updates the database fields that cache child object counts.

        Expects a deltas object in the form returned by stat_counts()
        methods, and also expected by CountStats.update_all_counts().

        Classes that do not maintain cached counts of child objects
        need not override this method.
        """
        pass


class GcdData(GcdBase):
    """
    Base class for all data objects in the gcd app.

    A data object is a type of object that can be edited using the
    Changeset/Revision workflow in the 'oi' app, and persists in
    the 'gcd' app table even after deletion.
    """
    class Meta:
        app_label = 'gcd'
        abstract = True

    deleted = models.BooleanField(default=False, db_index=True)

    def has_keywords(self):
        return self.keywords.exists()

    def delete(self):
        self.deleted = True
        self.save()


class GcdLink(GcdBase):
    """
    Base class for link objects connection two data objects.

    These are edited with Revisions, but do not persist in the
    database upon deletion, and therefore need neither a "deleted"
    column nor an override of the delete() method.
    """
    class Meta:
        app_label = 'gcd'
        abstract = True
