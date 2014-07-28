

1

from django.contrib.auth.decorators import login_required



2

from django.template import RequestContext



3

from django.shortcuts import render_to_response, get_object_or_404



4

from django.core import urlresolvers



5

from django.http import HttpResponseRedirect



6



7

from apps.gcd.models import Issue



8

from apps.mycomics.models import CollectionItem



9



10

def index(request):



    11

"""Generates the front index page."""



12



13

vars = {'next': urlresolvers.reverse('collections')}



14

return render_to_response('mycomics/index.html', vars,



                          15

context_instance=RequestContext(request))



16



17

@login_required



18

def collections(request):



    19

collection_list = request.user.collector.collections.all()



20

vars = {'collection_list': collection_list}



21



22

return render_to_response('mycomics/collections.html', vars,



                          23

context_instance=RequestContext(request))



24 

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

25

@login_required



26

def have_issue(request, issue_id):



    27

issue = get_object_or_404(Issue, id=issue_id)



28



29

collected = CollectionItem.objects.create(issue=issue)



30

collected.collections.add(request.user.collector.default_have_collection)



31



32

return HttpResponseRedirect(urlresolvers.reverse('apps.gcd.views.details.issue',



                                                 33

kwargs={'issue_id': issue_id} ))



34



35

@login_required



36

def want_issue(request, issue_id):



    37

issue = get_object_or_404(Issue, id=issue_id)



38



39

collected = CollectionItem.objects.create(issue=issue)



40

collected.collections.add(request.user.collector.default_want_collection)



41



42

return HttpResponseRedirect(urlresolvers.reverse('apps.gcd.views.details.issue',



                                                 43

kwargs={'issue_id': issue_id} ))