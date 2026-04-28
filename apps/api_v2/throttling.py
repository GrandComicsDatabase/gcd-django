"""Throttle classes for the v2 API.

Rates are set as class attributes rather than via
``REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']`` so v2 stays decoupled from
the project-wide DRF config (which v1 also depends on).

The unique ``scope`` strings keep v2 traffic in its own cache bucket so
v1 throttle counters are not shared.
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class V2AnonRateThrottle(AnonRateThrottle):
    """30 requests per hour per IP for unauthenticated v2 traffic."""

    scope = 'v2_anon'
    rate = '30/hour'


class V2UserRateThrottle(UserRateThrottle):
    """2000 requests per day per user for authenticated v2 traffic."""

    scope = 'v2_user'
    rate = '2000/day'
