# -*- coding: utf-8 -*-
from django.contrib.auth import logout
from apps.indexer.views import render_error
from django.utils.deprecation import MiddlewareMixin

#
# read_only mode, keep all users logged out
#

class ReadOnlyMiddleware(MiddlewareMixin):
    def process_response(self, request, response): 
        if request.user.is_authenticated:
            logout(request)
            return render_error(request, "Online editing is currently turned "
                "off, no user can login. We are working on the site. "
                "More information on the <a href='/'>main page</a>.", 
              redirect=False, is_safe=True)
        return response
