"""
Bulk changes: one changeset of type 'bulk' that changes many objects.

Most of this module needs no request, so that views, tests and scripts
share it; only the start from a list keeps its selection in the session.
It must not import apps.oi.views.
"""
import re
import secrets
from collections import Counter, defaultdict
from decimal import Decimal

from diff_match_patch import diff_match_patch
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import QuerySet
from django.http import HttpResponseRedirect
from django.template.defaultfilters import yesno
from django.utils.encoding import escape_uri_path
from django.utils.safestring import mark_safe
import django.urls as urlresolvers

from apps.gcd.models import Issue, Publisher
from apps.gcd.templatetags.credits import format_page_count
from apps.gcd.templatetags.display import field_name
from apps.indexer.views import render_error
from apps.oi import states
from apps.oi.models import (
    BULK_OBJECT_NAMES, IssueRevision, RevisionLock, bulk_object_name)
from apps.oi.templatetags.compare import key_date_years_note, show_diff

# A space, a tab or a line break that is all of a changed part would
# vanish in HTML; a no-break space of the same length shows it.
NO_BREAK_SPACE = '\u00a0'

# Spaces that HTML would merge or hide: a run of two or more, or a tab or
# a line break.
HIDDEN_SPACES = re.compile(r'\s{2,}|[^\S ]')

# A run of spaces, which HTML would merge.
SPACE_RUNS = re.compile(r' {2,}')

# Spaces at the start and at the end of a value, which HTML hides at the
# edges of a cell.
LEADING_SPACES = re.compile(r'\A\s+')
TRAILING_SPACES = re.compile(r'\s+\Z')

# The models that a bulk change can change, with their revision classes.
BULK_TARGETS = {Issue: IssueRevision}

# The fields that a bulk change can change, by their nature in the field
# census: T transcribed as printed, F in a prescribed format, L a link to
# another record, flag a yes or no.
FIELD_POLICY = {
    IssueRevision: {
        'T': ('rating',),
        'T+F': ('publication_date', 'indicia_frequency'),
        'F': ('volume', 'key_date', 'price', 'page_count'),
        'L': ('indicia_publisher',),
        'flag': ('no_title', 'no_volume', 'volume_not_printed',
                 'display_volume_with_number', 'indicia_pub_not_printed',
                 'no_brand', 'no_indicia_frequency', 'page_count_uncertain',
                 'indicia_printer_not_printed', 'no_isbn', 'no_barcode',
                 'no_rating'),
    },
}

# The fields that a bulk change leaves alone, by reason.  With the fields
# of FIELD_POLICY they are all the fields of the edit form.
EXCLUDED = {
    IssueRevision: {
        'unique to each issue': ('number', 'isbn', 'barcode'),
        'a parent, changed by its own move': ('series', 'variant_of'),
        'left out, as in the issue bulk change': (
            'title', 'notes', 'year_on_sale', 'month_on_sale', 'day_on_sale',
            'on_sale_date_uncertain'),
        'set for each variant': ('variant_name', 'variant_cover_status'),
        'later: credits, keywords and links to many objects': (
            'editing', 'no_editing', 'keywords', 'brand_emblem',
            'indicia_printer', 'indicia_printer_sourced_by'),
    },
}

# Fields that a flag of the parent turns off, as the edit forms do:
# {model: (parent, {flag: fields})}.  Where a field is off, a bulk
# change leaves it alone.
TURNED_OFF_BY = {
    Issue: ('series', {
        'has_issue_title': ('no_title',),
        'has_volume': ('volume', 'no_volume', 'volume_not_printed',
                       'display_volume_with_number'),
        'has_indicia_frequency': ('indicia_frequency',
                                  'no_indicia_frequency'),
        'has_indicia_printer': ('indicia_printer_not_printed',),
        'has_isbn': ('no_isbn',),
        'has_barcode': ('no_barcode',),
        'has_rating': ('rating', 'no_rating'),
    }),
}

# The operations, as form choices: on the objects that hold one exact old
# value, or on all of them.  Values compare as stored: spaces and case
# count.
OPERATIONS = (('replace_exact', 'Replace the old value'),
              ('set', 'Set all to the new value'))

# Fields of a date, which belongs to each object: a bulk change never
# sets one for all objects, never empties one, never fills an empty one.
NOT_EMPTY = ('publication_date', 'key_date')

# The most values that the form lists.
LISTED_VALUES = 100

# The session key of the selection that start_from_list keeps.
SELECTION_KEY = 'bulk_selection'


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
    its committed flag, which not every approved revision has.  Of two
    revisions stored with the same time, the one with the lower id was
    made first.
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
                   if (other['created'], other['id'])
                   < (row['created'], row['id'])]
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
    return _diff_and_values(rev_class, revision_ids)[0]


def _diff_and_values(rev_class, revision_ids):
    """
    Return exact_diff(rev_class, revision_ids) and, read from the same
    rows, the new values that it compared: {revision id: {field name:
    value}} for each id, with the values in the form of the diff.
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

    diff, new_values = {}, {}
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
        new_values[revision_id] = dict(
          [(field.name, new[field.attname]) for field in single] +
          [(field.name, linked[field.name][revision_id])
           for field in multi])
    return diff, new_values


def _seen_flags(revision):
    """
    Return the names of the flags, such as _seen_volume, that the IMP
    rules of revision have set since its _start_imp_sum.
    """
    return {name for name, value in vars(revision).items()
            if name.startswith('_seen_') and value is True}


def _logical_points(revision, names):
    """
    Return {logical field: points} for the fields names that revision
    changed, scored in model order as a normal edit scores them.  The
    logical field of a name is the flag that its rule sets, such as
    _seen_volume for volume and no_volume, else the name itself.
    """
    revision._start_imp_sum()
    points = {}
    for name in names:
        seen = _seen_flags(revision)
        earned = revision._imps_for(name)
        key = ' '.join(sorted(_seen_flags(revision) - seen)) or name
        points[key] = points.get(key, 0) + earned
    return points


def changeset_imps(changeset):
    """
    Return the Index Measurement Points of a bulk change.

    Each logical field changed in the change counts once, with the rules
    of a normal edit (_start_imp_sum and _imps_for of the revision class),
    which join a value and its flags into one field.  The rules run on
    each changed revision for the fields that it changed only, so that
    a field it left alone takes nothing from those it changed, and a
    logical field earns the most points that a revision which changed
    it gets: a rule that reads the values of a revision, such as the
    page count that an uncertain flag needs, counts if any revision that
    changed the field meets it.  Only the changed objects count, not the
    revisions that anchor them, such as the issues of changed sequences.
    """
    name, revisions = changeset.bulk_target()
    if name is None:
        return 0
    revision_ids = list(revisions.values_list('id', flat=True))
    diff = exact_diff(revisions.model, revision_ids)
    changed_ids = [revision_id for revision_id in revision_ids
                   if diff[revision_id]]
    single, multi = _compared_fields(revisions.model)
    points = defaultdict(int)
    for revision in revisions.filter(id__in=changed_ids):
        names = [field.name for field in single + multi
                 if field.name in diff[revision.id]]
        for key, earned in _logical_points(revision, names).items():
            points[key] = max(points[key], earned)
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
    The spaces that HTML would hide show as no-break spaces: those of a
    changed part, and those at the start and at the end of each value.
    """
    old = _shown_value(field, old, names)
    new = _shown_value(field, new, names)
    if field.get_internal_type() in ('CharField', 'TextField'):
        diff = diff_match_patch().diff_main(old, new)
        diff_match_patch().diff_cleanupSemantic(diff)
    else:
        diff = [(-1, old), (1, new)]
    diff = [(op, _shown_spaces(text) if op else text)
            for op, text in diff if text]
    old_side = _shown_edges([part for part in diff if part[0] <= 0])
    new_side = _shown_edges([part for part in diff if part[0] >= 0])
    return show_diff(old_side, 'orig'), show_diff(new_side, 'change')


def _shown_edges(parts):
    """
    Return parts, the (op, text) parts of one side of a value, with the
    spaces at the start of the first part and at the end of the last
    one as no-break spaces, changed or not: HTML hides them at the edges
    of a cell.
    """
    for index, edge in ((0, LEADING_SPACES), (-1, TRAILING_SPACES)):
        if parts:
            op, text = parts[index]
            parts[index] = (op, edge.sub(
              lambda match: NO_BREAK_SPACE * len(match.group()), text))
    return parts


def _shown_spaces(text):
    """
    Return a changed part of a text with no-break spaces in place of the
    spaces that HTML would merge or hide; a part of spaces only is all
    no-break spaces, so that it does not vanish.
    """
    if text.isspace():
        return NO_BREAK_SPACE * len(text)
    return HIDDEN_SPACES.sub(
      lambda match: NO_BREAK_SPACE * len(match.group()), text)


# The fields of an issue that feed the notes of the compare page of one
# issue on a key date outside the years of its indicia publisher or of
# its brand emblems.
YEARS_NOTE_FIELDS = ('key_date', 'indicia_publisher', 'brand_emblem')


def _years_notes(rev_class, revisions, diff, new_values):
    """
    Return {(revision id, field name): [old note, new note]}, the notes
    that the compare page of one issue gives, by key_date_years_note, on
    a key date outside the years of the indicia publisher or of a brand
    emblem, for the issue revisions whose key date, indicia publisher or
    brand emblems changed.  Each side reads its own values from the rows
    of the diff, whose new values new_values holds, as _diff_and_values
    gives them: the new side those values, the old side the old value of
    each of these fields that changed.  A note is in the row of its own
    field when that changed, else in the Key Date row, the indicia
    publisher first.  At most two queries, whatever the number of
    revisions.
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
    sides = []
    publisher_ids, emblem_ids = set(), set()
    for revision in concerned:
        changes = diff[revision.id]
        key_row = 'key_date' if 'key_date' in changes else None
        rows = ('indicia_publisher' if 'indicia_publisher' in changes
                else key_row,
                'brand_emblem' if 'brand_emblem' in changes else key_row)
        stored = new_values[revision.id]
        for side in (0, 1):
            key_date, publisher, emblems = [
              changes[name][side] if name in changes else stored[name]
              for name in YEARS_NOTE_FIELDS]
            sides.append((revision, side, rows, key_date, publisher,
                          emblems))
            publisher_ids.add(publisher)
            emblem_ids.update(emblems)
    publishers = publisher_model.objects.in_bulk(publisher_ids - {None})
    emblems_by_id = emblem_field.related_model.objects.in_bulk(emblem_ids)
    notes = defaultdict(lambda: ['', ''])
    for revision, side, rows, key_date, publisher, emblems in sides:
        publisher_row, emblem_row = rows
        # The note reads the key date of the object it gets: an unsaved
        # revision that holds the key date of the side.
        dated = rev_class(key_date=key_date)
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
    diff, new_values = _diff_and_values(
      rev_class, [revision.id for revision in revisions])
    names = _related_names(rev_class, diff)
    notes = _years_notes(rev_class, revisions, diff, new_values)
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


def bulk_model(items):
    """
    Return the model of the list items if a bulk change can change it,
    else None.  Only a Django QuerySet qualifies, which a view may also
    build from the ids of search engine hits; a SearchQuerySet does not.
    """
    if isinstance(items, QuerySet) and items.model in BULK_TARGETS:
        return items.model
    return None


def entry_allowed(user, items):
    """
    Return whether user may start a bulk change from the list items:
    bulk changes are on, the site edits data, the user may reserve and a
    bulk change can change the objects of the list.
    """
    return (settings.BULK_CHANGE_ENABLED and not settings.MYCOMICS and
            not settings.NO_OI and user.has_perm('indexer.can_reserve') and
            bulk_model(items) is not None)


def start_from_list(request, items):
    """
    Start a bulk change from the list items: keep the sorted ids of its
    objects, deleted ones left out, in the session, and go to the bulk
    change page.  An empty list, or one with more than BULK_CHANGE_MAX
    objects, gives an error page.  Only the session is written.

    The address of the list is kept escaped, as get_full_path gives it,
    so that it stays one line of the record of the bulk change and a
    valid link.
    """
    ids = items.filter(deleted=False).order_by() \
               .values_list('id', flat=True).distinct()
    # One read gives the ids that are checked and kept.  One id
    # beyond the limit shows a list that is too long; only its
    # message needs its size.
    kept = sorted(ids[:settings.BULK_CHANGE_MAX + 1])
    count = len(kept)
    if count > settings.BULK_CHANGE_MAX:
        count = max(count, ids.count())
    if not count:
        return render_error(request, 'This list has no objects for a bulk '
                                     'change.', redirect=False)
    if count > settings.BULK_CHANGE_MAX:
        return render_error(
          request,
          'A bulk change can hold at most %d objects, and this list has %d.'
          ' Please narrow the list first, for example with a filter.'
          % (settings.BULK_CHANGE_MAX, count), redirect=False)
    query = request.GET.copy()
    query.pop('_export')
    source = escape_uri_path(request.path)
    if query:
        source += '?' + query.urlencode()
    token = secrets.token_urlsafe(8)
    request.session[SELECTION_KEY] = {
        'token': token,
        'model': items.model._meta.model_name,
        'ids': kept,
        'source': source,
    }
    return HttpResponseRedirect(
      urlresolvers.reverse('edit_issues_in_bulk') + '?token=' + token)


def stored_selection(request, token):
    """
    Return the selection that start_from_list kept for token, as (model,
    ids, url of the list), or None if the session no longer holds it: it
    expired, or a newer selection took its place.
    """
    selection = request.session.get(SELECTION_KEY)
    if not selection or selection['token'] != token:
        return None
    models = {model._meta.model_name: model for model in BULK_TARGETS}
    return (models[selection['model']], selection['ids'],
            selection['source'])


def policy_fields(rev_class):
    """Return {field name: nature} for the fields of FIELD_POLICY."""
    return {name: nature
            for nature, names in FIELD_POLICY[rev_class].items()
            for name in names}


def operations(name, nature):
    """
    Return the operations, as form choices, for the field name of this
    nature: a transcribed value or a date is replaced one exact value at
    a time, never set for all objects at once.
    """
    if 'T' in nature or 'D' in nature or name in NOT_EMPTY:
        return OPERATIONS[:1]
    return OPERATIONS


def applicable(data_object, name):
    """
    Return whether the field name is on for data_object: a flag of its
    parent, such as has_volume of the series of an issue, can turn it
    off, as in the edit form.
    """
    parent, flags = TURNED_OFF_BY.get(type(data_object), (None, {}))
    for flag, names in flags.items():
        if name in names:
            return getattr(getattr(data_object, parent), flag)
    return True


def _chunks(ids, size=1000):
    """Yield the list ids in slices of at most size ids."""
    for start in range(0, len(ids), size):
        yield ids[start:start + size]


def single_publisher(model, ids):
    """
    Return the publisher of all the objects of model with these ids, or
    None if they have several: an issue has the publisher of its series.
    A link field, such as the indicia publisher, is offered only with one
    publisher, whose records the edit form lists.
    """
    publisher_ids = set()
    for chunk in _chunks(ids):
        publisher_ids.update(model.objects.filter(id__in=chunk,
                                                  deleted=False)
                                  .values_list('series__publisher',
                                               flat=True))
    if len(publisher_ids) != 1:
        return None
    return Publisher.objects.get(id=publisher_ids.pop())


def deleted_count(model, ids):
    """
    Return how many of the objects of model with these ids were deleted
    since the list was chosen.
    """
    return sum(model.objects.filter(id__in=chunk, deleted=True).count()
               for chunk in _chunks(ids))


def distinct_values(model, ids, name):
    """
    Return the values of the field name among the objects of model with
    these ids, as (value, count) pairs, the most frequent first.  Values
    are counted in Python, so that spaces and case count, and None and ''
    stay apart, whatever the collation of the column.
    """
    attname = model._meta.get_field(name).attname
    counts = Counter()
    for chunk in _chunks(ids):
        counts.update(model.objects.filter(id__in=chunk, deleted=False)
                           .values_list(attname, flat=True))
    return sorted(counts.items(),
                  key=lambda item: (-item[1], value_key(item[0])))


def value_key(value):
    r"""
    Return the text that stands for a stored value in a form choice:
    'None' for None, else '=' and the value, so that no value, the empty
    text included, looks like no choice.  A backslash, a carriage return
    and a line feed are written \\, \r and \n: a browser changes the line
    breaks of a radio value before it sends it, and each value keeps a
    key of its own.
    """
    if value is None:
        return 'None'
    return '=' + str(value).replace('\\', '\\\\').replace('\r', '\\r') \
                           .replace('\n', '\\n')


def _object_names(field, values):
    """
    Return {id: name} for the objects that the relation field links to
    with these values, and {} for any other field.
    """
    if not field.is_relation:
        return {}
    return {pk: str(data_object) for pk, data_object in
            field.related_model.objects
                 .in_bulk([value for value in values if value is not None])
                 .items()}


def _label_text(value):
    r"""
    Return a text as the label of an old value shows it, so that no two
    values look alike: a backslash is \\, and a character that shows as
    nothing or as a space, such as a tab, a line break or a no-break
    space, is its Python escape; a run of spaces, which HTML would merge,
    is no-break spaces.
    """
    text = ''.join(
      char if char.isprintable() and char != '\\'
      else char.encode('unicode_escape').decode('ascii')
      for char in value)
    return SPACE_RUNS.sub(
      lambda match: NO_BREAK_SPACE * len(match.group()), text)


def value_choices(field, values):
    """
    Return form choices for values, the (value, count) pairs of one
    field: the key of each value and a label with its count.  A text is
    in quotes, as _label_text() shows it; a link shows the name of its
    object.
    """
    names = _object_names(field, [value for value, count in values])
    choices = []
    for value, count in values:
        if value is None or value == '':
            label = '(empty)'
        elif isinstance(value, str):
            label = '"%s"' % _label_text(value)
        else:
            label = _shown_value(field, value, names)
        choices.append((value_key(value), '%s (%d)' % (label, count)))
    return choices


def new_value(current, operation, old, new):
    """
    Return the value that operation gives to a field that holds current:
    'set' gives new; 'replace_exact' gives new where current is exactly
    old, as stored, and keeps current elsewhere.
    """
    if operation == 'set':
        return new
    if operation == 'replace_exact':
        return new if current == old else current
    raise ValueError('Unknown bulk change operation %r.' % operation)


def preview(model, ids, name, operation, old, new):
    """
    Return what operation would do to the field name of the objects of
    model with these ids, writing nothing.  The objects whose value would
    change are split four ways: 'deleted' since the list was chosen,
    'turned_off' where a flag of the parent turns the field off,
    'reserved' where another change reserves them, and the others,
    counted in 'changed'.  'rows' shows the first BULK_CHANGE_MAX of
    these, so all of them for a selection within the limit, each as
    (object, old HTML, new HTML).  Each thousand objects comes in the
    order of the model.
    """
    field = model._meta.get_field(name)
    parent = TURNED_OFF_BY.get(model, (None,))[0]
    changes, turned_off, deleted = [], [], []
    for chunk in _chunks(ids):
        objects = model.objects.filter(id__in=chunk)
        if parent:
            objects = objects.select_related(parent)
        for data_object in objects:
            current = getattr(data_object, field.attname)
            value = new_value(current, operation, old, new)
            if value == current:
                continue
            if data_object.deleted:
                deleted.append(data_object)
            elif applicable(data_object, name):
                changes.append((data_object, current, value))
            else:
                turned_off.append(data_object)

    locked = set(RevisionLock.objects
                 .filter(content_type=ContentType.objects
                                                 .get_for_model(model),
                         object_id__in=[change[0].id for change in changes])
                 .values_list('object_id', flat=True))
    reserved = [change[0] for change in changes if change[0].id in locked]
    changes = [change for change in changes if change[0].id not in locked]
    shown = changes[:settings.BULK_CHANGE_MAX]
    names = _object_names(field, [value for change in shown
                                  for value in change[1:]])
    rows = [(data_object,) + _shown_change(field, current, value, names)
            for data_object, current, value in shown]
    return {'changed': len(changes), 'rows': rows, 'reserved': reserved,
            'turned_off': turned_off, 'deleted': deleted}
