# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Unit tests for v2 pagination helpers."""

from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.api_v2.pagination import V2IssuePageNumberPagination


class _DeltaView:
    """Minimal stand-in view that opts into no-count pagination."""

    def should_skip_exact_count(self, request):
        del request
        return True


def test_issue_pagination_skips_exact_count_for_delta_requests():
    """Delta issue pagination returns links without paying for COUNT(*)."""
    paginator = V2IssuePageNumberPagination()
    request = Request(APIRequestFactory().get('/api/v2/issues/?page=2'))

    page = paginator.paginate_queryset(
        list(range(120)),
        request,
        view=_DeltaView(),
    )
    response = paginator.get_paginated_response(page)

    assert page == list(range(50, 100))
    assert response.data['count'] is None
    assert response.data['next'] == 'http://testserver/api/v2/issues/?page=3'
    assert response.data['previous'] == 'http://testserver/api/v2/issues/'
