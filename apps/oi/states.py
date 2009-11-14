"""
This module is just a place to define constants related to index status.
"""

"""
Used in old_state field when a reservation is created.
"""
UNRESERVED = 99

"""
Marks an artificial reservation that needs to be replaced when the
Log* tables are migrated.
"""
BASELINE = 0

"""
The reservation is open and the indexer is working on it.
"""
OPEN = 1

"""
The reservation has been submitted for approval, but is not being examined.
"""
PENDING = 2

"""
The change is being examined for approval.
"""
REVIEWING = 4

"""
Approval has been granted.
"""
APPROVED = 5

"""
Approval was not granted, no further work will be done.
"""
DISCARDED = 6

DISPLAY_NAME = {
    UNRESERVED: 'Available',
    BASELINE: 'Baseline',
    OPEN: 'Editing',
    PENDING: 'Pending Review',
    REVIEWING: 'Under Review',
    APPROVED: 'Approved',
    DISCARDED: 'Discarded',
}

ACTIVE = (OPEN, PENDING, REVIEWING)

