# -*- coding: utf-8 -*-
import sys
import re
import tempfile
import os
from codecs import EncodedFile, BOM_UTF16
from decimal import Decimal, InvalidOperation

from django.http import HttpResponse, HttpResponseRedirect
from django.utils.html import conditional_escape as esc
from django.contrib.auth.decorators import permission_required
from django.shortcuts import render_to_response, get_object_or_404

from apps.gcd.views import render_error
from apps.gcd.views.details import KEY_DATE_REGEXP
from apps.oi.models import *
from apps.oi.forms import *

MIN_ISSUE_FIELDS = 10
MAX_ISSUE_FIELDS = 12
MIN_SEQUENCE_FIELDS = 10
MAX_SEQUENCE_FIELDS = 16

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

ISSUE_FIELDS = ['number', 'volume', 'indicia_publisher', 'brand',
                'publication_date', 'key_date', 'indicia_frequency', 'price', 
                'page_count', 'editing', 'isbn', 'notes']

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

SEQUENCE_FIELDS = ['title', 'type', 'feature', 'page_count', 'script',
                   'pencils', 'inks', 'colors', 'letters', 'editing',
                   'genre', 'characters', 'job_number', 'reprint_notes',
                   'synopsis', 'notes']
# based on http://www.smontanaro.net/python/decodeh.py
def decode_heuristically(s, enc=None, denc=sys.getdefaultencoding()):
    """
    Try interpreting s using several possible encodings.
    The return value is a two-element tuple.  The first element is either an
    ASCII string or a Unicode object.  The second element is True if the 
    decoder was not successfully.
    """
    if isinstance(s, unicode):
        return s, False
    try:
        x = unicode(s, "ascii")
        # if it's ascii, we're done
        return s, False
    except UnicodeError:
        encodings = ["utf-8","iso-8859-1","cp1252","iso-8859-15"]
        # if the default encoding is not ascii it's a good thing to try
        if denc != "ascii": encodings.insert(0, denc)
        # always try any caller-provided encoding first
        if enc: encodings.insert(0, enc)
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
                re.search(r"[\xa4\xa6\xa8\xb4\xb8\xbc-\xbe]", s) is not None):
                continue

            try:
                x = unicode(s, enc)
            except UnicodeError:
                pass
            else:
                if x.encode(enc) == s:
                    return x, False

        return s, True


def _handle_import_error(request, changeset, error_text):
    response = render_error(request,
      '%s Back to the <a href="%s">editing page</a>.' % \
        (error_text, urlresolvers.reverse('edit', 
                                          kwargs={'id': changeset.id})), 
      is_safe=True)
    # there might be a temporary file attached
    if hasattr(request, "tmpfile"):
        request.tmpfile.close()
        os.remove(request.tmpfile_name)
    return response, True
    

def _process_file(request, changeset, is_issue):
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

    lines = []
    empty_line = False
    # process the file into a list of lines and check for length
    for line in upload:
        # see if the line can be decoded
        decoded_line, failure = decode_heuristically(line, enc=enc)
        if failure:
            error_text = 'line %s has unknown file encoding.' % line
            return _handle_import_error(request, changeset, error_text)

        split_line = decoded_line.strip('\n').split('\t')

        # if is_issue is set, the first line should be issue line
        if is_issue and not lines: 
            # check number of fields
            line_length = len(split_line)
            if line_length not in range(MIN_ISSUE_FIELDS,MAX_ISSUE_FIELDS+1):
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
            if line_length not in range(MIN_SEQUENCE_FIELDS,
                                        MAX_SEQUENCE_FIELDS+1):
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
        story_type = StoryType.objects.get(name=split_line[TYPE].\
                                                strip().lower)
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
        genre = fields[GENRE].strip()
        characters = fields[CHARACTERS].strip()
        job_number = fields[JOB_NUMBER].strip()
        reprint_notes = fields[REPRINT_NOTES].strip()
        synopsis = fields[SYNOPSIS].strip()
        notes = fields[STORY_NOTES].strip()

        story_revision = StoryRevision(changeset=changeset,
                                       title=title, 
                                       title_inferred=title_inferred,
                                       feature=feature,
                                       type=story_type,
                                       sequence_number=running_number,
                                       page_count=page_count,
                                       page_count_uncertain = page_count_uncertain,
                                       script = script,
                                       pencils = pencils,
                                       inks = inks,
                                       colors = colors,
                                       letters = letters,
                                       editing = editing,
                                       no_script = no_script,
                                       no_pencils = no_pencils,
                                       no_inks = no_inks,
                                       no_colors = no_colors,
                                       no_letters = no_letters,
                                       no_editing = no_editing,
                                       job_number = job_number,
                                       genre = genre,
                                       characters = characters,
                                       synopsis = synopsis,
                                       reprint_notes = reprint_notes,
                                       notes = notes,
                                       issue = Issue.objects.get(id=issue_id)
                                       )
        story_revision.save()
        running_number += 1
    return HttpResponseRedirect(urlresolvers.reverse('edit',
      kwargs={ 'id': changeset.id }))


def _find_publisher_object(request, changeset, name, publisher_objects, 
                           object_type, publisher):
    if not name:
        return None, False

    publisher_objects = publisher_objects.filter(name__iexact=name,
                                                 parent=publisher)
    if publisher_objects.count() == 1:
        return publisher_objects[0], False
    else:
        error_text = '%s "%s" does not exist for publisher %s.' % \
          (object_type, esc(name), esc(publisher))
        return _handle_import_error(request, changeset, error_text)        


@permission_required('gcd.can_reserve')
def import_issue_from_file(request, issue_id, changeset_id):
    changeset = get_object_or_404(Changeset, id=changeset_id)
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may import issue data.')
    try:
        # Process add form if this is a POST.
        if request.method == 'POST' and 'flatfile' in request.FILES:
            issue_revision = changeset.issuerevisions.get(issue=issue_id)
            if StoryRevision.objects.filter(changeset=changeset).count():
                return render_error(request,
                  'There are already sequences present for %s in this'
                  ' changeset. Back to the <a href="%s">editing page</a>.'\
                   % (esc(issue_revision), urlresolvers.reverse('edit', 
                      kwargs={'id': changeset.id})), is_safe=True)
            lines, failure = _process_file(request, changeset, is_issue=True)
            if failure:
                return lines

            # parse the issue line
            issue_fields = lines.pop(0) 
            issue_revision.number = issue_fields[NUMBER].strip()
            issue_revision.volume, issue_revision.no_volume = \
              _parse_volume(issue_fields[VOLUME].strip())

            indicia_publisher_name, issue_revision.indicia_pub_not_printed = \
              _check_for_none(issue_fields[INDICIA_PUBLISHER])
            indicia_publisher, failure = _find_publisher_object(request,
              changeset, indicia_publisher_name, 
              IndiciaPublisher.objects.all(), "Indicia publisher", 
              issue_revision.issue.series.publisher)
            if failure:
                return indicia_publisher
            else:
                issue_revision.indicia_publisher = indicia_publisher

            brand_name, issue_revision.no_brand = \
              _check_for_none(issue_fields[BRAND])
            brand, failure = _find_publisher_object(request, changeset, 
              brand_name, Brand.objects.all(), "Brand", 
              issue_revision.issue.series.publisher)
            if failure:
                return brand
            else:
                issue_revision.brand = brand

            issue_revision.publication_date = issue_fields[PUBLICATION_DATE]\
              .strip()
            issue_revision.key_date = issue_fields[KEY_DATE].strip()
            if not re.search(KEY_DATE_REGEXP, issue_revision.key_date):
                issue_revision.key_date = ''

            issue_revision.indicia_frequency = issue_fields[INDICIA_FREQUENCY]\
              .strip()
            issue_revision.price = issue_fields[PRICE].strip()
            issue_revision.page_count, issue_revision.page_count_uncertain =\
              _check_page_count(issue_fields[ISSUE_PAGE_COUNT])
            issue_revision.editing, issue_revision.no_editing = \
              _check_for_none(issue_fields[ISSUE_EDITING])
            issue_revision.isbn = issue_fields[ISBN].strip()
            issue_revision.notes = issue_fields[ISSUE_NOTES].strip()
            issue_revision.save()
            running_number = 0
            return _import_sequences(request, issue_id, changeset, 
                                     lines, running_number)
        else:
            return HttpResponseRedirect(urlresolvers.reverse('edit',
              kwargs={ 'id': changeset.id }))

    except (Issue.DoesNotExist, Issue.MultipleObjectsReturned, 
            IssueRevision.DoesNotExist):
        return render_error(request,
          'Could not find issue for id %s and changeset %s' \
            % (issue_id, changeset_id))


@permission_required('gcd.can_reserve')
def import_sequences_from_file(request, issue_id, changeset_id):
    changeset = get_object_or_404(Changeset, id=changeset_id)
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may import stories.')
    try:
        # Process add form if this is a POST.
        if request.method == 'POST' and 'flatfile' in request.FILES:
            issue_revision = changeset.issuerevisions.get(issue=issue_id)
            lines, failure = _process_file(request, changeset, is_issue=False)
            if failure:
                return lines
            running_number = issue_revision.next_sequence_number()
            return _import_sequences(request, issue_id, changeset, 
                                     lines, running_number)
        else:
            return HttpResponseRedirect(urlresolvers.reverse('edit',
              kwargs={ 'id': changeset.id }))

    except (Issue.DoesNotExist, Issue.MultipleObjectsReturned, 
            IssueRevision.DoesNotExist):
        return render_error(request,
          'Could not find issue for id %s and changeset %s' \
            % (issue_id, changeset_id))

@permission_required('gcd.can_reserve')
def export_issue_to_file(request, issue_id):
    issue = get_object_or_404(Issue, id=issue_id)
    export = ''
    for field_name in ISSUE_FIELDS:
        if field_name == 'brand' and not issue.brand and not issue.no_brand:
            export += "\t" 
        elif field_name == 'indicia_publisher' and not \
          issue.indicia_publisher and not issue.indicia_pub_not_printed:
            export += "\t" 
        else:
            export += "%s\t" % unicode(getattr(issue, field_name))
    export = export[:-1] + '\r\n'
    for sequence in issue.active_stories():
        for field_name in SEQUENCE_FIELDS:
            export += "%s\t" % unicode(getattr(sequence, field_name))
        export = export[:-1] + '\r\n'
    filename = unicode(issue).replace(' ', '_').encode('utf-8')
    response = HttpResponse(export, mimetype='text/tab-separated-values')
    response['Content-Disposition'] = 'attachment; filename=%s.tsv' % filename
    return response
