# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the filter form of the browsable v2 list pages."""

import re

import pytest
from django.urls import reverse

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


def _filter_form(response):
    """Return the opening tag and the fields of the Filters modal form."""
    content = response.content.decode()
    modal = content.split('id="filtersModal"', 1)[1]
    form = modal.split('<form', 1)[1].split('</form>', 1)[0]
    opening_tag, body = form.split('>', 1)
    names = [
        name
        for name in re.findall(r'name="([^"]*)"', body)
        if name and name != 'csrfmiddlewaretoken'
    ]
    return opening_tag, body, names


@pytest.mark.parametrize('route', LIST_ROUTES)
def test_filter_form_submits_its_fields_with_get(api_client, db, route):
    """The Filters modal sends its fields back to the list as a query."""
    url = reverse(route)
    response = api_client.get(url, HTTP_ACCEPT='text/html')

    assert response.status_code == 200
    opening_tag, body, names = _filter_form(response)
    assert 'method="get"' in opening_tag.lower()
    assert 'type="submit"' in body
    assert names

    submitted = api_client.get(
        url,
        dict.fromkeys(names, ''),
        HTTP_ACCEPT='text/html',
    )

    assert submitted.status_code == 200


def test_issue_filter_form_submission_filters_the_list(api_client, issue):
    """A submitted Filters form narrows the issue list to its values."""
    issue.__class__.objects.create(
        number='2',
        title='',
        volume='',
        isbn='',
        valid_isbn='',
        variant_name='',
        barcode='',
        publication_date='',
        key_date='',
        on_sale_date='',
        sort_code=2,
        indicia_frequency='',
        price='',
        editing='',
        notes='',
        indicia_printer_sourced_by='',
        series=issue.series,
    )
    url = reverse('api-v2-issue-list')
    _opening_tag, _body, names = _filter_form(
        api_client.get(url, HTTP_ACCEPT='text/html'),
    )
    query = dict.fromkeys(names, '')
    query['number'] = '1'

    response = api_client.get(url, query, HTTP_ACCEPT='text/html')

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == issue.pk
