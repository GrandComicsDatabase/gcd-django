# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 reprint endpoints."""

import django_filters

from apps.api_v2.filters.common import (
    TIMESTAMP_FILTER_FIELDS,
    TimestampFilterSet,
)
from apps.gcd.models import Reprint


class ReprintFilterSet(TimestampFilterSet):
    """Filters for reprint list endpoints."""

    origin_issue = django_filters.NumberFilter(field_name='origin_issue_id')
    target_issue = django_filters.NumberFilter(field_name='target_issue_id')
    origin_story = django_filters.NumberFilter(field_name='origin_id')
    target_story = django_filters.NumberFilter(field_name='target_id')
    origin_issue__series = django_filters.NumberFilter(
        field_name='origin_issue__series_id',
    )
    target_issue__series = django_filters.NumberFilter(
        field_name='target_issue__series_id',
    )

    class Meta:
        """FilterSet metadata for reprint filtering."""

        model = Reprint
        fields = (
            'origin_issue',
            'target_issue',
            'origin_story',
            'target_story',
            'origin_issue__series',
            'target_issue__series',
        ) + TIMESTAMP_FILTER_FIELDS
