from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from django.core import signing
from django.core.cache.backends.locmem import LocMemCache
from django.http import HttpResponse
from django.test import RequestFactory
from django.template.loader import get_template

from apps.gcd.models import STORY_TYPES
from apps.oi import states
from apps.oi.views import copy_cached_sequences


@pytest.fixture
def copy_context():
    user = SimpleNamespace(id=1)
    changeset = SimpleNamespace(id=10, indexer=user, state=states.OPEN)
    existing = [MagicMock(id=100, type_id=STORY_TYPES['comic story'], sequence_number=0),
                MagicMock(id=101, type_id=STORY_TYPES['comic story'], sequence_number=1)]
    issue = MagicMock(id=20, changeset_id=10)
    issue.active_stories.return_value = existing
    sources = [SimpleNamespace(id=7, type_id=STORY_TYPES['comic story'],
                               type=SimpleNamespace(name='comic story')),
               SimpleNamespace(id=8, type_id=STORY_TYPES['comic story'],
                               type=SimpleNamespace(name='comic story'))]
    data = {'issue_revision_id': 20, 'story': True, 'sequence_number': 1}
    with ExitStack() as stack:
        stack.enter_context(patch('apps.oi.views.IssueRevision.objects.select_for_update'))
        stack.enter_context(patch('apps.oi.views.get_object_or_404', return_value=issue))
        locked = stack.enter_context(patch('apps.oi.views.Changeset.objects.select_for_update'))
        locked.return_value.get.return_value = changeset
        receipts = stack.enter_context(patch(
            'apps.oi.views.cache', wraps=LocMemCache(uuid4().hex, {})))
        callbacks = []
        stack.enter_context(patch('apps.oi.views.transaction.on_commit',
                                  side_effect=callbacks.append))
        queryset = MagicMock()
        queryset.__iter__.side_effect = lambda: iter(sources)
        queryset.select_for_update.return_value = queryset
        def filter_sources(**kwargs):
            queryset.__iter__.side_effect = lambda: iter(
                s for s in sources if s.id in kwargs['id__in'])
            return queryset
        stack.enter_context(patch('apps.oi.views.Story.objects.filter', side_effect=filter_sources))
        copier = stack.enter_context(patch('apps.oi.views.StoryRevision.copied_revision'))
        copier.side_effect = lambda *a, **kw: MagicMock(sequence_number=99)
        render = stack.enter_context(patch('apps.oi.views.oi_render', return_value=HttpResponse()))
        yield SimpleNamespace(user=user, issue=issue, data=data, sources=sources,
                              existing=existing, receipts=receipts, copier=copier,
                              render=render, callbacks=callbacks)


def request_for(context, post):
    request = RequestFactory().post('/select_object/batch/', post)
    request.user = context.user
    request.session = {'cached_stories': [8, 7]}
    return request


def confirmation(context):
    operation_id = uuid4().hex
    context.receipts.set('story-copy:20:' + operation_id, 'ready', timeout=3600)
    context.receipts.reset_mock()
    return signing.dumps({'select_key': 'batch', 'issue_revision_id': 20,
                          'operation_id': operation_id,
                          'kind': 'story', 'ids': [8, 7]},
                         salt='copy-cached-sequences')


def test_bulk_copy_preview_uses_cache_order_without_writing(copy_context):
    c = copy_context
    request = request_for(c, {'copy_selected_cached_objects': 'story',
                             'cached_objects': ['story_7', 'story_8', 'story_7']})
    copy_cached_sequences.__wrapped__(request, c.data, 'batch')
    context = c.render.call_args.args[2]
    assert [story.id for story in context['stories']] == [8, 7]
    assert context['issue_revision'] == c.issue
    assert context['sequence_number'] == 1
    c.copier.assert_not_called()
    c.receipts.delete.assert_not_called()
    get_template('oi/edit/confirm_copy_sequence.html')


def test_distinct_operations_with_same_selection_key_copy_independently(copy_context):
    c = copy_context
    tokens = []
    for _ in range(2):
        request = request_for(c, {'copy_selected_cached_objects': 'story',
                                 'cached_objects': ['story_7', 'story_8']})
        copy_cached_sequences.__wrapped__(request, c.data, 'batch')
        tokens.append(c.render.call_args.args[2]['copy_batch'])
    assert tokens[0] != tokens[1]
    for token in tokens:
        request = request_for(c, {'confirm_bulk_copy': '1', 'copy_batch': token})
        for _ in range(2):
            assert copy_cached_sequences.__wrapped__(request, c.data, 'batch').status_code == 302
            for callback in c.callbacks:
                callback()
            c.callbacks.clear()
    assert c.copier.call_count == 4
    assert c.receipts.delete.call_count == 2


def test_legacy_confirmation_without_operation_id_is_rejected(copy_context):
    c = copy_context
    token = signing.dumps({'select_key': 'batch', 'issue_revision_id': 20,
                           'kind': 'story', 'ids': [8, 7]},
                          salt='copy-cached-sequences')
    response = copy_cached_sequences.__wrapped__(request_for(c, {
        'confirm_bulk_copy': '1', 'copy_batch': token}), c.data, 'batch')
    assert response.status_code == 400
    c.copier.assert_not_called()
    c.receipts.delete.assert_not_called()


def test_evicted_confirmation_cannot_copy_again(copy_context):
    c = copy_context
    token = confirmation(c)
    c.receipts.clear()
    response = copy_cached_sequences.__wrapped__(request_for(c, {
        'confirm_bulk_copy': '1', 'copy_batch': token}), c.data, 'batch')
    assert response.status_code == 400
    c.copier.assert_not_called()


def test_failed_copy_does_not_mark_done_or_allow_replay(copy_context):
    c = copy_context
    token = confirmation(c)
    request = request_for(c, {'confirm_bulk_copy': '1', 'copy_batch': token})
    c.copier.side_effect = RuntimeError('Copy failed')
    with pytest.raises(RuntimeError, match='Copy failed'):
        copy_cached_sequences.__wrapped__(request, c.data, 'batch')
    assert not c.callbacks
    assert copy_cached_sequences.__wrapped__(request, c.data, 'batch').status_code == 400
    assert c.copier.call_count == 1


def test_submission_before_commit_cannot_copy_twice(copy_context):
    c = copy_context
    request = request_for(c, {'confirm_bulk_copy': '1', 'copy_batch': confirmation(c)})
    assert copy_cached_sequences.__wrapped__(request, c.data, 'batch').status_code == 302
    assert copy_cached_sequences.__wrapped__(request, c.data, 'batch').status_code == 400
    assert c.copier.call_count == 2


def test_bulk_copy_preview_uses_manual_order_instead_of_eviction_order(copy_context):
    c = copy_context
    request = request_for(c, {'copy_selected_cached_objects': 'story',
                             'cached_objects': ['story_8', 'story_7']})
    request.session['cached_stories_order'] = [7, 8]
    copy_cached_sequences.__wrapped__(request, c.data, 'batch')
    assert [s.id for s in c.render.call_args.args[2]['stories']] == [7, 8]


def test_bulk_copy_confirmation_applies_options_order_and_receipt(copy_context):
    c = copy_context
    request = request_for(c, {'confirm_bulk_copy': '1', 'copy_batch': confirmation(c),
                             'copy_characters': 'on', 'copy_credit_info': 'on'})
    response = copy_cached_sequences.__wrapped__(request, c.data, 'batch')
    assert response.status_code == 302
    assert [call.args[0].id for call in c.copier.call_args_list] == [8, 7]
    assert all(call.kwargs['copy_characters'] and call.kwargs['copy_credit_info']
               for call in c.copier.call_args_list)
    assert c.existing[1].sequence_number == 3
    c.receipts.delete.assert_called_once()
    for callback in c.callbacks:
        callback()
    copy_cached_sequences.__wrapped__(request, c.data, 'batch')
    assert c.copier.call_count == 2


@pytest.mark.parametrize('post', [
    {'copy_selected_cached_objects': 'story', 'cached_objects': ['story_7', 'cover_8']},
    {'copy_selected_cached_objects': 'story', 'cached_objects': ['story_999']},
    {'copy_selected_cached_objects': 'story', 'cached_objects': []},
    {'confirm_bulk_copy': '1', 'copy_batch': 'tampered'},
])
def test_invalid_bulk_copy_never_writes(copy_context, post):
    c = copy_context
    response = copy_cached_sequences.__wrapped__(request_for(c, post), c.data, 'batch')
    assert response.status_code == 400
    c.copier.assert_not_called()
    c.receipts.delete.assert_not_called()


def test_unavailable_source_aborts_whole_copy(copy_context):
    c = copy_context
    c.sources.pop()
    response = copy_cached_sequences.__wrapped__(request_for(c, {
        'confirm_bulk_copy': '1', 'copy_batch': confirmation(c)}), c.data, 'batch')
    assert response.status_code == 400
    c.copier.assert_not_called()


def test_other_user_cannot_copy(copy_context):
    c = copy_context
    request = request_for(c, {'confirm_bulk_copy': '1', 'copy_batch': confirmation(c)})
    request.user = SimpleNamespace(id=2)
    with patch('apps.oi.views.render_error', return_value=HttpResponse(status=403)):
        response = copy_cached_sequences.__wrapped__(request, c.data, 'batch')
    assert response.status_code == 403
    c.copier.assert_not_called()


def test_mixed_copy_places_one_cover_at_zero_and_keeps_story_order(copy_context):
    c = copy_context
    c.sources.append(SimpleNamespace(id=9, type_id=STORY_TYPES['cover']))
    request = request_for(c, {
        'copy_selected_cached_objects': 'story',
        'cached_objects': ['story_7', 'story_8'], 'selected_cover': 'cover_9'})
    request.session['cached_covers'] = [9]
    copy_cached_sequences.__wrapped__(request, c.data, 'batch')
    context = c.render.call_args.args[2]
    assert [s.id for s in context['stories']] == [9, 8, 7]
    assert context['has_cover'] is True
    created = []
    def record_copy(*args, **kwargs):
        revision = MagicMock(sequence_number=99)
        created.append(revision)
        return revision
    c.copier.side_effect = record_copy
    confirm = request_for(c, {'confirm_bulk_copy': '1',
                              'copy_batch': context['copy_batch']})
    response = copy_cached_sequences.__wrapped__(confirm, c.data, 'batch')
    assert response.status_code == 302
    assert [r.sequence_number for r in created] == [0, 2, 3]
    assert [r.sequence_number for r in c.existing] == [1, 4]


def test_radio_cover_can_be_copied_without_stories(copy_context):
    c = copy_context
    c.sources[:] = [SimpleNamespace(id=9, type_id=STORY_TYPES['cover'])]
    request = request_for(c, {'copy_selected_cached_objects': 'story',
                             'selected_cover': 'cover_9'})
    request.session['cached_covers'] = [9]
    response = copy_cached_sequences.__wrapped__(request, c.data, 'batch')
    assert response.status_code == 200
    assert [s.id for s in c.render.call_args.args[2]['stories']] == [9]


@pytest.mark.parametrize('post', [
    {'copy_selected_cached_objects': 'story',
     'selected_cover': ['cover_7', 'cover_8']},
    {'copy_selected_cached_objects': 'cover',
     'cached_objects': ['cover_7', 'cover_8']},
])
def test_non_cover_sources_cannot_be_submitted_as_covers(copy_context, post):
    c = copy_context
    request = request_for(c, post)
    request.session['cached_covers'] = [7, 8]
    response = copy_cached_sequences.__wrapped__(request, c.data, 'batch')
    assert response.status_code == 400
    c.copier.assert_not_called()


@pytest.mark.parametrize('existing_cover', [False, True])
def test_three_covers_have_explicit_main_or_all_become_reprints(
        copy_context, existing_cover):
    c = copy_context
    c.sources[:] = [SimpleNamespace(id=pk, type_id=STORY_TYPES['cover'])
                    for pk in [7, 8, 9]]
    if existing_cover:
        c.existing[0].type_id = STORY_TYPES['cover']
    request = request_for(c, {'copy_selected_cached_objects': 'story',
                             'selected_covers': ['cover_9', 'cover_8', 'cover_7']})
    request.session['cached_covers'] = [7, 8, 9]
    copy_cached_sequences.__wrapped__(request, c.data, 'batch')
    preview = c.render.call_args.args[2]
    assert preview['needs_main_cover'] is (not existing_cover)
    c.copier.assert_not_called()
    if not existing_cover:
        copy_cached_sequences.__wrapped__(request_for(c, {
            'confirm_bulk_copy': '1', 'copy_batch': preview['copy_batch'],
            'main_cover': '9'}), c.data, 'batch')
        preview = c.render.call_args.args[2]
        c.copier.assert_not_called()
        assert preview['needs_main_cover'] is False
        assert [s.id for s in preview['stories']] == [9, 7, 8]
        assert [r['position'] for r in preview['preview_rows']] == [0, 2, 3]
        assert preview['preview_rows'][0]['copy_type'] == 'cover'
    else:
        assert all(r['copy_type'] == 'cover reprint (on interior page)'
                   for r in preview['preview_rows'])
    response = copy_cached_sequences.__wrapped__(request_for(c, {
        'confirm_bulk_copy': '1', 'copy_batch': preview['copy_batch']}),
        c.data, 'batch')
    assert response.status_code == 302
    assert c.copier.call_count == 3


def test_main_cover_must_belong_to_signed_selection(copy_context):
    c = copy_context
    preview = cover_preview(c)
    response = copy_cached_sequences.__wrapped__(request_for(c, {
        'confirm_bulk_copy': '1', 'copy_batch': preview['copy_batch'],
        'main_cover': '999'}), c.data, 'batch')
    assert response.status_code == 400
    c.copier.assert_not_called()


def cover_preview(c):
    c.sources[:] = [SimpleNamespace(id=9, type_id=STORY_TYPES['cover'])]
    request = request_for(c, {'copy_selected_cached_objects': 'story',
                             'selected_cover': 'cover_9'})
    request.session['cached_covers'] = [9]
    copy_cached_sequences.__wrapped__(request, c.data, 'batch')
    return c.render.call_args.args[2]


def test_existing_cover_keeps_zero_and_reprint_uses_insertion_point(copy_context):
    c = copy_context
    c.existing[0].type_id = STORY_TYPES['cover']
    c.data['sequence_number'] = 0
    preview = cover_preview(c)
    assert preview['cover_mode'] == 'reprint'
    assert preview['cover_position'] == 1
    created = MagicMock(sequence_number=99)
    c.copier.side_effect = None
    c.copier.return_value = created
    response = copy_cached_sequences.__wrapped__(request_for(c, {
        'confirm_bulk_copy': '1', 'copy_batch': preview['copy_batch']}),
        c.data, 'batch')
    assert response.status_code == 302
    assert c.existing[0].sequence_number == 0
    assert created.sequence_number == 1


@pytest.mark.parametrize('had_cover', [False, True])
def test_cover_state_change_requires_new_confirmation(copy_context, had_cover):
    c = copy_context
    if had_cover:
        c.existing[0].type_id = STORY_TYPES['cover']
    preview = cover_preview(c)
    c.existing[0].type_id = (STORY_TYPES['comic story'] if had_cover
                             else STORY_TYPES['cover'])
    response = copy_cached_sequences.__wrapped__(request_for(c, {
        'confirm_bulk_copy': '1', 'copy_batch': preview['copy_batch'],
        'copy_characters': 'on'}), c.data, 'batch')
    assert response.status_code == 200
    c.copier.assert_not_called()
    c.receipts.delete.assert_not_called()
    updated = c.render.call_args.args[2]
    assert updated['copy_plan_changed'] is True
    assert updated['cover_mode'] == ('main' if had_cover else 'reprint')
    assert updated['copy_characters'] is True
    assert updated['copy_batch'] != preview['copy_batch']
    original_payload = signing.loads(preview['copy_batch'], salt='copy-cached-sequences')
    updated_payload = signing.loads(updated['copy_batch'], salt='copy-cached-sequences')
    assert updated_payload['operation_id'] == original_payload['operation_id']


def test_reprint_at_end_uses_end_position(copy_context):
    c = copy_context
    c.existing[0].type_id = STORY_TYPES['cover']
    c.data['sequence_number'] = None
    preview = cover_preview(c)
    assert preview['cover_mode'] == 'reprint'
    assert preview['cover_position'] == 2
