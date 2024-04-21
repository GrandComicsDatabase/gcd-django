# -*- coding: utf-8 -*-


from apps.indexer.views import ViewTerminationError
from django.utils.deprecation import MiddlewareMixin

class ErrorHandlingMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if isinstance(exception, ViewTerminationError):
            return exception.get_response(request)

        return None
