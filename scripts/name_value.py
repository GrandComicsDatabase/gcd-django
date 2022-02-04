"""
This script produces an issue-centric name-value pair export of the database.
This format is useful for some clients of GCD data, but is not intended to
be a general-purpose format.  It folds some data from series, publishers, etc.
into the issue-centric view, and results in story-specific data fields simply
appearing mutliple times per issue with different values and no indication of
which field values are grouped on a particular story.
"""

import sys
import logging
import django
from django.db import connection, models
from apps.stddata.models import Country
from apps.gcd.models import Issue, Story
from apps.gcd.models.story import show_feature
from apps.gcd.templatetags.credits import show_creator_credit

# TODO: When we move up to Python 2.6 (or even 2.5) these related name access
# functions can all be replaced by the "x if foo else y" construct in a lambda.

def _brand_group_name(issue):
    if issue.brand:
        groups = ''
        for group in issue.brand.group.all():
            groups += group.name + ', '
        return groups[:-2]
    return ''

def _show_genre(story):
    genres = story.genre.lower()
    for feature in story.feature_object.all():
        for genre in feature.genre.split(';'):
            genre = genre.strip()
            if genre not in genres:
                if genres == '':
                    genres = genre
                else:
                    genres += '; %s' % genre
    return genres


# Map moderately human-friendly field names to functions producing the data
# from an issue record.
ISSUE_FIELDS = {
    'series name': lambda i: i.series.name or '',
    'issue number': lambda i: i.number,
    'volume': lambda i: i.volume,
    'no volume': lambda i: i.no_volume,
    'display number': lambda i: i.display_number,
    'variant name': lambda i: i.variant_name if i.variant_name else '',
    'variant_of': lambda i: i.variant_of.id if i.variant_of else '',
    'price': lambda i: i.price or '',
    'issue page count': lambda i: i.page_count if i.page_count else '',
    'issue page count uncertain': lambda i: i.page_count_uncertain,
    'publication date': lambda i: i.publication_date or '',
    'key date': lambda i: i.key_date or '',
    'publisher name': lambda i: i.series.publisher.name,
    'brand name': lambda i: i.brand.name if i.brand else '',
    'brand group names': _brand_group_name,
    'indicia publisher name': lambda i: i.indicia_publisher.name if \
                                        i.indicia_publisher else '',
    'format': lambda i: i.series.format,
    'language code': lambda i: i.series.language.code,
    'series country code': lambda i: i.series.country.code,
    'publisher country code': lambda i: i.series.publisher.country.code,
    'isbn': lambda i: i.isbn if i.isbn else '',
    'barcode': lambda i: i.barcode if i.barcode else ''
}


# Map moderately human-friendly field names to functions producing the data
# from a story record.
STORY_FIELDS = {'sequence_number': lambda s: s.sequence_number,
                'title': lambda s: s.title,
                'title by gcd': lambda s: s.title_inferred,
                'feature': lambda s: show_feature(s, url=False),
                'script': lambda s: show_creator_credit(s, 'script', url=False),
                'pencils': lambda s: show_creator_credit(s, 'pencils', url=False),
                'inks': lambda s: show_creator_credit(s, 'inks', url=False),
                'genre': lambda s: _show_genre(s),
                'type': lambda s: s.type.name}


# The story types to include in the data.  This is intended to pick up various
# sorts of illustrations that may provide an interesting art credit.
# "filler" is included due to it being used very inconsistently, sometimes for
# two or larger page stories, sometimes for up to half of an issue.
# Character profiles are included as our data includes some comics that contain
# nothing but character profiles.
STORY_TYPES = ('comic story',
               'photo story',
               'cover',
               'cover reprint',
               'cartoon',
               'illustration',
               'filler',
               'character profile')

DELTA = 10000


def _next_range(old_end, max):
    """
    This manages pushing the query window along for the large queries that
    need to be done in chunks to keep from using too much memory.
    """
    if old_end == max:
        return None, None

    end = old_end + DELTA
    if max < end:
        end = max

    # The range operator is inclusive, don't double up on the old end value.
    return old_end + 1, end


def _fix_value(value):
    """
    NULL and empty string values should not be present in the output at all,
    so ensure that both are flagged as None.  Supply consistent quotes for
    everything else.
    """
    if value is None or value == '':
        return None
    return '"' + value + '"'


def _dump_table(dumpfile, objects, max, fields, get_id):
    """
    Dump records from a table a chunk at a time, selecting particular fields.
    Fields with a NULL or empty string value are omitted.
    """
    start = 0
    end = start + DELTA
    had_error = False
    while start is not None:
        logging.info("Dumping object rows %d through %d (out of %d)" %
                     (start, end, max))
        try:
            for object in objects.filter(id__range=(start, end)).iterator():
                for name, func in list(fields.items()):
                    value = str(func(object)).replace('"', '""')
                    value = _fix_value(value)
                    if value is not None:
                        record = '"%d"\t"%s"\t%s\n' % (get_id(object),
                                                        name, value)
                        dumpfile.write(record.encode('utf-8'))
        except IndexError:
            # Somehow our count was wrong and we ran off the end.  That's OK
            # because it just means we tried to select extra rows that aren't
            # there.
            # Unless we're seeing it again, in which case our code is in error
            # and we'll probably be stuck in a loop if we don't let this go.
            if had_error:
                raise
            had_error = True

        start, end = _next_range(end, max)


def main(*args):
    """
    Dump public data in chunks, manually establishing a transaction to ensure
    a consistent view.  The BEGIN statement must be issued manually because
    django transation objects will only initiate a transaction when writes
    are involved.
    """

    logging.basicConfig(level=logging.NOTSET,
                        stream=sys.stdout,
                        format='%(asctime)s %(levelname)s: %(message)s',
                        force=True)

    if len(args) != 1:
        logging.error("Usage:  name-value.py <output-file>")
        # sys.exit(-1)

    filename = args[0]
    try:
        dumpfile = open(filename, 'wb')
    except (IOError, OSError) as e:
        logging.error("Error opening output file '%s': %s" % (filename,
                                                              e.strerror))
        sys.exit(-1)

    cursor = connection.cursor()
    cursor.execute('BEGIN')

    try:
        # Note: count() is relatively expensive with InnoDB, so don't call it
        # more than we absolutely have to.  Since this is being done within a
        # transaction, the count should never change.
        issues = Issue.objects \
                      .filter(series__country__code='us', deleted=False) \
                      .order_by() \
                      .select_related('series',
                                      'series__publisher',
                                      'brand',
                                      'indicia_publisher',
                                      'series__language',
                                      'series__country',
                                      'series__publisher__country') \
                      .prefetch_related('brand__group')
        max = issues.aggregate(models.Max('id'))['id__max']

        _dump_table(dumpfile, issues, max, ISSUE_FIELDS, lambda i: i.id)

        stories = Story.objects.filter(issue__series__country__code='us',
                                       type__name__in=STORY_TYPES,
                                       deleted=False) \
                               .order_by() \
                               .select_related('type')
        max = stories.aggregate(models.Max('id'))['id__max']
        _dump_table(dumpfile, stories, max, STORY_FIELDS, lambda s: s.issue_id)

    finally:
        # We shouldn't have anything to commit or roll back, so just to be
        # safe, use a rollback to end the transation.
        cursor.execute('ROLLBACK')

def run(*args):
    main(*args)

if __name__ == '__main__':
    main()
