# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""django-filter configuration for v2 Award endpoints."""

import django_filters

from apps.api_v2.filters.common import (
    TIMESTAMP_FILTER_FIELDS,
    TimestampFilterSet,
)
from apps.gcd.models import Award, ReceivedAward

AWARD_RECIPIENT_TYPES = (
    ('creator', 'Creator'),
    ('issue', 'Issue'),
    ('series', 'Series'),
    ('story', 'Story'),
)


class AwardFilterSet(TimestampFilterSet):
    """Filters for Award list endpoints."""

    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
    )

    class Meta:
        """FilterSet metadata for Award filtering."""

        model = Award
        fields = ('name',) + TIMESTAMP_FILTER_FIELDS


class AwardRecipientFilterSet(TimestampFilterSet):
    """Filters for the paginated Award recipient action."""

    recipient_type = django_filters.ChoiceFilter(
        choices=AWARD_RECIPIENT_TYPES,
        method='filter_recipient_type',
    )

    def filter_recipient_type(self, queryset, name, value):
        """Filter generic recipients by their supported public type."""
        del name
        if not value:
            return queryset
        return queryset.filter(
            content_type__app_label='gcd',
            content_type__model=value,
        )

    class Meta:
        """FilterSet metadata for received Award filtering."""

        model = ReceivedAward
        fields = (
            'recipient_type',
            'award_year',
        ) + TIMESTAMP_FILTER_FIELDS
