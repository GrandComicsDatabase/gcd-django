# -*- coding: utf-8 -*-


import logging

from apps.indexer.views import render_error, ViewTerminationError
from django.db import OperationalError
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

# MySQL gave up on a lock wait, or broke a deadlock.
LOCK_CONFLICTS = (1205, 1213)


class ErrorHandlingMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        """
        Answer a view that ended with a page of its own, or with a lock
        conflict in the database; the request's transaction has already
        been undone by then, so nothing was saved.
        """
        if isinstance(exception, ViewTerminationError):
            return exception.get_response(request)

        if isinstance(exception, OperationalError) and \
           exception.args[:1] and exception.args[0] in LOCK_CONFLICTS:
            logger.warning('Lock conflict on %s', request.path,
                           exc_info=exception)
            response = render_error(
              request, 'An error occurred when processing the request. '
                       'Please check and try again.',
              redirect=False)
            # A failed request for the log and for a script, as the server
            # error was; 503 tells that it can be sent again.
            response.status_code = 503
            return response

        return None
