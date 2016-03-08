# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import mock
import pytest

from apps.gcd.models import Story, Issue, Series

STORY_PATH = 'apps.oi.models.story.Story'


@pytest.mark.parametrize('is_comics, deleted',
                         [(True, True), (True, False),
                          (False, True), (False, False)])
def test_stat_counts(is_comics, deleted):
    story = Story(issue=Issue(series=Series(is_comics_publication=True)))
    story.deleted = deleted
    assert story.stat_counts() == {} if deleted else {'stories': 1}


@pytest.yield_fixture
def re_story_mocks():
    with mock.patch('%s.from_all_reprints' % STORY_PATH) as from_mock, \
            mock.patch('%s.to_all_reprints' % STORY_PATH) as to_mock:

        from_mock.exists.return_value = False
        to_mock.exclude.return_value.exists.return_value = False

        yield from_mock, to_mock, Story(title='Test Story')


def test_from_reprints(re_story_mocks):
    from_mock, to_mock, s = re_story_mocks
    r = s.from_reprints
    assert r == from_mock.exclude.return_value
    from_mock.exclude.assert_called_once_with(origin=None)


def test_to_reprints(re_story_mocks):
    from_mock, to_mock, s = re_story_mocks
    r = s.to_reprints
    assert r == to_mock.exclude.return_value
    to_mock.exclude.assert_called_once_with(target=None)


def test_from_issue_reprints(re_story_mocks):
    from_mock, to_mock, s = re_story_mocks
    r = s.from_issue_reprints
    assert r == from_mock.filter.return_value
    from_mock.filter.assert_called_once_with(origin=None)


def test_to_issue_reprints(re_story_mocks):
    from_mock, to_mock, s = re_story_mocks
    r = s.to_issue_reprints
    assert r == to_mock.filter.return_value
    to_mock.filter.assert_called_once_with(target=None)
