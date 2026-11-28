# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the field labels of the Filters form of the v2 list pages."""

import re

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

LIST_ROUTES = (
    'api-v2-award-list',
    'api-v2-brand-group-list',
    'api-v2-brand-list',
    'api-v2-character-list',
    'api-v2-creator-list',
    'api-v2-feature-list',
    'api-v2-group-list',
    'api-v2-indicia-printer-list',
    'api-v2-indicia-publisher-list',
    'api-v2-issue-list',
    'api-v2-publisher-list',
    'api-v2-reprint-list',
    'api-v2-series-bond-list',
    'api-v2-series-list',
    'api-v2-story-arc-list',
    'api-v2-story-list',
    'api-v2-universe-list',
)

DECLARED_LABELS = (
    ('api-v2-issue-list', 'on_sale_iso_week', 'On sale ISO week'),
    (
        'api-v2-creator-list',
        'birth_date__gte',
        'Birth date is greater than or equal to',
    ),
    (
        'api-v2-creator-list',
        'birth_date__lte',
        'Birth date is less than or equal to',
    ),
    (
        'api-v2-creator-list',
        'death_date__gte',
        'Death date is greater than or equal to',
    ),
    (
        'api-v2-creator-list',
        'death_date__lte',
        'Death date is less than or equal to',
    ),
    ('api-v2-series-list', 'search', 'Search'),
)


def _filter_labels(api_client, route):
    """Return the label of each field of the Filters modal form."""
    response = api_client.get(reverse(route), HTTP_ACCEPT='text/html')
    assert response.status_code == 200
    content = response.content.decode()
    modal = content.split('id="filtersModal"', 1)[1]
    form = modal.split('<form', 1)[1].split('</form>', 1)[0]
    return {
        name: ' '.join(label.split())
        for name, label in re.findall(
            r'<label[^>]*for="id_([^"]*)"[^>]*>(.*?)</label>',
            form,
            re.DOTALL,
        )
    }


@pytest.mark.parametrize('route', LIST_ROUTES)
def test_filter_form_has_a_label_for_every_field(api_client, route):
    """No field of a Filters form shows django-filter's fallback label."""
    labels = _filter_labels(api_client, route)

    assert labels
    assert '[invalid name]' not in labels.values()


@pytest.mark.parametrize(('route', 'field', 'label'), DECLARED_LABELS)
def test_filter_without_a_model_field_shows_its_label(
    api_client,
    route,
    field,
    label,
):
    """A filter that is not named after a model field shows its own label."""
    assert _filter_labels(api_client, route)[field] == label
