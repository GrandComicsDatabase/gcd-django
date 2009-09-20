# -*- coding: utf-8 -*-
from django.shortcuts import render_to_response
from django.template import RequestContext

def profile(request):
    return render_to_response(
      'gcd/accounts/profile.html',
      context_instance=RequestContext(request))

