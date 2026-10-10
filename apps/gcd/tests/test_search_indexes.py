"""Regression tests for Haystack search index preparation."""

from types import SimpleNamespace
from unittest.mock import Mock

from apps.gcd.models import CREDIT_TYPES, Universe
from apps.gcd.search_indexes import CreatorIndex, StoryIndex
from apps.gcd.templatetags.credits import search_creator_credit


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


def test_story_index_uses_legacy_characters_for_missing_universe():
    """Dangling universe references do not abort a full index rebuild."""
    show_characters = Mock(side_effect=Universe.DoesNotExist)
    story = SimpleNamespace(
        characters='Legacy Character',
        show_characters_as_text=show_characters,
    )

    assert StoryIndex().prepare_characters(story) == 'Legacy Character'
    show_characters.assert_called_once_with()


def test_search_creator_credit_excludes_missing_creator_names():
    """Orphaned credits do not abort search document template rendering."""
    active_credits = Mock()
    active_credits.filter.return_value = []
    issue = SimpleNamespace(active_credits=active_credits)

    assert search_creator_credit(issue, 'editing') == ''
    active_credits.filter.assert_called_once_with(
        credit_type_id=CREDIT_TYPES['editing'],
        creator__creator__isnull=False,
    )
