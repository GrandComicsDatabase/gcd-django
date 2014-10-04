from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.core import urlresolvers
from django.http import HttpResponseRedirect

from apps.gcd.models import Issue
from apps.mycomics.forms import CollectionForm
from apps.mycomics.models import CollectionItem

from apps.gcd.views import ResponsePaginator

INDEX_TEMPLATE='mycomics/index.html'
COLLECTION_TEMPLATE='mycomics/collection.html'
COLLECTION_LIST_TEMPLATE='mycomics/collections.html'
COLLECTION_FORM_TEMPLATE='mycomics/collectionForm.html'

def index(request):
    """Generates the front index page."""
    vars = {'next': urlresolvers.reverse('collections_list')}
    return render_to_response(INDEX_TEMPLATE, vars,
                              context_instance=RequestContext(request))


@login_required
def collections_list(request):
    def_have = request.user.collector.default_have_collection
    def_want = request.user.collector.default_want_collection
    collection_list = request.user.collector.collections.exclude(
        id=def_have.id).exclude(id=def_want.id).order_by('name')
    vars = {'collection_list': collection_list}

    return render_to_response(COLLECTION_LIST_TEMPLATE, vars,
                              context_instance=RequestContext(request))


@login_required
def view_collection(request, collection_id):
    collection = request.user.collector.collections.get(id=collection_id)
    items = collection.items.all().order_by('issue__series', 'issue__sort_code')
    collection_list = request.user.collector.collections.all().order_by('name')
    vars = {'collection': collection,
            'collection_list': collection_list}
    paginator = ResponsePaginator(items, template=COLLECTION_TEMPLATE,
                                  vars=vars, page_size=25)

    return paginator.paginate(request)


@login_required
def add_collection(request):
    if request.method == 'GET':
        vars = {'form': CollectionForm}
        return render_to_response(COLLECTION_FORM_TEMPLATE, vars,
                              context_instance=RequestContext(request))
    if request.method == 'POST':
        form = CollectionForm(request.POST)
        if not form.is_valid():
            return render_to_response(COLLECTION_FORM_TEMPLATE, {'form': form},
                                      context_instance=RequestContext(request))
        collection = form.save(commit=False)
        collection.collector = request.user.collector
        collection.save()
        form.save_m2m()
        return HttpResponseRedirect(urlresolvers.reverse('collections_list'))


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

