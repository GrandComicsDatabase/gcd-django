# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 Series Bond endpoints."""

import django_filters

from apps.api_v2.filters.common import (
    TIMESTAMP_FILTER_FIELDS,
    TimestampFilterSet,
)
from apps.gcd.models import SeriesBond


class SeriesBondFilterSet(TimestampFilterSet):
    """Filters for Series Bond list endpoints."""

    origin = django_filters.NumberFilter(field_name='origin_id')
    origin_issue = django_filters.NumberFilter(field_name='origin_issue_id')
    target = django_filters.NumberFilter(field_name='target_id')
    target_issue = django_filters.NumberFilter(field_name='target_issue_id')
    bond_type = django_filters.NumberFilter(field_name='bond_type_id')

    class Meta:
        """FilterSet metadata for Series Bond filtering."""

        model = SeriesBond
        fields = (
            'origin',
            'origin_issue',
            'target',
            'target_issue',
            'bond_type',
        ) + TIMESTAMP_FILTER_FIELDS
