# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models


class GcdBase(models.Model):
    """
    Base class for base classes.  Ensures consistent interface.
    """
    class Meta:
        app_label = 'gcd'
        abstract = True

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

    # Fields related to change management.
    reserved = models.BooleanField(default=False, db_index=True)

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)

    deleted = models.BooleanField(default=False, db_index=True)

    def delete(self):
        self.deleted = True
        self.reserved = False
        self.save()


class GcdLink(GcdBase):
    """
    Base class for link objects connection two data objects.

    These are edited with Revisions, but do not persist in the
    database upon deletion.  And we don't care as much about
    when they were created or modified.
    """
    class Meta:
        app_label = 'gcd'
        abstract = True

    reserved = models.BooleanField(default=False, db_index=True)

    @property
    def modified(self):
        # TODO: Fix hardcoded dependency on oi state value 5.
        #       Should we just add a modified column?  It is
        #       handled automatically anyway.
        return self.revisions.filter(changeset__state=5).latest().modified

    # we check for deleted in the oi for models, so set to False
    deleted = False

    def deletable(self):
        return True
