"""Regression tests for Haystack search index preparation."""

from types import SimpleNamespace
from unittest.mock import Mock

from apps.gcd.search_indexes import CreatorIndex, StoryIndex


def test_creator_index_handles_missing_birth_date():
    """Creators without a birth date can still be added to the index."""
    creator = SimpleNamespace(birth_date=None)
    index = CreatorIndex()

    assert index.prepare_year(creator) == 9999
    assert index.prepare_date(creator) is None


def test_story_index_excludes_credits_with_missing_creator_names():
    """Orphaned dump credits do not abort a full search-index rebuild."""
    story_credits = Mock()
    story_credits.filter.return_value = []
    issue_credits = Mock()
    issue_credits.filter.return_value = []
    story = SimpleNamespace(
        script='',
        editing='',
        active_credits=story_credits,
        issue=SimpleNamespace(editing='', active_credits=issue_credits),
    )
    index = StoryIndex()

    assert index.prepare_script(story) is None
    assert index.prepare_editing(story) == ['', '']
    story_credits.filter.assert_any_call(
        credit_type__name='script',
        creator__creator__isnull=False,
    )
    story_credits.filter.assert_any_call(
        credit_type__name='editing',
        creator__creator__isnull=False,
    )
    issue_credits.filter.assert_called_once_with(
        credit_type__name='editing',
        creator__creator__isnull=False,
    )
