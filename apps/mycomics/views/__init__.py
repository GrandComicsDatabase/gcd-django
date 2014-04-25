from django.template import RequestContext
from django.shortcuts import render_to_response

def index(request):
    """Generates the front index page."""

    vars = {}
    return render_to_response('mycomics/index.html', vars,
                              context_instance=RequestContext(request))
