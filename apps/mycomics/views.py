from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.core import urlresolvers

def index(request):
    """Generates the front index page."""

    vars = {'next': urlresolvers.reverse('collections')}
    return render_to_response('mycomics/index.html', vars,
                              context_instance=RequestContext(request))

@login_required
def collections(request):
    collection_list = request.user.collector.collections.all()
    vars = {'collection_list': collection_list}

    return render_to_response('mycomics/collections.html', vars,
                          context_instance=RequestContext(request))

@login_required
def collection(request, collection_id):
    collection = request.user.collector.collections.get(id=collection_id)
    vars = {'collection': collection}

    return render_to_response('mycomics/collection.html', vars,
                              context_instance=RequestContext(request))
