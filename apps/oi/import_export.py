# -*- coding: utf-8 -*-
import sys
import re
import tempfile
import os
import csv
import codecs
import io
from codecs import EncodedFile, BOM_UTF16
from decimal import Decimal, InvalidOperation
from datetime import datetime

from django.core import urlresolvers
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.html import conditional_escape as esc
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404

from apps.indexer.views import render_error
from apps.gcd.views.details import KEY_DATE_REGEXP
from apps.gcd.models import StoryType, Issue
from apps.gcd.models.support import GENRES
from apps.oi.models import (
    Changeset, StoryRevision, IssueRevision, PreviewIssue, get_keywords,
    on_sale_date_as_string)

MIN_ISSUE_FIELDS = 10
# MAX_ISSUE_FIELDS is set to 16 to allow import of export issue lines, but
# the final reprint notes are ignored on import
MAX_ISSUE_FIELDS = 17
MIN_SEQUENCE_FIELDS = 10
MAX_SEQUENCE_FIELDS = 18

NUMBER = 0
VOLUME = 1
INDICIA_PUBLISHER = 2
BRAND = 3
PUBLICATION_DATE = 4
KEY_DATE = 5
INDICIA_FREQUENCY = 6
PRICE = 7
ISSUE_PAGE_COUNT = 8
ISSUE_EDITING = 9
ISBN = 10
ISSUE_NOTES = 11
BARCODE = 12
ON_SALE_DATE = 13
ISSUE_TITLE = 14
ISSUE_KEYWORDS = 16

ISSUE_FIELDS = ['number', 'volume', 'indicia_publisher', 'brand',
                'publication_date', 'key_date', 'indicia_frequency', 'price',
                'page_count', 'editing', 'isbn', 'notes', 'barcode',
                'on_sale_date', 'title']

TITLE = 0
TYPE = 1
FEATURE = 2
STORY_PAGE_COUNT = 3
SCRIPT = 4
PENCILS = 5
INKS = 6
COLORS = 7
LETTERS = 8
STORY_EDITING = 9
GENRE = 10
CHARACTERS = 11
JOB_NUMBER = 12
REPRINT_NOTES = 13
SYNOPSIS = 14
STORY_NOTES = 15
STORY_KEYWORDS = 16
FIRST_LINE = 17

SEQUENCE_FIELDS = ['title', 'type', 'feature', 'page_count', 'script',
                   'pencils', 'inks', 'colors', 'letters', 'editing',
                   'genre', 'characters', 'job_number', 'reprint_notes',
                   'synopsis', 'notes', 'keywords', 'first_line']


# from http://docs.python.org/library/csv.html
class UTF8Recoder:
    """
    Iterator that reads an encoded stream and reencodes the input to UTF-8
    """
    def __init__(self, f, encoding):
        self.reader = codecs.getreader(encoding)(f)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.reader).encode("utf-8")


class UnicodeReader:
    """
    A CSV reader which will iterate over lines in the CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        f = UTF8Recoder(f, encoding)
        self.reader = csv.reader(f, dialect=dialect, **kwds)

    def __next__(self):
        row = next(self.reader)
        return [str(s, "utf-8") for s in row]

    def __iter__(self):
        return self


class UnicodeWriter:
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = io.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        self.writer.writerow([s.encode("utf-8") for s in row])
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


# based on http://www.smontanaro.net/python/decodeh.py
def decode_heuristically(s, enc=None, denc=sys.getdefaultencoding()):
    """
    Try interpreting s using several possible encodings.
    The return value is a two-element tuple.  The first element is either an
    ASCII string or a Unicode object.  The second element is True if the
    decoder was not successfully.
    """
    if isinstance(s, str):
        return s, False, None
    try:
        x = str(s, "ascii")
        # if it's ascii, we're done
        return s, False, "ascii"
    except UnicodeError:
        encodings = ["utf-8", "iso-8859-1", "cp1252", "iso-8859-15"]
        # if the default encoding is not ascii it's a good thing to try
        if denc != "ascii":
            encodings.insert(0, denc)
        # always try any caller-provided encoding first
        if enc:
            encodings.insert(0, enc)
        for enc in encodings:

            # Most of the characters between 0x80 and 0x9F are displayable
            # in cp1252 but are control characters in iso-8859-1.  Skip
            # iso-8859-1 if they are found, even though the unicode() call
            # might well succeed.

            if (enc in ("iso-8859-15", "iso-8859-1") and
                    re.search(r"[\x80-\x9f]", s) is not None):
                continue

            # Characters in the given range are more likely to be
            # symbols used in iso-8859-15, so even though unicode()
            # may accept such strings with those encodings, skip them.

            if (enc in ("iso-8859-1", "cp1252") and
                    re.search(r"[\xa4\xa6\xa8\xb4\xb8\xbc-\xbe]", s)
                    is not None):
                continue

            try:
                x = str(s, enc)
            except UnicodeError:
                pass
            else:
                if x.encode(enc) == s:
                    return x, False, enc

        return s, True, None


def _handle_import_error(request, changeset, error_text):
    response = render_error(
        request,
        '%s Back to the <a href="%s">editing page</a>.' %
        (error_text, urlresolvers.reverse('edit',
                                          kwargs={'id': changeset.id})),
        is_safe=True)
    # there might be a temporary file attached
    if hasattr(request, "tmpfile"):
        request.tmpfile.close()
        os.remove(request.tmpfile_name)
    return response, True


def _process_file(request, changeset, is_issue, use_csv=False):
    '''
    checks the file useable encodings and correct lengths
    returns two values
    if all correct:
      - a list of the processed lines (which are lists of the values)
      - False for no failure
    if some error:
      - error message
      - True for having failed
    '''
    # we need a real file to be able to use pythons Universal Newline Support
    tmpfile_handle, tmpfile_name = tempfile.mkstemp(".import")
    for chunk in request.FILES['flatfile'].chunks():
        os.write(tmpfile_handle, chunk)
    os.close(tmpfile_handle)
    tmpfile = open(tmpfile_name, 'U')
    request.tmpfile = tmpfile
    request.tmpfile_name = tmpfile_name

    # TODO use chardet

    # check if file starts with byte order mark
    if tmpfile.read(2) == BOM_UTF16:
        enc = 'utf-16'
        # use EncodedFile from codecs to get transparent encoding translation
        upload = EncodedFile(tmpfile, enc)
    # otherwise just do as usual
    else:
        upload = tmpfile
        # charset was None in my local tests, not sure if actually useful here
        enc = request.FILES['flatfile'].charset
    tmpfile.seek(0)

    if use_csv:
        dummy, failure, enc = decode_heuristically(tmpfile.read(), enc=enc)
        if failure:
            error_text = 'Uploaded file has unknown file encoding.'
            return _handle_import_error(request, changeset, error_text)
        tmpfile.seek(0)
        if enc:
            upload = UnicodeReader(tmpfile, encoding=enc)
        else:
            upload = UnicodeReader(tmpfile)
    lines = []
    empty_line = False
    # process the file into a list of lines and check for length
    for line in upload:
        # see if the line can be decoded
        if use_csv:
            split_line = line
        else:
            decoded_line, failure, ignore = decode_heuristically(line, enc=enc)
            if failure:
                error_text = 'line %s has unknown file encoding.' % line
                error_text = str(error_text, errors='replace')
                return _handle_import_error(request, changeset, error_text)

            split_line = decoded_line.strip('\n').split('\t')

        # if is_issue is set, the first line should be issue line
        if is_issue and not lines:
            # check number of fields
            line_length = len(split_line)
            if line_length not in list(range(MIN_ISSUE_FIELDS, MAX_ISSUE_FIELDS+1)):
                error_text = 'issue line %s has %d fields, it must have at '\
                             'least %d and not more than %d.' \
                  % (split_line, line_length, MIN_ISSUE_FIELDS,
                     MAX_ISSUE_FIELDS)
                return _handle_import_error(request, changeset, error_text)
            if line_length < MAX_ISSUE_FIELDS:
                for i in range(MAX_ISSUE_FIELDS - line_length):
                    split_line.append('')
        # later lines are story lines
        else:
            # we had an empty line just before
            if empty_line:
                error_text = 'The file includes an empty line.'
                return _handle_import_error(request, changeset, error_text)
            # we have an empty line now, OK if it is the last line
            if len(split_line) == 1:
                empty_line = True
                continue

            # check number of fields
            line_length = len(split_line)
            if line_length not in list(range(MIN_SEQUENCE_FIELDS,
                                        MAX_SEQUENCE_FIELDS+1)):
                error_text = 'sequence line %s has %d fields, it must have '\
                             'at least %d and not more than %d.' \
                  % (split_line, line_length, MIN_SEQUENCE_FIELDS,
                     MAX_SEQUENCE_FIELDS)
                return _handle_import_error(request, changeset, error_text)
            if line_length < MAX_SEQUENCE_FIELDS:
                for i in range(MAX_SEQUENCE_FIELDS - line_length):
                    split_line.append('')

            # check here for story_type, otherwise sequences up to an error
            # will be be added
            response, failure = _find_story_type(request, changeset,
                                                 split_line)
            if failure:
                return response, True

        lines.append(split_line)

    tmpfile.close()
    os.remove(tmpfile_name)
    del request.tmpfile
    del request.tmpfile_name
    return lines, False


# order of the fields in line with the OI, but not
# all fields (i.e. no_...) are present explicitly
# relevant documentation and order is here:
# http://docs.comics.org/wiki/Indexing_Offline
def _check_for_none(value):
    if value.strip().lower() == 'none':
        return '', True
    else:
        return value.strip(), False


def _check_page_count(page_count):
    if page_count.find('?') >= 0:
        page_count_uncertain = True
        page_count = page_count[:page_count.find('?')]
    else:
        page_count_uncertain = False
    try:
        page_count = Decimal(page_count)
    except InvalidOperation:
        page_count = None
        page_count_uncertain = True
    return page_count, page_count_uncertain


def _parse_volume(volume):
    if volume == '':
        no_volume = True
    else:
        no_volume = False
    return volume, no_volume


def _find_story_type(request, changeset, split_line):
    '''
    make sure that we have a valid StoryType
    returns two values
    if all correct:
      - the story type
      - False for no failure
    if some error:
      - error message
      - True for having failed
    '''
    try:
        story_type = StoryType.objects.get(name=split_line[TYPE].
                                           strip().lower())
        return story_type, False
    except StoryType.DoesNotExist:
        error_text = 'Story type "%s" in line %s does not exist.' \
            % (esc(split_line[TYPE]), esc(split_line))
        return _handle_import_error(request, changeset, error_text)


def _import_sequences(request, issue_id, changeset, lines, running_number):
    """
    Processing of story lines happens here.
    lines is a list of lists.
    This routine is independent of a particular format of the file,
    as long as the order of the fields in lines matches.
    """

    for fields in lines:
        story_type, failure = _find_story_type(request, changeset, fields)
        if failure:
            return story_type

        title = fields[TITLE].strip()
        first_line = fields[FIRST_LINE].strip()
        if title.startswith('[') and title.endswith(']'):
            title = title[1:-1]
            title_inferred = True
        else:
            title_inferred = False
        feature = fields[FEATURE].strip()
        page_count, page_count_uncertain = \
          _check_page_count(fields[STORY_PAGE_COUNT])
        script, no_script = _check_for_none(fields[SCRIPT])
        if story_type == StoryType.objects.get(name='cover'):
            if not script:
                no_script = True
        pencils, no_pencils = _check_for_none(fields[PENCILS])
        inks, no_inks = _check_for_none(fields[INKS])
        colors, no_colors = _check_for_none(fields[COLORS])
        letters, no_letters = _check_for_none(fields[LETTERS])
        editing, no_editing = _check_for_none(fields[STORY_EDITING])
        genres = fields[GENRE].strip()
        if genres:
            filtered_genres = ''
            for genre in genres.split(';'):
                if genre.strip() in GENRES['en']:
                    filtered_genres += ';' + genre
            genre = filtered_genres[1:]
        else:
            genre = genres
        characters = fields[CHARACTERS].strip()
        job_number = fields[JOB_NUMBER].strip()
        reprint_notes = fields[REPRINT_NOTES].strip()
        synopsis = fields[SYNOPSIS].strip()
        notes = fields[STORY_NOTES].strip()
        keywords = fields[STORY_KEYWORDS].strip()

        story_revision = StoryRevision(
          changeset=changeset,
          title=title,
          title_inferred=title_inferred,
          first_line=first_line,
          feature=feature,
          type=story_type,
          sequence_number=running_number,
          page_count=page_count,
          page_count_uncertain=page_count_uncertain,
          script=script,
          pencils=pencils,
          inks=inks,
          colors=colors,
          letters=letters,
          editing=editing,
          no_script=no_script,
          no_pencils=no_pencils,
          no_inks=no_inks,
          no_colors=no_colors,
          no_letters=no_letters,
          no_editing=no_editing,
          job_number=job_number,
          genre=genre,
          characters=characters,
          synopsis=synopsis,
          reprint_notes=reprint_notes,
          notes=notes,
          keywords=keywords,
          issue=Issue.objects.get(id=issue_id)
          )
        story_revision.save()
        running_number += 1
    return HttpResponseRedirect(urlresolvers.reverse('edit',
                                                     kwargs={'id':
                                                             changeset.id}))


def _find_publisher_object(request, changeset, name, publisher_objects,
                           object_type, publisher):
    if not name:
        return None, False

    publisher_objects = publisher_objects.filter(name__iexact=name)
    if publisher_objects.count() == 1:
        return publisher_objects[0], False
    else:
        error_text = '%s "%s" does not exist for publisher %s.' % \
          (object_type, esc(name), esc(publisher))
        return _handle_import_error(request, changeset, error_text)


@permission_required('indexer.can_reserve')
def import_issue_from_file(request, issue_id, changeset_id, use_csv=False):
    changeset = get_object_or_404(Changeset, id=changeset_id)
    if request.user != changeset.indexer:
        return render_error(request,
                            'Only the reservation holder may import issue '
                            'data.')
    try:
        # Process add form if this is a POST.
        if request.method == 'POST' and 'flatfile' in request.FILES:
            issue_revision = changeset.issuerevisions.get(issue=issue_id)
            if StoryRevision.objects.filter(changeset=changeset).count():
                return render_error(
                  request,
                  'There are already sequences present for %s in this'
                  ' changeset. Back to the <a href="%s">editing page</a>.'
                  % (esc(issue_revision), urlresolvers.reverse('edit',
                     kwargs={'id': changeset.id})),
                  is_safe=True)
            if 'csv' in request.POST:
                use_csv = True
            else:
                use_csv = False
            lines, failure = _process_file(request, changeset,
                                           is_issue=True, use_csv=use_csv)
            if failure:
                return lines

            # parse the issue line
            issue_fields = lines.pop(0)
            issue_revision.number = issue_fields[NUMBER].strip()
            issue_revision.volume, issue_revision.no_volume = \
              _parse_volume(issue_fields[VOLUME].strip())

            indicia_publisher_name, issue_revision.indicia_pub_not_printed = \
              _check_for_none(issue_fields[INDICIA_PUBLISHER])
            indicia_publisher, failure = _find_publisher_object(
              request,
              changeset, indicia_publisher_name,
              issue_revision.issue.series.publisher.active_indicia_publishers(),
              "Indicia publisher", issue_revision.issue.series.publisher)
            if failure:
                return indicia_publisher
            else:
                issue_revision.indicia_publisher = indicia_publisher

            brand_name, issue_revision.no_brand = \
              _check_for_none(issue_fields[BRAND])
            brand, failure = _find_publisher_object(
              request, changeset, brand_name,
              issue_revision.issue.series.publisher.active_brand_emblems(),
              "Brand", issue_revision.issue.series.publisher)
            if failure:
                return brand
            else:
                issue_revision.brand = brand

            issue_revision.publication_date = \
              issue_fields[PUBLICATION_DATE].strip()
            issue_revision.key_date = issue_fields[KEY_DATE].strip()\
                                                            .replace('.', '-')
            if issue_revision.key_date and not \
              re.search(KEY_DATE_REGEXP, issue_revision.key_date):
                return render_error(
                  request,
                  "key_date '%s' is invalid." % issue_revision.key_date)

            issue_revision.indicia_frequency, \
              issue_revision.no_indicia_frequency = \
              _check_for_none(issue_fields[INDICIA_FREQUENCY])
            issue_revision.price = issue_fields[PRICE].strip()
            issue_revision.page_count, issue_revision.page_count_uncertain = \
              _check_page_count(issue_fields[ISSUE_PAGE_COUNT])
            issue_revision.editing, issue_revision.no_editing = \
              _check_for_none(issue_fields[ISSUE_EDITING])
            issue_revision.isbn, issue_revision.no_isbn = \
              _check_for_none(issue_fields[ISBN])
            issue_revision.barcode, issue_revision.no_barcode = \
              _check_for_none(issue_fields[BARCODE])
            on_sale_date = issue_fields[ON_SALE_DATE].strip()
            if on_sale_date:
                if on_sale_date[-1] == '?':
                    issue_revision.on_sale_date_uncertain = True
                    on_sale_date = on_sale_date[:-1].strip()
                else:
                    issue_revision.on_sale_date_uncertain = False
                try:
                    # only full dates can be imported
                    sale_date = datetime.strptime(on_sale_date, '%Y-%m-%d')
                    issue_revision.year_on_sale = sale_date.year
                    issue_revision.month_on_sale = sale_date.month
                    issue_revision.day_on_sale = sale_date.day
                except ValueError:
                    return render_error(request,
                                        "on-sale_date '%s' is invalid." %
                                        on_sale_date)
            issue_revision.notes = issue_fields[ISSUE_NOTES].strip()
            if issue_revision.series.has_issue_title:
                issue_revision.title, issue_revision.no_title = \
                  _check_for_none(issue_fields[ISSUE_TITLE])
            issue_revision.keywords = issue_fields[ISSUE_KEYWORDS].strip()
            issue_revision.save()
            running_number = 0
            return _import_sequences(request, issue_id, changeset,
                                     lines, running_number)
        else:
            return HttpResponseRedirect(
              urlresolvers.reverse('edit',
                                   kwargs={'id': changeset.id}))

    except (Issue.DoesNotExist, Issue.MultipleObjectsReturned,
            IssueRevision.DoesNotExist):
        return render_error(
          request,
          'Could not find issue for id %s and changeset %s'
          % (issue_id, changeset_id))


@permission_required('indexer.can_reserve')
def import_sequences_from_file(request, issue_id, changeset_id, use_csv=False):
    changeset = get_object_or_404(Changeset, id=changeset_id)
    if request.user != changeset.indexer:
        return render_error(request,
                            'Only the reservation holder may import stories.')
    try:
        # Process add form if this is a POST.
        if request.method == 'POST' and 'flatfile' in request.FILES:
            issue_revision = changeset.issuerevisions.get(issue=issue_id)
            if 'csv' in request.POST:
                use_csv = True
            else:
                use_csv = False
            lines, failure = _process_file(request, changeset,
                                           is_issue=False, use_csv=use_csv)
            if failure:
                return lines
            running_number = issue_revision.next_sequence_number()
            return _import_sequences(request, issue_id, changeset,
                                     lines, running_number)
        else:
            return HttpResponseRedirect(urlresolvers.reverse('edit',
                                        kwargs={'id': changeset.id}))

    except (Issue.DoesNotExist, Issue.MultipleObjectsReturned,
            IssueRevision.DoesNotExist):
        return render_error(request,
                            'Could not find issue for id %s and changeset %s'
                            % (issue_id, changeset_id))


def generate_reprint_link(reprints, direction):
    reprint_note = ''
    for reprint in reprints:
        if direction == 'from':
            if hasattr(reprint, 'origin_issue') and \
              reprint.origin_issue:
                issue = reprint.origin_issue
            else:
                issue = reprint.origin.issue
        else:
            if hasattr(reprint, 'target_issue') and \
              reprint.target_issue:
                issue = reprint.target_issue
            else:
                issue = reprint.target.issue
        reprint_note += '%s %s' % (direction, issue.full_name())
        if reprint.notes:
            reprint_note = '%s [%s]' % (reprint_note, reprint.notes)
        if issue.publication_date:
            reprint_note += " (" + issue.publication_date + ")"
        reprint_note += '; '
    return reprint_note


@permission_required('indexer.can_reserve')
def export_issue_to_file(request, issue_id, use_csv=False, revision=False):
    if revision:
        issue_revision = get_object_or_404(IssueRevision, id=issue_id)
        issue = PreviewIssue(issue_revision)
        issue.series = issue_revision.series
        issue.on_sale_date = on_sale_date_as_string(issue_revision)
        issue.revision = issue_revision
        issue.keywords = issue_revision.keywords
    else:
        issue = get_object_or_404(Issue, id=issue_id)
    series = issue.series
    filename = str(issue).replace(' ', '_').encode('utf-8')
    if use_csv:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="%s.csv"' % \
                                          filename
        writer = UnicodeWriter(response)
    export_data = []
    for field_name in ISSUE_FIELDS:
        if field_name == 'brand' and not issue.brand and not issue.no_brand:
            export_data.append('')
        elif field_name == 'indicia_publisher' and not \
          issue.indicia_publisher and not issue.indicia_pub_not_printed:
            export_data.append('')
        elif field_name == 'editing' and getattr(issue, 'no_editing'):
            export_data.append('None')
        elif field_name in ['indicia_frequency', 'isbn', 'barcode']\
          and not getattr(series, 'has_%s' % field_name):
            export_data.append('')
        elif field_name == 'title' and not getattr(series, 'has_issue_title'):
            export_data.append('')
        elif field_name in ['indicia_frequency', 'isbn', 'barcode', 'title']\
          and getattr(issue, 'no_%s' % field_name):
            export_data.append('None')
        else:
            export_data.append(str(getattr(issue, field_name)))
    reprint = ''
    from_reprints = list(issue.from_reprints.select_related().all())
    from_reprints.extend(list(issue.from_issue_reprints.select_related()
                                                       .all()))
    from_reprints = sorted(from_reprints, key=lambda a: a.origin_sort)
    reprint += generate_reprint_link(from_reprints, 'from')

    to_reprints = list(issue.to_reprints.select_related().all())
    to_reprints.extend(list(issue.to_issue_reprints.select_related().all()))
    to_reprints = sorted(to_reprints, key=lambda a: a.target_sort)
    reprint += generate_reprint_link(to_reprints, 'in')
    if reprint != '':
        reprint = reprint[:-2]
    export_data.append(str(reprint))
    # keywords were added after reprint_links on issue level, so they come
    # later in the export
    # TODO check after refactor if this can be changed
    if revision:
        export_data.append(issue.keywords)
    else:
        export_data.append(get_keywords(issue))

    if use_csv:
        writer.writerow(export_data)
    else:
        export = '\t'.join(export_data) + '\r\n'
    for sequence in issue.active_stories():
        export_data = []
        for field_name in SEQUENCE_FIELDS:
            if field_name in ['script', 'pencils', 'inks', 'colors',
                              'letters', 'editing'] and \
                             getattr(sequence, 'no_%s' % field_name):
                export_data.append('None')
            elif field_name == 'title' and sequence.title_inferred:
                export_data.append('[%s]' % sequence.title)
            elif field_name == 'reprint_notes':
                reprint = ''
                from_reprints = list(sequence.from_reprints.select_related()
                                                           .all())
                from_reprints.extend(list(sequence.from_issue_reprints
                                                  .select_related().all()))
                from_reprints = sorted(from_reprints, key=lambda a:
                                       a.origin_sort)
                reprint += generate_reprint_link(from_reprints, 'from')

                to_reprints = list(sequence.to_reprints.select_related().all())
                to_reprints.extend(list(sequence.to_issue_reprints
                                                .select_related().all()))
                to_reprints = sorted(to_reprints, key=lambda a: a.target_sort)
                reprint += generate_reprint_link(to_reprints, 'in')

                if reprint != '':
                    if sequence.reprint_notes:
                        reprint += sequence.reprint_notes
                    else:
                        reprint = reprint[:-2]
                else:
                    reprint = sequence.reprint_notes
                export_data.append(str(reprint))
            elif field_name == 'keywords':
                # TODO check after refactor if this can be changed
                if revision:
                    export_data.append(sequence.keywords)
                else:
                    export_data.append(get_keywords(sequence))
            else:
                export_data.append(str(getattr(sequence, field_name)))
        if use_csv:
            writer.writerow(export_data)
        else:
            export += '\t'.join(export_data) + '\r\n'
    if not use_csv:
        response = HttpResponse(export,
                                content_type='text/tab-separated-values')
        response['Content-Disposition'] = 'attachment; filename="%s.tsv"' % \
                                          filename
    return response
