# -*- coding: utf-8 -*-
import re
import tempfile
import os
import csv
import chardet
import json
import yaml
from decimal import Decimal, InvalidOperation
from datetime import datetime

import django.urls as urlresolvers
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.html import conditional_escape as esc
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404

from apps.indexer.views import render_error
from apps.gcd.templatetags.credits import show_creator_credit
from apps.gcd.views.details import KEY_DATE_REGEXP
from apps.gcd.models import StoryType, Issue, Series, IndiciaPrinter, \
                            VARIANT_COVER_STATUS, VCS_Codes
from apps.gcd.models.support import GENRES
from apps.oi.models import (
    Changeset, StoryRevision, IssueRevision, PreviewIssue, get_keywords,
    on_sale_date_as_string, CTYPES)
from apps.oi import states
MIN_ISSUE_FIELDS = 10
# MAX_ISSUE_FIELDS is set to 19 to allow import of exported issue lines, but
# the reprint notes are ignored on import.
MAX_ISSUE_FIELDS = 19
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
INDICIA_PRINTER = 15
AGE_GUIDELINES = 16
ISSUE_KEYWORDS = 18
VARIANT_NAME = 19
VARIANT_STATUS = 20

ISSUE_FIELDS = ['number', 'volume', 'indicia_publisher', 'brand_emblem',
                'publication_date', 'key_date', 'indicia_frequency', 'price',
                'page_count', 'editing', 'isbn', 'notes', 'barcode',
                'on_sale_date', 'title', 'indicia_printer', 'rating',]

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


def _handle_import_error(request, return_url, error_text):
    response = render_error(
        request,
        '%s Back to the <a href="%s">editing page</a>.' %
        (error_text, return_url),
        is_safe=True)
    # there might be a temporary file attached
    if hasattr(request, "tmpfile"):
        request.tmpfile.close()
        os.remove(request.tmpfile_name)
    return response


def _convert_upload_to_file(request, request_file):
    # we need a real file to be able to use pythons Universal Newline Support
    tmpfile_handle, tmpfile_name = tempfile.mkstemp(".import")
    for chunk in request_file.chunks():
        os.write(tmpfile_handle, chunk)
    os.close(tmpfile_handle)
    tmpfile = open(tmpfile_name, 'rb')
    request.tmpfile = tmpfile
    request.tmpfile_name = tmpfile_name
    encoding = chardet.detect(tmpfile.read())['encoding']
    tmpfile = open(tmpfile_name, encoding=encoding)
    return tmpfile


def _process_file(request, changeset_url, is_issue, use_csv=False):
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
    tmpfile = _convert_upload_to_file(request, request.FILES['flatfile'])
    if use_csv:
        upload = csv.reader(tmpfile)
    else:
        upload = tmpfile
    lines = []
    empty_line = False
    # process the file into a list of lines and check for length
    for line in upload:
        # see if the line can be decoded
        if use_csv:
            split_line = line
        else:
            split_line = line.strip('\n').split('\t')

        # if is_issue is set, the first line should be issue line
        if is_issue and not lines:
            # check number of fields
            line_length = len(split_line)
            if line_length not in list(range(MIN_ISSUE_FIELDS,
                                             MAX_ISSUE_FIELDS+1)):
                error_text = 'issue line %s has %d fields, it must have at '\
                             'least %d and not more than %d.' \
                  % (split_line, line_length, MIN_ISSUE_FIELDS,
                     MAX_ISSUE_FIELDS)
                return _handle_import_error(request, changeset_url,
                                            error_text), True
        # later lines are story lines
        else:
            # we had an empty line just before
            if empty_line:
                error_text = 'The file includes an empty line.'
                return _handle_import_error(request, changeset_url,
                                            error_text), True
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
                return _handle_import_error(request, changeset_url,
                                            error_text), True
            if line_length < MAX_SEQUENCE_FIELDS:
                for i in range(MAX_SEQUENCE_FIELDS - line_length):
                    split_line.append('')

            # check here for story_type, otherwise sequences up to an error
            # will be be added
            response, failure = _find_story_type(request, changeset_url,
                                                 split_line[TYPE], split_line)
            if failure:
                return response, True

        lines.append(split_line)

    tmpfile.close()
    os.remove(request.tmpfile_name)
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


def _find_story_type(request, changeset_url, story_type_name,
                     sequence_fields):
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
        story_type = StoryType.objects.get(name=story_type_name.
                                           strip().lower())
        return story_type, False
    except StoryType.DoesNotExist:
        error_text = 'Story type "%s" in line %s does not exist.' \
            % (esc(story_type_name), esc(sequence_fields))
        return _handle_import_error(request, changeset_url, error_text), True


def _process_sequence_data(request, sequence_fields, changeset):
    parsed_data = {}
    story_type, failure = _find_story_type(request, changeset,
                                           sequence_fields['type'],
                                           sequence_fields)
    if failure:
        return story_type, True
    parsed_data['type'] = story_type

    for field in ['title', 'first_line', 'feature', 'genre', 'characters',
                  'job_number', 'reprint_notes', 'synopsis', 'notes',
                  'keywords']:
        parsed_data[field] = sequence_fields.get(field, '').strip()

    if parsed_data['title'].startswith('[') and \
       parsed_data['title'].endswith(']'):
        parsed_data['title'] = parsed_data['title'][1:-1]
        parsed_data['title_inferred'] = True
    else:
        parsed_data['title_inferred'] = False

    genres = parsed_data.pop('genre')
    if genres:
        filtered_genres = ''
        for genre in genres.split(';'):
            if genre.strip() in GENRES['en']:
                filtered_genres += ';' + genre
        parsed_data['genre'] = filtered_genres[1:]
    else:
        parsed_data['genre'] = genres

    parsed_data['page_count'], parsed_data['page_count_uncertain'] = \
        _check_page_count(sequence_fields['page_count'])

    # check for none as value and process
    for field in ['script', 'pencils', 'inks', 'colors', 'letters', 'editing']:
        parsed_data[field], parsed_data['no_' + field] = \
          _check_for_none(sequence_fields.get(field, '').strip())

    if story_type == StoryType.objects.get(name='cover'):
        if not parsed_data['script']:
            parsed_data['no_script'] = True
        if not parsed_data['letters']:
            parsed_data['no_letters'] = True
    if not parsed_data['editing']:
        parsed_data['no_editing'] = True
    return parsed_data, False


def _create_story_add(story_data, request, issue, changeset, running_number):
    parsed_data, failure = _process_sequence_data(request, story_data,
                                                  changeset)
    if failure:
        return parsed_data, True
    story_revision = StoryRevision(
      changeset=changeset,
      sequence_number=running_number,
      issue=issue,
      **parsed_data)
    story_revision.save()
    return story_revision, False


def _import_sequences_structured(request, issue, changeset, story_data,
                                 running_number):
    for story in story_data:
        response, failure = _create_story_add(story, request, issue,
                                              changeset, running_number)
        if failure:
            return response
        running_number += 1
    return HttpResponseRedirect(urlresolvers.reverse(
                                'edit',
                                kwargs={'id': changeset.id}))


def _import_sequences(request, issue, changeset, lines, running_number):
    """
    Processing of story lines happens here.
    lines is a list of lists.
    This routine is independent of a particular format of the file,
    as long as the order of the fields in lines matches.
    """

    for fields in lines:
        data = {}
        cnt = 0
        line_length = len(fields)
        if line_length < MAX_SEQUENCE_FIELDS:
            for i in range(MAX_SEQUENCE_FIELDS - line_length):
                fields.append('')
        for field in SEQUENCE_FIELDS:
            data[field] = fields[cnt]
            cnt += 1
        response, failure = _create_story_add(data, request, issue,
                                              changeset, running_number)
        if failure:
            return response
        running_number += 1
    return HttpResponseRedirect(urlresolvers.reverse('edit',
                                                     kwargs={'id':
                                                             changeset.id}))


def _find_publisher_object(request, changeset_url, name, publisher_objects,
                           object_type, publisher):
    if not name:
        return None, False

    publisher_objects = publisher_objects.filter(name__iexact=name)
    if publisher_objects.count() == 1:
        return publisher_objects[0], False
    else:
        if publisher:
            publisher_string = ' for publisher %s' % esc(publisher)
        else:
            publisher_string = ''
        if publisher_objects.count() > 1:
            error_text = '%s "%s" is not unique%s.' % \
                         (object_type, esc(name), publisher_string)
        else:
            error_text = '%s "%s" does not exist%s.' % \
                         (object_type, esc(name), publisher_string)
        return _handle_import_error(request, changeset_url, error_text), True


def _parse_issue_line(request, issue_fields, series, changeset_url):
    parsed_data = {}
    cnt = 0
    line_length = len(issue_fields)
    if line_length < MAX_ISSUE_FIELDS:
        for i in range(MAX_ISSUE_FIELDS - line_length):
            issue_fields.append('')
    for field in ISSUE_FIELDS:
        parsed_data[field] = issue_fields[cnt]
        cnt += 1
    parsed_data['reprint_notes'] = issue_fields[cnt]
    parsed_data['keywords'] = issue_fields[cnt+1]
    cnt += 2
    if len(issue_fields) > cnt:
        parsed_data['variant_name'] = issue_fields[cnt]
        cnt += 1
        parsed_data['variant_cover_status'] = issue_fields[cnt]\
            .strip().upper().replace(' ', '_')
    return _process_issue_data(request, parsed_data, series, changeset_url)


def _process_issue_data(request, issue_fields, series, changeset_url):
    parsed_data = {}
    # use the string value
    for field in ['number', 'publication_date', 'keywords', 'price', 'notes']:
        parsed_data[field] = issue_fields.get(field, '').strip()

    parsed_data['volume'], parsed_data['no_volume'] = _parse_volume(
      issue_fields.get('volume', '').strip())

    # check for none as value and process
    for field in ['indicia_frequency', 'editing', 'isbn', 'barcode', 'rating']:
        parsed_data[field], parsed_data['no_' + field] = \
          _check_for_none(issue_fields.get(field, '').strip())

    brand_name, parsed_data['no_brand'] = \
        _check_for_none(issue_fields.get('brand_emblem', '').strip())
    # if we have a brand, we need to find the corresponding brand emblems
    brand_array = []
    for brand_emblem in brand_name.split(';'):
        parsed_data['brand_emblem'], failure = _find_publisher_object(
          request, changeset_url, brand_emblem.strip(),
          series.publisher.active_brand_emblems(),
          "Brand", series.publisher)
        if failure:
            return parsed_data['brand_emblem'], True
        brand_array.append(parsed_data['brand_emblem'])
    if brand_array:
        parsed_data['brand_emblem'] = brand_array
    else:
        parsed_data['brand_emblem'] = None

    # indicia publisher has special no_-field, find the corresponding object
    indicia_publisher_name, parsed_data['indicia_pub_not_printed'] = \
        _check_for_none(issue_fields.get('indicia_publisher', '').strip())
    parsed_data['indicia_publisher'], failure = _find_publisher_object(
      request, changeset_url, indicia_publisher_name,
      series.publisher.active_indicia_publishers(),
      "Indicia publisher", series.publisher)
    if failure:
        return parsed_data['indicia_publisher'], True

    # check the key date for correct format
    parsed_data['key_date'] = issue_fields.get('key_date', '').strip()\
                                          .replace('.', '-')
    if parsed_data['key_date'] and not re.search(KEY_DATE_REGEXP,
                                                 parsed_data['key_date']):
        return render_error(
          request,
          "key_date '%s' is invalid." % parsed_data['key_date']), True

    parsed_data['page_count'], parsed_data['page_count_uncertain'] = \
        _check_page_count(issue_fields.get('page_count', '').strip())
    if not parsed_data['page_count']:
        parsed_data['page_count_uncertain'] = False
    on_sale_date = issue_fields.get('on_sale_date', '').strip()
    if on_sale_date:
        if on_sale_date[-1] == '?':
            parsed_data['on_sale_date_uncertain'] = True
            on_sale_date = on_sale_date[:-1].strip()
        else:
            parsed_data['on_sale_date_uncertain'] = False
        try:
            # try full date first, then partial dates
            month = True
            day = False
            if len(on_sale_date.split('-')) == 3:
                sale_date = datetime.strptime(on_sale_date, '%Y-%m-%d')
                day = True
            elif len(on_sale_date.split('-')) == 2:
                sale_date = datetime.strptime(on_sale_date + '-01', '%Y-%m-%d')
            elif len(on_sale_date.split('-')) == 1:
                sale_date = datetime.strptime(on_sale_date + '-01-01',
                                              '%Y-%m-%d')
                month = False
            else:
                raise ValueError("Invalid date format")
            parsed_data['year_on_sale'] = sale_date.year
            if month:
                parsed_data['month_on_sale'] = sale_date.month
            if day:
                parsed_data['day_on_sale'] = sale_date.day
        except ValueError:
            return render_error(request,
                                "on-sale_date '%s' is invalid." %
                                on_sale_date), True
    if series.has_issue_title:
        parsed_data['title'], parsed_data['no_title'] = \
          _check_for_none(issue_fields.get('title', '').strip())

    if series.has_indicia_printer:
        printer_name, parsed_data['indicia_printer_not_printed'] = \
            _check_for_none(issue_fields.get('indicia_printer', '').strip())
        printer_array = []
        for printer in printer_name.split(';'):
            parsed_data['indicia_printer'], failure = _find_publisher_object(
              request, changeset_url, printer.strip(),
              IndiciaPrinter.objects.filter(deleted=False),
              "Indicia Printer", None)
            if failure:
                return parsed_data['indicia_printer'], True
            printer_array.append(parsed_data['indicia_printer'])
        if printer_array:
            parsed_data['indicia_printer'] = printer_array
        else:
            parsed_data['indicia_printer'] = None

    if 'variant_name' in issue_fields:
        parsed_data['variant_name'] = issue_fields.get('variant_name')
        parsed_data['variant_cover_status'] = \
            issue_fields.get('variant_cover_status', '').upper().replace(' ',
                                                                         '_')
        if parsed_data['variant_cover_status'] not in VCS_Codes._member_names_:
            return render_error(request,
                                "variant_cover_status '%s' is invalid." %
                                parsed_data['variant_cover_status']), True
        parsed_data['variant_cover_status'] = VCS_Codes[parsed_data[
                                              'variant_cover_status']]
    return parsed_data, False


def _create_issue_add(parsed_data, request, series, series_url):
    changeset = Changeset(indexer=request.user, state=states.OPEN,
                          change_type=CTYPES['issue_add'])
    changeset.save()
    # check for variant add
    if parsed_data.get('variant_name'):
        number = parsed_data['number']
        issue = Issue.objects.filter(series=series, number=number,
                                     variant_of__isnull=True)
        if issue.count() == 1:
            issue = issue[0]
            parsed_data['variant_of'] = issue
        else:
            error_text = 'Could not find base issue for variant %s ' \
                           'with number %s in series %s.' % (
                             parsed_data['variant_name'], number,
                             series)
            return _handle_import_error(request, series_url,
                                        error_text), True
        current_variants = issue.variant_set.order_by('-sort_code')
        if current_variants:
            add_after = current_variants[0]
        else:
            add_after = issue
    else:
        add_after = series.last_issue
    brand_emblem = parsed_data.pop('brand_emblem')
    indicia_printer = parsed_data.pop('indicia_printer')
    issue_revision = IssueRevision(
        changeset=changeset, series=series,
        after=add_after, **parsed_data)
    issue_revision.save()
    if brand_emblem:
        issue_revision.brand_emblem.set(brand_emblem)
    if indicia_printer:
        issue_revision.indicia_printer.set(indicia_printer)
    return issue_revision, False


@permission_required('indexer.can_reserve')
def import_issues_to_series_structured(request, series_id, use_yaml=False):
    series = get_object_or_404(Series, id=series_id)
    series_url = urlresolvers.reverse('add_issues',
                                      kwargs={'series_id': series.id})
    if request.method == 'POST' and 'file' in request.FILES:
        tmpfile = _convert_upload_to_file(request, request.FILES['file'])
        if use_yaml:
            try:
                data = yaml.safe_load(tmpfile)
            except yaml.YAMLError as e:
                error_text = f'Invalid YAML format: {e}'
                return _handle_import_error(request, series_url, error_text)
        else:
            try:
                data = json.load(tmpfile)
            except json.JSONDecodeError as e:
                error_text = f'Invalid JSON format: {e}'
                return _handle_import_error(request, series_url, error_text)
        if 'issue_set' not in data:
            error_text = 'File must contain an "issue_set" key.'
            return _handle_import_error(request, series_url, error_text)
        for issue_data in data['issue_set']:
            # JSON null entries become None in Python, but we want to treat
            # them as empty strings for the import.
            for key in issue_data.keys():
                if issue_data[key] is None:
                    issue_data[key] = ''
            parsed_data, failure = _process_issue_data(request, issue_data,
                                                       series, series_url)
            if failure:
                return parsed_data
            issue_revision, failure = _create_issue_add(parsed_data, request,
                                                        series, series_url)
            if failure:
                return issue_revision
            if issue_revision.variant_of:
                if len(issue_data.get('story_set', [])) > 1:
                    error_text = 'Variant %s has more than one story.' % (
                        issue_revision)
                    return _handle_import_error(request, series_url,
                                                error_text)
                variant_cover_status = issue_revision.variant_cover_status
                if variant_cover_status != VCS_Codes['ARTWORK_DIFFERENCE'] \
                   and issue_data.get('story_set', []):
                    error_text = 'Variant is of cover status %s, ' \
                                 'but a sequence exists for variant %s.' % (
                                    VARIANT_COVER_STATUS[variant_cover_status],
                                    issue_revision)
                    return _handle_import_error(request, series_url,
                                                error_text)
                for story_data in issue_data.get('story_set', []):
                    if story_data.get('type', '').strip().lower() != 'cover':
                        error_text = 'Sequence for variant %s is not of ' \
                          'type cover.' % (issue_revision)
                        return _handle_import_error(request, series_url,
                                                    error_text)
                    parsed_data, failure = _process_sequence_data(
                      request, story_data, issue_revision.changeset)
                    if failure:
                        return parsed_data
                    story_revision = StoryRevision(
                      changeset=issue_revision.changeset,
                      sequence_number=0,
                      issue=None,
                      **parsed_data)
                    story_revision.save()
        return HttpResponseRedirect(urlresolvers.reverse('editing'))
    else:
        return HttpResponseRedirect(
          urlresolvers.reverse('series_details', kwargs={'id': series.id}))


@permission_required('indexer.can_reserve')
def import_issues_to_series(request, series_id):
    if request.method == 'POST' and 'json' in request.POST:
        return import_issues_to_series_structured(request, series_id)
    if request.method == 'POST' and 'yaml' in request.POST:
        return import_issues_to_series_structured(request, series_id,
                                                  use_yaml=True)

    series = get_object_or_404(Series, id=series_id)
    series_url = urlresolvers.reverse('add_issues',
                                      kwargs={'series_id': series.id})
    if request.method == 'POST' and 'file' in request.FILES:
        tmpfile = _convert_upload_to_file(request, request.FILES['file'])
        upload = csv.reader(tmpfile)
        lines = []
        for split_line in upload:
            # check number of fields
            line_length = len(split_line)
            if line_length not in list(range(MIN_ISSUE_FIELDS,
                                             MAX_ISSUE_FIELDS+3)):
                error_text = 'issue line %s has %d fields, it must have at '\
                             'least %d and not more than %d.' \
                  % (split_line, line_length, MIN_ISSUE_FIELDS,
                     MAX_ISSUE_FIELDS)
                return _handle_import_error(request, series_url, error_text)
            if line_length > MAX_ISSUE_FIELDS and \
               line_length < MAX_ISSUE_FIELDS + 2:
                error_text = 'issue line %s has %d fields, but for variants ' \
                             'it must have %d fields.' \
                  % (split_line, line_length, MAX_ISSUE_FIELDS+2)
                return _handle_import_error(request, series_url, error_text)
            lines.append(split_line)
        variant = False
        # initialize to avoid flake warning
        variant_cover_status = -1
        issue_revision = None
        for line in lines:
            if variant:
                if line[TYPE].strip().lower() == 'cover':
                    if variant_cover_status != VCS_Codes['ARTWORK_DIFFERENCE']:
                        error_text = 'Variant is of cover status %s, ' \
                          'but cover sequence exists in line %s.' % (
                            VARIANT_COVER_STATUS[variant_cover_status], line)
                        return _handle_import_error(request, series_url,
                                                    error_text)
                    _import_sequences(request, None, issue_revision.changeset,
                                      [line], 0)
                    variant = False
                    continue
            parsed_data, failure = _parse_issue_line(request, line, series,
                                                     series_url)
            if failure:
                return parsed_data
            issue_revision, failure = _create_issue_add(parsed_data, request,
                                                        series, series_url)
            if failure:
                return issue_revision
            if issue_revision.variant_of:
                variant = True
                variant_cover_status = issue_revision.variant_cover_status
        return HttpResponseRedirect(urlresolvers.reverse('editing'))
    else:
        return HttpResponseRedirect(
          urlresolvers.reverse('show_series', kwargs={'series_id': series.id}))


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
            changeset_url = urlresolvers.reverse('edit',
                                                 kwargs={'id': changeset.id})
            if StoryRevision.objects.filter(changeset=changeset).count():
                return render_error(
                  request,
                  'There are already sequences present for %s in this'
                  ' changeset. Back to the <a href="%s">editing page</a>.'
                  % (esc(issue_revision), changeset_url),
                  is_safe=True)

            use_csv = False
            use_tsv = False
            use_json = False
            use_yaml = False

            if 'csv' in request.POST:
                use_csv = True
            elif 'json' in request.POST:
                use_json = True
            elif 'yaml' in request.POST:
                use_yaml = True
            else:
                use_tsv = True
            if use_tsv or use_csv:
                lines, failure = _process_file(request, changeset_url,
                                               is_issue=True, use_csv=use_csv)
                if failure:
                    return lines
                # parse the issue line
                issue_fields = lines.pop(0)
                parsed_data, failure = _parse_issue_line(
                  request, issue_fields,
                  issue_revision.issue.series, changeset_url)
            elif use_json or use_yaml:
                tmpfile = _convert_upload_to_file(request,
                                                  request.FILES['flatfile'])
                if use_yaml:
                    try:
                        issue_data = yaml.safe_load(tmpfile)
                    except yaml.YAMLError as e:
                        error_text = f'Invalid YAML format: {e}'
                        return _handle_import_error(request, changeset_url,
                                                    error_text)
                else:
                    try:
                        issue_data = json.load(tmpfile)
                    except json.JSONDecodeError as e:
                        error_text = f'Invalid JSON format: {e}'
                        return _handle_import_error(request, changeset_url,
                                                    error_text)
                issue_data.pop('variant_name', None)
                parsed_data, failure = _process_issue_data(
                  request, issue_data, issue_revision.series, changeset_url)
            if failure:
                return parsed_data

            for field, value in parsed_data.items():
                if field in ['brand_emblem', 'indicia_printer']:
                    # these are foreign keys, set them differently
                    continue
                setattr(issue_revision, field, value)
            if 'brand_emblem' in parsed_data:
                if parsed_data['brand_emblem']:
                    issue_revision.brand_emblem.set(
                      parsed_data['brand_emblem'])
                else:
                    issue_revision.brand_emblem.clear()
            if 'indicia_printer' in parsed_data:
                if parsed_data['indicia_printer']:
                    issue_revision.indicia_printer.set(
                      parsed_data['indicia_printer'])
                else:
                    issue_revision.indicia_printer.clear()
            issue_revision.save()
            running_number = 0
            issue = Issue.objects.get(id=issue_id)
            if use_json or use_yaml:
                return _import_sequences_structured(
                  request, issue, changeset, issue_data.get('story_set'),
                  running_number)
            else:
                return _import_sequences(request, issue, changeset,
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
            changeset_url = urlresolvers.reverse('edit',
                                                 kwargs={'id': changeset.id})
            use_csv = False
            use_tsv = False
            use_json = False
            use_yaml = False

            if 'csv' in request.POST:
                use_csv = True
            elif 'json' in request.POST:
                use_json = True
            elif 'yaml' in request.POST:
                use_yaml = True
            else:
                use_tsv = True
            running_number = issue_revision.next_sequence_number()
            issue = Issue.objects.get(id=issue_id)
            if use_csv or use_tsv:
                lines, failure = _process_file(request, changeset_url,
                                               is_issue=False, use_csv=use_csv)
                if failure:
                    return lines
                return _import_sequences(request, issue, changeset,
                                         lines, running_number)
            elif use_json or use_yaml:
                tmpfile = _convert_upload_to_file(request,
                                                  request.FILES['flatfile'])
                if use_yaml:
                    try:
                        story_data = yaml.safe_load(tmpfile)
                    except yaml.YAMLError as e:
                        error_text = f'Invalid YAML format: {e}'
                        return _handle_import_error(request, changeset_url,
                                                    error_text)
                else:
                    try:
                        story_data = json.load(tmpfile)
                    except json.JSONDecodeError as e:
                        error_text = f'Invalid JSON format: {e}'
                        return _handle_import_error(request, changeset_url,
                                                    error_text)
                story_data = story_data.get('story_set')
                return _import_sequences_structured(request, issue, changeset,
                                                    story_data, running_number)
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
    filename = str(issue).replace(' ', '_')
    if use_csv:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="%s.csv"' % \
                                          filename
        writer = csv.writer(response)
    export_data = []
    for field_name in ISSUE_FIELDS:
        if field_name == 'brand_emblem':
            if not issue.brand_emblem and not issue.no_brand:
                export_data.append('')
            else:
                brands = issue.brand_emblem.all()
                brand_names = ''
                for brand in brands:
                    brand_names += brand.name + '; '
                brand_names = brand_names[:-2]
                export_data.append(brand_names)
        elif (field_name == 'indicia_publisher' and not
              issue.indicia_publisher and not issue.indicia_pub_not_printed):
            export_data.append('')
        elif field_name == 'editing':
            credit = show_creator_credit(issue, field_name, url=False)
            if credit:
                export_data.append(credit)
            else:
                export_data.append('None')
        elif (field_name in ['indicia_frequency', 'isbn', 'barcode', 'rating',
                             'indicia_printer']
              and not getattr(series, 'has_%s' % field_name)):
            export_data.append('')
        elif field_name == 'title' and not getattr(series, 'has_issue_title'):
            export_data.append('')
        elif field_name in ['indicia_frequency', 'isbn', 'barcode', 'title',
                            'rating'] and getattr(issue, 'no_%s' % field_name):
            export_data.append('None')
        elif field_name == 'indicia_printer':
            export_data.append(issue.show_printer(url=False))
        else:
            export_data.append(str(getattr(issue, field_name)))

    # reprint_links and keywords need extra handling and come last
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
                              'letters', 'editing']:
                credit = show_creator_credit(sequence, field_name, url=False)
                if credit:
                    export_data.append(credit)
                else:
                    export_data.append('None')
            elif field_name == 'title' and sequence.title_inferred:
                export_data.append('[%s]' % sequence.title)
            elif field_name == 'feature':
                export_data.append('%s' % sequence.show_feature_as_text())
            elif field_name == 'characters':
                export_data.append('%s' % sequence.show_characters_as_text())
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
        response = HttpResponse(export.encode(encoding='UTF-8'),
                                content_type='text/tab-separated-values')
        response['Content-Disposition'] = 'attachment; filename="%s.tsv"' % \
                                          filename
    return response
