"""
Bulk changes: one changeset of type 'bulk' that changes many objects.

Most of this module needs no request, so that views, tests and scripts
share it; only the start from a list keeps its selection in the session.
It must not import apps.oi.views.
"""
import copy
import json
import re
import secrets
from collections import Counter, defaultdict, namedtuple
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace

from diff_match_patch import diff_match_patch
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.db import OperationalError, connection, transaction
from django.db.models import QuerySet
from django.http import HttpResponseRedirect
from django.template.defaultfilters import yesno
from django.utils import timezone
from django.utils.encoding import escape_uri_path
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
import django.urls as urlresolvers

from apps.gcd.models import Issue, Publisher
from apps.gcd.templatetags.credits import format_page_count
from apps.gcd.templatetags.display import field_name
from apps.indexer.models import Indexer
from apps.indexer.views import ErrorWithMessage, render_error
from apps.oi import states
from apps.oi.models import (
    BULK_OBJECT_NAMES, BULK_REVISION_ORDER, CTYPES, Changeset, IssueRevision,
    RevisionLock, _free_revision_lock, _get_revision_lock, bulk_object_name)
from apps.oi.templatetags.compare import key_date_years_note, show_diff
from apps.oi.validation import revision_form_messages

# A space, a tab or a line break that is all of a changed part would
# vanish in HTML; a no-break space of the same length shows it.
NO_BREAK_SPACE = '\u00a0'

# Spaces that HTML would merge or hide: a run of two or more, or a tab or
# a line break.
HIDDEN_SPACES = re.compile(r'\s{2,}|[^\S ]')

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
# A revision holds the same parent as its object.
TURNED_OFF_BY[IssueRevision] = TURNED_OFF_BY[Issue]

# The operations, as form choices: on the objects that hold one exact old
# value, or on all of them.  Values compare as stored: spaces and case
# count.
OPERATIONS = (('replace_exact', 'Replace the old value'),
              ('set', 'Set all to the new value'))

# Fields of a date, which belongs to each object: a bulk change never
# sets one for all objects, never empties one, never fills an empty one.
# A revert may still put back the empty value that such a field held
# before the change it reverts.
NOT_EMPTY = ('publication_date', 'key_date')

# The most values that the form lists.
LISTED_VALUES = 100

# The session key of the selection that start_from_list keeps.
SELECTION_KEY = 'bulk_selection'

# The cache key that marks the selection of a user and a token as
# applied, and for how long: as long as a session keeps the selection,
# so that a token is applied once.
APPLIED_KEY = 'bulk_applied_%d_%s'
APPLIED_SECONDS = settings.SESSION_COOKIE_AGE

# Why a selection cannot be applied again.
APPLIED_ALREADY = ('This selection was applied already, or is being '
                   'applied. Please look for its change in your editing '
                   'queue, or start again from the list.')

# The outcomes of an operation for each object, in the order of the
# comment that records them, and those whose objects the comment lists.
# An object is removed when it leaves the change after an operation has
# changed it: its author took it out, or a later operation took it back
# to the values of the object.
OUTCOMES = ('changed', 'unchanged', 'turned_off', 'reserved', 'invalid',
            'blocked', 'removed')
LISTED_OUTCOMES = ('reserved', 'invalid', 'blocked')
LISTED_OBJECTS = 50

# A revert has two outcomes more: an object changed since, or deleted.
# It also lists the objects whose field is turned off, which an Apply
# only counts: there the value that the change wrote stays, as the commit
# would not copy the old one, so the indexer must be able to find them.
REVERT_OUTCOMES = OUTCOMES + ('later', 'deleted')
REVERT_LISTED = LISTED_OUTCOMES + ('later', 'turned_off', 'deleted')

# The fields that make one logical field, a value and its flags, as the
# points of an edit join them (_imps_for of the revision class).  A
# revert puts them back together, or not at all.
LOGICAL_FIELDS = {
    IssueRevision: (
        ('volume', 'no_volume', 'volume_not_printed',
         'display_volume_with_number'),
        ('title', 'no_title'),
        ('indicia_publisher', 'indicia_pub_not_printed'),
        ('indicia_frequency', 'no_indicia_frequency'),
        ('indicia_printer', 'indicia_printer_not_printed'),
        ('brand_emblem', 'no_brand'),
        ('page_count', 'page_count_uncertain'),
        ('isbn', 'no_isbn'),
        ('barcode', 'no_barcode'),
        ('rating', 'no_rating'),
    ),
}

# Why a revert leaves out an old link that is deleted, is being deleted or
# belongs to another publisher, early, before the edit form checks it; the
# rules of the edit form, its years among them, check the other old links.
OLD_LINK_REFUSED = ('The old value is deleted or belongs to another '
                    'publisher.')

# Why a revert takes no further operation, for its objects.
NO_OPERATION_ON_REVERT = ('A revert only puts old values back, so it takes no '
                          'further operation. To write a different value, '
                          'discard this change and start a new bulk change '
                          'on these %s.')

# What would hold more objects than a bulk change can, as the refusal of
# _over_limit ends: a list, or a revert, and what to do instead.
IN_LIST = ('this list has %d. Please narrow the list first, for example '
           'with a filter.')
IN_REVERT = ('this revert would hold %d. To restore just one of them, edit '
             'it as usual.')

# Why a change of the older kind offers no way to put a field back.
OLDER_KIND = ('This older kind of bulk change cannot be reverted '
              'automatically.')
OLDER_DELETED = OLDER_KIND + ' All its issues have been deleted.'
OLDER_OVER = OLDER_KIND + (
  ' It holds %(count)d issues, and one bulk change can hold at most '
  '%(limit)d. To put a field back, start a bulk change from a list of at '
  'most %(limit)d of these issues, for example a search with a filter. '
  'Credits, brand emblems and indicia printers cannot be put back this '
  'way.')

# Why a bulk change cannot lose all its objects, and why work on it stopped.
LEFT_EMPTY = ('That would leave this bulk change without objects. To give '
              'it up, please discard it.')
CHANGE_BUSY = ('Another request was working on this change at the same '
               'moment, so nothing was changed. Please try again.')

# MySQL errors: a lock wait timeout undoes the statement only, or with
# innodb_rollback_on_timeout the whole transaction, a deadlock always the
# whole transaction.  A query with NOWAIT that finds a row held fails at
# once, with the third error.
LOCK_WAIT_TIMEOUT = 1205
DEADLOCK = 1213
NOWAIT_REFUSED = 3572

# The fields of a model that link it to the rows its new revisions point
# to, in the order in which a bulk change holds these rows, table by
# table.
HELD_PARENTS = {
    Issue: ('series', 'indicia_publisher', 'brand_emblem', 'indicia_printer'),
}

# The revision sets that an edit of issues or sequences by hand adds, as
# in an issue change, and that a bulk change never makes.
OTHER_REVISION_SETS = (
    'issuecreditrevisions', 'storycreditrevisions', 'storycharacterrevisions',
    'storygrouprevisions', 'coverrevisions', 'reprintrevisions',
    'publishercodenumberrevisions', 'externallinkrevisions',
    'characterorderrevisions')

# The time of a checkpoint in the comment of an operation, in UTC.
CHECKPOINT_FORMAT = '%Y-%m-%d %H:%M:%S'

# One operation of a bulk change: on the field name, the operation of
# OPERATIONS with the old value that replace_exact looks for and the new
# value, as stored.
Operation = namedtuple('Operation', 'name operation old new')


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


def can_start_bulk(user, count, held=IN_LIST):
    """
    Return why user may not start a bulk change of count objects, or None
    if they may: bulk changes are on, the user may reserve another
    change, has fewer active bulk changes than BULK_CHANGE_MAX_ACTIVE,
    and count is within bulk_limit; held says, as for _over_limit, what
    would hold them.
    """
    if not settings.BULK_CHANGE_ENABLED:
        return 'Bulk changes are turned off.'
    if not user.indexer.can_reserve_another():
        return ('You have reached your limit of open changes. Please submit'
                ' or discard one of them first.')
    active = Changeset.objects.filter(indexer=user,
                                      change_type=CTYPES['bulk'],
                                      state__in=states.ACTIVE).count()
    if active >= settings.BULK_CHANGE_MAX_ACTIVE:
        return ('You already have %d active bulk change%s, the most allowed.'
                ' Each must be approved or discarded before you start'
                ' another.' % (active, '' if active == 1 else 's'))
    return _over_limit(user, count, held)


def bulk_limit(user):
    """
    Return the most objects that a bulk change of user can hold:
    BULK_CHANGE_MAX, or BULK_CHANGE_MAX_NEW for a new indexer.
    """
    return settings.BULK_CHANGE_MAX_NEW if user.indexer.is_new \
        else settings.BULK_CHANGE_MAX


def _over_limit(user, count, held=IN_LIST):
    """
    Return why count objects are too many for user, or None if not; held
    says what would hold them, and what to do instead: IN_LIST or
    IN_REVERT.
    """
    limit = bulk_limit(user)
    if count > limit:
        return 'A bulk change can hold at most %d objects, and %s' % (
          limit, held % count)
    return None


def start_from_list(request, items):
    """
    Start a bulk change from the list items: keep the sorted ids of its
    objects, deleted ones left out, in the session, and go to the bulk
    change page.  An empty list, or one that can_start_bulk refuses,
    gives an error page.  Only the session is written.

    The address of the list is kept escaped, as get_full_path gives it,
    so that it stays one line of the record of the bulk change and a
    valid link.
    """
    ids = items.filter(deleted=False).order_by() \
               .values_list('id', flat=True).distinct()
    # One read gives the ids that are checked and kept.  One id
    # beyond the larger limit shows a list that is too long for
    # anyone; only its message needs its size.
    most = max(settings.BULK_CHANGE_MAX,
               settings.BULK_CHANGE_MAX_NEW)
    kept = sorted(ids[:most + 1])
    count = len(kept)
    if count > most:
        count = max(count, ids.count())
    if not count:
        return render_error(request, 'This list has no objects for a bulk '
                                     'change.', redirect=False)
    refusal = can_start_bulk(request.user, count)
    if refusal:
        return render_error(request, refusal, redirect=False)
    query = request.GET.copy()
    query.pop('_export')
    source = escape_uri_path(request.path)
    if query:
        source += '?' + query.urlencode()
    return _keep_selection(request, items.model, kept, source)


def _keep_selection(request, model, ids, source, change=None):
    """
    Keep the sorted ids of the objects of model in the session, with the
    address they came from and the older change, if any, and go to the
    bulk change page.
    """
    token = secrets.token_urlsafe(8)
    request.session[SELECTION_KEY] = {
        'token': token,
        'model': model._meta.model_name,
        'ids': sorted(ids),
        'source': source,
        'change': change,
    }
    return HttpResponseRedirect(
      urlresolvers.reverse('edit_issues_in_bulk') + '?token=' + token)


def older_selection(user, changeset):
    """
    Return the sorted ids of the issues of changeset, an approved change
    of the older kind, that are not deleted, and why user cannot start a
    bulk change on them, or None: none is left, or they are more than
    bulk_limit.
    """
    ids = sorted(set(changeset.issuerevisions.filter(issue__deleted=False)
                              .values_list('issue_id', flat=True)))
    if not ids:
        return ids, OLDER_DELETED
    limit = bulk_limit(user)
    if len(ids) > limit:
        return ids, OLDER_OVER % {'count': len(ids), 'limit': limit}
    return ids, None


def start_from_change(request, changeset):
    """
    Start a bulk change on the issues of changeset, an approved change of
    the older kind, which has no record to revert from: the indexer puts
    a field back with an operation of its own.  Issues deleted since are
    left out.  A refusal of older_selection, which the page of the change
    shows too, or of can_start_bulk gives an error page.  Only the session
    is written.
    """
    ids, refusal = older_selection(request.user, changeset)
    refusal = refusal or can_start_bulk(request.user, len(ids))
    if refusal:
        return render_error(request, refusal, redirect=False)
    return _keep_selection(
      request, Issue, ids,
      urlresolvers.reverse('compare', kwargs={'id': changeset.id}),
      changeset.id)


def selection_change(request):
    """
    Return the id of the older change that the kept selection came from,
    or None if it came from a list.
    """
    return request.session.get(SELECTION_KEY, {}).get('change')


def stored_selection(request, token):
    """
    Return the selection that start_from_list or start_from_change kept
    for token, as (model, ids, address it came from), or None if the
    session no longer holds it: it expired, or a newer selection took its
    place.
    """
    selection = request.session.get(SELECTION_KEY)
    if not selection or selection['token'] != token:
        return None
    models = {model._meta.model_name: model for model in BULK_TARGETS}
    return (models[selection['model']], selection['ids'],
            selection['source'])


def selection_applied(user, token):
    """
    Return whether user applied the selection of token, or is applying
    it: its page then asks to start again from the list.  The session is
    left alone, as another tab may have stored a newer selection.
    """
    return cache.get(APPLIED_KEY % (user.id, token)) is not None


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
    """
    Return the text that stands for a stored value in a form choice:
    'None' for None, else '=' and the value, so that no value, the empty
    text included, looks like no choice.
    """
    return 'None' if value is None else '=' + str(value)


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


def value_choices(field, values):
    """
    Return form choices for values, the (value, count) pairs of one
    field: the key of each value and a label with its count.  A text is
    in quotes, with the spaces that HTML would hide as no-break spaces; a
    link shows the name of its object.
    """
    names = _object_names(field, [value for value, count in values])
    choices = []
    for value, count in values:
        if value is None or value == '':
            label = '(empty)'
        elif isinstance(value, str):
            label = '"%s"' % HIDDEN_SPACES.sub(
              lambda match: NO_BREAK_SPACE * len(match.group()), value)
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
    return {'changed': len(changes), 'rows': _preview_rows(field, changes),
            'reserved': reserved, 'turned_off': turned_off,
            'deleted': deleted}


def _preview_rows(field, changes):
    """
    Return the rows of a preview for changes of field, given as (object,
    current value, new value): the first BULK_CHANGE_MAX, each as (object,
    old HTML, new HTML).
    """
    shown = changes[:settings.BULK_CHANGE_MAX]
    names = _object_names(field, [value for change in shown
                                  for value in change[1:]])
    return [(data_object,) + _shown_change(field, current, value, names)
            for data_object, current, value in shown]


def preview_of_change(revisions, name, operation, old, new):
    """
    Return what operation would do to the field name of revisions, the
    revisions of an open bulk change, writing nothing, as preview does
    for objects.  A revision needs no lock or check of its object, which
    the change holds; 'leaving' are the objects that the operation takes
    back to their own values, so that they leave the change, and
    'left_empty' says that none would remain.
    """
    rev_class = revisions.model
    field = rev_class._meta.get_field(name)
    candidates, turned_off = [], []
    for revision in revisions:
        current = getattr(revision, field.attname)
        value = new_value(current, operation, old, new)
        if value == current:
            continue
        if applicable(revision, name):
            candidates.append((revision, current, value))
        else:
            turned_off.append(revision.source)

    diff = exact_diff(rev_class, [candidate[0].id for candidate in candidates])
    leaving = [revision.source for revision, current, value in candidates
               if list(diff[revision.id]) == [name] and
               diff[revision.id][name][0] == value]
    changes = [(revision.source, current, value)
               for revision, current, value in candidates]
    return {'changed': len(changes), 'rows': _preview_rows(field, changes),
            'reserved': [], 'turned_off': turned_off, 'deleted': [],
            'leaving': leaving, 'left_empty': len(leaving) == len(revisions)}


class _LeftOut(Exception):
    """
    Ends the work on one object of a bulk change and undoes it: the
    outcome and a message for the comment of the operation.
    """

    def __init__(self, outcome, message=''):
        super().__init__(outcome)
        self.outcome = outcome
        self.message = message


def _no_single_head(rev_class, data_object):
    """
    Raise the outcome of an object that has not exactly one latest
    approved revision: it is reserved if a change holds a revision of it,
    else invalid.
    """
    if rev_class.objects.active_set().filter(
         **{rev_class.source_name: data_object}).exists():
        raise _LeftOut('reserved')
    raise _LeftOut('invalid', 'It has no single approved revision.')


def _clone(rev_class, data_object, changeset):
    """
    Return a new revision of data_object in changeset, or raise the
    outcome of _no_single_head.
    """
    try:
        return rev_class.clone(data_object, changeset)
    except (ObjectDoesNotExist, MultipleObjectsReturned):
        _no_single_head(rev_class, data_object)


def _values(revision, fields):
    """Return the values of fields on revision, in order."""
    return [getattr(revision, field.attname) for field in fields]


def _checked_values(revision, changes, user, dependents=True):
    """
    Check revision with the rules of its edit form for user, with changes,
    a list of (field, value, current), and return the values that the
    form cleans for those fields, in order; dependents goes to
    revision_form_messages.  The changes are left out, by _LeftOut, if
    the check gives a message, as invalid if it passes without the
    changes and as blocked if it fails already, or if the form would also
    change another field, which the preview did not show.

    The edit form takes its choices from the revision as it was before
    the changes were set, as on its edit page, where only the values
    that the revision holds are offered beyond the rules of the choices.
    """
    attnames = {field.attname for field, value, current in changes}
    others = [other for other in type(revision)._meta.concrete_fields
              if other.attname not in attnames]
    stored = _values(revision, others)
    original = copy.copy(revision)
    for field, value, current in changes:
        setattr(revision, field.attname, value)
    messages = revision_form_messages(revision, user, dependents,
                                      original=original)
    cleaned = [getattr(revision, field.attname)
               for field, value, current in changes]
    after = _values(revision, others)
    if messages or after != stored:
        # The check of the object as it is tells apart what the change
        # does from what the object holds already.
        for other, old in zip(others, stored):
            setattr(revision, other.attname, old)
        for field, value, current in changes:
            setattr(revision, field.attname, current)
        before = revision_form_messages(revision, user, dependents)
        if messages:
            if before:
                raise _LeftOut('blocked', before[0])
            raise _LeftOut('invalid', messages[0])
        follows = [field_name(other.name) for other, old, new
                   in zip(others, _values(revision, others), after)
                   if old != new]
        if follows:
            raise _LeftOut('invalid', 'Its edit form would also change %s.'
                                      % ', '.join(follows))
    return cleaned


def _checked_value(revision, field, value, current, user):
    """
    Check revision with value in field instead of current, as
    _checked_values does, and return the value that the form cleans.
    """
    return _checked_values(revision, [(field, value, current)], user)[0]


def _store(revision, field, value, current, user):
    """
    Check revision, with value in field instead of current, with the
    rules of its edit form for user, and save value in field.  The object
    is left out if the form would store anything else.
    """
    cleaned = _checked_value(revision, field, value, current, user)
    if cleaned != value:
        raise _LeftOut('invalid', 'Its edit form stores "%s" instead.'
                                  % cleaned)
    setattr(revision, field.attname, value)
    revision.save(update_fields=[field.attname, 'modified'])


def _locked(data_object):
    """
    Return whether a change holds the lock of data_object.  A lock that
    an approval is freeing counts until the approval ends: the approval
    then waits for the bulk change, which holds the parent, so a wait for
    that lock would be a deadlock.
    """
    return RevisionLock.objects.filter(
      content_type=ContentType.objects.get_for_model(data_object),
      object_id=data_object.id).exists()


def _share_rows(table, ids, suffix=''):
    """
    Hold the rows of table with these ids with a shared lock, by primary
    key and in id order, until the transaction ends; suffix goes at the
    end of the query.
    """
    sql = 'SELECT id FROM %s WHERE id IN (%s) ORDER BY id FOR SHARE%s' % (
      table, ', '.join(['%s'] * len(ids)), suffix)
    with connection.cursor() as cursor:
        cursor.execute(sql, sorted(ids))


def _hold_rows(data_object):
    """
    Hold the row of data_object and, for a variant, the row of its base
    with a shared lock, which its new revision needs anyway; if a
    transaction is writing one of them the query fails at once.  An
    approval writes an issue before its series, and the series waits for
    this bulk change, so a wait for that row would be a deadlock.
    """
    ids = {data_object.id}
    base = getattr(data_object, 'variant_of_id', None)
    if base:
        ids.add(base)
    _share_rows(type(data_object)._meta.db_table, ids, ' NOWAIT')


def process_item(changeset, data_object, operation, user):
    """
    Change one object for a bulk change, in changeset, and return its
    outcome and a message, as (outcome, message).

    An object that another change holds is left out as reserved without
    a wait, and so is one whose row, or the row of whose base, another
    transaction is writing.  Else in a savepoint the object is locked,
    read again, changed only if the operation still changes it and its
    field is on, and its new revision is checked with the rules of its
    edit form for user.  The revision keeps the values of the object, but
    for the field, which gets the value of the operation, as the preview
    showed it; an object for which the form would store anything else is
    left out, and all its work is undone.  The lock of an object that a
    reservation in flight is taking waits for its end; a wait beyond the
    server's limit stops the whole Apply.
    """
    model = type(data_object)
    field = model._meta.get_field(operation.name)
    attname = field.attname
    parent = TURNED_OFF_BY.get(model, (None,))[0]
    if _locked(data_object):
        return 'reserved', ''
    try:
        with transaction.atomic():
            if _get_revision_lock(data_object, changeset) is None:
                raise _LeftOut('reserved')
            objects = model.objects.filter(id=data_object.id, deleted=False)
            if parent:
                objects = objects.select_related(parent)
            fresh = objects.first()
            if fresh is None:
                raise _LeftOut('invalid', 'It was deleted.')
            current = getattr(fresh, attname)
            value = new_value(current, operation.operation, operation.old,
                              operation.new)
            if value == current:
                raise _LeftOut('unchanged')
            if not applicable(fresh, operation.name):
                raise _LeftOut('turned_off')

            _hold_rows(fresh)
            revision = _clone(BULK_TARGETS[model], fresh, changeset)
            _store(revision, field, value, current, user)
    except _LeftOut as left_out:
        return left_out.outcome, left_out.message
    except OperationalError as error:
        # Another transaction is writing a row that the new revision needs.
        if error.args[0] != NOWAIT_REFUSED:
            raise
        return 'reserved', ''
    return 'changed', ''


def _apply_to_objects(changeset, model, ids, operation, user):
    """
    Apply operation to the objects of model with these ids, in id order,
    in changeset.  Return the count of each outcome and, for the outcomes
    of LISTED_OUTCOMES, the objects with their messages.  An object
    whose value the operation leaves as it is, or whose field is off, is
    not locked.
    """
    counts = dict.fromkeys(OUTCOMES, 0)
    listed = {outcome: [] for outcome in LISTED_OUTCOMES}
    attname = model._meta.get_field(operation.name).attname
    parent = TURNED_OFF_BY.get(model, (None,))[0]
    for chunk in _chunks(sorted(ids)):
        objects = model.objects.filter(id__in=chunk).order_by('id')
        if parent:
            objects = objects.select_related(parent)
        found = 0
        for data_object in objects:
            found += 1
            current = getattr(data_object, attname)
            if new_value(current, operation.operation, operation.old,
                         operation.new) == current:
                outcome, message = 'unchanged', ''
            elif not applicable(data_object, operation.name):
                outcome, message = 'turned_off', ''
            else:
                outcome, message = process_item(changeset, data_object,
                                                operation, user)
            counts[outcome] += 1
            if outcome in listed:
                listed[outcome].append((data_object, message))
        # Objects are deleted by a flag; a missing row is invalid.
        counts['invalid'] += len(chunk) - found
    return counts, listed


def _counts_text(counts):
    """Return the counts of the outcomes, as the comment shows them."""
    return ', '.join('%s %d' % (outcome.replace('_', ' '), count)
                     for outcome, count in counts.items())


def _checked_text(checked, total, counts):
    """Return the line of a record with the objects checked and counted."""
    return 'Checked %d of %d: %s' % (checked, total, _counts_text(counts))


def _nothing_changed(consequence, counts, listed):
    """
    Return the error message of an operation that changed no object: the
    counts and, so that the author learns why, each different reason for
    leaving an object out, at most LISTED_OBJECTS, with the first object
    it applies to.
    """
    reasons = {}
    for objects in listed.values():
        for data_object, message in objects:
            if message:
                reasons.setdefault(message, data_object)
    lines = ['Nothing was changed, so %s: %s.' % (consequence,
                                                  _counts_text(counts))]
    lines += ['%s: %s' % (data_object, message) for message, data_object
              in list(reasons.items())[:LISTED_OBJECTS]]
    return ' '.join(lines)


def _label(outcome):
    """
    Return the label of the lines of a record that list objects of
    outcome: its words, as the counts write them, capitalized.
    """
    return outcome.replace('_', ' ').capitalize()


def _outcome(label):
    """Return the outcome of the lines of a record with label."""
    return label.lower().replace(' ', '_')


def operation_text(model, operation, source, total, counts, listed,
                   checkpoint):
    """
    Return the comment that records an operation of a bulk change on
    total objects of model, or on total values for a revert: a first line
    for machines, with the values in JSON, for a revert the change that it
    reverts, the list it came from, the counts of the outcomes, the time
    after which a revision must be checked again, and a line for each
    object left out, at most LISTED_OBJECTS for each outcome.
    """
    values = [operation.new]
    if operation.operation == 'replace_exact':
        values.insert(0, operation.old)
    lines = [
      'Operation: %s.%s %s %s' % (
        model._meta.model_name, operation.name, operation.operation,
        ' '.join(json.dumps(value, default=str, ensure_ascii=False)
                 for value in values)),
      'Source: %s%s' % (settings.SITE_URL.rstrip('/'), source),
      _checked_text(sum(counts.values()), total, counts),
      'Checkpoint: %s' % checkpoint.astimezone(dt_timezone.utc)
                                   .strftime(CHECKPOINT_FORMAT),
    ]
    if operation.operation == 'restore':
        lines.insert(1, 'Reverts change %d' % operation.new)
    for outcome, objects in listed.items():
        label = _label(outcome)
        for data_object, message in objects[:LISTED_OBJECTS]:
            lines.append(('%s: %s%s %s' % (
              label, settings.SITE_URL.rstrip('/'),
              data_object.get_absolute_url(), message)).rstrip())
        more = len(objects) - LISTED_OBJECTS
        if more > 0:
            lines.append('%s: and %d more' % (label, more))
    return '\n'.join(lines)


OPERATION_LINE = re.compile(r'Operation: (\w+)\.([\w,]+) (\w+) (.*)$')
CHECKED_LINE = re.compile(r'Checked (\d+) of (\d+): (.*)$')
LISTED_LABELS = '|'.join(_label(outcome) for outcome in REVERT_LISTED)
LISTED_LINE = re.compile(r'(%s): \S*?(\d+)/(?: |$)' % LISTED_LABELS)
MORE_LINE = re.compile(r'(%s): and \d+ more$' % LISTED_LABELS)


def parse_operation(text):
    """
    Read a comment that operation_text wrote, and return a dict with the
    model name, field name, operation and values of its first line, the
    source, the number checked, the total, the counts, the checkpoint,
    the ids listed for each outcome and, as 'more', the outcomes with more
    objects than it lists.  Return None for any other text, even one that
    only starts like such a comment.
    """
    try:
        return _parsed_operation(text)
    except (ValueError, RecursionError):
        return None


def _record_comments(changeset):
    """
    Return the comments of changeset that record its operations, oldest
    first.  Each goes from unreserved to open, as the first comment of a
    reservation does: a comment that anybody adds keeps the state of the
    change, so it never counts, whatever it says.
    """
    return changeset.comments.filter(old_state=states.UNRESERVED,
                                     new_state=states.OPEN).order_by('id')


def operation_records(changeset):
    """
    Return the records of the operations of the bulk change changeset, in
    their order, each as parse_operation gives it.
    """
    records = [parse_operation(comment.text)
               for comment in _record_comments(changeset)]
    return [record for record in records if record is not None]


def operation_record(changeset):
    """
    Return the record of the first operation of the bulk change
    changeset, which made its revisions; None if there is no such record.
    """
    comment = _record_comments(changeset).first()
    return parse_operation(comment.text) if comment else None


def _parsed_operation(text):
    """
    Return the record of parse_operation, or None if the first line is
    not that of an operation; a value that does not parse raises
    ValueError.
    """
    lines = text.split('\n')
    match = OPERATION_LINE.match(lines[0])
    if match is None:
        return None
    record = dict(zip(('model', 'name', 'operation'), match.groups()))
    decoder = json.JSONDecoder()
    values, rest = [], match.group(4)
    while rest:
        value, end = decoder.raw_decode(rest)
        values.append(value)
        rest = rest[end:].lstrip(' ')
    record['values'] = values
    record['listed'] = {outcome: [] for outcome in LISTED_OUTCOMES}
    record['more'] = []
    for line in lines[1:]:
        label, _, value = line.partition(': ')
        checked = CHECKED_LINE.match(line)
        listed = LISTED_LINE.match(line)
        more = MORE_LINE.match(line)
        if label == 'Source':
            record['source'] = value
        elif label == 'Checkpoint':
            record['checkpoint'] = datetime.strptime(
              value, CHECKPOINT_FORMAT).replace(tzinfo=dt_timezone.utc)
        elif checked:
            record['checked'] = int(checked.group(1))
            record['total'] = int(checked.group(2))
            record['counts'] = {
              outcome.replace(' ', '_'): int(count)
              for outcome, count in re.findall(r'([a-z ]+?) (\d+)(?:, |$)',
                                               checked.group(3))}
        elif listed:
            record['listed'].setdefault(_outcome(listed.group(1)),
                                        []).append(int(listed.group(2)))
        elif more:
            record['more'].append(_outcome(more.group(1)))
    return record


@contextmanager
def _deadlock_refused():
    """
    Turn a lock conflict in the block, a deadlock or a wait beyond the
    server's limit, into ErrorWithMessage.  The refusal undoes the whole
    transaction, so that nothing is left half done.
    """
    try:
        yield
    except OperationalError as error:
        if error.args[0] not in (DEADLOCK, LOCK_WAIT_TIMEOUT):
            raise
        raise ErrorWithMessage('Another change was using some of the same '
                               'records at the same moment, so nothing was '
                               'changed. Please apply again.')


def _hold_parents(model, ids, operation):
    """
    Hold the rows that the new revisions of the objects of model with
    these ids will point to, and the new value of operation if it is a
    link, as _hold_links does.
    """
    _hold_links(model, ids, {operation.name: [operation.new]})


def _hold_links(model, ids, new_values):
    """
    Hold with a shared lock the rows that the new revisions of the objects
    of model with these ids will point to: the links that they hold now
    and new_values, {field name: values}, whose empty values are no links,
    table by table in the order of HELD_PARENTS.  Each row that another
    transaction writes is waited for, each wait with its own limit of the
    server, and the waits add up.  Afterwards an object whose row another
    transaction writes is left out at once.  A wait beyond that limit
    raises ErrorWithMessage.
    """
    try:
        for name in HELD_PARENTS.get(model, ()):
            parents = set(model.objects.filter(id__in=ids)
                               .values_list(name, flat=True))
            parents.discard(None)
            parents.update(value for value in new_values.get(name, ())
                           if value)
            if parents:
                _share_rows(model._meta.get_field(name)
                            .related_model._meta.db_table, parents)
    except OperationalError as error:
        if error.args[0] != LOCK_WAIT_TIMEOUT:
            raise
        raise ErrorWithMessage('The series of these objects are being saved '
                               'at this moment, so nothing was changed. '
                               'Please apply again.')


def _take_turn(user):
    """
    Lock the indexer row of user, so that two requests of one user that
    make a bulk change take turns; a wait beyond the server's limit raises
    ErrorWithMessage.
    """
    try:
        Indexer.objects.select_for_update().get(user=user)
    except OperationalError as error:
        if error.args[0] != LOCK_WAIT_TIMEOUT:
            raise
        raise ErrorWithMessage('Another request of yours is applying a bulk'
                               ' change. Please wait until it ends, then'
                               ' look in your editing queue.')


def _make_change(user, model, ids, source, operation):
    """
    Create the bulk change of apply, apply operation and record it in a
    comment; raise ErrorWithMessage if no object changed.
    """
    changeset = Changeset.objects.create(indexer=user, state=states.OPEN,
                                         change_type=CTYPES['bulk'])
    counts, listed = _apply_to_objects(changeset, model, ids, operation, user)
    if not counts['changed']:
        raise ErrorWithMessage(_nothing_changed('no change was made', counts,
                                                listed))
    _write_record(changeset, user, model, operation, source, len(ids),
                  counts, listed)
    return changeset


def _write_record(changeset, user, model, operation, source, total, counts,
                  listed):
    """
    Add to changeset the comment that records operation on total objects
    of model, or values for a revert, with the time after which a
    revision needs a new check.
    """
    changeset.comments.create(
      commenter=user, old_state=states.UNRESERVED, new_state=states.OPEN,
      text=operation_text(model, operation, source, total, counts, listed,
                          timezone.now()))


@transaction.atomic
def apply(user, token, model, ids, source, operation):
    """
    Make one bulk change of user: apply operation to the objects of model
    with these ids, which the list at source gave under token, and return
    the changeset, OPEN, with the comment that records the operation.

    The rows that the new revisions will point to are held first, then
    the indexer row is locked, so that two requests of one user take
    turns.  An Apply may wait on each of these rows and on each object
    that a reservation in flight is taking; each wait has its own limit
    of the server, and their sum has no limit.  A refusal of
    can_start_bulk, a token already applied, a wait beyond the server's
    limit, a deadlock or no changed object raise ErrorWithMessage.  On
    any error nothing is written, and the selection may be applied again.
    """
    with _deadlock_refused():
        _hold_parents(model, ids, operation)
        _take_turn(user)
        refusal = can_start_bulk(user, len(ids))
        if refusal:
            raise ErrorWithMessage(refusal)
        key = APPLIED_KEY % (user.id, token)
        if not cache.add(key, True, APPLIED_SECONDS):
            raise ErrorWithMessage(APPLIED_ALREADY)
        try:
            return _make_change(user, model, ids, source, operation)
        except BaseException:
            cache.delete(key)
            raise


def other_revisions(changeset):
    """
    Return the names of the sets of OTHER_REVISION_SETS that hold
    revisions in changeset.
    """
    return [name for name in OTHER_REVISION_SETS
            if getattr(changeset, name).exists()]


def _turned_off(changeset):
    """
    Return a pair (revision, message) for each object of the bulk change
    changeset and each field of its operations that a flag of its parent
    has turned off since the operation.  At approval such a value would
    not be written, or would stay hidden in the edit form.  Only an object
    whose revision changed the field counts.
    """
    revisions = changeset.bulk_target()[1]
    if revisions is None:
        return []
    rev_class = revisions.model
    parent = TURNED_OFF_BY.get(rev_class.source_class, (None,))[0]
    if parent is None:
        return []
    names = sorted({name for record in operation_records(changeset)
                    for name in record_fields(record)})
    revisions = list(revisions.select_related(
      '%s__%s' % (rev_class.source_name, parent)))
    diff = exact_diff(rev_class, [revision.id for revision in revisions])
    return [(revision, '%s: %s is turned off in its %s.' % (
               bulk_object_name(revision), field_name(name), parent))
            for revision in revisions
            for name in names
            if name in diff[revision.id]
            and not applicable(revision.source, name)]


def turned_off_messages(changeset):
    """
    Return the messages of _turned_off(changeset): one for each object of
    the bulk change changeset and each field of its operations that a
    flag of its parent has turned off since the operation.
    """
    return [message for revision, message in _turned_off(changeset)]


def approval_refusal(changeset):
    """
    Return why the bulk change changeset cannot be approved, or None if it
    can.  The parents of its objects are locked first, in id order and
    until the approval ends: a flag read here then stays as it is until
    the values are written, and an approval in the series of an Apply
    waits for the Apply before it writes anything.
    """
    target, revisions = changeset.bulk_target()
    if target is None:
        return None
    rev_class = revisions.model
    parent = TURNED_OFF_BY.get(rev_class.source_class, (None,))[0]
    if parent:
        parents = rev_class.source_class._meta.get_field(parent).related_model
        ids = set(revisions.values_list('%s__%s' % (rev_class.source_name,
                                                    parent), flat=True))
        list(parents.objects.select_for_update().filter(id__in=ids)
             .order_by('id').values_list('id', flat=True))
    messages = turned_off_messages(changeset)
    if not messages:
        return None
    return 'This bulk change cannot be approved. %s Please send it back to ' \
           'its author, so that they can take these objects out.' % \
           ' '.join(messages)


def _submit_problems(changeset, forms=True):
    """
    Return why the bulk change changeset cannot be submitted, as a list of
    pairs (revision, message), empty if it can; the revision is None for
    a message on the change as a whole.  Its revisions passed the rules
    of their edit forms when its operations made them; only those changed
    since the checkpoint of its latest operation record, with a second of
    margin, are checked again, and all of them if there is no checkpoint
    or if the change is a revert, whose old values face the rules of
    today.  Each operation starts with this check, so that its checkpoint
    hides no revision that was not checked.  The change must also hold no
    revision of a kind that bulk changes do not use, and no value in a
    field that is turned off now, whenever that happened.  forms False
    leaves out the edit forms and keeps the checks that need none.
    """
    problems = [(None, 'It holds revisions that a bulk change does not '
                       'make: %s.' % name)
                for name in other_revisions(changeset)]
    problems += _turned_off(changeset)
    if not forms:
        return problems
    records = operation_records(changeset)
    record = records[-1] if records else None
    if records and records[0]['operation'] == 'restore':
        record = None
    for name in BULK_REVISION_ORDER:
        revisions = getattr(changeset, name).all()
        if record and 'checkpoint' in record:
            revisions = revisions.filter(
              modified__gte=record['checkpoint'] - timedelta(seconds=1))
        for revision in revisions:
            for message in revision_form_messages(revision,
                                                  changeset.indexer):
                problems.append((revision, '%s: %s' % (
                  bulk_object_name(revision), message)))
    return problems


def submit_messages(changeset):
    """
    Return why the bulk change changeset cannot be submitted, as a list of
    messages, empty if it can: those of _submit_problems, edit forms
    included.
    """
    return [message for revision, message in _submit_problems(changeset)]


def change_refusal(user, changeset):
    """
    Return why user may not work on the bulk change changeset, by a
    further operation or by taking objects out of it, or None if they
    may: bulk changes are on, it is theirs, it is open, and it holds
    objects.
    """
    if not settings.BULK_CHANGE_ENABLED:
        return 'Bulk changes are turned off.'
    if changeset.change_type != CTYPES['bulk'] or \
       changeset.indexer != user:
        return 'Only the author of a bulk change may work on it.'
    if changeset.state != states.OPEN:
        return 'Only an open bulk change can be changed.'
    if changeset.bulk_target()[0] is None:
        return 'This bulk change holds no objects.'
    return None


@contextmanager
def _work_on_change(user, changeset):
    """
    Run the block in a transaction, with changeset read again and its row
    locked, so that requests on it take turns, and with its revisions.
    Raise ErrorWithMessage, with nothing written, if user may not work on
    it, or after a deadlock or a long wait for a row.

    The work counts as activity, for the sweep of old reservations, and
    the points of the change follow it, as a change sent back can reach
    its approval through Discuss, without another submission.
    """
    try:
        with transaction.atomic():
            changeset = Changeset.objects.select_for_update() \
                                 .get(id=changeset.id)
            refusal = change_refusal(user, changeset)
            if refusal:
                raise ErrorWithMessage(refusal)
            yield changeset, changeset.bulk_target()[1]
            changeset.calculate_imps()
            changeset.save(update_fields=['imps', 'modified'])
    except OperationalError as error:
        if error.args[0] not in (DEADLOCK, LOCK_WAIT_TIMEOUT):
            raise
        raise ErrorWithMessage(CHANGE_BUSY)


def _change_revision(revision, field, operation, user):
    """
    Apply operation to revision, of a bulk change that this request holds,
    and return the outcome and a message, as process_item does.  The
    object is locked by this change already, so nothing is locked here.
    """
    current = getattr(revision, field.attname)
    value = new_value(current, operation.operation, operation.old,
                      operation.new)
    if value == current:
        return 'unchanged', ''
    if not applicable(revision, operation.name):
        return 'turned_off', ''
    try:
        _store(revision, field, value, current, user)
    except _LeftOut as left_out:
        return left_out.outcome, left_out.message
    return 'changed', ''


def _drop(revisions):
    """Delete revisions of a bulk change and free the lock of each object."""
    for revision in revisions:
        source = revision.source
        revision.delete()
        _free_revision_lock(source)


def _record_weights(changeset, revisions):
    """
    Return {revision id: how many the record of the first operation of
    changeset counts for it}: one for each revision or, for a revert,
    which counts values, its logical fields among those of the record.
    """
    record = operation_record(changeset)
    if record is None or record['operation'] != 'restore' or not revisions:
        return {revision.id: 1 for revision in revisions}
    rev_class = type(revisions[0])
    names = set(record_fields(record))
    diff = exact_diff(rev_class, [revision.id for revision in revisions])
    return {revision.id: len(_units(rev_class, names, diff[revision.id]))
            for revision in revisions}


def _count_removed(changeset, removed):
    """
    Move removed, a number of objects or, for a revert, of values, from
    changed to removed in the record of the first operation of changeset,
    which made all its revisions; the record then counts what remains.
    """
    comment = _record_comments(changeset).first()
    record = parse_operation(comment.text) if comment else None
    if record is None:
        raise ErrorWithMessage('This bulk change has no record of its '
                               'operations.')
    counts = record['counts']
    counts['changed'] -= removed
    counts['removed'] += removed
    comment.text = '\n'.join(
      _checked_text(record['checked'], record['total'], counts)
      if CHECKED_LINE.match(line) else line
      for line in comment.text.split('\n'))
    comment.save(update_fields=['text'])


# Why a bulk change takes no further operation while the check of a
# submission fails: the messages, then the way out, which is to take out
# the objects they name or, if they name all of them, to discard it.
FURTHER_REFUSED = 'This bulk change cannot take another operation. %s %s'
REMOVE_OR_DISCARD = ('Please remove these %s from this change, or discard '
                     'it.')
ONLY_DISCARD = 'Please discard this change: it holds no other %s.'


def operation_refusal(changeset, forms=True):
    """
    Return why the bulk change changeset takes no further operation now,
    or None if it does.  A revert never does, as it promises only that
    old values go back.  Any other change starts an operation with the
    check of a submission, so that its checkpoint hides no revision that
    was not checked; while that check fails, as when a flag of a parent
    has turned off a field that the change holds, the way out is to
    remove the objects it names or, if it names every object of the
    change, to discard it.  forms False leaves out the edit forms, as in
    _submit_problems; a revert is refused either way.
    """
    record = operation_record(changeset)
    if record is not None and record['operation'] == 'restore':
        return NO_OPERATION_ON_REVERT % BULK_OBJECT_NAMES[
          changeset.bulk_target()[0]][1]
    problems = _submit_problems(changeset, forms)
    if not problems:
        return None
    name, revisions = changeset.bulk_target()
    singular, plural = BULK_OBJECT_NAMES[name]
    # Only the objects of the change count, not the anchors beside them.
    named = {revision.id for revision, message in problems
             if isinstance(revision, revisions.model)}
    if named and len(named) == revisions.count():
        way_out = ONLY_DISCARD % singular
    else:
        way_out = REMOVE_OR_DISCARD % plural
    return FURTHER_REFUSED % (
      ' '.join(message for revision, message in problems), way_out)


def add_operation(user, changeset, operation):
    """
    Apply operation to the revisions of the open bulk change changeset of
    user, and record it in a comment of its own.

    A revision that the operation takes back to the values of its object
    no longer changes anything, so it leaves the change and its object is
    free again.  Raise ErrorWithMessage, with nothing written, if the
    change is a revert, if a revision no longer passes its checks, if no
    revision changes, or if none would remain.
    """
    with _work_on_change(user, changeset) as (changeset, revisions):
        _apply_to_revisions(changeset, revisions, operation, user)


def _apply_to_revisions(changeset, revisions, operation, user):
    """Do the work of add_operation, in its transaction."""
    refusal = operation_refusal(changeset)
    if refusal:
        raise ErrorWithMessage(refusal)
    rev_class = revisions.model
    field = rev_class._meta.get_field(operation.name)
    revisions = list(revisions)
    counts = dict.fromkeys(OUTCOMES, 0)
    listed = {outcome: [] for outcome in LISTED_OUTCOMES}
    changed = []
    for revision in revisions:
        outcome, message = _change_revision(revision, field, operation, user)
        counts[outcome] += 1
        if outcome in listed:
            listed[outcome].append((revision.source, message))
        if outcome == 'changed':
            changed.append(revision)
    if not changed:
        raise ErrorWithMessage(_nothing_changed('no operation was added',
                                                counts, listed))

    diff = exact_diff(rev_class, [revision.id for revision in changed])
    back = [revision for revision in changed if not diff[revision.id]]
    if len(back) == len(revisions):
        raise ErrorWithMessage(LEFT_EMPTY)
    # Comments never attach to the revisions of a bulk change, as their
    # edit pages refuse them, so deleting a revision loses no comment.
    _drop(back)
    counts['changed'] -= len(back)
    counts['removed'] = len(back)
    _write_record(changeset, user, rev_class.source_class, operation,
                  urlresolvers.reverse('compare',
                                       kwargs={'id': changeset.id}),
                  len(revisions), counts, listed)
    if back:
        _count_removed(changeset, len(back))


def remove_objects(user, changeset, revision_ids):
    """
    Take the revisions with these ids out of the open bulk change
    changeset of user, free their objects and count them, or their values
    for a revert, in its record.  Ids of other revisions are ignored.  A
    bulk change keeps at least one object: raise ErrorWithMessage if it
    would lose them all, or if no id is one of its revisions.
    """
    with _work_on_change(user, changeset) as (changeset, revisions):
        chosen = list(revisions.filter(id__in=revision_ids))
        if not chosen:
            raise ErrorWithMessage('Please select the objects to remove.')
        if len(chosen) == revisions.count():
            raise ErrorWithMessage(LEFT_EMPTY)
        removed = sum(_record_weights(changeset, chosen).values())
        _drop(chosen)
        _count_removed(changeset, removed)


# One logical field that a bulk change changed on one object: those of its
# fields that the operations name, the values before the change and the
# values that the change wrote.
_Unit = namedtuple('_Unit', 'fields before wrote')

# What a revert does with a unit: the outcome, its message and, if the
# unit goes back, the values as the edit form cleans them and whether
# that lost spaces at the start or end of a text.
_Restored = namedtuple('_Restored', 'unit outcome message values spaces')

# What the page of a revert says of what it leaves out, in its order; a
# value of a logical field changed later has a table of its own there.
REVERT_SUMMARIES = (
    ('invalid', 'Refused by the edit form today, so left out'),
    ('blocked', 'Already failing the edit form, so left out'),
    ('later', 'Changed later, so left out'),
    ('reserved', 'Reserved by other changes, so left out'),
    ('turned_off', 'Field turned off in their series, so left out'),
    ('deleted', 'Deleted since that change, so left out'),
    ('unchanged', 'Already back to the old value'),
)

# What the page of a revert says of what it left out, as (outcome, one,
# several), in its order.
REVERT_LEFT_OUT = (
    ('later', 'changed later', 'changed later'),
    ('reserved', 'reserved', 'reserved'),
    ('invalid', 'refused', 'refused'),
    ('blocked', 'already failing', 'already failing'),
    ('turned_off', 'field off', 'fields off'),
    ('deleted', 'deleted', 'deleted'),
    ('removed', 'removed by the author', 'removed by the author'),
)


def record_fields(record):
    """Return the names of the fields of the operation of record."""
    return record['name'].split(',')


def _units(rev_class, names, changes):
    """
    Return as _Unit tuples the logical fields, among the fields names, of
    a revision of rev_class whose entry in exact_diff is changes.
    """
    groups = list(LOGICAL_FIELDS.get(rev_class, ()))
    grouped = {name for group in groups for name in group}
    groups += [(name,) for name in sorted(names - grouped)]
    units = []
    for group in groups:
        changed = [name for name in group
                   if name in names and name in changes]
        if changed:
            units.append(_Unit(
              [rev_class._meta.get_field(name) for name in changed],
              [changes[name][0] for name in changed],
              [changes[name][1] for name in changed]))
    return units


def _revert_items(changeset):
    """
    Return what the approved bulk change changeset wrote: the model of its
    objects, the names of the fields of its operations, and for each
    object with a unit, in the order of its page, the pair of its id and
    its units.
    """
    names = set()
    for record in operation_records(changeset):
        names.update(record_fields(record))
    revisions = changeset.bulk_target()[1]
    rev_class = revisions.model
    source = rev_class._meta.get_field(rev_class.source_name).attname
    pairs = list(revisions.values_list('id', source))
    diff = exact_diff(rev_class, [pair[0] for pair in pairs])
    items = []
    for revision_id, object_id in pairs:
        units = _units(rev_class, names, diff[revision_id])
        if units:
            items.append((object_id, units))
    return rev_class.source_class, names, items


def _old_values(items):
    """
    Return the values that the units of items, as _revert_items gives them,
    put back, as {field name: set of values}.
    """
    values = defaultdict(set)
    for object_id, units in items:
        for unit in units:
            for field, value in zip(unit.fields, unit.before):
                values[field.name].add(value)
    return values


def _left(unit, outcome, message=''):
    """Return the _Restored tuple of a unit that stays as it is."""
    return _Restored(unit, outcome, message, None, False)


def _old_link_allowed(data_object, value):
    """
    Return whether value, an old link of data_object, is an indicia
    publisher of the publisher of its series that is neither deleted nor
    being deleted.  One that is not is refused early, before the object
    is locked; the rules of the edit form, its years among them, check
    the others when their unit is checked, after the units without a
    link.  It knows only the indicia publisher, the one link of
    FIELD_POLICY; a new link there needs its own check here.
    """
    return data_object.series.publisher \
                      .active_indicia_publishers_no_pending() \
                      .filter(id=value).exists()


def _without_spaces(values):
    """Return values, each text without spaces at its start or end."""
    return [value.strip() if isinstance(value, str) else value
            for value in values]


def _split_units(data_object, units):
    """
    Split units as the present values of data_object say: return those
    that stay as they are, as _Restored tuples, and those that can go
    back, which still hold what the change wrote.  A value already back
    is unchanged also without the spaces that a revert does not restore.
    An old link, which can only be an indicia publisher, is invalid if
    _old_link_allowed refuses it; an empty one goes back.  The rules of
    the edit form check the other old links later, with the other units.
    """
    left, pending = [], []
    for unit in units:
        now = _values(data_object, unit.fields)
        if now == unit.before or now == _without_spaces(unit.before):
            left.append(_left(unit, 'unchanged'))
        elif now != unit.wrote:
            left.append(_left(unit, 'later'))
        elif not all(applicable(data_object, field.name)
                     for field in unit.fields):
            left.append(_left(unit, 'turned_off'))
        elif not all(value is None or not field.is_relation or
                     _old_link_allowed(data_object, value)
                     for field, value in zip(unit.fields, unit.before)):
            left.append(_left(unit, 'invalid', OLD_LINK_REFUSED))
        else:
            pending.append(unit)
    return left, pending


def _only_spaces_lost(unit, cleaned):
    """
    Return whether cleaned, the old values of unit as the edit form cleans
    them, lost spaces at the start or end of a text; if the form would
    store anything else, unit is left out.
    """
    spaces = False
    for old, value in zip(unit.before, cleaned):
        if old != value:
            if not isinstance(old, str) or old.strip() != value:
                raise _LeftOut('invalid', 'Its edit form stores "%s" instead.'
                                          % value)
            spaces = True
    return spaces


def _restored(revision, units, user, dependents=True):
    """
    Put each of units back on revision, in memory and in turn, with the
    rules of its edit form for user, and return their _Restored tuples in
    the order of units.  The units without a link go back first, so that
    a link meets the values that the object keeps, as its choices depend
    on them.  A unit that a rule refuses stays as it is, not the whole
    object; one whose old value the form cleans into the present value is
    unchanged.  The revert Apply and its preview both go through it.
    """
    results = [None] * len(units)
    order = sorted(range(len(units)),
                   key=lambda index: any(field.is_relation
                                         for field in units[index].fields))
    for index in order:
        unit = units[index]
        now = _values(revision, unit.fields)
        try:
            cleaned = _checked_values(
              revision, list(zip(unit.fields, unit.before, now)), user,
              dependents)
            spaces = cleaned != now and _only_spaces_lost(unit, cleaned)
        except _LeftOut as left_out:
            for field, value in zip(unit.fields, now):
                setattr(revision, field.attname, value)
            results[index] = _left(unit, left_out.outcome, left_out.message)
            continue
        results[index] = _Restored(
          unit, 'unchanged' if cleaned == now else 'changed', '', cleaned,
          spaces)
    return results


def _save_restored(revision, results):
    """Save on revision the values of the results that change it."""
    attnames = []
    for result in results:
        if result.outcome == 'changed':
            for field, value in zip(result.unit.fields, result.values):
                setattr(revision, field.attname, value)
                attnames.append(field.attname)
    if attnames:
        revision.save(update_fields=attnames + ['modified'])


def _restore_object(changeset, data_object, units, user):
    """
    Put units back on data_object, in changeset, and return their
    _Restored tuples.  As in process_item an object held by another change
    is reserved without a wait, and so is one whose row, or the row of
    whose base, another transaction is writing.  Else in a savepoint it is
    locked, read again and checked; if no unit goes back all its work is
    undone.  The lock of an object that a reservation in flight is taking
    waits for its end; a wait beyond the server's limit stops the whole
    revert.
    """
    if data_object.deleted:
        return [_left(unit, 'deleted') for unit in units]
    left, pending = _split_units(data_object, units)
    if not pending:
        return left
    if _locked(data_object):
        return left + [_left(unit, 'reserved') for unit in pending]
    model = type(data_object)
    parent = TURNED_OFF_BY.get(model, (None,))[0]
    results = None
    try:
        with transaction.atomic():
            if _get_revision_lock(data_object, changeset) is None:
                raise _LeftOut('reserved')
            objects = model.objects.filter(id=data_object.id, deleted=False)
            if parent:
                objects = objects.select_related(parent)
            fresh = objects.first()
            if fresh is None:
                raise _LeftOut('deleted')
            left, pending = _split_units(fresh, units)
            results = left
            if pending:
                results = None
                _hold_rows(fresh)
                revision = _clone(BULK_TARGETS[model], fresh, changeset)
                results = left + _restored(revision, pending, user)
                _save_restored(revision, results)
            if not any(result.outcome == 'changed' for result in results):
                raise _LeftOut('unchanged')
    except _LeftOut as left_out:
        if results is not None:
            return results
        if left_out.outcome == 'deleted':
            return [_left(unit, 'deleted') for unit in units]
        return left + [_left(unit, left_out.outcome, left_out.message)
                       for unit in pending]
    except OperationalError as error:
        # Another transaction is writing a row that the new revision needs.
        if error.args[0] != NOWAIT_REFUSED:
            raise
        return left + [_left(unit, 'reserved') for unit in pending]
    return results


def _restore_objects(changeset, model, items, user):
    """
    Put back the units of items, as _revert_items gives them, in id
    order, in changeset; return the count of each outcome, for each
    unit, and the objects of the outcomes that the record lists, each
    once for an outcome, with the different messages of its units joined
    by a space.
    """
    counts = dict.fromkeys(REVERT_OUTCOMES, 0)
    listed = {outcome: [] for outcome in REVERT_LISTED}
    units = dict(items)
    parent = TURNED_OFF_BY.get(model, (None,))[0]
    for chunk in _chunks(sorted(units)):
        objects = model.objects.filter(id__in=chunk).order_by('id')
        if parent:
            objects = objects.select_related(parent)
        for data_object in objects:
            reasons = {}
            for result in _restore_object(changeset, data_object,
                                          units[data_object.id], user):
                counts[result.outcome] += 1
                if result.outcome in listed:
                    messages = reasons.setdefault(result.outcome, [])
                    if result.message not in messages:
                        messages.append(result.message)
            for outcome, messages in reasons.items():
                listed[outcome].append((data_object, ' '.join(messages)))
    return counts, listed


def reverts_of(changeset):
    """
    Return the bulk changes that revert the bulk change changeset, except
    the discarded ones, oldest first, each as a pair with its record.  One
    query finds the changes whose comments may be such a record; the
    record of each decides.
    """
    candidates = (
      Changeset.objects
      .filter(change_type=CTYPES['bulk'], id__gt=changeset.id,
              comments__text__contains='restore %d\n' % changeset.id)
      .exclude(state=states.DISCARDED).distinct().order_by('id'))
    reverts = []
    for candidate in candidates:
        record = operation_record(candidate)
        if record and record['operation'] == 'restore' and \
           record['values'] == [changeset.id]:
            reverts.append((candidate, record))
    return reverts


def _active_revert(changeset):
    """Return the revert of changeset under way, or None."""
    return next((revert for revert, record in reverts_of(changeset)
                 if revert.state in states.ACTIVE), None)


def revert_refusal(changeset):
    """
    Return why changeset cannot be reverted, or None if it can: bulk
    changes are on, it is a bulk change, approved, with the record of its
    operations, which says which fields it changed.
    """
    if not settings.BULK_CHANGE_ENABLED:
        return 'Bulk changes are turned off.'
    if changeset.change_type != CTYPES['bulk']:
        return 'Only a bulk change can be reverted.'
    if changeset.state != states.APPROVED:
        return 'Only an approved bulk change can be reverted.'
    if changeset.bulk_target()[0] is None or \
       operation_record(changeset) is None:
        return ('This bulk change has no record of its operations, so it '
                'cannot be reverted.')
    return None


def _planned(changeset, data_object, units, user, holder, active):
    """
    Return the _Restored tuples that a revert of changeset would give
    units of data_object, writing nothing: holder is the change that
    holds the lock of the object, and active the revert under way, whose
    own objects are not left out.  The edit form checks, in memory, the
    latest approved revision of the object as a revision of a bulk change
    without dependents, which is what the revert would make.
    """
    if data_object.deleted:
        return [_left(unit, 'deleted') for unit in units]
    left, pending = _split_units(data_object, units)
    if not pending or (active is not None and holder == active.id):
        return left
    if holder is not None:
        return left + [_left(unit, 'reserved') for unit in pending]
    rev_class = BULK_TARGETS[type(data_object)]
    try:
        try:
            head = rev_class.objects.get(
              next_revision=None, changeset__state=states.APPROVED,
              **{rev_class.source_name: data_object})
        except (ObjectDoesNotExist, MultipleObjectsReturned):
            _no_single_head(rev_class, data_object)
    except _LeftOut as left_out:
        return left + [_left(unit, left_out.outcome, left_out.message)
                       for unit in pending]
    head.changeset = changeset
    return left + _restored(head, pending, user, dependents=False)


def _revert_labels(name, names):
    """
    Return what a revert counts, as (one, several): the objects of the
    set name, or the changed values if the operations named several
    fields.
    """
    if len(names) > 1:
        return 'changed value', 'changed values'
    return BULK_OBJECT_NAMES[name]


def _part_of_change(done, total, labels):
    """Return words such as '3 of its 6 issues', for done of total."""
    if total == 1:
        return 'its one %s' % labels[0]
    if done == total:
        return 'all %d of its %s' % (total, labels[1])
    return '%d of its %d %s' % (done, total, labels[1])


def _restored_rows(result):
    """
    Return the rows of the table of a revert for result: for each field
    of its unit (label, old HTML, new HTML).
    """
    rows = []
    for field, old, value in zip(result.unit.fields, result.unit.wrote,
                                 result.values):
        rows.append((field_name(field.name),) + _shown_change(
          field, old, value, _object_names(field, [old, value])))
    return rows


def _later_rows(data_object, unit):
    """
    Return, for each field of unit, changed since on data_object, a row
    of the object, the label of the field and the values before the
    change, after it and now.
    """
    rows = []
    for field, before, wrote in zip(unit.fields, unit.before, unit.wrote):
        now = getattr(data_object, field.attname)
        names = _object_names(field, [before, wrote, now])
        rows.append((data_object, field_name(field.name),
                     _shown_value(field, before, names),
                     _shown_value(field, wrote, names),
                     _shown_value(field, now, names)))
    return rows


def revert_plan(changeset, user):
    """
    Return what a revert of the approved bulk change changeset would do
    for user, writing nothing, as a dict: 'rows' for the table of the
    values that go back, 'objects' and 'values' that go back, 'total'
    values of the change, 'others' that keep their present values, 'part'
    in words, 'groups' of what does not go back, left out or already
    back, as (summary, logical fields counted, rows, is the table of
    later changes), 'spaces' if a value loses spaces, and 'active', the
    revert under way.
    """
    model, names, items = _revert_items(changeset)
    name = changeset.bulk_target()[0]
    several = len(names) > 1
    active = _active_revert(changeset)
    holders = dict(RevisionLock.objects
                   .filter(content_type=ContentType.objects
                                                   .get_for_model(model),
                           object_id__in=[item[0] for item in items])
                   .values_list('object_id', 'changeset_id'))
    parent = TURNED_OFF_BY.get(model, (None,))[0]
    objects = {}
    for chunk in _chunks([item[0] for item in items]):
        query = model.objects.filter(id__in=chunk)
        if parent:
            query = query.select_related(parent)
        objects.update(query.in_bulk())

    plan = {'rows': [], 'objects': 0, 'values': 0, 'spaces': False,
            'total': sum(len(units) for object_id, units in items),
            'active': active}
    left = {outcome: [] for outcome, summary in REVERT_SUMMARIES}
    later = 0
    for object_id, units in items:
        data_object = objects[object_id]
        fields = []
        for result in _planned(changeset, data_object, units, user,
                               holders.get(object_id), active):
            if result.outcome == 'changed':
                plan['values'] += 1
                plan['spaces'] = plan['spaces'] or result.spaces
                fields += _restored_rows(result)
            elif result.outcome == 'later':
                later += 1
                left['later'] += _later_rows(data_object, result.unit)
            else:
                label = ', '.join(field_name(field.name)
                                  for field in result.unit.fields)
                left[result.outcome].append((data_object,
                                             label if several else '',
                                             result.message))
        if fields:
            plan['objects'] += 1
            plan['rows'].append((SimpleNamespace(source=data_object),
                                 str(data_object), fields))
    plan['others'] = plan['total'] - plan['values']
    plan['part'] = _part_of_change(plan['values'], plan['total'],
                                   _revert_labels(name, names))
    plan['groups'] = [(summary,
                       later if outcome == 'later' else len(left[outcome]),
                       left[outcome], outcome == 'later')
                      for outcome, summary in REVERT_SUMMARIES
                      if left[outcome]]
    return plan


@transaction.atomic
def apply_revert(user, change):
    """
    Make the bulk change of user that puts back what the approved bulk
    change change wrote, and return it, OPEN, with the comment that
    records it.  What changed since, or is reserved or refused, is left
    out and listed.

    As in apply, the rows that the new revisions will point to, the old
    values of their links included, are held first, then the indexer row
    is locked, so that two requests of one user take turns.  A revert may
    wait on each of these rows and on each object that a reservation in
    flight is taking; each wait has its own limit of the server, and
    their sum has no limit.  A revert under way, a refusal of
    can_start_bulk, more objects than its limit, a wait beyond the
    server's limit, a deadlock or nothing to put back raise
    ErrorWithMessage, with nothing written.  The locks of the objects
    keep two reverts from both changing an object; the second one finds
    nothing to change.
    """
    with _deadlock_refused():
        model, names, items = _revert_items(change)
        _hold_links(model, [item[0] for item in items], _old_values(items))
        _take_turn(user)
        active = _active_revert(change)
        if active is not None:
            raise ErrorWithMessage('Change %d is already reverting this '
                                   'change.' % active.id)
        refusal = can_start_bulk(user, 0)
        if refusal:
            raise ErrorWithMessage(refusal)
        changeset = Changeset.objects.create(indexer=user, state=states.OPEN,
                                             change_type=CTYPES['bulk'])
        counts, listed = _restore_objects(changeset, model, items, user)
        if not counts['changed']:
            raise ErrorWithMessage(_nothing_changed('no change was made',
                                                    counts, listed))
        refusal = _over_limit(user, changeset.bulk_target()[1].count(),
                              IN_REVERT)
        if refusal:
            raise ErrorWithMessage(refusal)
        _write_record(changeset, user, model,
                      Operation(','.join(sorted(names)), 'restore', None,
                                change.id),
                      urlresolvers.reverse('compare',
                                           kwargs={'id': change.id}),
                      sum(len(units) for object_id, units in items), counts,
                      listed)
        return changeset


def _links_to(changes):
    """Return links to changes in words, such as 4901, 4950 and 4960."""
    links = [format_html('<a href="{}">{}</a>',
                         urlresolvers.reverse('compare',
                                              kwargs={'id': change.id}),
                         change.id)
             for change in changes]
    if len(links) < 2:
        return links[0]
    return format_html('{} and {}',
                       format_html_join(', ', '{}',
                                        ((link,) for link in links[:-1])),
                       links[-1])


def _revert_words(changeset, may_start=True):
    """
    Return what the page of the approved bulk change changeset says of
    its reverts, as revert_status does, without 'in_turn' and with
    'done', the reverts that it names as done; None without a record.
    """
    if operation_record(changeset) is None:
        return None
    reverts = reverts_of(changeset)
    active = [revert for revert, record in reverts
              if revert.state in states.ACTIVE]
    if active:
        return {'text': 'Being reverted by change%s'
                        % ('s' if len(active) > 1 else ''),
                'links': _links_to(active), 'can_revert': False,
                'done': []}
    done = [revert for revert, record in reverts]
    if not done:
        return {'text': '', 'links': '', 'can_revert': may_start,
                'done': []}
    if len(reverts) == 1 and not any(
         reverts[0][1]['counts'].get(outcome, 0)
         for outcome, one, several in REVERT_LEFT_OUT):
        return {'text': 'Reverted by change', 'links': _links_to(done),
                'can_revert': False, 'done': done}
    return {'text': 'Partly reverted by change%s'
                    % ('s' if len(done) > 1 else ''),
            'links': _links_to(done), 'can_revert': may_start,
            'done': done}


def revert_status(changeset, may_start=True):
    """
    Return what the page of the approved bulk change changeset says of
    its reverts, as a dict: 'text' and the 'links' to the changes that
    it names, 'can_revert' for the link that starts another, if
    may_start says the reader may, and 'in_turn', a sentence for each
    revert named as done that a later revert puts back, in part or in
    full, or is putting back, such as "Change 4901 is itself reverted by
    change 4950."; one step only, as the page of each change names the
    next.  None if it has no record, so that it cannot be reverted.
    """
    status = _revert_words(changeset, may_start)
    if status is None:
        return None
    turns = []
    for revert in status.pop('done'):
        words = _revert_words(revert)
        if words['text']:
            turns.append(format_html('Change {} is itself {} {}.',
                                     _links_to([revert]),
                                     words['text'].lower(), words['links']))
    status['in_turn'] = format_html_join(' ', '{}',
                                         ((turn,) for turn in turns))
    return status


def revert_summary(changeset, may_open=True):
    """
    Return what the page of a bulk change that reverts another says of
    it, as a dict: the 'change' it reverts, 'part' and 'verb' for the
    words on the values that go back, 'left' for what stayed out,
    'in_comments' if the comments list any of that, 'more' if they list
    only the first 'listed' of an outcome and 'full_list' if the page
    with all of them is open, and may_open says the reader may see it;
    None for any other bulk change.
    """
    record = operation_record(changeset)
    if record is None or record['operation'] != 'restore':
        return None
    counts = record['counts']
    left = ['%d %s' % (counts[outcome], one if counts[outcome] == 1
                       else several)
            for outcome, one, several in REVERT_LEFT_OUT
            if counts.get(outcome)]
    return {'change': record['values'][0],
            'part': _part_of_change(
              counts['changed'], record['total'],
              _revert_labels(changeset.bulk_target()[0],
                             record_fields(record))),
            'verb': 'goes' if counts['changed'] == 1 else 'go',
            'left': ', '.join(left),
            'listed': LISTED_OBJECTS,
            'in_comments': any(counts.get(outcome, 0)
                               for outcome in REVERT_LISTED),
            'more': bool(record['more']),
            'full_list': settings.BULK_CHANGE_ENABLED and may_open}
