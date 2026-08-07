# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Performance tests for indicia publisher endpoints."""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import IndiciaPublisher


def _create_indicia_publisher(*, publisher, country, name):
    """Create a minimal indicia publisher row for performance tests."""
    return IndiciaPublisher.objects.create(
        name=name,
        year_began=1950,
        notes='',
        parent=publisher,
        country=country,
    )


def test_indicia_publisher_list_query_count(
    api_client,
    publisher,
    country,
):
    """The indicia publisher list stays on its query budget."""
    _create_indicia_publisher(
        publisher=publisher,
        country=country,
        name='Alpha Imprint',
    )
    _create_indicia_publisher(
        publisher=publisher,
        country=country,
        name='Beta Imprint',
    )

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(reverse('indicia-publisher-list'))

    assert response.status_code == 200
    assert len(context) == 3


def test_indicia_publisher_detail_query_count(
    api_client,
    publisher,
    country,
):
    """The detail endpoint avoids lazy-loading regressions."""
    indicia_publisher = _create_indicia_publisher(
        publisher=publisher,
        country=country,
        name='Detail Imprint',
    )
    indicia_publisher.keywords.add('detail')

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(
            reverse(
                'indicia-publisher-detail',
                kwargs={'pk': indicia_publisher.pk},
            ),
        )

    assert response.status_code == 200
    assert len(context) == 3
