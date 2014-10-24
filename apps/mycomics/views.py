from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.core import urlresolvers
from django.http import HttpResponseRedirect

from apps.gcd.models import Issue
from apps.gcd.views import render_error, ResponsePaginator, paginate_response
from apps.gcd.views.search_haystack import PaginatedFacetedSearchView, \
    GcdSearchQuerySet
from apps.mycomics.forms import CollectionForm
from apps.mycomics.models import Collection, CollectionItem

from apps.select.views import store_select_data

from apps.mycomics.forms import CollectionForm
from apps.mycomics.models import Collection, CollectionItem

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
    collection = get_object_or_404(Collection, id=collection_id,
                                   collector=request.user.collector)
    items = collection.items.all().order_by('issue__series', 'issue__sort_code')
    collection_list = request.user.collector.collections.all().order_by('name')
    vars = {'collection': collection,
            'collection_list': collection_list}
    paginator = ResponsePaginator(items, template=COLLECTION_TEMPLATE,
                                  vars=vars, page_size=25)

    return paginator.paginate(request)


@login_required
def edit_collection(request, collection_id=None):
    """
    View for editing and adding of collections. First request comes as GET,
    which results in displaying page with form. Second request with POST saves
    this form.
    """
    if collection_id:
        collection = get_object_or_404(Collection, id=collection_id,
                                       collector=request.user.collector)
    else:
        collection = Collection(collector=request.user.collector)

    if request.method == 'POST':
        form = CollectionForm(request.POST, instance=collection)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(
                urlresolvers.reverse('collections_list'))

    else:
        form = CollectionForm(instance=collection)

    return render_to_response(COLLECTION_FORM_TEMPLATE, {'form': form},
                              context_instance=RequestContext(request))


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


@login_required
def add_selected_issues_to_collection(request, data):
    selections = data['selections']
    issues = Issue.objects.filter(id__in=selections['issue'])
    if 'story' in selections:
        issues |= Issue.objects.filter(story__id__in=selections['story'])
    issues = issues.distinct()
    if 'confirm_selection' in request.POST:
        collection_id = int(request.POST['collection_id'])
        collection = get_object_or_404(Collection, id=collection_id)
        if collection.collector.user != request.user:
            return render_error(request,
              'Only the owner of a collection can add issues to it.',
              redirect=False)
        for issue in issues:
            collected = CollectionItem.objects.create(issue=issue)
            collected.collections.add(collection)
        return HttpResponseRedirect(
            urlresolvers.reverse('view_collection',
                                kwargs={'collection_id': collection_id}))
    else:
        collection_list = request.user.collector.collections.all()\
                                                            .order_by('name')
        context = {
                'item_name': 'issue',
                'plural_suffix': 's',
                'no_bulk_edit': True,
                'heading': 'Issues',
                'confirm_selection': True,
                'collection_list': collection_list
            }
        return paginate_response(request, issues,
                                 'gcd/search/issue_list.html', context)

@login_required
def mycomics_search(request):
    sqs = GcdSearchQuerySet().facet('facet_model_name')

    allowed_selects = ['issue', 'story']
    data = {'issue': True,
            'story': True,
            'allowed_selects': allowed_selects,
            'return': add_selected_issues_to_collection,
            'cancel': HttpResponseRedirect(urlresolvers\
                                           .reverse('collections_list'))}
    select_key = store_select_data(request, None, data)
    context = {'select_key': select_key,
               'multiple_selects': True,
               'allowed_selects': allowed_selects}
    return PaginatedFacetedSearchView(searchqueryset=sqs)(request,
                                                          context=context)
