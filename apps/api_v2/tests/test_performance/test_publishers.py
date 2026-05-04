# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Performance tests for publisher endpoints."""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import Publisher


def test_publisher_list_query_count(api_client, country):
    """The publisher list stays on the expected query budget."""
    first = Publisher.objects.create(
        name='Alpha Publisher',
        year_began=1940,
        notes='',
        country=country,
    )
    second = Publisher.objects.create(
        name='Beta Publisher',
        year_began=1950,
        notes='',
        country=country,
    )
    first.keywords.add('alpha')
    second.keywords.add('beta')

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(reverse('publisher-list'))

    assert response.status_code == 200
    assert len(context) == 4


def test_publisher_detail_query_count(api_client, publisher):
    """The publisher detail endpoint avoids lazy-loading regressions."""
    publisher.keywords.add('detail')

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(
            reverse('publisher-detail', kwargs={'pk': publisher.pk}),
        )

    assert response.status_code == 200
    assert len(context) == 3
