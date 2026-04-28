"""Throttle classes for the v2 API.

Three buckets per the PRD: one for anonymous traffic, one for users
who authenticate via Token or Basic credentials (programmatic), and
one for users who authenticate via session cookie (browsable API).

Rates are pinned as class attributes so v2 stays decoupled from the
project-wide ``REST_FRAMEWORK`` config that v1 still relies on. The
PRD limits changes to existing project files to ``INSTALLED_APPS``
additions only.
"""

from rest_framework.authentication import (
    BasicAuthentication,
    SessionAuthentication,
    TokenAuthentication,
)
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class V2AnonRateThrottle(AnonRateThrottle):
    """30 requests per hour per IP for unauthenticated v2 traffic."""

    scope = 'v2_anon'
    rate = '30/hour'


class V2TokenUserRateThrottle(UserRateThrottle):
    """2000 requests per day for Token or Basic authenticated users.

    Both methods carry credentials per request and target programmatic
    consumers (third-party tools, scripts, CI). The PRD lists the rate
    explicitly for Token; Basic is grouped here because it is the same
    use case.
    """

    scope = 'v2_user_token'
    rate = '2000/day'

    def get_cache_key(self, request, view):
        """Skip this throttle for non-Token/Basic authenticators."""
        auth = request.successful_authenticator
        if not isinstance(auth, (TokenAuthentication, BasicAuthentication)):
            return None
        return super().get_cache_key(request, view)


class V2SessionUserRateThrottle(UserRateThrottle):
    """2000 requests per day for session-authenticated users."""

    scope = 'v2_user_session'
    rate = '2000/day'

    def get_cache_key(self, request, view):
        """Skip this throttle for non-Session authenticators."""
        if not isinstance(
            request.successful_authenticator, SessionAuthentication
        ):
            return None
        return super().get_cache_key(request, view)
