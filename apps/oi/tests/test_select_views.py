# -*- coding: utf-8 -*-


from unittest.mock import patch

import pytest

from django.test import RequestFactory

from apps.gcd.models.issue import IssuePublisherTable
from apps.gcd.models.publisher import PublisherSearchTable
from apps.gcd.models.series import SeriesPublisherTable
from apps.gcd.models.story import StoryTable
from apps.select.views import process_select_search


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
    assert 'Select this publisher' in body
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
