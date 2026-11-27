# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 story-arc endpoints."""

import django_filters

from apps.api_v2.filters.common import (
    TIMESTAMP_FILTER_FIELDS,
    TimestampFilterSet,
)
from apps.gcd.models import StoryArc


class StoryArcFilterSet(TimestampFilterSet):
    """Filters for story-arc list endpoints."""

    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
    )

    class Meta:
        """FilterSet metadata for story-arc filtering."""

        model = StoryArc
        fields = ('name',) + TIMESTAMP_FILTER_FIELDS
