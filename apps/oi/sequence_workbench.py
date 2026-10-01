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


def reprint_validation_errors(changeset, story, request):
    """Use submission validation, including the selected unchanged sequence."""
    from apps.oi.views import validate_changeset_revisions, validate_revision_for_transition
    errors = validate_changeset_revisions(changeset, request)
    if story and not any(revision == story for revision, _ in errors):
        messages = validate_revision_for_transition(story, request)
        if messages:
            errors.append((story, messages))
    return errors


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
    for story in changeset.storyrevisions.filter(deleted=False):
        if story.old_credits():
            story.migrate_credits()
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
            if data.get('version') != snapshot_version(sequence_snapshot(changeset)):
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
                title='', feature='', type=sequence_type, page_count=1,
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
    return JsonResponse({'issues': issues, 'version': snapshot_version(issues),
                         'row_html': html, 'row_id': story.pk})


def sequence_snapshot(changeset):
    issues = []
    for issue in changeset.issuerevisions.all():
        rows = []
        for story in issue.ordered_story_revisions().prefetch_related(
                'feature_name', 'feature_logo'):
            names = list(story.feature_name.all())
            logos = list(story.feature_logo.all())
            rows.append({
                'id': story.pk, 'title': story.title,
                'feature': story.feature or '; '.join(str(f) for f in names + logos),
                'feature_names': [f.pk for f in names],
                'selected_features': [{'id': f.pk, 'text': str(f)} for f in names],
                'feature_text': story.feature,
                'selected_feature': names[0].pk if len(names) == 1 and not logos and not story.feature else None,
                'feature_logos': [f.pk for f in logos],
                'type': story.type_id, 'pages': str(story.page_count)
                if story.page_count is not None else '',
                'sequence': story.sequence_number, 'deleted': story.deleted,
                'allowed_types': list(allowed_sequence_types(story).values_list('pk', flat=True)),
            })
        declared = issue.page_count
        issues.append({'id': issue.pk, 'rows': rows,
                       'declared': str(declared) if declared is not None else None})
    return issues


def snapshot_version(issues):
    return hashlib.sha256(json.dumps(issues, sort_keys=True).encode()).hexdigest()


def workbench_context(changeset, request=None):
    issues = sequence_snapshot(changeset)
    issue_revisions = list(changeset.issuerevisions.all())
    if request is not None and changeset.indexer_id == request.user.pk and changeset.state == states.OPEN:
        from apps.oi.views import sequence_selection_url
        for issue in issue_revisions:
            if issue.issue_id and not issue.variant_of_id:
                issue.sequence_copy_url = sequence_selection_url(request, issue)
    return {'workbench_issues': issue_revisions,
            'sequence_types': StoryType.objects.all(),
            'sequence_workbench': {'issues': issues,
                                   'version': snapshot_version(issues),
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


@permission_required('indexer.can_reserve', raise_exception=True)
@require_POST
def save_sequences(request, id):
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or not isinstance(data.get('issues'), list):
            raise ValueError('Invalid sequence data.')
        with transaction.atomic():
            changeset = get_object_or_404(Changeset.objects.select_for_update(), pk=id)
            if changeset.indexer_id != request.user.pk or changeset.state != states.OPEN:
                return JsonResponse({'error': 'This changeset is not editable by you.'}, status=403)
            current = sequence_snapshot(changeset)
            version = snapshot_version(current)
            # A retry after a lost response is safe and idempotent.
            if data['issues'] == current:
                return JsonResponse({'version': version, 'issues': current})
            if data.get('version') != version:
                return JsonResponse({'error': 'Sequences changed in another window. Your local draft is retained. Reload and reconcile it before saving.'}, status=409)
            if [i['id'] for i in data['issues']] != [i['id'] for i in current]:
                raise ValueError('The issue list has changed.')
            types = dict(StoryType.objects.values_list('pk', 'name'))
            reprint_type = next((pk for pk, name in types.items()
                                 if name == 'cover reprint (on interior page)'), None)
            for incoming, original in zip(data['issues'], current):
                before = {r['id']: r for r in original['rows']}
                rows = incoming['rows']
                if len(rows) != len(before) or {r['id'] for r in rows} != set(before):
                    raise ValueError('The sequence list has changed.')
                revisions = {r.pk: r for r in changeset.storyrevisions.filter(pk__in=before)}
                cover_seen = False
                sequence = int(any(not row['deleted'] and
                                   int(row['type']) == STORY_TYPES['cover']
                                   for row in rows))
                for row in rows:
                    if not isinstance(row.get('title'), str) or not isinstance(row.get('feature'), str):
                        raise ValueError('Title and feature must be text.')
                    old = before[row['id']]
                    story = revisions[row['id']]
                    if row['deleted'] != old['deleted']:
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
                    # Respect the same issue/series type restrictions as the full editor.
                    if type_id != story.type_id:
                        if not allowed_sequence_types(story).filter(pk=type_id).exists():
                            raise ValueError('Sequence type is not allowed for this issue.')
                    story.type_id = type_id
                    story.sequence_number = 0 if type_id == STORY_TYPES['cover'] else sequence
                    if type_id != STORY_TYPES['cover']:
                        sequence += 1
                    story.title = StoryRevision._meta.get_field('title').clean(row['title'], story)
                    if row['pages'] != old['pages']:
                        story.page_count = None if row['pages'] == '' else validate_pages(row['pages'])
                    # Preserve linked feature records when the text was not edited.
                    if type_id in NO_FEATURE_TYPES:
                        story.feature = ''
                        story.feature_name.clear()
                        story.feature_logo.clear()
                        story.feature_object.clear()
                    elif 'selected_features' in row and (row['selected_features'] != old['selected_features'] or row.get('feature_text') != old['feature_text']):
                        features = available_feature_names(changeset, incoming['id'], type_id)
                        ids = {int(item['id']) for item in row['selected_features']}
                        names = list(features.filter(pk__in=ids))
                        if len(names) != len(ids):
                            raise ValueError('The selected features are not available for this language and sequence type.')
                        text = row.get('feature_text', '').strip()
                        if names and text:
                            raise ValueError('Use either linked feature names or free text, as in the full editor.')
                        story.feature = StoryRevision._meta.get_field('feature').clean(text, story)
                        story.feature_name.set(names)
                        story.feature_logo.clear()
                        story.feature_object.set([name.feature_id for name in names])
                    elif row.get('selected_feature') is not None and (
                            row.get('selected_feature') != old.get('selected_feature') or
                            row['feature'] != old['feature']):
                        features = available_feature_names(changeset, incoming['id'], type_id)
                        name = features.filter(
                            pk=row['selected_feature']).first()
                        if name is None:
                            raise ValueError('The selected feature is not available for this language and sequence type.')
                        story.feature = ''
                        story.feature_name.set([name])
                        story.feature_logo.clear()
                        story.feature_object.set([name.feature])
                    elif row['feature'] != old['feature'] or row.get('selected_feature') != old.get('selected_feature'):
                        story.feature = StoryRevision._meta.get_field('feature').clean(row['feature'].strip(), story)
                        story.feature_name.clear()
                        story.feature_logo.clear()
                        story.feature_object.clear()
                    # Drafts may have incomplete credits, but changing type
                    # must not silently preserve incompatible hidden data.
                    try:
                        validate_sequence_page_count({
                            'type': story.type, 'page_count': story.page_count,
                            'page_count_uncertain': story.page_count_uncertain,
                        })
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
            saved = sequence_snapshot(changeset)
            return JsonResponse({'version': snapshot_version(saved), 'issues': saved})
    except (ValueError, TypeError, KeyError, OverflowError, ValidationError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)
