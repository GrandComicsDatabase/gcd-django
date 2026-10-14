"""Small, transactional API for the changeset sequence workbench."""
import hashlib
import json
from copy import copy
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from apps.gcd.models import StoryType
from apps.gcd.models.story import NO_FEATURE_TYPES, STORY_TYPES
from apps.oi import states
from apps.oi.models import Changeset, StoryRevision, CTYPES
from apps.oi.sequence_validation import (validate_sequence_type_fields,
                                         validate_sequence_page_count)


def duplicate_sequence(source, issue):
    """Duplicate editable values and active dependents, with fresh revision IDs."""
    revision_class = type(source.biblioentryrevision) if hasattr(source, 'biblioentryrevision') else StoryRevision
    original = source.biblioentryrevision if hasattr(source, 'biblioentryrevision') else source
    duplicate = revision_class.clone(original, source.changeset, fork=True,
                                     exclude={'keywords'})
    duplicate.keywords = source.keywords
    duplicate.issue = issue.issue
    duplicate.sequence_number = issue.next_sequence_number()
    if duplicate.type_id == STORY_TYPES['cover']:
        duplicate.type = StoryType.objects.get(name='cover reprint (on interior page)')
    duplicate.save()
    for related in ('story_credit_revisions', 'story_character_revisions',
                    'story_group_revisions'):
        for child in getattr(source, related).filter(deleted=False):
            type(child).clone(child, source.changeset, fork=True,
                              story_revision=duplicate)
    return duplicate


def allowed_sequence_types(story):
    from apps.oi.forms.story import get_story_revision_form
    # Form construction normalizes genre in memory. Do not mutate the model
    # being saved just to obtain the choices for its type field.
    return get_story_revision_form(revision=copy(story)).base_fields['type'].queryset


@permission_required('indexer.can_reserve', raise_exception=True)
@require_POST
@transaction.atomic
def migrate_all_credits(request, id):
    """Migrate active sequence credits together, using the existing converter."""
    changeset = get_object_or_404(Changeset.objects.select_for_update(), pk=id)
    if changeset.indexer_id != request.user.pk or changeset.state != states.OPEN:
        return JsonResponse({'error': 'This changeset is not editable by you.'}, status=403)
    data = None
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except ValueError:
            return JsonResponse({'error': 'Invalid request.'}, status=400)
        if not isinstance(data, dict) or data.get('version') != sequence_version(changeset):
            return JsonResponse({'error': 'Sequences changed. Reload before migrating.'}, status=409)
    stories = changeset.storyrevisions.filter(deleted=False)
    story_id = None
    if data and data.get('story') is not None:
        try:
            story_id = int(data['story'])
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid request.'}, status=400)
        stories = [get_object_or_404(stories, pk=story_id)]
    # Same steps as migrate_story_revision.
    for story in stories:
        if story.old_credits():
            story.migrate_credits()
        if story.feature:
            story.migrate_feature()
    if data is not None:
        rows = []
        for issue in changeset.issuerevisions.all():
            for story in issue.ordered_story_revisions():
                # A single-row migration only needs that row back.
                if story_id is not None and story.pk != story_id:
                    continue
                rows.append({'id': story.pk, 'html': render_to_string(
                    'oi/bits/sequence_row.html', {
                        'story': story, 'issue_revision': issue,
                        'changeset': changeset, 'CTYPES': CTYPES,
                        'sequence_types': StoryType.objects.all(),
                    }, request=request)})
        issues = sequence_snapshot(changeset)
        return JsonResponse({'issues': issues, 'version': sequence_version(changeset), 'rows': rows})
    return redirect('edit', id=changeset.pk)


@permission_required('indexer.can_reserve', raise_exception=True)
@require_POST
def add_sequence(request, id):
    """Create an incomplete editable draft, without leaving the workbench."""
    from apps.oi.forms.story import get_story_revision_form

    try:
        data = json.loads(request.body)
        with transaction.atomic():
            changeset = get_object_or_404(
                Changeset.objects.select_for_update(), pk=id)
            if changeset.indexer_id != request.user.pk or changeset.state != states.OPEN:
                return JsonResponse({'error': 'This changeset is not editable by you.'}, status=403)
            issue = get_object_or_404(changeset.issuerevisions, pk=data['issue'])
            if issue.deleted or (not issue.issue_id and not issue.variant_of_id):
                return JsonResponse({'error': 'Create the issue before adding sequences.'}, status=400)
            if data.get('version') != sequence_version(changeset):
                return JsonResponse({'error': 'Sequences changed in another window. Reload before adding a sequence.'}, status=409)
            if issue.variant_of_id and (
                    issue.active_stories().exists() or issue.variant_cover_status != 3):
                return JsonResponse({'error': 'This variant cannot accept another sequence.'}, status=400)
            if data.get('duplicate') is not None:
                source = get_object_or_404(issue.ordered_story_revisions(),
                                           pk=data['duplicate'], deleted=False)
                story = duplicate_sequence(source, issue)
                return added_sequence_response(request, changeset, issue, story)
            allowed = get_story_revision_form(
                issue_revision=issue, user=request.user).base_fields['type'].queryset
            first = not issue.active_stories().exists()
            preferred = STORY_TYPES['cover'] if first else STORY_TYPES['comic story']
            sequence_type = allowed.filter(pk=preferred).first()
            if sequence_type is None:
                sequence_type = allowed.exclude(pk=STORY_TYPES['cover']).first()
            if sequence_type is None:
                return JsonResponse({'error': 'No sequence type is available for this issue.'}, status=400)
            cover = sequence_type.pk == STORY_TYPES['cover']
            story = StoryRevision(
                title='', feature='', type=sequence_type, page_count=None,
                sequence_number=0 if cover else max(1, issue.next_sequence_number()),
                no_editing=True, no_script=cover)
            story.save_added_revision(changeset=changeset, issue=issue.issue)
            return added_sequence_response(request, changeset, issue, story)
    except (ValueError, TypeError, KeyError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)


def added_sequence_response(request, changeset, issue, story):
    issues = sequence_snapshot(changeset)
    html = render_to_string('oi/bits/sequence_row.html', {
        'story': story, 'issue_revision': issue, 'changeset': changeset,
        'sequence_types': StoryType.objects.all(), 'CTYPES': CTYPES,
    }, request=request)
    return JsonResponse({'issues': issues, 'version': sequence_version(changeset),
                         'row_html': html, 'row_id': story.pk})


def sequence_snapshot(changeset):
    issues = []
    # Allowed types depend only on the issue and the current type.
    allowed = {}
    for issue in changeset.issuerevisions.all():
        rows = []
        for story in issue.ordered_story_revisions().prefetch_related(
                'feature_name', 'feature_logo'):
            key = (story.issue_id, story.type_id)
            if key not in allowed:
                allowed[key] = list(allowed_sequence_types(story)
                                    .values_list('pk', flat=True))
            names = list(story.feature_name.all())
            logos = list(story.feature_logo.all())
            rows.append({
                'id': story.pk, 'title': story.title,
                'feature': story.feature or '; '.join(str(f) for f in names + logos),
                'selected_features': [{'id': f.pk, 'text': str(f)} for f in names],
                'feature_text': story.feature,
                'type': story.type_id, 'pages': str(story.page_count)
                if story.page_count is not None else '',
                'sequence': story.sequence_number, 'deleted': story.deleted,
                'allowed_types': allowed[key],
            })
        declared = issue.page_count
        issues.append({'id': issue.pk, 'rows': rows,
                       'declared': str(declared) if declared is not None else None})
    return issues


def sequence_version(changeset):
    """Version of the sequence data the workbench edits, in two queries.

    Every path that changes a sequence saves its revision, which updates
    ``modified``; of the issue, the workbench shows only the page count.
    """
    issues = list(changeset.issuerevisions.order_by('pk')
                  .values_list('pk', 'page_count'))
    stories = list(changeset.storyrevisions.order_by('pk')
                   .values_list('pk', 'modified'))
    return hashlib.sha256(repr((issues, stories)).encode()).hexdigest()


def workbench_context(changeset):
    issues = sequence_snapshot(changeset)
    return {'sequence_types': StoryType.objects.all(),
            'sequence_workbench': {'issues': issues,
                                   'version': sequence_version(changeset),
                                   'coverType': STORY_TYPES['cover'],
                                   'noFeatureTypes': NO_FEATURE_TYPES}}


def available_feature_names(changeset, issue_id, type_id):
    """Use the full editor's feature search restrictions for inline edits."""
    from apps.select.views import FeatureNameAutocomplete
    issue = changeset.issuerevisions.get(pk=issue_id)
    lookup = SimpleNamespace(q='', forwarded={
        'language_code': issue.series.language.code, 'type': type_id})
    return FeatureNameAutocomplete.get_queryset(lookup, interactive=False)


def validate_pages(value):
    try:
        pages = Decimal(str(value))
        if not pages.is_finite() or pages <= 0:
            raise ValueError('Pages must be a positive number.')
        StoryRevision._meta.get_field('page_count').clean(pages, None)
        return pages
    except (InvalidOperation, ValidationError) as exc:
        raise ValueError('Pages must be positive, with at most three decimal places.') from exc


def page_text(page_count):
    """The page count as the workbench sends it back when it is not edited."""
    return str(page_count) if page_count is not None else ''


def sequence_changes(issue, rows, types):
    """Compare the rows of one issue with the database, without writing.

    Returns (story, values) for each row that differs, with ``values`` holding
    the type, number, title, pages and, when edited, the features to save.
    """
    stories = {story.pk: story for story in
               issue.ordered_story_revisions().prefetch_related('feature_name')}
    if len(rows) != len(stories) or {row.get('id') for row in rows} != set(stories):
        raise ValueError('The sequence list has changed.')
    reprint_type = next((pk for pk, name in types.items()
                         if name == 'cover reprint (on interior page)'), None)
    cover_seen = False
    sequence = int(any(not row['deleted'] and
                       int(row['type']) == STORY_TYPES['cover'] for row in rows))
    changes = []
    for row in rows:
        if not isinstance(row.get('title'), str) or not isinstance(row.get('feature'), str):
            raise ValueError('Title and feature must be text.')
        story = stories[row['id']]
        if row['deleted'] != story.deleted:
            raise ValueError('Use the sequence deletion action.')
        if story.deleted:
            continue
        type_id = int(row['type'])
        if type_id not in types:
            raise ValueError('Unknown sequence type.')
        if type_id == STORY_TYPES['cover']:
            if cover_seen:
                if reprint_type is None:
                    raise ValueError('Cover reprint type is unavailable.')
                type_id = reprint_type
            cover_seen = True
        number = 0 if type_id == STORY_TYPES['cover'] else sequence
        if type_id != STORY_TYPES['cover']:
            sequence += 1
        title = StoryRevision._meta.get_field('title').clean(row['title'], story)
        pages = story.page_count
        if row['pages'] != page_text(story.page_count):
            pages = None if row['pages'] == '' else validate_pages(row['pages'])
        names = {name.pk for name in story.feature_name.all()}
        features = None
        if type_id in NO_FEATURE_TYPES:
            if type_id != story.type_id or story.feature or names:
                features = ('', set())
        else:
            text = row.get('feature_text', '')
            if not isinstance(text, str):
                raise ValueError('Title and feature must be text.')
            ids = {int(item['id']) for item in row.get('selected_features') or []}
            # Rows whose feature was not edited are left as they are.
            if ids != names or text != story.feature:
                features = (text.strip(), ids)
        if (type_id, number, title, pages) != (story.type_id, story.sequence_number,
                                               story.title, story.page_count) \
           or features is not None:
            changes.append((story, {'issue': issue.pk, 'type': type_id,
                                    'number': number, 'title': title,
                                    'pages': pages, 'features': features}))
    return changes


def save_sequence_change(changeset, story, values):
    """Validate and save one changed row, with the full editor's rules.

    Returns True when the type changed, so the caller can send the new type
    choices of the row.
    """
    type_id = values['type']
    type_changed = type_id != story.type_id
    pages_changed = values['pages'] != story.page_count
    # Respect the same issue/series type restrictions as the full editor.
    if type_changed and not allowed_sequence_types(story).filter(pk=type_id).exists():
        raise ValueError('Sequence type is not allowed for this issue.')
    story.type_id = type_id
    story.sequence_number = values['number']
    story.title = values['title']
    story.page_count = values['pages']
    if values['features'] is not None:
        text, ids = values['features']
        if type_id in NO_FEATURE_TYPES:
            story.feature = ''
            story.feature_name.clear()
            story.feature_logo.clear()
            story.feature_object.clear()
        else:
            available = available_feature_names(changeset, values['issue'], type_id)
            names = list(available.filter(pk__in=ids))
            if len(names) != len(ids):
                raise ValueError('The selected features are not available for this language and sequence type.')
            if names and text:
                raise ValueError('Use either linked feature names or free text, as in the full editor.')
            story.feature = StoryRevision._meta.get_field('feature').clean(text, story)
            story.feature_name.set(names)
            story.feature_logo.clear()
            story.feature_object.set([name.feature_id for name in names])
    # Drafts may have incomplete credits, but changing type
    # must not silently preserve incompatible hidden data.
    try:
        # A new sequence starts without a page count, which
        # must not block saving other rows.
        if pages_changed or type_changed:
            validate_sequence_page_count({
                'type': story.type,
                'page_count': story.page_count,
                'page_count_uncertain': story.page_count_uncertain,
            })
        if type_changed or values['features'] is not None:
            validate_sequence_type_fields({
                'type': story.type, 'feature': story.feature,
                'feature_name': story.feature_name.all(),
                'feature_logo': story.feature_logo.all(),
                'genre': story.genre,
                'story_arc': story.story_arc.all(),
            })
    except ValidationError as exc:
        raise ValueError(
            'Sequence %s (%s): %s Use Edit to update the related fields before changing type.'
            % (story.sequence_number, story.type.name, ' '.join(exc.messages))) from exc
    story.save()
    return type_changed


@permission_required('indexer.can_reserve', raise_exception=True)
@require_POST
def save_sequences(request, id):
    """Save the workbench rows, writing only those that differ from the database."""
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or not isinstance(data.get('issues'), list):
            raise ValueError('Invalid sequence data.')
        with transaction.atomic():
            changeset = get_object_or_404(Changeset.objects.select_for_update(), pk=id)
            if changeset.indexer_id != request.user.pk or changeset.state != states.OPEN:
                return JsonResponse({'error': 'This changeset is not editable by you.'}, status=403)
            issues = list(changeset.issuerevisions.all())
            if [i.get('id') for i in data['issues']] != [i.pk for i in issues]:
                raise ValueError('The issue list has changed.')
            types = dict(StoryType.objects.values_list('pk', 'name'))
            changes = []
            for incoming, issue in zip(data['issues'], issues):
                changes += sequence_changes(issue, incoming['rows'], types)
            version = sequence_version(changeset)
            # Nothing to write, as for a retry after a lost response.
            if not changes:
                return JsonResponse({'version': version, 'allowed': {}})
            if data.get('version') != version:
                return JsonResponse({'error': 'Sequences changed in another window. Reload the page.'}, status=409)
            allowed = {}
            for story, values in changes:
                if save_sequence_change(changeset, story, values):
                    # The type choices of a row depend on its current type.
                    allowed[story.pk] = list(allowed_sequence_types(story)
                                             .values_list('pk', flat=True))
            return JsonResponse({'version': sequence_version(changeset), 'allowed': allowed})
    except (ValueError, TypeError, KeyError, OverflowError, ValidationError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)
