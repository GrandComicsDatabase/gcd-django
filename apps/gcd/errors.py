# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from apps.gcd.views import ViewTerminationError, render_error
from django.utils.translation import ugettext as _


class ErrorWithMessage(ViewTerminationError):
    def __init__(self, message):
        self.message = message

    def get_response(self, request):
        return render_error(request, _(self.message), redirect=False)


class ErrorHandlingMiddleware:
    def process_exception(self, request, exception):
        if isinstance(exception, ViewTerminationError):
            return exception.get_response(request)

        return None
