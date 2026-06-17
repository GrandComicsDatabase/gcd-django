# -*- coding: utf-8 -*-



import mock
import pytest

from apps.gcd.models import Story, Issue, Series

STORY_PATH = 'apps.gcd.models.story.Story'


@pytest.mark.parametrize('is_comics, deleted',
                         [(True, True), (True, False),
                          (False, True), (False, False)])
def test_stat_counts(is_comics, deleted):
    story = Story(issue=Issue(series=Series(is_comics_publication=True)))
    story.deleted = deleted
    assert story.stat_counts() == {} if deleted else {'stories': 1}


def test_story_model_exposes_api_v2_browse_and_modified_indexes():
    index_map = {
        index.name: list(index.fields)
        for index in Story._meta.indexes
    }

    assert index_map['gcd_story_v2_browse_idx'] == [
        'deleted',
        'issue',
        'sequence_number',
        'id',
    ]
    assert index_map['gcd_story_v2_modified_idx'] == [
        'deleted',
        'modified',
        'id',
    ]


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
    assert r == from_mock.all.return_value
    from_mock.all.assert_called_once()


def test_to_reprints(re_story_mocks):
    from_mock, to_mock, s = re_story_mocks
    r = s.to_reprints
    assert r == to_mock.all.return_value
    to_mock.all.assert_called_once()


def test_from_issue_reprints(re_story_mocks):
    from_mock, to_mock, s = re_story_mocks
    r = s.from_issue_reprints
    assert r == from_mock.all().filter.return_value
    from_mock.all().filter.assert_called_once_with(origin=None)


def test_to_issue_reprints(re_story_mocks):
    from_mock, to_mock, s = re_story_mocks
    r = s.to_issue_reprints
    assert r == to_mock.all().filter.return_value
    to_mock.all().filter.assert_called_once_with(target=None)
