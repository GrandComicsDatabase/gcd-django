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
