# -*- coding: utf-8 -*-

from __future__ import unicode_literals


class RevisionCoordinator(object):
    """
    Base class for operations involving multiple Revisions together.

    Some Revision operations, such as calculating the total IMPs,
    are dependent not only on the individual Revisions, but on
    what combinations of Revisions are present.

    Others, such as moving a child item from one parent object to another,
    by nature require code outside of the individual Revisions.

    Finally, the coordinator routes operations that apply to multiple
    Revisions individually, such as commiting all revisions to display.
    """
    def __init__(self, changeset):
        self._changeset = changeset
        self._revisions = []

    def add_revision(self, revision):
        """
        Add a revision to this coordinator.
        """
        self._revisions.append(revision)

    def calculate_imps(self):
        """
        Calculate IMPs for the set of Revisions.

        By default, we just add up all of the individual IMP counts.
        Child classes should override if more complex behavior is required.
        """
        return sum([r.calculate_imps() for r in self._revisions])

    def commit_all_to_display(self):
        """
        Commit the revision changes to their display objects.

        Revisions should handle their own dependencies (in a manner TBD).
        Committing a Revision twice in the same transaction should always
        be safe, and generally not cause additional database changes.
        """
        # TODO: Figure out dependency code flow.
        for rev in self._revisions:
            rev.commit_to_display()
