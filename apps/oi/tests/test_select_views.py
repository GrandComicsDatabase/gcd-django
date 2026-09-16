# -*- coding: utf-8 -*-


from unittest.mock import patch
from types import SimpleNamespace

import pytest

from django.test import Client, RequestFactory
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django import forms
from django.template.loader import render_to_string

from apps.gcd.models.issue import IssuePublisherTable
from apps.gcd.models.publisher import PublisherSearchTable
from apps.gcd.models.series import SeriesPublisherTable
from apps.gcd.models.story import StoryTable
from apps.select.views import process_select_search, select_object, \
                              store_select_data


def cache_request(params=None, method='post'):
    request = getattr(RequestFactory(), method)('/select_object/test/',
                                               params or {})
    request.session = SessionStore()
    request.session.update({'cached_issues': [1, 2],
                            'cached_stories': [1, 3, 3],
                            'cached_covers': [1, 4],
                            'unrelated': 'preserved'})
    store_select_data(request, 'test', {'story': True,
                                      'return': '_selected_copy_sequence',
                                      'cancel': '/cancel/'})
    return request


@pytest.mark.parametrize('action, choices, expected', [
    ('clear_objects', [], {}),
    ('remove_objects', ['story_1', 'story_3', 'cover_4', 'issue_999',
                        'invalid', 'unrelated'],
     {'cached_issues': [1, 2], 'cached_stories': [], 'cached_covers': [1]}),
    ('remove_objects', [],
     {'cached_issues': [1, 2], 'cached_stories': [1, 3, 3],
      'cached_covers': [1, 4]}),
])
def test_cache_actions_preserve_context(action, choices, expected):
    request = cache_request({action: '', 'cached_object': choices})
    context = {key: value for key, value in request.session.items()
               if not key.startswith('cached_')}

    response = select_object.__wrapped__(request, 'test')

    assert response.url == '/select_object/test/'
    assert dict(request.session) == {**context, **expected}
    assert request.session.modified


def test_clear_empty_cache_is_safe():
    request = cache_request({'clear_objects': ''})
    request.session.clear()
    store_select_data(request, 'test', {})

    assert select_object.__wrapped__(request, 'test').status_code == 302


def test_cache_management_get_does_not_change_session():
    request = cache_request({'clear_objects': ''}, method='get')
    request.session.update({'test_heading': '', 'test_target': 'a story'})
    request.session['test_items'] += ['heading', 'target']
    before = dict(request.session)

    with patch('apps.select.views.get_select_forms',
               return_value=(forms.Form(), forms.Form())), \
            patch('apps.select.views.render'):
        select_object.__wrapped__(request, 'test')

    assert dict(request.session) == before


def test_cache_management_requires_csrf_token():
    response = Client(enforce_csrf_checks=True).post(
        '/select_object/test/', {'clear_objects': ''})

    assert response.status_code == 403


@pytest.mark.parametrize('field', ['object_choice', 'cached_object'])
def test_single_cached_selection_calls_original_handler(field):
    request = cache_request({'select_object': '', field: 'cover_4'})

    with patch('apps.oi.views._selected_copy_sequence') as handler:
        select_object.__wrapped__(request, 'test')

    assert handler.call_args.args[2:] == ('story', '4')
    assert request.session['cached_covers'] == [1, 4]


@pytest.mark.parametrize('can_copy_multiple', [True, False])
def test_cache_management_controls_share_one_form(can_copy_multiple):
    class CacheForm(forms.Form):
        object_choice = forms.ChoiceField(
            widget=forms.RadioSelect,
            choices=[('story_1', 'First story'), ('cover_4', 'Cover')])

    body = render_to_string('select/select_object.html', {
        'select_key': 'test', 'cache_form': CacheForm(),
        'can_copy_multiple': can_copy_multiple,
        'user': SimpleNamespace(is_authenticated=False),
    })

    assert 'Clear Objects' in body
    assert 'Remove Selected Object' in body
    assert ('Copy Selected Objects' in body) == can_copy_multiple
    assert body.count('name="select_object"') == int(not can_copy_multiple)
    assert body.count('id="manage_cached_objects"') == 1
    assert body.count('type="checkbox" name="cached_object"') == 2
    assert '<label for="cached_object_1">First story</label>' in body


def test_empty_cache_hides_management_controls():
    body = render_to_string('select/select_object.html', {
        'select_key': 'test', 'cache_form': forms.Form(),
        'user': SimpleNamespace(is_authenticated=False),
    })

    assert 'Clear Objects' not in body
    assert 'Remove Selected Object' not in body


@pytest.mark.parametrize('choices', [[], ['story_1', 'cover_4']])
def test_single_selection_flow_requires_one_checked_object(choices):
    request = cache_request({'select_object': '',
                             'cached_object': choices})

    with patch('apps.oi.views._selected_copy_sequence') as handler:
        response = select_object.__wrapped__(request, 'test')

    assert b'Please select exactly one object.' in response.content
    handler.assert_not_called()


@pytest.mark.parametrize('choice', ['malformed', 'story_not_an_id',
                                    'unknown_1'])
def test_single_selection_rejects_invalid_choice(choice):
    request = cache_request({'select_object': '', 'cached_object': choice})

    with patch('apps.oi.views._selected_copy_sequence') as handler:
        response = select_object.__wrapped__(request, 'test')

    assert b'The selected object is invalid.' in response.content
    handler.assert_not_called()


@pytest.fixture
def multiple_copy_request(any_added_story, any_editing_changeset):
    from apps.gcd.models import Story
    from apps.oi.models import IssueRevision, StoryRevision

    issue_revision = IssueRevision.clone(any_added_story.issue,
                                         any_editing_changeset)
    StoryRevision.clone(any_added_story, any_editing_changeset)
    second = Story.objects.create(issue=any_added_story.issue,
                                  type=any_added_story.type,
                                  sequence_number=2, title='Second story')
    request = cache_request({'confirm_copy_objects': '1', 'cached_object': [
        'story_%s' % any_added_story.id, 'story_%s' % second.id]})
    request.POST = request.POST.copy()
    request.user = any_editing_changeset.indexer
    request.session['cached_stories'] = [any_added_story.id, second.id]
    data = {'story': True, 'return': '_selected_copy_sequence',
            'issue_revision_id': issue_revision.id,
            'changeset_id': any_editing_changeset.id,
            'sequence_number': 0, 'cancel': '/cancel/'}
    store_select_data(request, 'test', data)
    return request, issue_revision


@pytest.mark.django_db
@pytest.mark.parametrize('multiple', [True, False])
def test_copy_preview_does_not_write(multiple_copy_request, multiple):
    request, issue_revision = multiple_copy_request
    request.POST.pop('confirm_copy_objects')
    if multiple:
        request.POST['copy_objects'] = '1'
    else:
        request.POST['select_object'] = '1'
        request.POST.setlist('cached_object',
                             request.POST.getlist('cached_object')[:1])
    before = issue_revision.active_stories().count()

    response = select_object.__wrapped__(request, 'test')

    assert response.status_code == 200
    body = response.content.decode()
    assert ('Second story' in body) == multiple
    assert 'Test Story Title' in body
    assert ('name="confirm_copy_objects"' in body) == multiple
    assert body.count('name="cached_object"') == (2 if multiple else 0)
    assert issue_revision.active_stories().count() == before


@pytest.mark.django_db
@pytest.mark.parametrize('position, expected', [
    (0, ['Test Story Title', 'Second story', 'Test Story Title']),
    (-1, ['Test Story Title', 'Second story', 'Test Story Title']),
    (None, ['Test Story Title', 'Test Story Title', 'Second story']),
    (1, ['Test Story Title', 'Test Story Title', 'Second story']),
])
def test_multiple_copy_preserves_order_and_options(multiple_copy_request,
                                                   position, expected):
    request, issue_revision = multiple_copy_request
    request.POST['copy_characters'] = 'True'
    request.POST['copy_credit_info'] = 'True'
    request.session['test_sequence_number'] = position
    before = dict(request.session)

    response = select_object.__wrapped__(request, 'test')

    assert response.url.endswith('/%s/edit/' % issue_revision.changeset_id)
    copies = list(issue_revision.active_stories())
    assert [story.title for story in copies] == expected
    numbers = [story.sequence_number for story in copies]
    assert numbers == sorted(set(numbers))
    assert copies[0 if position in (0, -1) else 1].characters
    assert dict(request.session) == before


@pytest.mark.django_db
def test_multiple_copy_deduplicates_story_and_cover(multiple_copy_request):
    request, issue_revision = multiple_copy_request
    source_id = request.session['cached_stories'][0]
    request.session['cached_covers'] = [source_id]
    request.POST.setlist('cached_object', ['story_%s' % source_id,
                                          'cover_%s' % source_id])

    select_object.__wrapped__(request, 'test')

    assert issue_revision.active_stories().count() == 2


@pytest.mark.django_db
def test_multiple_copy_into_empty_issue_uses_default_options(
        multiple_copy_request):
    request, issue_revision = multiple_copy_request
    issue_revision.active_stories().delete()

    select_object.__wrapped__(request, 'test')

    stories = list(issue_revision.active_stories())
    assert [story.title for story in stories] == ['Test Story Title',
                                                'Second story']
    assert [story.sequence_number for story in stories] == [0, 1]
    assert all(story.characters == '' for story in stories)


@pytest.mark.django_db
@pytest.mark.parametrize('choices', [[], ['issue_1'], ['story_999999'],
                                    ['malformed']])
def test_multiple_copy_rejects_invalid_choices(multiple_copy_request, choices):
    request, issue_revision = multiple_copy_request
    request.POST.setlist('cached_object', choices)

    response = select_object.__wrapped__(request, 'test')

    assert b'Select at least one cached story' in response.content
    assert issue_revision.active_stories().count() == 1


@pytest.mark.django_db
def test_multiple_copy_checks_reservation_holder(multiple_copy_request):
    from django.contrib.auth.models import User

    request, issue_revision = multiple_copy_request
    request.user = User.objects.create_user('other_indexer')

    response = select_object.__wrapped__(request, 'test')

    assert b'Only the reservation holder' in response.content
    assert issue_revision.active_stories().count() == 1


@pytest.mark.django_db
def test_multiple_copy_rolls_back_on_failure(multiple_copy_request):
    from apps.oi.models import StoryRevision

    request, issue_revision = multiple_copy_request
    original = StoryRevision.copied_revision
    calls = 0

    def fail_second_copy(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError('Copy failed')
        return original(*args, **kwargs)

    with patch.object(StoryRevision, 'copied_revision',
                      side_effect=fail_second_copy), \
            pytest.raises(RuntimeError, match='Copy failed'):
        select_object.__wrapped__(request, 'test')

    assert issue_revision.active_stories().count() == 1


@pytest.mark.django_db
def test_multiple_copy_rejects_deleted_source(multiple_copy_request):
    from apps.gcd.models import Story

    request, issue_revision = multiple_copy_request
    Story.objects.filter(id=request.session['cached_stories'][1]).update(
        deleted=True)

    response = select_object.__wrapped__(request, 'test')

    assert b'no longer available' in response.content
    assert issue_revision.active_stories().count() == 1


def test_multiple_copy_cancel_does_not_call_copy_handler():
    request = cache_request({'confirm_copy_objects': '1', 'cancel': 'Cancel'})

    with patch('apps.oi.views._selected_copy_sequences') as handler:
        response = select_object.__wrapped__(request, 'test')

    assert response.url == '/cancel/'
    handler.assert_not_called()


def test_multiple_copy_unavailable_in_other_selection_flows():
    request = cache_request({'copy_objects': '1'})
    request.session['test_return'] = 'confirm_reprint'

    with patch('apps.oi.views._selected_copy_sequences') as handler:
        response = select_object.__wrapped__(request, 'test')

    assert b'Multiple copies are not available' in response.content
    handler.assert_not_called()


def selector_request(params, user):
    request = RequestFactory().get('/select_object/test/search/', params)
    request.user = user
    return request


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
