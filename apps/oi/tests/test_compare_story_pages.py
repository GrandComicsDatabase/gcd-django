# -*- coding: utf-8 -*-
"""Tests of the pages of sequences on the compare page of an issue."""

import html
import re
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import StoryType
from apps.oi import states
from apps.oi.models import Changeset, CTYPES, IssueRevision, StoryRevision

PAGE_SIZE = 'apps.oi.templatetags.compare.COMPARE_SEQUENCES_PER_PAGE'


def _add_sequences(changeset, issue, numbers, title='Title'):
    """Add to the change a sequence of the issue for each number."""
    story_type = StoryType.objects.get(name='comic story')
    for number in numbers:
        StoryRevision.objects.create(
          changeset=changeset, issue=issue, type=story_type,
          sequence_number=number, title='%s%03dx' % (title, number))


def _change(indexer, *issues):
    """Return an open change of the issues."""
    change_type = CTYPES['two_issues' if len(issues) > 1 else 'issue']
    changeset = Changeset.objects.create(
      indexer=indexer, state=states.OPEN, change_type=change_type)
    for issue in issues:
        IssueRevision.clone(data_object=issue, changeset=changeset)
    return changeset


def _compare(client, changeset, query=''):
    """Return the compare page of the change."""
    url = reverse('compare', kwargs={'id': changeset.id}) + query
    response = client.get(url)
    assert response.status_code == 200
    return response.content.decode()


def _links(content, label):
    """Return the addresses of the page links with that label."""
    return [html.unescape(link) for link in re.findall(
      r'<a href="([^"]*)">%s\s+(?:sequences|compare view)</a>' % label,
      content)]


@pytest.fixture
def five_sequences(client, any_indexer, any_added_issue):
    """A change with five sequences, with two sequences on a page."""
    client.force_login(any_indexer)
    changeset = _change(any_indexer, any_added_issue)
    _add_sequences(changeset, any_added_issue, range(5))
    with patch(PAGE_SIZE, 2, create=True):
        yield changeset


@pytest.mark.parametrize('count, shown, more', [(100, 100, False),
                                                (101, 100, True)])
def test_a_page_has_at_most_one_hundred_sequences(count, shown, more):
    """Up to one hundred sequences nothing changes on the page."""
    from apps.oi.templatetags.compare import sequences_page
    ordered = Mock()
    ordered.order_by.return_value = list(range(count))
    revision = SimpleNamespace(ordered_story_revisions=lambda: ordered)
    page = sequences_page({'request': SimpleNamespace(GET={})}, revision)
    assert len(page) == shown
    assert page.has_other_pages() is more
    # the id settles the order of the sequences that share a number
    ordered.order_by.assert_called_once_with('sequence_number', 'id')


@pytest.mark.django_db
def test_first_page_shows_only_its_sequences(client, five_sequences):
    """The links are both above and below the sequences of the page."""
    content = _compare(client, five_sequences)
    assert 'Title000x' in content and 'Title001x' in content
    assert 'Title002x' not in content
    assert re.search(r'Sequences 1-2\s+of 5', content)
    assert len(_links(content, 'Next')) == 2
    assert _links(content, 'Previous') == []


@pytest.mark.django_db
def test_links_of_the_page_lead_to_the_other_pages(client, five_sequences):
    """The links as rendered move between the pages, in the same view."""
    first = _compare(client, five_sequences, '?collapse=1')
    second = _compare(client, five_sequences, _links(first, 'Next')[0])
    assert 'Title002x' in second and 'Title003x' in second
    assert 'Title001x' not in second and 'Title004x' not in second
    assert re.search(r'Sequences 3-4\s+of 5', second)

    back = _links(second, 'Previous')[0]
    assert 'collapse=1' in back
    assert 'Title000x' in _compare(client, five_sequences, back)


@pytest.mark.django_db
def test_last_page_has_no_next_link(client, five_sequences):
    """The last page ends the links."""
    content = _compare(client, five_sequences, '?page=3')
    assert 'Title004x' in content
    assert _links(content, 'Next') == []


@pytest.mark.django_db
@pytest.mark.parametrize('page, shown', [('abc', 'Title000x'),
                                         ('99', 'Title004x')])
def test_invalid_page_shows_a_page(client, five_sequences, page, shown):
    """A page number that does not exist is not an error."""
    assert shown in _compare(client, five_sequences, '?page=%s' % page)


@pytest.mark.django_db
def test_no_links_when_all_sequences_fit(client, five_sequences):
    """All the sequences on one page need no links."""
    with patch(PAGE_SIZE, 5, create=True):
        content = _compare(client, five_sequences)
    assert 'Title004x' in content
    assert not re.search(r'Sequences 1-', content)


@pytest.mark.django_db
def test_sequences_with_the_same_number_are_on_one_page_each(
        client, five_sequences):
    """Two sequences can have one number, across the end of a page."""
    five_sequences.storyrevisions.filter(title='Title002x').update(
      sequence_number=1)
    first = _compare(client, five_sequences)
    second = _compare(client, five_sequences, '?page=2')
    assert 'Title001x' in first and 'Title001x' not in second
    assert 'Title002x' in second and 'Title002x' not in first


@pytest.mark.django_db
def test_collapse_and_expand_stay_on_the_page(client, five_sequences):
    """The links of the compare view keep the page of sequences."""
    second = _compare(client, five_sequences, '?page=2')
    collapsed = _compare(client, five_sequences,
                         _links(second, 'Collapse')[0])
    assert 'Title002x' in collapsed and 'Title000x' not in collapsed
    expanded = _compare(client, five_sequences,
                        _links(collapsed, 'Expand')[0])
    assert 'Title002x' in expanded and 'Collapse compare view' in expanded


@pytest.mark.django_db
def test_both_issues_of_a_change_are_in_pages(
        client, any_indexer, any_added_issue, any_added_variant):
    """A change of two issues shows the same page of both."""
    client.force_login(any_indexer)
    changeset = _change(any_indexer, any_added_issue, any_added_variant)
    _add_sequences(changeset, any_added_issue, range(3))
    _add_sequences(changeset, any_added_variant, range(3), title='Other')
    with patch(PAGE_SIZE, 2, create=True):
        content = _compare(client, changeset, '?page=2')
    assert 'Title002x' in content and 'Other002x' in content
    assert 'Title000x' not in content and 'Other000x' not in content


@pytest.mark.django_db
def test_queries_do_not_grow_with_the_sequences_of_other_pages(
        client, five_sequences, any_added_issue):
    """Only the sequences of the page cost queries."""
    _compare(client, five_sequences)
    with CaptureQueriesContext(connection) as five:
        _compare(client, five_sequences)
    _add_sequences(five_sequences, any_added_issue, range(5, 25))
    with CaptureQueriesContext(connection) as twenty_five:
        _compare(client, five_sequences)
    assert len(twenty_five) == len(five)
