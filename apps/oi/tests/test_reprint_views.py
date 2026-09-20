# -*- coding: utf-8 -*-

from html.parser import HTMLParser

import mock
import pytest

from django.db.models import Q
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.test import RequestFactory

from apps.gcd.models import Issue, Reprint, Story
from apps.oi.models import ReprintRevision
from apps.oi.views import add_reprint, confirm_reprint, move_story_revision, \
                          save_reprint
from apps.select.forms import get_select_cache_form
from apps.select.views import select_object, store_select_data


class _DisabledChoiceParser(HTMLParser):
    """Collect disabled-choice markup without parsing unrelated page HTML."""

    def __init__(self):
        super().__init__()
        self.buttons = []
        self.help = {}
        self._help_id = None
        self._help_text = []
        self._help_emphasized = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'button' and attrs.get('name') == 'select_object':
            self.buttons.append(attrs)
        elif tag == 'small' and attrs.get('id', '').startswith(
                'disabled-choice-'):
            self._help_id = attrs['id']
            self._help_text = []
            self._help_emphasized = False
        elif tag == 'em' and self._help_id:
            self._help_emphasized = True

    def handle_data(self, data):
        if self._help_id:
            self._help_text.append(data)

    def handle_endtag(self, tag):
        if tag == 'small' and self._help_id:
            self.help[self._help_id] = {
                'text': ' '.join(''.join(self._help_text).split()),
                'emphasized': self._help_emphasized,
            }
            self._help_id = None


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
        'exclude_issue_id': any_added_story.issue_id,
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
    oi_render_mock.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize('object_type', ('issue', 'story'))
def test_confirm_reprint_accepts_object_from_different_issue(
        any_added_story, any_added_variant, any_changeset, object_type):
    if object_type == 'story':
        selected_story = type(any_added_story).objects.get(
            pk=any_added_story.pk)
        selected_story.pk = None
        selected_story.issue = any_added_variant
        selected_story.save()
        selected_id = selected_story.id
    else:
        selected_id = any_added_variant.id
    request = RequestFactory().post('/')
    request.session = {}
    confirm_response = HttpResponse('confirm reprint')
    data = {
        'story_id': any_added_story.id,
        'changeset_id': any_changeset.id,
        'exclude_issue_id': any_added_story.issue_id,
    }

    with mock.patch('apps.oi.views.oi_render',
                    return_value=confirm_response) as oi_render_mock, \
            mock.patch('apps.oi.views.render_error') as render_error_mock:
        response = confirm_reprint.__wrapped__(request, data, object_type,
                                               selected_id)

    assert response is confirm_response
    oi_render_mock.assert_called_once()
    render_error_mock.assert_not_called()


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
        'disabled_choice_title': (
            'Cannot select because reprint links must connect different '
            'issues.'),
        'disabled_choice_help': (
            'Current issue; cannot select for a reprint link.'),
    })
    response = HttpResponse('select object')

    with mock.patch('apps.select.views.render',
                    return_value=response) as render_mock:
        actual = select_object.__wrapped__(request, select_key)

    assert actual is response
    context = render_mock.call_args.args[2]
    assert set(context['cache_form'].disabled_choices) == {
        'issue_%d' % any_added_story.issue_id,
        'story_%d' % any_added_story.id,
        'cover_%d' % any_added_story.id,
    }
    assert isinstance(context['cache_form'].disabled_choices, tuple)
    html = render_to_string('select/select_object.html', context,
                            request=request)
    assert 'aria-disabled' not in html
    parser = _DisabledChoiceParser()
    parser.feed(html)
    assert len(parser.buttons) == 3
    for counter, button in enumerate(parser.buttons, start=1):
        help_id = 'disabled-choice-%d' % counter
        assert set(button['class'].split()) == {
            'btn-blue-disabled', 'inline', 'py-1', 'px-2'}
        assert button['type'] == 'submit'
        assert 'disabled' in button
        assert button['aria-describedby'] == help_id
        assert button['title'] == (
            'Cannot select because reprint links must connect different '
            'issues.')
        assert parser.help[help_id] == {
            'text': '(Current issue; cannot select for a reprint link.)',
            'emphasized': True,
        }


def test_select_cache_form_keeps_other_issue_enabled():
    current_issue = mock.Mock(id=1)
    other_issue = mock.Mock(id=2)

    form = get_select_cache_form(
        cached_issues=[current_issue, other_issue],
        exclude_issue_id=current_issue.id)()

    assert form.disabled_choices == ('issue_1',)
    assert [choice[0] for choice in
            form.fields['object_choice'].choices] == ['issue_1', 'issue_2']


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
