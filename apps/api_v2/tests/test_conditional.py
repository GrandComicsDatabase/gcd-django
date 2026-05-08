# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the conditional-request helpers in ``api_v2.utils``."""

from datetime import datetime
from unittest.mock import Mock

from apps.api_v2.utils.conditional import make_last_modified


class _DummyModel:
    """Minimal stand-in model with a mock default manager."""

    _meta = Mock(label_lower='tests.dummy')
    _default_manager = Mock()


def test_make_last_modified_uses_queryset_getter_for_list_result_set():
    """A custom queryset getter scopes list timestamps to view results."""
    default_qs = Mock(name='default_qs')
    filtered_qs = Mock(name='filtered_qs')
    ordered_qs = Mock(name='ordered_qs')
    values_qs = Mock(name='values_qs')

    _DummyModel._default_manager = Mock()
    _DummyModel._default_manager.all.return_value = default_qs
    filtered_qs.filter.return_value = filtered_qs
    filtered_qs.order_by.return_value = ordered_qs
    ordered_qs.values_list.return_value = values_qs
    values_qs.first.return_value = 'filtered-latest'

    queryset_getter = Mock(return_value=filtered_qs)
    last_modified = make_last_modified(
        _DummyModel,
        queryset_getter=queryset_getter,
    )

    assert last_modified(request='request') == 'filtered-latest'
    queryset_getter.assert_called_once_with('request', pk=None)
    _DummyModel._default_manager.all.assert_not_called()
    filtered_qs.filter.assert_called_once_with(deleted=False)
    filtered_qs.order_by.assert_called_once_with('-modified')
    ordered_qs.values_list.assert_called_once_with('modified', flat=True)
    values_qs.first.assert_called_once_with()


def test_make_last_modified_applies_soft_delete_to_custom_queryset():
    """Custom queryset getters still honor the helper's soft-delete rule."""
    raw_qs = Mock(name='raw_qs')
    visible_qs = Mock(name='visible_qs')
    ordered_qs = Mock(name='ordered_qs')
    values_qs = Mock(name='values_qs')

    raw_qs.filter.return_value = visible_qs
    visible_qs.order_by.return_value = ordered_qs
    ordered_qs.values_list.return_value = values_qs
    values_qs.first.return_value = 'visible-latest'

    queryset_getter = Mock(return_value=raw_qs)
    last_modified = make_last_modified(
        _DummyModel,
        queryset_getter=queryset_getter,
    )

    assert last_modified(request='request') == 'visible-latest'
    raw_qs.filter.assert_called_once_with(deleted=False)
    visible_qs.order_by.assert_called_once_with('-modified')
    ordered_qs.values_list.assert_called_once_with('modified', flat=True)
    values_qs.first.assert_called_once_with()


def test_make_last_modified_caches_request_local_list_result():
    """List requests reuse cached metadata within a single request."""
    qs = Mock(name='qs')
    ordered_qs = Mock(name='ordered_qs')
    values_qs = Mock(name='values_qs')
    latest = datetime(2026, 5, 3, 12, 0, 0)

    _DummyModel._default_manager = Mock()
    _DummyModel._default_manager.all.return_value = qs
    qs.filter.return_value = qs
    qs.order_by.return_value = ordered_qs
    ordered_qs.values_list.return_value = values_qs
    values_qs.first.return_value = latest

    class _Request:
        """Minimal request object with a stable path."""

        def get_full_path(self):
            return '/api/v2/issues/'

    request = _Request()
    last_modified = make_last_modified(_DummyModel)

    assert last_modified(request=request) == latest
    assert last_modified(request=request) == latest
    qs.filter.assert_called_once_with(deleted=False)
    qs.order_by.assert_called_once_with('-modified')
    ordered_qs.values_list.assert_called_once_with('modified', flat=True)
    values_qs.first.assert_called_once_with()
