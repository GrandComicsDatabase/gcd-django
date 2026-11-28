# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for v2 detail URLs whose id is not a number."""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

DETAIL_ROUTES = (
    'api-v2-award-detail',
    'api-v2-brand-group-detail',
    'api-v2-brand-detail',
    'api-v2-character-detail',
    'api-v2-creator-detail',
    'api-v2-feature-detail',
    'api-v2-group-detail',
    'api-v2-indicia-printer-detail',
    'api-v2-indicia-publisher-detail',
    'api-v2-issue-detail',
    'api-v2-publisher-detail',
    'api-v2-reprint-detail',
    'api-v2-series-bond-detail',
    'api-v2-series-detail',
    'api-v2-story-arc-detail',
    'api-v2-story-detail',
    'api-v2-universe-detail',
)


@pytest.mark.parametrize('route', DETAIL_ROUTES)
def test_detail_with_an_unparsable_id_is_not_found(api_client, route):
    """A detail URL whose id is not a number answers 404, not an error."""
    response = api_client.get(reverse(route, kwargs={'pk': 'abc'}))

    assert response.status_code == 404
    assert 'detail' in response.data


def test_award_recipients_without_an_award_id_are_not_found(api_client):
    """``/awards/recipients/`` is read as an Award id and answers 404."""
    url = reverse('api-v2-award-detail', kwargs={'pk': 'recipients'})

    response = api_client.get(url)

    assert url == '/api/v2/awards/recipients/'
    assert response.status_code == 404
    assert 'detail' in response.data


def test_award_recipients_of_an_unparsable_id_are_not_found(api_client):
    """The recipient action answers 404 for an Award id that is no number."""
    response = api_client.get(
        reverse('api-v2-award-recipients', kwargs={'pk': 'abc'}),
    )

    assert response.status_code == 404
    assert 'detail' in response.data
