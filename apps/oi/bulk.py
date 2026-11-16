"""
Bulk changes: one changeset of type 'bulk' that changes many objects.

This module holds the parts that need no request, so that views, tests
and scripts share them.  It must not import apps.oi.views.
"""
from collections import defaultdict
from decimal import Decimal

from diff_match_patch import diff_match_patch
from django.template.defaultfilters import yesno
from django.utils.safestring import mark_safe

from apps.gcd.templatetags.credits import format_page_count
from apps.gcd.templatetags.display import field_name
from apps.oi import states
from apps.oi.models import BULK_OBJECT_NAMES, bulk_object_name
from apps.oi.templatetags.compare import key_date_years_note, show_diff

# A space, a tab or a line break that is all of a changed part would
# vanish in HTML; a no-break space of the same length shows it.
NO_BREAK_SPACE = '\u00a0'


def _compared_fields(rev_class):
    """
    Return the regular fields of rev_class as a pair: the fields read
    with .values(), keywords included, in model order, then the
    many-to-many fields.  Model order puts each single value before its
    flags, as the IMP rules expect.
    """
    regular = rev_class._get_regular_fields()
    single = [field for field in rev_class._meta.concrete_fields
              if field.name in regular]
    multi = [field for field in rev_class._meta.many_to_many
             if field.name in regular]
    return single, multi


def _previous_ids(rev_class, source, rows):
    """
    Map the id of each revision in rows to the id of its previous revision.

    A discarded revision has lost the link.  As in Revision.previous(),
    the latest revision of its object created no later than itself takes
    its place, with one query for all of them: a revision of an approved
    change, as the clone that made the discarded one required, whatever
    its committed flag, which not every approved revision has.
    """
    previous = {revision_id: row['previous_revision_id']
                for revision_id, row in rows.items()}
    lost = [row for row in rows.values()
            if row['previous_revision_id'] is None]
    if not lost:
        return previous

    approved = defaultdict(list)
    for row in rev_class.objects \
                        .filter(changeset__state=states.APPROVED,
                                **{source + '__in': {row[source]
                                                     for row in lost}}) \
                        .order_by('created', 'id') \
                        .values('id', 'created', source):
        approved[row[source]].append(row)
    for row in lost:
        earlier = [other['id'] for other in approved[row[source]]
                   if other['created'] <= row['created']]
        if not earlier:
            raise ValueError('Revision %d of a bulk change has no previous '
                             'revision.' % row['id'])
        previous[row['id']] = earlier[-1]
    return previous


def _linked_ids(field, revision_ids):
    """
    Map each revision id to the frozenset of the ids that the
    many-to-many field links to it, read from the through table.
    """
    through = field.remote_field.through
    own = through._meta.get_field(field.m2m_field_name()).attname
    other = through._meta.get_field(field.m2m_reverse_field_name()).attname
    linked = defaultdict(set)
    for own_id, other_id in through.objects \
                                   .filter(**{own + '__in': revision_ids}) \
                                   .values_list(own, other):
        linked[own_id].add(other_id)
    return {revision_id: frozenset(linked[revision_id])
            for revision_id in revision_ids}


def exact_diff(rev_class, revision_ids):
    """
    Compare revisions of rev_class with their previous revisions, exactly.

    Return {revision id: {field name: (old value, new value)}}, with an
    entry, empty when nothing changed, for each id.  The fields are the
    regular fields of the class, in model order.  Values are compared as
    stored: unlike compare_changes(), spaces and case count, and credits,
    which a bulk change does not clone, play no part.  Single values and
    keywords come from .values(), with the ids of foreign keys; a
    many-to-many value is the frozenset of the linked ids.
    """
    revision_ids = list(revision_ids)
    single, multi = _compared_fields(rev_class)
    source = rev_class._meta.get_field(rev_class.source_name).attname
    columns = [field.attname for field in single]
    rows = {row['id']: row for row in rev_class.objects
            .filter(id__in=revision_ids)
            .values(*dict.fromkeys(['id', 'previous_revision_id',
                                    'created', source] + columns))}
    previous = _previous_ids(rev_class, source, rows)
    old_rows = {row['id']: row for row in rev_class.objects
                .filter(id__in=set(previous.values()))
                .values('id', *columns)}
    linked = {field.name: _linked_ids(field, list(rows) + list(old_rows))
              for field in multi}

    diff = {}
    for revision_id in revision_ids:
        new = rows[revision_id]
        old = old_rows[previous[revision_id]]
        changes = {}
        for field in single:
            if old[field.attname] != new[field.attname]:
                changes[field.name] = (old[field.attname],
                                       new[field.attname])
        for field in multi:
            values = linked[field.name]
            if values[old['id']] != values[revision_id]:
                changes[field.name] = (values[old['id']],
                                       values[revision_id])
        diff[revision_id] = changes
    return diff


def changeset_imps(changeset):
    """
    Return the Index Measurement Points of a bulk change.

    Each logical field changed in the change counts once, with the rules
    of a normal edit (_start_imp_sum and _imps_for of the revision class),
    which join a value and its flags into one field.  The rules run on
    each changed revision for all the changed fields, so that a value
    and its flags count once, and a field earns the most points that a
    revision which changed it gets: a rule that reads the values of a
    revision, such as the page count that an uncertain flag needs,
    counts if any revision that changed the field meets it.  Only the
    changed objects count, not the revisions that anchor them, such as
    the issues of changed sequences.
    """
    name, revisions = changeset.bulk_target()
    if name is None:
        return 0
    revision_ids = list(revisions.values_list('id', flat=True))
    diff = exact_diff(revisions.model, revision_ids)
    changed_ids = [revision_id for revision_id in revision_ids
                   if diff[revision_id]]
    changed_fields = set()
    for revision_id in changed_ids:
        changed_fields.update(diff[revision_id])
    single, multi = _compared_fields(revisions.model)
    names = [field.name for field in single + multi
             if field.name in changed_fields]
    points = dict.fromkeys(names, 0)
    for revision in revisions.filter(id__in=changed_ids):
        revision._start_imp_sum()
        for changed in names:
            earned = revision._imps_for(changed)
            if changed in diff[revision.id]:
                points[changed] = max(points[changed], earned)
    return sum(points.values())


def compare_heading(name, revisions):
    """
    Return the heading of the page of a bulk change, such as "248
    sequences in 97 issues", for the set name and the revisions that
    bulk_target() returns.
    """
    count = revisions.count()
    singular, plural = BULK_OBJECT_NAMES[name]
    heading = '%d %s' % (count, singular if count == 1 else plural)
    if name == 'storyrevisions':
        issues = revisions.order_by().values('issue_id').distinct().count()
        heading += ' in %d issue%s' % (issues, '' if issues == 1 else 's')
    return heading


def _related_names(rev_class, diff):
    """
    Map each relation field in diff to {id: name} for the objects that
    its old and new values point to, with one query per field.
    """
    ids = defaultdict(set)
    for changes in diff.values():
        for name, values in changes.items():
            if not rev_class._meta.get_field(name).is_relation:
                continue
            for value in values:
                if isinstance(value, frozenset):
                    ids[name].update(value)
                elif value is not None:
                    ids[name].add(value)
    return {name: {pk: str(data_object) for pk, data_object in
                   rev_class._meta.get_field(name).related_model.objects
                                  .in_bulk(field_ids).items()}
            for name, field_ids in ids.items()}


def _shown_value(field, value, names):
    """
    Return the text that shows value, a value of field as exact_diff
    gives it: the names of the objects for a relation, joined with "; "
    for a many-to-many field; a decimal, such as a page count, as the
    site shows it.
    """
    if value is None:
        return ''
    if field.is_relation:
        if isinstance(value, frozenset):
            return '; '.join(sorted(names[pk] for pk in value))
        return names[value]
    if isinstance(value, bool):
        return yesno(value, 'Yes,No')
    if isinstance(value, Decimal):
        return format_page_count(value)
    return str(value)


def _shown_change(field, old, new, names):
    """
    Return the old and the new value of field as HTML, with the deleted
    and the added parts marked.  Text is compared character by character
    and keeps spaces and case; any other value is marked as a whole.
    """
    old = _shown_value(field, old, names)
    new = _shown_value(field, new, names)
    if field.get_internal_type() in ('CharField', 'TextField'):
        diff = diff_match_patch().diff_main(old, new)
        diff_match_patch().diff_cleanupSemantic(diff)
    else:
        diff = [(-1, old), (1, new)]
    diff = [(op, NO_BREAK_SPACE * len(text) if op and text.isspace()
             else text) for op, text in diff if text]
    return show_diff(diff, 'orig'), show_diff(diff, 'change')


# The fields of an issue that feed the notes of the compare page of one
# issue on a key date outside the years of its indicia publisher or of
# its brand emblems.
YEARS_NOTE_FIELDS = ('key_date', 'indicia_publisher', 'brand_emblem')


def _years_notes(rev_class, revisions, diff):
    """
    Return {(revision id, field name): [old note, new note]}, the notes
    that the compare page of one issue gives, by key_date_years_note, on
    a key date outside the years of the indicia publisher or of a brand
    emblem, for the issue revisions whose key date, indicia publisher or
    brand emblems changed.  Each side reads its own values: the new side
    those of the revision, the old side the old value of each of these
    fields that changed.  A note is in the row of its own field when
    that changed, else in the Key Date row, the indicia publisher first.
    At most three queries, whatever the number of revisions.
    """
    if rev_class.source_name != 'issue':
        return {}
    publisher_model = rev_class._meta.get_field(
      'indicia_publisher').related_model
    emblem_field = rev_class._meta.get_field('brand_emblem')
    concerned = [revision for revision in revisions
                 if set(YEARS_NOTE_FIELDS).intersection(diff[revision.id])]
    if not concerned:
        return {}
    links = _linked_ids(emblem_field,
                        [revision.id for revision in concerned])
    sides = []
    publisher_ids, emblem_ids = set(), set()
    for revision in concerned:
        changes = diff[revision.id]
        key_row = 'key_date' if 'key_date' in changes else None
        rows = ('indicia_publisher' if 'indicia_publisher' in changes
                else key_row,
                'brand_emblem' if 'brand_emblem' in changes else key_row)
        stored = (revision.key_date, revision.indicia_publisher_id,
                  links[revision.id])
        for side in (0, 1):
            key_date, publisher, emblems = [
              changes[name][side] if name in changes else value
              for name, value in zip(YEARS_NOTE_FIELDS, stored)]
            sides.append((revision, side, rows, key_date, publisher,
                          emblems))
            publisher_ids.add(publisher)
            emblem_ids.update(emblems)
    publishers = publisher_model.objects.in_bulk(publisher_ids - {None})
    emblems_by_id = emblem_field.related_model.objects.in_bulk(emblem_ids)
    notes = defaultdict(lambda: ['', ''])
    for revision, side, rows, key_date, publisher, emblems in sides:
        publisher_row, emblem_row = rows
        # The note reads the key date of the object it gets: for the old
        # side, an unsaved revision that holds the old key date.
        dated = revision if side else rev_class(key_date=key_date)
        if publisher_row:
            notes[revision.id, publisher_row][side] += key_date_years_note(
              dated, publishers.get(publisher), 'Indicia publisher')
        if emblem_row:
            for emblem in sorted((emblems_by_id[pk] for pk in emblems),
                                 key=str):
                notes[revision.id, emblem_row][side] += key_date_years_note(
                  dated, emblem, 'Brand emblem')
    return notes


def compare_rows(revisions):
    """
    Return the rows of the page of a bulk change for revisions of one
    class: for each revision with changes, a tuple of the revision, the
    name of its object and its changed fields, in the order of
    _compared_fields, each as (label, old HTML, new HTML).  A cell ends
    with the notes that _years_notes gives for its side and row.
    """
    revisions = list(revisions)
    if not revisions:
        return []
    rev_class = type(revisions[0])
    diff = exact_diff(rev_class, [revision.id for revision in revisions])
    names = _related_names(rev_class, diff)
    notes = _years_notes(rev_class, revisions, diff)
    rows = []
    for revision in revisions:
        fields = []
        for name, (old, new) in diff[revision.id].items():
            field = rev_class._meta.get_field(name)
            shown = _shown_change(field, old, new, names.get(name))
            ends = notes.get((revision.id, name), ('', ''))
            fields.append((field_name(name),) + tuple(
              mark_safe(cell + end) for cell, end in zip(shown, ends)))
        if fields:
            rows.append((revision, bulk_object_name(revision), fields))
    return rows
