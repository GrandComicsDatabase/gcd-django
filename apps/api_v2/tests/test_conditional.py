"""Tests for the conditional-request helpers in ``api_v2.utils``."""

from unittest.mock import Mock

from apps.api_v2.utils.conditional import make_last_modified


class _DummyModel:
    """Minimal stand-in model with a mock default manager."""

    _default_manager = Mock()


def test_make_last_modified_uses_queryset_getter_for_list_result_set():
    """A custom queryset getter scopes list timestamps to view results."""
    default_qs = Mock(name='default_qs')
    filtered_qs = Mock(name='filtered_qs')

    _DummyModel._default_manager = Mock()
    _DummyModel._default_manager.all.return_value = default_qs
    filtered_qs.filter.return_value = filtered_qs
    filtered_qs.aggregate.return_value = {'latest': 'filtered-latest'}

    queryset_getter = Mock(return_value=filtered_qs)
    last_modified = make_last_modified(
        _DummyModel,
        queryset_getter=queryset_getter,
    )

    assert last_modified(request='request') == 'filtered-latest'
    queryset_getter.assert_called_once_with('request', pk=None)
    _DummyModel._default_manager.all.assert_not_called()
    filtered_qs.filter.assert_called_once_with(deleted=False)
    filtered_qs.aggregate.assert_called_once()


def test_make_last_modified_applies_soft_delete_to_custom_queryset():
    """Custom queryset getters still honor the helper's soft-delete rule."""
    raw_qs = Mock(name='raw_qs')
    visible_qs = Mock(name='visible_qs')

    raw_qs.filter.return_value = visible_qs
    visible_qs.aggregate.return_value = {'latest': 'visible-latest'}

    queryset_getter = Mock(return_value=raw_qs)
    last_modified = make_last_modified(
        _DummyModel,
        queryset_getter=queryset_getter,
    )

    assert last_modified(request='request') == 'visible-latest'
    raw_qs.filter.assert_called_once_with(deleted=False)
    visible_qs.aggregate.assert_called_once()
