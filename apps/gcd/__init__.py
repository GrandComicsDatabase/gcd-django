"""
The gcd app contains the core code for displaying GCD content to site users.
Currently, the gcd app also contains shared code such as the indexer profile
model, the error model, and several other things.
"""

from apps.gcd.views import ViewTerminationError, render_error
from django.utils.translation import ugettext as _


class ErrorWithMessage(ViewTerminationError):
    def __init__(self, message):
        ViewTerminationError.__init__(self, None)
        self.message = message


class ErrorHandlingMiddleware:
    def process_exception(self, request, exception):
        if isinstance(exception, ViewTerminationError):
            return exception.response or render_error(request,
                                                      _(exception.message),
                                                      redirect=False)

        return None