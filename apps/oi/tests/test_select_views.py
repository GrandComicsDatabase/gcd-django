# -*- coding: utf-8 -*-


from unittest.mock import patch
from types import SimpleNamespace

import pytest

from django import forms
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.test import RequestFactory

from apps.gcd.models.issue import IssuePublisherTable
from apps.gcd.models.publisher import PublisherSearchTable
from apps.gcd.models.series import SeriesPublisherTable
from apps.gcd.models.story import StoryTable
from apps.select.views import (_process_caching, cache_content,
                               get_cached_covers, process_select_search,
                               select_object, store_select_data)


def selector_request(params, user):
    request = RequestFactory().get('/select_object/test/search/', params)
    request.user = user
    return request


@pytest.mark.parametrize('command, expected', [
    ({'clear_cache': 'all'}, {}),
    ({'clear_cache': 'story'},
     {'cached_issues': [1], 'cached_covers': [3]}),
    ({'remove_cached_object': 'story_2'},
     {'cached_issues': [1], 'cached_stories': [4], 'cached_covers': [3]}),
])
def test_cache_commands_preserve_selection_and_other_session_data(command,
                                                                expected):
    request = RequestFactory().post('/select_object/test/', command)
    request.session = {'cached_issues': [1], 'cached_stories': [2, 4, 2],
                       'cached_covers': [3], 'unrelated': 'preserve me'}
    store_select_data(request, 'test', {'target': 'a story', 'story': True})
    preserved = {key: value for key, value in request.session.items()
                 if not key.startswith('cached_')}

    response = select_object.__wrapped__(request, 'test')

    assert response.status_code == 302
    assert response.url.endswith('/select_object/test/')
    assert request.session == {**preserved, **expected}


@pytest.mark.parametrize('command', [
    {'clear_cache': 'unrelated'},
    {'remove_cached_object': 'story_invalid'},
    {'remove_cached_object': 'unknown_1'},
])
def test_invalid_cache_command_does_not_change_session(command):
    request = RequestFactory().post('/select_object/test/', command)
    request.session = {'cached_stories': [2]}
    store_select_data(request, 'test', {'story': True})
    original = request.session.copy()
    response = select_object.__wrapped__(request, 'test')
    assert response.status_code == 400
    assert request.session == original


@pytest.mark.parametrize('field', ['cached_objects', 'selected_covers'])
def test_bulk_cache_removal_preserves_other_categories_and_is_idempotent(field):
    request = RequestFactory().post('/select_object/test/', {
        'remove_selected_cached_objects': 'cover',
        field: ['cover_7', 'cover_9', 'cover_7'],
    })
    request.session = {'cached_covers': [7, 8, 9], 'cached_stories': [7],
                       'unrelated': 'keep'}
    store_select_data(request, 'test', {'cover': True})
    expected = {**request.session, 'cached_covers': [8]}
    for _ in range(2):
        response = select_object.__wrapped__(request, 'test')
        assert response.status_code == 302
        assert request.session == expected


@pytest.mark.parametrize('kind, choices', [
    ('cover', []),
    ('cover', ['cover_7', 'story_8']),
    ('cover', ['cover_7', 'cover_bad']),
    ('cover', ['cover_7', 'cover_-1']),
    ('unknown', ['cover_7']),
])
@pytest.mark.parametrize('field', ['cached_objects', 'selected_covers'])
def test_bulk_cache_removal_validates_whole_batch_before_changing_session(
        kind, choices, field):
    request = RequestFactory().post('/select_object/test/', {
        'remove_selected_cached_objects': kind, field: choices})
    request.session = {'cached_covers': [7, 8], 'cached_stories': [8]}
    store_select_data(request, 'test', {'cover': True})
    original = request.session.copy()
    response = select_object.__wrapped__(request, 'test')
    assert response.status_code == 400
    assert request.session == original


@pytest.mark.parametrize('covers, status', [(['cover_7'], 302),
                                          (['cover_bad'], 400)])
def test_mixed_removal_validates_before_deleting_and_syncs_order(covers, status):
    request = RequestFactory().post('/select_object/test/', {
        'remove_selected_cached_objects': 'all',
        'cached_objects': ['story_2'], 'selected_covers': covers,
    })
    request.session = {'cached_covers': [7, 8], 'cached_stories': [2, 3],
                       'cached_covers_order': [8, 7],
                       'cached_stories_order': [3, 2]}
    store_select_data(request, 'test', {'cover': True, 'story': True})
    expected = request.session.copy()
    if status == 302:
        expected.update(cached_covers=[8], cached_stories=[3],
                        cached_covers_order=[8], cached_stories_order=[3])
    response = select_object.__wrapped__(request, 'test')
    assert response.status_code == status
    assert request.session == expected


def test_remembering_again_deduplicates_and_refreshes_eviction_order():
    cached = _process_caching([1, 2, 1, 3], 1, 3)
    assert cached == [2, 3, 1]
    assert _process_caching(cached, 4, 3) == [3, 1, 4]
    assert _process_caching(cached, 4, 1) == [4]
    assert _process_caching(cached, 4, 0) == []


def test_cache_size_changes_apply_only_when_remembering_another_object():
    initial = [1, 2, 3]
    assert _process_caching(initial, 4, 10) == [1, 2, 3, 4]
    assert _process_caching(initial, 4, 1) == [4]
    assert initial == [1, 2, 3]


@pytest.mark.parametrize('invalid', ['', None, 0, -1])
def test_profile_rejects_invalid_cache_size(invalid):
    from django.core.exceptions import ValidationError
    from apps.indexer.forms import ProfileForm
    with pytest.raises(ValidationError):
        ProfileForm.base_fields['cache_size'].clean(invalid)


@pytest.mark.parametrize('invalid', [None, 0, -1])
def test_legacy_invalid_cache_size_does_not_empty_cache(invalid):
    request = RequestFactory().get('/cover/3/cache/', HTTP_REFERER='/issue/1/')
    request.user = SimpleNamespace(indexer=SimpleNamespace(cache_size=invalid))
    request.session = {'cached_covers': [1, 2]}
    cache_content.__wrapped__(request, cover_story_id=3)
    assert request.session['cached_covers'] == [1, 2, 3]


@pytest.mark.parametrize('initial', [[], [7, 8], [7, 7, 7]])
def test_remembering_same_cover_three_times_uses_one_cache_slot(initial):
    request = RequestFactory().get('/cover/7/cache/', HTTP_REFERER='/issue/1/')
    request.user = SimpleNamespace(indexer=SimpleNamespace(cache_size=3))
    request.session = {'cached_covers': initial.copy()}
    for _ in range(3):
        response = cache_content.__wrapped__(request, cover_story_id=7)
        assert response.status_code == 302
        assert request.session['cached_covers'].count(7) == 1
    assert request.session['cached_covers'] == ([8, 7] if 8 in initial else [7])


def test_existing_duplicate_covers_are_cleaned_when_read():
    request = RequestFactory().get('/select_object/test/')
    request.session = {'cached_covers': [7, 7, 7], 'unrelated': 'keep'}
    cover = SimpleNamespace(id=7)
    with patch('apps.select.views.Story.objects.get', return_value=cover) as get:
        assert get_cached_covers(request) == [cover]
    get.assert_called_once_with(id=7, deleted=False)
    assert request.session == {'cached_covers': [7], 'unrelated': 'keep'}


@pytest.mark.parametrize('kind,key', [('story', 'cached_stories'),
                                     ('cover', 'cached_covers')])
def test_cache_reorder_preserves_eviction_queue_and_other_categories(kind, key):
    request = RequestFactory().post('/select_object/test/', {
        'reorder_cached_objects': kind,
        'ordered_objects': [kind + '_3', kind + '_1', kind + '_2']})
    request.session = {key: [1, 2, 3], 'unrelated': 'keep'}
    store_select_data(request, 'test', {'story': True})
    with patch('apps.select.views.Story.objects.get',
               side_effect=lambda id, **kw: SimpleNamespace(id=id)):
        response = select_object.__wrapped__(request, 'test')
    assert response.status_code == 200
    assert request.session[key] == [1, 2, 3]
    assert request.session[key + '_order'] == [3, 1, 2]
    assert request.session['unrelated'] == 'keep'


@pytest.mark.parametrize('choices,status', [
    (['cover_1', 'story_2', 'cover_3'], 400),
    (['cover_1', 'cover_1', 'cover_3'], 400),
    (['cover_bad'], 400), ([], 400),
    (['cover_1', 'cover_2'], 409),
    (['cover_1', 'cover_2', 'cover_999'], 409),
])
def test_cache_reorder_rejects_invalid_or_stale_lists(choices, status):
    request = RequestFactory().post('/select_object/test/', {
        'reorder_cached_objects': 'cover', 'ordered_objects': choices})
    request.session = {'cached_covers': [1, 2, 3]}
    store_select_data(request, 'test', {'cover': True})
    original = request.session.copy()
    with patch('apps.select.views.Story.objects.get',
               side_effect=lambda id, **kw: SimpleNamespace(id=id)):
        response = select_object.__wrapped__(request, 'test')
    assert response.status_code == status
    assert request.session == original


def test_remember_after_reorder_evicts_oldest_not_first_displayed():
    request = RequestFactory().get('/cover/4/cache/', HTTP_REFERER='/issue/1/')
    request.user = SimpleNamespace(indexer=SimpleNamespace(cache_size=3))
    request.session = {'cached_covers': [1, 2, 3],
                       'cached_covers_order': [3, 1, 2]}
    cache_content.__wrapped__(request, cover_story_id=4)
    assert request.session['cached_covers'] == [2, 3, 4]
    assert request.session['cached_covers_order'] == [3, 2, 4]


def test_clear_cache_also_clears_saved_order():
    request = RequestFactory().post('/select_object/test/', {'clear_cache': 'cover'})
    request.session = {'cached_covers': [1, 2], 'cached_covers_order': [2, 1]}
    store_select_data(request, 'test', {'cover': True})
    select_object.__wrapped__(request, 'test')
    assert 'cached_covers' not in request.session
    assert 'cached_covers_order' not in request.session


@pytest.mark.parametrize('allow_copy', [False, True])
def test_cache_sections_render_with_bulk_removal_and_danger_zone(
        allow_copy):
    cache_form = forms.Form()
    cache_form.fields['object_choice'] = forms.ChoiceField(
        widget=forms.RadioSelect,
        choices=[('story_1', 'A remembered story'),
                 ('cover_2', 'A remembered cover'),
                 ('unknown_3', 'An unsupported object')])
    cache_form.disabled_choices = ('story_1',)
    request = RequestFactory().get('/select_object/test/')
    request.user = SimpleNamespace(indexer=SimpleNamespace(cache_size=10))
    request.session = {'cached_stories': [1], 'cached_covers': [2]}
    store_select_data(request, 'test', {
        'story': True, 'heading': 'Select a story', 'target': 'a story',
        'disabled_choice_help': 'Current issue',
        'return': '_selected_copy_sequence' if allow_copy else 'confirm_reprint',
    })
    with patch('apps.select.views.get_select_forms',
               return_value=(forms.Form(), cache_form)), \
            patch('apps.select.views.render', return_value=HttpResponse()) as render:
        select_object.__wrapped__(request, 'test')
    html = render_to_string('select/select_object.html', render.call_args.args[2])
    last_table_position = html.rindex('</table>')
    clear_cache_position = html.index('aria-label="Clear remembered objects"')
    selection_actions_position = html.index('id="selection-actions"')

    assert 'Stories (1/10)' in html
    assert 'An unsupported object' not in html
    assert 'Covers (1/10)' in html
    assert 'Clear all remembered objects' in html
    assert 'Clear story cache' in html
    assert 'Clear cover cache' in html
    assert 'name="remove_cached_object"' not in html
    assert 'id="cache-heading"' not in html
    assert html.count('type="checkbox"') == 2
    assert last_table_position < clear_cache_position < selection_actions_position
    assert ('aria-describedby="disabled-choice-2"' in html) is not allow_copy
    assert 'id="cache-selection"' in html
    assert 'form="cache-selection"' in html
    assert '>Select all</button>' in html
    assert 'Select all covers' not in html
    assert 'data-cache-clear' not in html
    assert ('data-cache-copy' in html) is allow_copy
    assert 'type="checkbox" name="selected_covers" value="cover_2"' in html
    assert 'name="selected_cover"' not in html
    assert '<th scope="col">Order</th>' in html
    assert '<th scope="col">Story</th>' in html
    assert html.index('Covers (1/10)') < html.index('Stories (1/10)')
    assert ('>Select</button>' in html) is not allow_copy
    assert '>Delete</button>' not in html
    assert 'data-cache-list="cover"' in html
    assert '<th scope="col">Cover</th>' in html
    assert 'Drag a cover row to reorder it. Order is saved automatically.' in html
    assert html.count('name="select_object"') == (0 if allow_copy else 2)
    assert html.count('<colgroup>') == 2
    assert 'Delete selected stories' not in html
    assert html.index('data-cache-remove') > html.index('</section>')


def test_bulk_copy_is_rejected_in_single_target_workflows():
    request = RequestFactory().post('/select_object/test/', {
        'copy_selected_cached_objects': 'story', 'cached_objects': ['story_1']})
    request.session = {}
    store_select_data(request, 'test', {'return': 'confirm_reprint'})
    with patch('apps.oi.views.copy_cached_sequences') as copy:
        response = select_object.__wrapped__(request, 'test')
    assert response.status_code == 400
    copy.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    'select_type, search_param, search_fields, table_class, target',
    [
        ('publisher', 'search_publisher', {'publisher': 'Test'},
         PublisherSearchTable, 'publisher'),
        ('series', 'search_series', {'series': 'Test'},
         SeriesPublisherTable, 'series'),
        ('issue', 'search_issue',
         {'publisher': 'Test', 'series': 'Test', 'number': '1'},
         IssuePublisherTable, 'issue'),
        ('story', 'search_story',
         {'publisher': 'Test', 'series': 'Test', 'number': '1'},
         StoryTable, 'story'),
        ('cover', 'search_cover',
         {'publisher': 'Test', 'series': 'Test', 'number': '1'},
         StoryTable, 'story'),
    ])
def test_database_selector_uses_sortable_table(
        select_type, search_param, search_fields, table_class, target,
        any_indexer):
    data = {select_type: True}
    params = {'select_key': 'test', search_param: 'Search'}
    params.update(search_fields)
    request = selector_request(params, any_indexer)

    with patch('apps.select.views.get_select_data', return_value=data), \
            patch('apps.gcd.views.details.generic_sortable_list') as render:
        process_select_search.__wrapped__(request, 'test')

    table = render.call_args.args[2]
    context = render.call_args.args[4]
    assert isinstance(table, table_class)
    assert context['select_key'] == 'test'
    assert context['select_target'] == target
    assert context['select_issue'] is False


@pytest.mark.django_db
def test_publisher_selector_renders_selection_column(any_added_publisher,
                                                     any_indexer):
    data = {'publisher': True}
    request = selector_request({
        'select_key': 'test',
        'search_publisher': 'Search',
        'publisher': any_added_publisher.name,
    }, any_indexer)

    with patch('apps.select.views.get_select_data', return_value=data):
        response = process_select_search.__wrapped__(request, 'test')

    body = response.content.decode()
    assert 'Selection' in body
    assert 'Select This Publisher' in body
    assert 'publisher_%d' % any_added_publisher.id in body


@pytest.mark.django_db
def test_story_selector_keeps_issue_selection(any_indexer):
    data = {'story': True, 'issue': True}
    request = selector_request({
        'select_key': 'test',
        'search_story': 'Search',
        'publisher': 'Test',
        'series': 'Test',
        'number': '1',
    }, any_indexer)

    with patch('apps.select.views.get_select_data', return_value=data), \
            patch('apps.gcd.views.details.generic_sortable_list') as render:
        process_select_search.__wrapped__(request, 'test')

    context = render.call_args.args[4]
    assert context['select_target'] == 'story'
    assert context['select_issue'] is True


@pytest.mark.django_db
def test_issue_selector_does_not_render_duplicate_issue_action(any_indexer):
    data = {'issue': True}
    request = selector_request({
        'select_key': 'test',
        'search_issue': 'Search',
        'publisher': 'Test',
        'series': 'Test',
        'number': '1',
    }, any_indexer)

    with patch('apps.select.views.get_select_data', return_value=data), \
            patch('apps.gcd.views.details.generic_sortable_list') as render:
        process_select_search.__wrapped__(request, 'test')

    assert render.call_args.args[4]['select_issue'] is False
