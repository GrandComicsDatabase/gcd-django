# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

from apps.indexer.views import ViewTerminationError


class ErrorHandlingMiddleware:
    def process_exception(self, request, exception):
        if isinstance(exception, ViewTerminationError):
            return exception.get_response(request)

        return None
