# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 reprint endpoints."""

from apps.api_v2.filters.common import (
    TIMESTAMP_FILTER_FIELDS,
    IntegerFilter,
    TimestampFilterSet,
)
from apps.gcd.models import Reprint


class ReprintFilterSet(TimestampFilterSet):
    """Filters for reprint list endpoints."""

    origin_issue = IntegerFilter(field_name='origin_issue_id')
    target_issue = IntegerFilter(field_name='target_issue_id')
    origin_story = IntegerFilter(field_name='origin_id')
    target_story = IntegerFilter(field_name='target_id')
    origin_issue__series = IntegerFilter(
        field_name='origin_issue__series_id',
    )
    target_issue__series = IntegerFilter(
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
