# -*- coding: utf-8 -*-
from django.contrib.auth import logout
from apps.gcd.views import render_error

#
# read_only mode, keep all users logged out
#

class ReadOnlyMiddleware:
    def process_response(self, request, response): 
        if request.user.is_authenticated():
            logout(request)
            return render_error(request, "Online editing is currently turned "
                "off, no user can login. We are working on the site. "
                "More information on the <a href='/'>main page</a>.", 
              redirect=False, is_safe=True)
        return response
