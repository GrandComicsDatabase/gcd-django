# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Pagination classes for the v2 API."""

from rest_framework.pagination import PageNumberPagination


class V2PageNumberPagination(PageNumberPagination):
    """Page-number pagination with v2 defaults.

    50 results per page out of the box. Clients may request a smaller
    or larger page via ``?page_size=`` up to a hard cap of 200.
    """

    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200
