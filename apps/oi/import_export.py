# -*- coding: utf-8 -*-
"""
Import and export of issues with their sequences in four formats, CSV, TSV,
JSON and YAML. All formats carry the same record, see apps.oi.interchange.
An import is checked and resolved completely before any revision is created,
so that it either succeeds as a whole or fails without changes.
"""
import csv
import io
import json
import re

import chardet
import yaml

import django.urls as urlresolvers
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.html import conditional_escape as esc
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.indexer.views import render_error
from apps.gcd.models import Issue, Series, Universe
from apps.oi.models import (
    Changeset, StoryRevision, IssueRevision, CTYPES, IssueCreditRevision,
    StoryCreditRevision)
from apps.oi import states
from apps.oi.interchange import (
    CREDIT_FIELDS, ISSUE_CREDIT_FIELDS, ISSUE_FIELDS, STORY_FIELDS,
    NotationError, RecordDecoder, RecordImporter, Resolver, check_text,
    create_credits, create_revisions, flat_rows, issue_record,
    read_flat_records, set_multi)


class ImportFailure(Exception):
    pass


def _handle_import_error(request, return_url, error_text):
    return render_error(
        request,
        '%s Back to the <a href="%s">editing page</a>.' %
        (esc(error_text), return_url),
        is_safe=True)


def _file_format(request):
    for file_format in ('csv', 'json', 'yaml'):
        if file_format in request.POST:
            return file_format
    return 'tsv'


def _read_upload(request_file):
    content = b''.join(request_file.chunks())
    try:
        return content.decode('utf-8-sig')
    except UnicodeDecodeError:
        return content.decode(chardet.detect(content)['encoding'])


def _read_records(request_file, file_format, sequences_only=False):
    """
    Returns the decoded records of the file as a list of the issue values
    and the list of sequence values.
    """
    text = _read_upload(request_file)
    try:
        if file_format in ('csv', 'tsv'):
            decoder = RecordDecoder(flat=True)
            # control characters in cells are escaped, any line break ends
            # a row
            if file_format == 'csv':
                rows = list(csv.reader(io.StringIO(text, newline='')))
            else:
                # only line breaks end a row, the other separators of
                # str.splitlines are text
                rows = [line.split('\t')
                        for line in re.split('\r\n|\n|\r', text)]
            records = []
            for issue, line, sequences in read_flat_records(
                                            rows, sequences_only):
                records.append((
                  decoder.decode(issue, ISSUE_FIELDS, ISSUE_CREDIT_FIELDS,
                                 'line %d' % line) if issue else None,
                  [decoder.decode(sequence, STORY_FIELDS, CREDIT_FIELDS,
                                  'line %d' % sequence_line)
                   for sequence, sequence_line in sequences]))
            return records
        decoder = RecordDecoder(flat=False)
        try:
            data = yaml.safe_load(text) if file_format == 'yaml' \
                   else json.loads(text)
        except (yaml.YAMLError, json.JSONDecodeError) as error:
            raise ImportFailure('Invalid %s format: %s' % (
              file_format.upper(), error))
        if isinstance(data, dict) and 'issue_set' in data:
            issues = data['issue_set']
            paths = ['issue_set[%d]' % number for number in range(
                     len(issues) if isinstance(issues, list) else 0)]
        else:
            issues = [data]
            paths = ['issue']
        if not isinstance(issues, list) or not issues:
            raise ImportFailure('The file contains no issue.')
        records = []
        for issue, path in zip(issues, paths):
            if not isinstance(issue, dict):
                raise ImportFailure('%s is not an issue.' % path)
            stories = issue.get('story_set') or []
            if not isinstance(stories, list):
                raise ImportFailure('%s.story_set is not a list.' % path)
            if sequences_only:
                values = None
            else:
                values = decoder.decode(issue, ISSUE_FIELDS,
                                        ISSUE_CREDIT_FIELDS, path)
            records.append((values, [
              decoder.decode(story, STORY_FIELDS, CREDIT_FIELDS,
                             '%s.story_set[%d]' % (path, number))
              for number, story in enumerate(stories)]))
        return records
    except NotationError as error:
        raise ImportFailure(str(error))


def _resolve(importer, records):
    """
    Resolves all records before anything is created.
    """
    resolved = []
    for issue, stories in records:
        resolved.append((importer.issue(issue) if issue else None,
                         [importer.story(story) for story in stories]))
    try:
        importer.check()
    except NotationError as error:
        raise ImportFailure(str(error))
    return resolved


def _create_stories(changeset, issue, stories, running_number):
    for values, multi, credits, characters in stories:
        story_revision = StoryRevision(
          changeset=changeset, issue=issue, sequence_number=running_number,
          **values)
        story_revision.save()
        set_multi(story_revision, multi)
        create_credits(StoryCreditRevision, credits, changeset=changeset,
                       story_revision=story_revision)
        create_revisions(story_revision, *characters)
        running_number += 1


def _set_issue_values(issue_revision, values, multi, credits):
    for name, value in values.items():
        setattr(issue_revision, name, value)
    issue_revision.save()
    set_multi(issue_revision, multi)
    for credit in issue_revision.issue_credit_revisions.filter(deleted=False):
        if credit.source:
            credit.deleted = True
            credit.save()
        else:
            credit.delete()
    create_credits(IssueCreditRevision, credits,
                   changeset=issue_revision.changeset,
                   issue_revision=issue_revision)


def _base_issue(series, values):
    base = Issue.objects.filter(series=series, number=values['variant_of'],
                                variant_of=None, deleted=False)
    if base.count() != 1:
        raise ImportFailure('Could not find base issue %s for variant %s.' % (
          values['variant_of'], values['variant_name']))
    return base.get()


@permission_required('indexer.can_reserve')
def import_issues_to_series(request, series_id):
    series = get_object_or_404(Series, id=series_id)
    series_url = urlresolvers.reverse('add_issues',
                                      kwargs={'series_id': series.id})
    if request.method != 'POST' or 'file' not in request.FILES:
        return HttpResponseRedirect(
          urlresolvers.reverse('show_series', kwargs={'series_id': series.id}))
    try:
        records = _read_records(request.FILES['file'], _file_format(request))
        bases = [_base_issue(series, issue) if issue['variant_of'] else None
                 for issue, stories in records]
        resolved = _resolve(RecordImporter(series), records)
        with transaction.atomic():
            for base, (issue, stories) in zip(bases, resolved):
                values, multi, credits = issue
                if base:
                    variants = base.variant_set.order_by('-sort_code')
                    after = variants[0] if variants else base
                else:
                    after = series.last_issue
                changeset = Changeset(indexer=request.user, state=states.OPEN,
                                      change_type=CTYPES['issue_add'])
                changeset.save()
                issue_revision = IssueRevision(changeset=changeset,
                                               series=series, after=after,
                                               variant_of=base)
                _set_issue_values(issue_revision, values, multi, credits)
                # stories of a variant added with its issue have no issue
                _create_stories(changeset, None, stories, 0)
    except ImportFailure as error:
        return _handle_import_error(request, series_url, str(error))
    return HttpResponseRedirect(urlresolvers.reverse('editing'))


@permission_required('indexer.can_reserve')
def import_issue_from_file(request, issue_id, changeset_id, use_csv=False):
    changeset = get_object_or_404(Changeset, id=changeset_id)
    if request.user != changeset.indexer:
        return render_error(request,
                            'Only the reservation holder may import issue '
                            'data.')
    changeset_url = urlresolvers.reverse('edit', kwargs={'id': changeset.id})
    if request.method != 'POST' or 'flatfile' not in request.FILES:
        return HttpResponseRedirect(changeset_url)
    try:
        issue_revision = changeset.issuerevisions.get(issue=issue_id)
    except IssueRevision.DoesNotExist:
        return render_error(
          request, 'Could not find issue for id %s and changeset %s'
          % (issue_id, changeset_id))
    if StoryRevision.objects.filter(changeset=changeset).count():
        return render_error(
          request,
          'There are already sequences present for %s in this'
          ' changeset. Back to the <a href="%s">editing page</a>.'
          % (esc(issue_revision), changeset_url),
          is_safe=True)
    try:
        records = _read_records(request.FILES['flatfile'],
                                _file_format(request))
        if len(records) != 1:
            raise ImportFailure('The file must contain exactly one issue.')
        (issue, stories), = _resolve(
          RecordImporter(issue_revision.series), records)
        with transaction.atomic():
            _set_issue_values(issue_revision, *issue)
            _create_stories(changeset, issue_revision.issue, stories, 0)
    except ImportFailure as error:
        return _handle_import_error(request, changeset_url, str(error))
    return HttpResponseRedirect(changeset_url)


@permission_required('indexer.can_reserve')
def import_sequences_from_file(request, issue_id, changeset_id, use_csv=False):
    changeset = get_object_or_404(Changeset, id=changeset_id)
    if request.user != changeset.indexer:
        return render_error(request,
                            'Only the reservation holder may import stories.')
    changeset_url = urlresolvers.reverse('edit', kwargs={'id': changeset.id})
    if request.method != 'POST' or 'flatfile' not in request.FILES:
        return HttpResponseRedirect(changeset_url)
    try:
        issue_revision = changeset.issuerevisions.get(issue=issue_id)
    except IssueRevision.DoesNotExist:
        return render_error(
          request, 'Could not find issue for id %s and changeset %s'
          % (issue_id, changeset_id))
    try:
        records = _read_records(request.FILES['flatfile'],
                                _file_format(request), sequences_only=True)
        stories = [story for issue, stories in _resolve(
                     RecordImporter(issue_revision.series), records)
                   for story in stories]
        with transaction.atomic():
            _create_stories(changeset, issue_revision.issue, stories,
                            issue_revision.next_sequence_number())
    except ImportFailure as error:
        return _handle_import_error(request, changeset_url, str(error))
    return HttpResponseRedirect(changeset_url)


@permission_required('indexer.can_reserve')
@require_POST
def check_characters(request, series_id):
    """
    The problems of the characters field of a sequence of the series while
    it is typed, and the text the migration would save.
    """
    series = get_object_or_404(Series, id=series_id)
    universes = Universe.objects.filter(
      id__in=[value for value in request.POST.getlist('universe')
              if value.isdigit()])
    problems, text = check_text(
      request.POST.get('characters', '').strip(),
      Resolver(series.language, series),
      universes.get() if universes.count() == 1 else None)
    return render(request, 'oi/bits/characters_check.html',
                  {'problems': problems, 'text': text})


def _export_object(issue_id, revision):
    if revision:
        return get_object_or_404(IssueRevision, id=issue_id)
    return get_object_or_404(Issue, id=issue_id)


@permission_required('indexer.can_reserve')
def export_issue_to_file(request, issue_id, use_csv=False, revision=False):
    issue = _export_object(issue_id, revision)
    rows = flat_rows(issue_record(issue, revision=revision))
    filename = str(issue).replace(' ', '_')
    if use_csv:
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="%s.csv"' % \
                                          filename
        csv.writer(response).writerows(rows)
        return response
    export = ''.join('\t'.join(row) + '\r\n' for row in rows)
    response = HttpResponse(export.encode('utf-8'),
                            content_type='text/tab-separated-values; '
                                         'charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="%s.tsv"' % \
                                      filename
    return response


@permission_required('indexer.can_reserve')
def export_issue_to_structured_file(request, issue_id, use_yaml=False,
                                    revision=False):
    issue = _export_object(issue_id, revision)
    data = issue_record(issue, revision=revision)
    filename = str(issue).replace(' ', '_')
    if use_yaml:
        response = HttpResponse(
          yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
          content_type='application/yaml; charset=utf-8')
        response['Content-Disposition'] = \
            'attachment; filename="%s.yaml"' % filename
    else:
        response = HttpResponse(
          json.dumps(data, ensure_ascii=False, indent=2),
          content_type='application/json; charset=utf-8')
        response['Content-Disposition'] = \
            'attachment; filename="%s.json"' % filename
    return response
