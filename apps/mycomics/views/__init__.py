from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.shortcuts import render_to_response

def index(request):
    """Generates the front index page."""

    vars = {}
    return render_to_response('mycomics/index.html', vars,
                              context_instance=RequestContext(request))

@login_required
def collections(request):
    vars = {}
    return render_to_response('mycomics/collections.html', vars,
                          context_instance=RequestContext(request))
