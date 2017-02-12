# -*- coding: utf-8 -*-
from apps.indexer.views import render_error

def dummy(request, id=None, issue_id=None, model_name=None, image_type=None,
          image_id=None):
    return render_error(request, \
      "Online editing and change history are currently turned off. "
      "We are working on the site. More information on the "
      "<a href='/'>main page</a>.", redirect=False, is_safe=True)
