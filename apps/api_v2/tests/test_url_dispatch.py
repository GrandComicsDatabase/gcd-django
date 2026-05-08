# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the MYCOMICS-gated URL dispatch in ``apps/api_v2/urls.py``.

The v2 API mirrors the project's existing two-instance deployment
model: the ``www`` instance (``MYCOMICS=False``) serves approved GCD
data, the ``my`` instance (``MYCOMICS=True``) serves user data
(collections, reading orders). The dispatcher includes **exactly one**
surface URL conf per flag state, plus cross-cutting routes (token,
schema, swagger-ui, redoc) that appear on both surfaces.

Django evaluates ``urlpatterns`` once at module import, so tests that
flip ``settings.MYCOMICS`` via ``@override_settings`` must reload the
dispatcher module afterwards and clear Django's URL resolver caches
before assertions run.
"""

from importlib import reload

import pytest
from django.test import override_settings
from django.urls import URLResolver, clear_url_caches, resolve, reverse
from rest_framework.authentication import (
    BasicAuthentication,
    SessionAuthentication,
    TokenAuthentication,
)
from rest_framework.permissions import AllowAny

from apps.api_v2.throttling import (
    V2AnonRateThrottle,
    V2SessionUserRateThrottle,
    V2TokenUserRateThrottle,
)


def _reload_v2_urlconf():
    """Re-evaluate ``apps.api_v2.urls`` and reset Django's URL caches."""
    import apps.api_v2.urls

    reload(apps.api_v2.urls)
    clear_url_caches()


@pytest.fixture
def restore_v2_urlconf():
    """Reload the dispatcher with default settings after each test.

    Without this teardown, an ``@override_settings(MYCOMICS=...)`` test
    that triggered a reload would leave the dispatcher pointing at the
    wrong surface for whatever runs next.
    """
    yield
    _reload_v2_urlconf()


def _included_module_names():
    """Return module names of every ``include()`` resolver in the dispatcher.

    Each ``path('', include('apps.api_v2.urls_www'))`` entry produces a
    ``URLResolver`` whose ``urlconf_name`` is either the dotted module
    string passed to ``include()`` or, after the include resolves, the
    module object itself. Normalize both forms to a string.
    """
    import apps.api_v2.urls

    names = []
    for entry in apps.api_v2.urls.urlpatterns:
        if isinstance(entry, URLResolver):
            ucn = entry.urlconf_name
            names.append(ucn if isinstance(ucn, str) else ucn.__name__)
    return names


def _assert_v2_api_policy(view_cls):
    """Assert that a view class is pinned to the shared v2 API policy."""
    assert tuple(view_cls.authentication_classes) == (
        TokenAuthentication,
        BasicAuthentication,
        SessionAuthentication,
    )
    assert tuple(view_cls.permission_classes) == (AllowAny,)
    assert tuple(view_cls.throttle_classes) == (
        V2AnonRateThrottle,
        V2TokenUserRateThrottle,
        V2SessionUserRateThrottle,
    )


@override_settings(MYCOMICS=False)
def test_www_surface_includes_urls_www_only(restore_v2_urlconf):
    """``MYCOMICS=False`` mounts the www surface, not the my surface."""
    _reload_v2_urlconf()

    included = _included_module_names()
    assert 'apps.api_v2.urls_www' in included
    assert 'apps.api_v2.urls_my' not in included


@override_settings(MYCOMICS=True)
def test_my_surface_includes_urls_my_only(restore_v2_urlconf):
    """``MYCOMICS=True`` mounts the my surface, not the www surface."""
    _reload_v2_urlconf()

    included = _included_module_names()
    assert 'apps.api_v2.urls_my' in included
    assert 'apps.api_v2.urls_www' not in included


@override_settings(MYCOMICS=False)
def test_cross_cutting_routes_resolve_on_www_surface(restore_v2_urlconf):
    """Token, schema, swagger-ui, redoc all resolve on the www surface."""
    _reload_v2_urlconf()

    assert reverse('api-v2-auth-token') == '/api/v2/auth/token/'
    assert reverse('api-v2-schema') == '/api/v2/schema/'
    assert reverse('api-v2-swagger-ui') == '/api/v2/schema/swagger-ui/'
    assert reverse('api-v2-redoc') == '/api/v2/schema/redoc/'


@override_settings(MYCOMICS=False)
def test_cross_cutting_routes_use_v2_policy_on_www_surface(
    restore_v2_urlconf,
):
    """Cross-cutting views use the shared v2 auth and throttle policy."""
    _reload_v2_urlconf()

    for path in (
        '/api/v2/auth/token/',
        '/api/v2/schema/',
        '/api/v2/schema/swagger-ui/',
        '/api/v2/schema/redoc/',
    ):
        _assert_v2_api_policy(resolve(path).func.cls)


@override_settings(MYCOMICS=True)
def test_cross_cutting_routes_resolve_on_my_surface(restore_v2_urlconf):
    """Token, schema, swagger-ui, redoc all resolve on the my surface."""
    _reload_v2_urlconf()

    assert reverse('api-v2-auth-token') == '/api/v2/auth/token/'
    assert reverse('api-v2-schema') == '/api/v2/schema/'
    assert reverse('api-v2-swagger-ui') == '/api/v2/schema/swagger-ui/'
    assert reverse('api-v2-redoc') == '/api/v2/schema/redoc/'


@override_settings(MYCOMICS=False)
def test_api_root_uses_v2_policy_on_www_surface(restore_v2_urlconf):
    """The www API root stays aligned with the shared v2 policy."""
    _reload_v2_urlconf()

    _assert_v2_api_policy(resolve('/api/v2/').func.cls)


@override_settings(MYCOMICS=True)
def test_api_root_uses_v2_policy_on_my_surface(restore_v2_urlconf):
    """The my API root stays aligned with the shared v2 policy."""
    _reload_v2_urlconf()

    _assert_v2_api_policy(resolve('/api/v2/').func.cls)
