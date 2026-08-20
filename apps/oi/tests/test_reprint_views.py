# -*- coding: utf-8 -*-

import re

import mock
import pytest

from django.db.models import Q
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.test import RequestFactory

from apps.gcd.models import Issue, Reprint, Story
from apps.oi import states
from apps.oi.models import ReprintRevision, StoryRevision
from apps.oi.views import add_reprint, confirm_reprint, \
                          create_matching_sequence, edit_reprint, \
                          move_story_revision, save_reprint
from apps.select.forms import get_select_cache_form
from apps.select.views import select_object, store_select_data


def _other_story_in_same_issue(story):
    other_story = type(story).objects.get(pk=story.pk)
    other_story.pk = None
    other_story.sequence_number += 1
    other_story.save()
    assert other_story.issue == story.issue
    return other_story


@pytest.mark.django_db
def test_save_reprint_rejects_link_within_same_issue(any_added_story,
                                                     any_changeset):
    other_story = _other_story_in_same_issue(any_added_story)

    request = RequestFactory().post('/', {
        'direction': 'from',
        'reprint_link_notes': '',
        'comments': '',
    })
    request.user = any_changeset.indexer
    error_response = HttpResponse('internal reprint')

    with mock.patch('apps.oi.views.render_error',
                    return_value=error_response) as render_error_mock:
        response = save_reprint.__wrapped__(
            request,
            reprint_revision_id='new',
            changeset_id=str(any_changeset.id),
            story_one_id=any_added_story.id,
            story_two_id=other_story.id)

    assert response is error_response
    render_error_mock.assert_called_once_with(
        request,
        'Reprint links must connect different issues.',
        redirect=False)
    assert not ReprintRevision.objects.filter(
        changeset=any_changeset).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('object_type', ('issue', 'story'))
def test_confirm_reprint_rejects_object_from_same_issue(any_added_story,
                                                        any_changeset,
                                                        object_type):
    other_story = _other_story_in_same_issue(any_added_story)
    selected_id = (any_added_story.issue_id if object_type == 'issue'
                   else other_story.id)
    request = RequestFactory().post('/')
    request.session = {}
    error_response = HttpResponse('internal reprint')
    data = {
        'story_id': any_added_story.id,
        'changeset_id': any_changeset.id,
    }

    with mock.patch('apps.oi.views.render_error',
                    return_value=error_response) as render_error_mock, \
            mock.patch('apps.oi.views.oi_render') as oi_render_mock:
        response = confirm_reprint.__wrapped__(request, data, object_type,
                                               selected_id)

    assert response is error_response
    render_error_mock.assert_called_once_with(
        request,
        'Reprint links must connect different issues.',
        redirect=False)
    assert not oi_render_mock.called


@pytest.mark.django_db
def test_select_object_disables_cached_objects_from_current_issue(
        any_added_story, any_indexer):
    request = RequestFactory().get('/')
    request.user = any_indexer
    request.session = {
        'cached_issues': [any_added_story.issue_id],
        'cached_stories': [any_added_story.id],
        'cached_covers': [any_added_story.id],
    }
    select_key = store_select_data(request, 'reprint-test', {
        'heading': 'Select reprint target',
        'target': 'a story or issue',
        'story': True,
        'issue': True,
        'exclude_issue_id': any_added_story.issue_id,
    })
    response = HttpResponse('select object')

    with mock.patch('apps.select.views.render',
                    return_value=response) as render_mock:
        actual = select_object.__wrapped__(request, select_key)

    assert actual is response
    context = render_mock.call_args.args[2]
    assert set(context['disabled_choices']) == {
        'issue_%d' % any_added_story.issue_id,
        'story_%d' % any_added_story.id,
        'cover_%d' % any_added_story.id,
    }
    assert isinstance(context['disabled_choices'], tuple)
    html = render_to_string('select/select_object.html', context,
                            request=request)
    assert html.count('\n  disabled\n') == 3
    assert 'aria-disabled' not in html
    assert html.count('btn-blue-disabled') == 3
    assert html.count(
        'title="Cannot select because reprint links must connect different '
        'issues."') == 3
    assert html.count('aria-describedby="disabled-reprint-') == 3
    assert html.count('<small id="disabled-reprint-') == 3
    assert html.count('<em>(Current issue;') == 3


def test_select_cache_form_keeps_other_issue_enabled():
    current_issue = mock.Mock(id=1)
    other_issue = mock.Mock(id=2)

    form = get_select_cache_form(
        cached_issues=[current_issue, other_issue],
        exclude_issue_id=current_issue.id)()

    assert form.disabled_choices == ('issue_1',)
    assert [choice[0] for choice in
            form.fields['object_choice'].choices] == ['issue_1', 'issue_2']


@pytest.mark.parametrize(
    'action', ('flip_direction', 'restore', 'matching_sequence'))
def test_edit_reprint_rejects_invalid_action_on_internal_link(action):
    request = RequestFactory().post('/', {action: '1'})
    indexer = mock.Mock()
    request.user = indexer
    changeset = mock.Mock(indexer=indexer)
    reprint_revision = mock.Mock(changeset=changeset)
    reprint_revision.is_internal.return_value = True
    reprint_revision.deleted = True
    error_response = HttpResponse('internal reprint')

    with mock.patch('apps.oi.views.get_object_or_404',
                    return_value=reprint_revision), \
            mock.patch('apps.oi.views.render_error',
                       return_value=error_response) as render_error_mock:
        response = edit_reprint.__wrapped__(request, id=1)

    assert response is error_response
    render_error_mock.assert_called_once_with(
        request,
        'Reprint links must connect different issues.',
        redirect=False)
    reprint_revision.save.assert_not_called()


def test_create_matching_sequence_rejects_internal_link_before_copying():
    request = RequestFactory().post('/')
    indexer = mock.Mock()
    request.user = indexer
    issue = mock.Mock()
    changeset = mock.Mock(indexer=indexer)
    changeset.issuerevisions.get.return_value = mock.Mock(issue=issue)
    reprint_revision = mock.Mock(changeset=changeset)
    reprint_revision.is_internal.return_value = True
    error_response = HttpResponse('internal reprint')

    with mock.patch('apps.oi.views.get_object_or_404',
                    side_effect=(mock.Mock(), issue, reprint_revision)), \
            mock.patch('apps.oi.views.render_error',
                       return_value=error_response) as render_error_mock, \
            mock.patch.object(
                StoryRevision, 'copied_revision') as copied_revision_mock:
        response = create_matching_sequence.__wrapped__(
            request, reprint_revision_id=1, story_id=2, issue_id=3)

    assert response is error_response
    render_error_mock.assert_called_once_with(
        request,
        'Reprint links must connect different issues.',
        redirect=False)
    copied_revision_mock.assert_not_called()


def _button_tag(html, name):
    match = re.search(r'<button[^>]*name="%s"[^>]*>' % name, html)
    assert match
    return match.group()


@pytest.mark.parametrize(
    ('is_source', 'origin_action', 'target_action', 'note_action'),
    ((False, 'edit_origin', 'edit_target', 'edit_note_target'),
     (True, 'edit_origin_internal', 'edit_target', 'edit_note_origin')))
@pytest.mark.parametrize('render_branch', ('display', 'current', 'approved'))
def test_internal_reprint_only_enables_corrective_actions(
        is_source, origin_action, target_action, note_action, render_branch):
    changeset = mock.Mock(id=2)
    if render_branch == 'display':
        reprint_changeset = None
        reprint_changeset_id = None
    elif render_branch == 'current':
        reprint_changeset = changeset
        reprint_changeset_id = changeset.id
    else:
        reprint_changeset = mock.Mock(id=3, state=states.APPROVED)
        reprint_changeset_id = reprint_changeset.id
    reprint = mock.Mock(
        id=1,
        changeset=reprint_changeset,
        changeset_id=reprint_changeset_id,
        deleted=False,
        previous_revision=mock.Mock(),
        source=None,
        origin=None,
        origin_issue=None,
        target=None,
        target_issue=None)
    reprint.source = reprint
    reprint.is_internal.return_value = True

    with mock.patch(
            'apps.oi.templatetags.editing.ContentType.objects.'
            'get_for_model'), \
            mock.patch(
                'apps.oi.templatetags.editing.RevisionLock.objects.filter'
            ) as lock_filter:
        lock_filter.return_value.first.return_value = None
        html = render_to_string(
            'oi/bits/reprint_type_list.html',
            {'reprint': reprint,
             'changeset': changeset,
             'is_source': is_source,
             'create_sequence': True,
             'states': states})

    for action in (origin_action, note_action, 'flip_direction',
                   'matching_sequence'):
        button = _button_tag(html, action)
        assert 'btn-blue-disabled' in button
        assert re.search(r'\sdisabled(?:\s|>)', button)
        assert 'aria-describedby=' in button

    for action in (target_action, 'delete'):
        button = _button_tag(html, action)
        assert 'btn-blue-editing' in button
        assert not re.search(r'\sdisabled(?:\s|>)', button)

    assert 'name="edit_target_internal"' not in html

    assert html.count(
        'Legacy internal link; change its target or mark it to delete.'
    ) == 1


def test_internal_reprint_disables_restore():
    changeset = mock.Mock(id=2)
    reprint = mock.Mock(
        id=1,
        changeset=changeset,
        changeset_id=changeset.id,
        deleted=True,
        previous_revision=mock.Mock(),
        source=mock.Mock(),
        origin=None,
        origin_issue=None,
        target=None,
        target_issue=None)
    reprint.is_internal.return_value = True

    with mock.patch(
            'apps.oi.templatetags.editing.ContentType.objects.'
            'get_for_model'), \
            mock.patch(
                'apps.oi.templatetags.editing.RevisionLock.objects.filter'
            ) as lock_filter:
        lock_filter.return_value.first.return_value = None
        html = render_to_string(
            'oi/bits/reprint_type_list.html',
            {'reprint': reprint,
             'changeset': changeset,
             'is_source': True})

    button = _button_tag(html, 'restore')
    assert 'btn-blue-disabled' in button
    assert re.search(r'\sdisabled(?:\s|>)', button)
    assert 'aria-describedby=' in button
    assert html.count(
        'Legacy internal link; restoring it is unavailable.'
    ) == 1


def test_move_story_rejects_internal_reprint_before_reserving():
    request = RequestFactory().post('/')
    indexer = mock.Mock()
    request.user = indexer
    old_issue = mock.Mock()
    new_issue = mock.Mock(issue=mock.Mock(), issue_id=2)
    changeset = mock.Mock(indexer=indexer)
    changeset.issuerevisions.count.return_value = 2
    changeset.issuerevisions.exclude.return_value.get.return_value = new_issue
    story = mock.Mock(changeset=changeset, issue=old_issue, story_id=1)
    error_response = HttpResponse('internal reprint')

    with mock.patch('apps.oi.views.get_object_or_404', return_value=story), \
            mock.patch('apps.oi.views.render_error',
                       return_value=error_response) as render_error_mock, \
            mock.patch.object(Reprint.objects, 'filter') as filter_mock, \
            mock.patch('apps.oi.views._do_reserve') as reserve_mock:
        filter_mock.return_value.exists.return_value = True
        response = move_story_revision.__wrapped__(request, id=story.id)

    assert response is error_response
    render_error_mock.assert_called_once_with(
        request,
        'Reprint links must connect different issues.',
        redirect=False)
    assert story.issue is old_issue
    reserve_mock.assert_not_called()
    changeset.reprintrevisions.filter.assert_not_called()
    filter_mock.assert_called_once_with(
        Q(target_id=story.story_id,
          origin_issue_id=new_issue.issue_id) |
        Q(origin_id=story.story_id,
          target_issue_id=new_issue.issue_id))


@pytest.mark.django_db
def test_add_reprint_excludes_current_issue_from_selector(
        any_added_story_rev):
    request = RequestFactory().get('/')
    request.session = {}

    with mock.patch('apps.oi.views.store_select_data',
                    return_value='reprint-test') as store_select_data_mock:
        add_reprint.__wrapped__(
            request,
            changeset_id=any_added_story_rev.changeset_id,
            story_id=any_added_story_rev.id)

    data = store_select_data_mock.call_args.args[2]
    assert data['exclude_issue_id'] == any_added_story_rev.issue_id


def test_save_reprint_rejects_before_saving_story_revision():
    request = RequestFactory().post('/', {
        'direction': 'from',
        'reprint_link_notes': '',
        'reprint_notes': 'must not be saved',
        'comments': '',
    })
    issue = Issue(id=1)
    story = Story(id=2, issue=issue)
    story_revision = mock.Mock(id=3, story=story, issue=issue)
    changeset = mock.Mock(id=4)
    error_response = HttpResponse('internal reprint')

    with mock.patch('apps.oi.views.get_object_or_404',
                    return_value=changeset), \
            mock.patch('apps.oi.views.StoryRevision.objects.get',
                       return_value=story_revision), \
            mock.patch('apps.oi.views.Story.objects.get',
                       return_value=story), \
            mock.patch('apps.oi.views.Issue.objects.get',
                       return_value=issue), \
            mock.patch('apps.oi.views.render_error',
                       return_value=error_response) as render_error_mock:
        response = save_reprint.__wrapped__(
            request,
            reprint_revision_id='new',
            changeset_id=str(changeset.id),
            story_revision_id=story_revision.id,
            issue_two_id=issue.id)

    assert response is error_response
    render_error_mock.assert_called_once_with(
        request,
        'Reprint links must connect different issues.',
        redirect=False)
    story_revision.save.assert_not_called()
