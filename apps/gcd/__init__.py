"""
The gcd app contains the core code for displaying GCD content to site users.
Currently, the gcd app also contains shared code such as the indexer profile
model, the error model, and several other things.
"""

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