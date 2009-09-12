# -*- coding: utf-8 -*-
from django.contrib.auth.models import User, Group
from django.shortcuts import render_to_response
from django.template import RequestContext

from apps.gcd.models import Indexer


def profile(request):
    indexer = request.user.get_profile()
    return render_to_response(
      'gcd/accounts/profile.html',
      {'user' : indexer },
      context_instance=RequestContext(request))

