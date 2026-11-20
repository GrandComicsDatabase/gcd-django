"""
The integrity of bulk changes, checked at the end of each test that makes
them: the invariants I1-I5, I7 and I8 of the plan of issue #49.
"""
from django.contrib.contenttypes.models import ContentType

from apps.oi import bulk, states
from apps.oi.models import BULK_REVISION_ORDER, CTYPES, Changeset


def _check_revision(changeset, revision, locks):
    """
    Check one revision of a bulk change: its lock while the change is
    active (I2), its committed flag once closed (I3), one approved latest
    revision of its object (I4).
    """
    source = revision.source
    rev_class = type(revision)
    if changeset.state in states.ACTIVE:
        assert (ContentType.objects.get_for_model(source).id,
                source.id) in locks, revision
    elif changeset.state == states.APPROVED:
        assert revision.committed is True, revision
    elif changeset.state == states.DISCARDED:
        assert not revision.committed, revision
        assert revision.previous_revision is None, revision
    if revision.previous_revision is not None:
        assert revision.previous_revision.source == source, revision
    approved = rev_class.objects.filter(
      changeset__state=states.APPROVED, **{rev_class.source_name: source})
    heads = approved.exclude(next_revision__changeset__state=states.APPROVED)
    assert heads.count() == 1, revision


def _check_operation(changeset, record, first):
    """
    Check the comment of an operation: counts that add up to the objects,
    or for a revert the values, checked, listed ids of real objects and,
    in a revert, each outcome of REVERT_LISTED listed if and only if it is
    counted (I7), and the value of each field of the record of each
    approved latest revision on its object (I5).  The first operation
    made the revisions, so it counts one changed object for each revision
    of the change that changes something, or for a revert one changed
    value for each of their logical fields among those of the record.
    """
    assert sum(record['counts'].values()) == record['checked']
    name, revisions = changeset.bulk_target()
    if first:
        diff = bulk.exact_diff(revisions.model,
                               revisions.values_list('id', flat=True))
        if record['operation'] == 'restore':
            names = set(bulk.record_fields(record))
            changed = sum(len(bulk._units(revisions.model, names, changes))
                          for changes in diff.values())
        else:
            changed = sum(1 for changes in diff.values() if changes)
        assert record['counts']['changed'] == changed
    model = revisions.model._meta.get_field(
      revisions.model.source_name).related_model
    for ids in record['listed'].values():
        assert model.objects.filter(id__in=ids).count() == len(set(ids))
    if record['operation'] == 'restore':
        # A revert lists each outcome that it counts, under a label that
        # reads back, and nothing else.
        for outcome in bulk.REVERT_LISTED:
            assert bool(record['counts'].get(outcome)) == \
                bool(record['listed'].get(outcome)), (changeset, outcome)
    if changeset.state == states.APPROVED:
        for field_name in bulk.record_fields(record):
            attname = model._meta.get_field(field_name).attname
            for revision in revisions.exclude(
                 next_revision__changeset__state=states.APPROVED):
                assert getattr(revision.source, attname) == \
                    getattr(revision, attname), revision


def check_invariants():
    """Assert the invariants on every bulk change in the database."""
    for changeset in Changeset.objects.filter(change_type=CTYPES['bulk']):
        locks = set(changeset.revision_locks.values_list('content_type_id',
                                                         'object_id'))
        # I1: only an active change holds locks.
        assert not locks or changeset.state in states.ACTIVE, changeset
        # I8: no revision of a kind that bulk changes do not make.
        assert not bulk.other_revisions(changeset), changeset
        locked = set()
        for name in BULK_REVISION_ORDER:
            for revision in getattr(changeset, name).all():
                _check_revision(changeset, revision, locks)
                locked.add((ContentType.objects.get_for_model(
                  revision.source).id, revision.source.id))
        # I2: an active change holds no lock without its revision, such
        # as the lock of an object that left the change.
        assert changeset.state not in states.ACTIVE or locks == locked, \
            changeset
        records = bulk.operation_records(changeset)
        # A revert takes no further operation.
        assert len(records) == 1 or not any(
          record['operation'] == 'restore' for record in records), changeset
        for position, record in enumerate(records):
            _check_operation(changeset, record, position == 0)
