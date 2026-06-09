# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Pagination classes for the v2 API."""

from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.utils.urls import remove_query_param, replace_query_param


class V2PageNumberPagination(PageNumberPagination):
    """Page-number pagination with v2 defaults.

    50 results per page out of the box. Clients may request a smaller
    or larger page via ``?page_size=`` up to a hard cap of 200.
    """

    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class V2DeltaPageNumberPagination(V2PageNumberPagination):
    """Pagination with an optional no-count delta mode.

    Broad delta sync requests can match hundreds of thousands of rows. For
    those requests the exact ``COUNT(*)`` dominates latency, so a view can opt
    into a page-number mode that fetches one extra row to determine ``next``
    and returns ``count: null`` instead of paying for the full count query.
    """

    def paginate_queryset(self, queryset, request, view=None):
        """Paginate, optionally skipping the exact count query."""
        self._delta_mode = False
        self.request = request
        page_size = self.get_page_size(request)
        if not page_size:
            return None

        if not self._should_skip_exact_count(request, view):
            return super().paginate_queryset(queryset, request, view=view)

        page_number = request.query_params.get(self.page_query_param, 1)
        if page_number in self.last_page_strings:
            return super().paginate_queryset(queryset, request, view=view)

        try:
            page_number = int(page_number)
        except (TypeError, ValueError) as exc:
            raise NotFound('Invalid page.') from exc
        if page_number < 1:
            raise NotFound('Invalid page.')

        offset = (page_number - 1) * page_size
        window = list(queryset[offset : offset + page_size + 1])
        if page_number > 1 and not window:
            raise NotFound('Invalid page.')

        self._delta_mode = True
        self._delta_page_number = page_number
        self._delta_page_size = page_size
        self._delta_has_next = len(window) > page_size
        return window[:page_size]

    def get_paginated_response(self, data):
        """Return the standard envelope, with nullable count in delta mode."""
        if not getattr(self, '_delta_mode', False):
            return super().get_paginated_response(data)

        return Response(
            {
                'count': None,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'results': data,
            }
        )

    def get_next_link(self):
        """Return the next page link for delta mode without total counts."""
        if not getattr(self, '_delta_mode', False):
            return super().get_next_link()
        if not self._delta_has_next:
            return None

        url = self.request.build_absolute_uri()
        return replace_query_param(
            url,
            self.page_query_param,
            self._delta_page_number + 1,
        )

    def get_previous_link(self):
        """Return the previous page link for delta mode."""
        if not getattr(self, '_delta_mode', False):
            return super().get_previous_link()
        if self._delta_page_number <= 1:
            return None

        url = self.request.build_absolute_uri()
        previous_page = self._delta_page_number - 1
        if previous_page == 1:
            return remove_query_param(url, self.page_query_param)
        return replace_query_param(url, self.page_query_param, previous_page)

    def get_paginated_response_schema(self, schema):
        """Document that delta pages may omit an exact count."""
        paginated = super().get_paginated_response_schema(schema)
        paginated['properties']['count'] = {
            'anyOf': [
                {'type': 'integer', 'example': 123},
                {'type': 'null'},
            ],
            'description': (
                'Exact total result count. Delta-style sync responses may '
                'return null to avoid an expensive count.'
            ),
        }
        return paginated

    def _should_skip_exact_count(self, request, view):
        """Return whether the owning view requested no-count pagination."""
        if view is None or not hasattr(view, 'should_skip_exact_count'):
            return False
        return bool(view.should_skip_exact_count(request))


class V2IssuePageNumberPagination(V2DeltaPageNumberPagination):
    """Issue pagination with an optional no-count delta mode."""
