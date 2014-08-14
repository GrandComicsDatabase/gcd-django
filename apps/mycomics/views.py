from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.core import urlresolvers
from django.http import HttpResponseRedirect

from apps.gcd.models import Issue
from apps.mycomics.models import CollectionItem

from apps.gcd.views import ResponsePaginator

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
    items = collection.items.all()
    collection_list = request.user.collector.collections.all()
    vars = {'collection': collection,
            'collection_list': collection_list}
    paginator = ResponsePaginator(items, template='mycomics/collection.html',
                                  vars=vars, page_size=25)

    return paginator.paginate(request)


@login_required
def have_issue(request, issue_id):
    issue = get_object_or_404(Issue, id=issue_id)

    collected = CollectionItem.objects.create(issue=issue)
    collected.collections.add(request.user.collector.default_have_collection)

    return HttpResponseRedirect(
        urlresolvers.reverse('apps.gcd.views.details.issue',
                             kwargs={'issue_id': issue_id}))

@login_required
def want_issue(request, issue_id):
    issue = get_object_or_404(Issue, id=issue_id)

    collected = CollectionItem.objects.create(issue=issue)
    collected.collections.add(request.user.collector.default_want_collection)

    return HttpResponseRedirect(
        urlresolvers.reverse('apps.gcd.views.details.issue',
                             kwargs={'issue_id': issue_id}))

