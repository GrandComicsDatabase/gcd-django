import csv

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.core import urlresolvers
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.core.exceptions import PermissionDenied
from django.conf import settings

from apps.gcd.models import Issue, Series
from apps.gcd.views import render_error, ResponsePaginator, paginate_response
from apps.gcd.views.alpha_pagination import AlphaPaginator
from apps.gcd import ErrorWithMessage
from apps.gcd.views.search_haystack import PaginatedFacetedSearchView, \
    GcdSearchQuerySet

from apps.oi.import_export import UnicodeWriter

from apps.select.views import store_select_data

from apps.mycomics.forms import *
from apps.stddata.forms import DateForm
from apps.mycomics.models import Collection, CollectionItem

from django.contrib import messages
from django.utils.translation import ugettext as _

INDEX_TEMPLATE='mycomics/index.html'
COLLECTION_TEMPLATE='mycomics/collection.html'
COLLECTION_LIST_TEMPLATE='mycomics/collections.html'
COLLECTION_FORM_TEMPLATE='mycomics/collection_form.html'
COLLECTION_ITEM_TEMPLATE='mycomics/collection_item.html'
MESSAGE_TEMPLATE='mycomics/message.html'
SETTINGS_TEMPLATE='mycomics/settings.html'
DEFAULT_PER_PAGE=25


def index(request):
    """Generates the front index page."""
    if request.user:
        return HttpResponseRedirect(urlresolvers.reverse('collections_list'))
    vars = {'next': urlresolvers.reverse('collections_list')}
    return render_to_response(INDEX_TEMPLATE, vars,
                              context_instance=RequestContext(request))


@login_required
def display_message(request):
    """Generates a page displaying only a message set in messages framework."""
    return render_to_response(MESSAGE_TEMPLATE, {},
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


def view_collection(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)
    if request.user.is_authenticated() and \
      collection.collector == request.user.collector:
        collection_list = request.user.collector.ordered_collections()
    elif collection.public == True:
        collection_list = Collection.objects.none()
    elif not request.user.is_authenticated():
        return redirect('%s?next=%s' % (settings.LOGIN_URL, request.path))
    else:
        raise PermissionDenied

    items = collection.items.all().order_by('issue__series',
                                            'issue__sort_code')\
                                  .select_related('issue__series')
    vars = {'collection': collection,
            'collection_list': collection_list}
    paginator = ResponsePaginator(items, template=COLLECTION_TEMPLATE,
                                  vars=vars, per_page=DEFAULT_PER_PAGE)
    alpha_paginator = AlphaPaginator(items, per_page=DEFAULT_PER_PAGE)
    paginator.vars['alpha_paginator'] = alpha_paginator
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
            messages.success(request, _('Collection saved.'))
            return HttpResponseRedirect(
                urlresolvers.reverse('collections_list'))

    else:
        form = CollectionForm(instance=collection)

    return render_to_response(COLLECTION_FORM_TEMPLATE, {'form': form},
                              context_instance=RequestContext(request))


@login_required
def delete_collection(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id,
                                   collector=request.user.collector)
    collection.delete()
    #Since above command doesn't delete any CollectionItems I just delete here
    # all collection items not belonging now to any collection.
    CollectionItem.objects.filter(collections=None).delete()
    messages.success(request, _('Collection deleted.'))
    return HttpResponseRedirect(urlresolvers.reverse('collections_list'))

@login_required
def export_collection(request, collection_id):
    """
    Export of collections in csv-format. Only used fields are exported.
    """
    collection = get_object_or_404(Collection, id=collection_id,
                                   collector=request.user.collector)
    filename = unicode(collection).replace(' ', '_').encode('utf-8')
    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = 'attachment; filename=%s.csv' % filename
    writer = UnicodeWriter(response)

    export_data = ["series", "publisher", "number"]
    if collection.condition_used:
        export_data.append("grade")
    if collection.acquisition_date_used:
        export_data.append("acquisition date")
    if collection.sell_date_used:
        export_data.append("sell_date")
    if collection.location_used:
        export_data.append("location")
    if collection.purchase_location_used:
        export_data.append("purchase location")
    if collection.was_read_used:
        export_data.append("was read")
    if collection.for_sale_used:
        export_data.append("for sale")
    if collection.signed_used:
        export_data.append("signed")
    if collection.price_paid_used:
        export_data.append("price paid")
    if collection.market_value_used:
        export_data.append("market value")
    if collection.sell_price_used:
        export_data.append("sell price")
    writer.writerow(export_data)

    items = collection.items.all().order_by('issue__series',
                                            'issue__sort_code')
    for item in items:
        export_data = [item.issue.series.name, item.issue.series.publisher.name]
        if item.issue.variant_name:
            export_data.append("%s [%s]" % (item.issue.issue_descriptor(),
                                            item.issue.variant_name))
        else:
            export_data.append(item.issue.issue_descriptor())
        if collection.condition_used:
            export_data.append(unicode(item.grade) if item.grade else u'')
        if collection.acquisition_date_used:
            export_data.append(unicode(item.acquisition_date) \
                               if item.acquisition_date else u'')
        if collection.sell_date_used:
            export_data.append(unicode(item.sell_date) \
                               if item.sell_date else u'')
        if collection.location_used:
            export_data.append(unicode(item.location) \
                               if item.location else u'')
        if collection.purchase_location_used:
            export_data.append(unicode(item.purchase_location) \
                               if item.purchase_location else u'')
        if collection.was_read_used:
            export_data.append(unicode(item.was_read) \
                               if item.was_read != None else u'')
        if collection.for_sale_used:
            export_data.append(unicode(item.for_sale))
        if collection.signed_used:
            export_data.append(unicode(item.signed))
        if collection.price_paid_used:
            export_data.append(u"%s %s" % (item.price_paid,
                                           item.price_paid_currency.code) \
                               if item.price_paid else u'')
        if collection.market_value_used:
            export_data.append(u"%s %s" % (item.market_value,
                                           item.market_value_currency.code) \
                               if item.market_value else u'')
        if collection.sell_price_used:
            export_data.append(u"%s %s" % (item.sell_price,
                                           item.sell_price_currency.code) \
                               if item.sell_price else u'')
        writer.writerow(export_data)

    return response


def get_item_for_collector(item_id, collector):
    item = get_object_or_404(CollectionItem, id=item_id)
    #checking if this user can see this item
    if item.collections.all()[0].collector != collector:
        raise PermissionDenied
    return item


def check_item_is_in_collection(request, item, collection):
    if item not in collection.items.all():
        raise ErrorWithMessage("This item doesn't belong to given collection.")


def check_item_is_not_in_collection(request, item, collection):
    if item in collection.items.all():
        raise ErrorWithMessage("This item already does belong to given "
                               "collection.")


@login_required
def delete_item(request, item_id, collection_id):
    if request.method != 'POST':
        raise ErrorWithMessage("This page may only be accessed through the "
                               "proper form.")

    collection = get_object_or_404(Collection, id=collection_id)
    item = get_item_for_collector(item_id, request.user.collector)

    check_item_is_in_collection(request, item, collection)

    position = collection.items.filter(issue__series__name__lte=
                                         item.issue.series.name)\
                               .exclude(issue__series__name=
                                          item.issue.series.name,
                                        issue__sort_code__gt=
                                          item.issue.sort_code).count()

    collection.items.remove(item)
    if not item.collections.count():
        if item.acquisition_date:
            item.acquisition_date.delete()
        if item.sell_date:
            item.sell_date.delete()
        item.delete()
    messages.success(request, _("Item removed from collection"))
    return HttpResponseRedirect(urlresolvers.reverse('view_collection',
                                  kwargs={'collection_id': collection_id}) + \
                                "?page=%d" % (position/DEFAULT_PER_PAGE + 1))


@login_required
def move_item(request, item_id, collection_id):
    if request.method != 'POST':
        raise ErrorWithMessage("This page may only be accessed through the "
                               "proper form.")
    from_collection = get_object_or_404(Collection, id=collection_id)
    item = get_item_for_collector(item_id, request.user.collector)
    check_item_is_in_collection(request, item, from_collection)
    collection_form = CollectionSelectForm(request.user.collector, None, request.POST)
    if collection_form.is_valid():
        to_collection_id = collection_form.cleaned_data['collection']
        to_collection = get_object_or_404(Collection, id=to_collection_id)

        check_item_is_in_collection(request, item, from_collection)
        check_item_is_not_in_collection(request, item, to_collection)
        if 'move' in request.POST:
            from_collection.items.remove(item)
            item.collections.add(to_collection)
            messages.success(request, _("Item moved between collections"))
            return HttpResponseRedirect(urlresolvers.reverse('view_item',
                                    kwargs={'item_id': item_id,
                                            'collection_id': to_collection_id}))
        #elif 'copy' in request.POST:
            #item.collections.add(to_collection)
            #messages.success(request, _("Item copied between collections"))
        else:
            messages.error(request, _("Item unchanged"))

    return HttpResponseRedirect(urlresolvers.reverse('view_item',
                                kwargs={'item_id': item_id,
                                        'collection_id': collection_id}))


def view_item(request, item_id, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)
    if request.user.is_authenticated() and \
      collection.collector == request.user.collector:
        item = get_item_for_collector(item_id, request.user.collector)
    elif collection.public == True:
        item = get_item_for_collector(item_id, collection.collector)
    elif not request.user.is_authenticated():
        return redirect('%s?next=%s' % (settings.LOGIN_URL, request.path))
    else:
        raise PermissionDenied

    check_item_is_in_collection(request, item, collection)

    sell_date_form = None
    acquisition_date_form = None
    if request.user.is_authenticated() and \
      collection.collector == request.user.collector:
        item_form = CollectionItemForm(request.user.collector, instance=item)
        if item.collections.filter(sell_date_used=True).exists():
            sell_date_form = DateForm(instance=item.sell_date, prefix='sell_date')
            sell_date_form.fields['date'].label = _('Sell date')
        if item.collections.filter(acquisition_date_used=True).exists():
            acquisition_date_form = DateForm(instance=item.acquisition_date,
                                            prefix='acquisition_date')
            acquisition_date_form.fields['date'].label = _('Acquisition date')
        collection_form = CollectionSelectForm(request.user.collector,
                                        collections=item.collections.all())
        other_collections = item.collections.exclude(id=collection.id)
    else:
        item_form = None
        collection_form = None
        other_collections = None

    item_before = collection.items.filter(issue__series__name__lte=
                                              item.issue.series.name)\
                                    .exclude(issue__series__name=
                                               item.issue.series.name,
                                             issue__sort_code__gte=
                                               item.issue.sort_code).reverse()

    if item_before:
        page = item_before.count()/DEFAULT_PER_PAGE + 1
        item_before = item_before[0]
    else:
        page = 1
    item_after = collection.items.filter(issue__series__name__gte=
                                             item.issue.series.name)\
                                     .exclude(issue__series__name=
                                                item.issue.series.name,
                                              issue__sort_code__lte=
                                                item.issue.sort_code)
    if item_after:
        item_after = item_after[0]

    return render_to_response(COLLECTION_ITEM_TEMPLATE,
                              {'item': item, 'item_form': item_form,
                               'item_before': item_before,
                               'item_after': item_after,
                               'page': page,
                               'collection': collection,
                               'other_collections': other_collections,
                               'sell_date_form': sell_date_form,
                               'acquisition_date_form': acquisition_date_form,
                               'collection_form': collection_form},
                              context_instance=RequestContext(request))


@login_required
def save_item(request, item_id, collection_id):
    if request.method == 'POST':
        collection = get_object_or_404(Collection, id=collection_id)
        item = get_item_for_collector(item_id, request.user.collector)
        item_form = CollectionItemForm(request.user.collector, request.POST,
                                       instance=item)
        item_form_valid = item_form.is_valid()

        if item.collections.filter(sell_date_used=True).exists():
            sell_date_form = DateForm(request.POST, instance=item.sell_date,
                                      prefix='sell_date')
            sell_date_form_valid = sell_date_form.is_valid()
        else:
            sell_date_form = None
            sell_date_form_valid = True

        if item.collections.filter(acquisition_date_used=True).exists():
            acquisition_date_form = DateForm(request.POST,
                                             instance=item.acquisition_date,
                                             prefix='acquisition_date')
            acquisition_date_form_valid = acquisition_date_form.is_valid()
        else:
            acquisition_date_form = None
            acquisition_date_form_valid = True

        if item_form_valid:
            if  sell_date_form_valid and acquisition_date_form_valid:
                if sell_date_form:
                    sell_date = sell_date_form.save()
                else:
                    sell_date = None
                if acquisition_date_form:
                    acquisition_date = acquisition_date_form.save()
                else:
                    acquisition_date = None
                item = item_form.save(commit=False)
                item.acquisition_date = acquisition_date
                item.sell_date = sell_date
                item.save()
                item_form.save_m2m()

                messages.success(request, _('Item saved.'))
            else:
                if sell_date_form:
                    sell_date_form.fields['date'].label = _('Sell date')
                if acquisition_date_form:
                    acquisition_date_form.fields['date'].label = \
                                                        _('Acquisition date')
                messages.error(request, _('Date was entered in wrong format.'))
                return render_to_response(COLLECTION_ITEM_TEMPLATE,
                                   {'item': item, 'item_form': item_form,
                                    'collection': collection,
                                    'sell_date_form': sell_date_form,
                                    'acquisition_date_form': acquisition_date_form},
                                   context_instance=RequestContext(request))
        else:
            messages.error(request, _('Some data was entered incorrectly.'))
            return render_to_response(COLLECTION_ITEM_TEMPLATE,
                               {'item': item, 'item_form': item_form,
                                'collection': collection,
                                'sell_date_form': sell_date_form,
                                'acquisition_date_form': acquisition_date_form},
                               context_instance=RequestContext(request))
        return HttpResponseRedirect(
            urlresolvers.reverse('view_item',
                                 kwargs={'item_id': item_id,
                                         'collection_id': collection_id}))

    raise Http404


def add_issues_to_collection(request, collection_id, issues, redirect):
    collection = get_object_or_404(Collection, id=collection_id)
    if collection.collector.user != request.user:
        return render_error(request,
            'Only the owner of a collection can add issues to it.',
            redirect=False)
    for issue in issues:
        collected = CollectionItem.objects.create(issue=issue)
        collected.collections.add(collection)
    return HttpResponseRedirect(redirect)


@login_required
def add_single_issue_to_collection(request, issue_id):
    issue = Issue.objects.filter(id=issue_id)
    return add_issues_to_collection(request, 
        int(request.POST['collection_id']), issue,
        urlresolvers.reverse('show_issue', 
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
        return add_issues_to_collection(request,
          collection_id, issues, urlresolvers.reverse('view_collection',
                                 kwargs={'collection_id': collection_id}))
    else:
        collection_list = request.user.collector.ordered_collections()
        context = {
                'item_name': 'issue',
                'plural_suffix': 's',
                'no_bulk_edit': True,
                'heading': 'Issues',
                'confirm_selection': True,
                'collection_list': collection_list
            }
        return paginate_response(request, issues,
                                 'gcd/search/issue_list.html', context,
                                 per_page=issues.count())


@login_required
def add_series_issues_to_collection(request, series_id):
    series = get_object_or_404(Series, id=series_id)
    issues = series.active_base_issues()
    if 'confirm_selection' in request.POST:
        # add all issues (without variants) to the selected collection
        collection_id = int(request.POST['collection_id'])
        collection = get_object_or_404(Collection, id=collection_id)
        messages.success(request, u"All issues added to your '%s' collection."\
                                  % collection.name)
        return add_issues_to_collection(request, collection_id, issues,
          urlresolvers.reverse('show_series', kwargs={'series_id': series_id}))
    else:
        # allow user to choose which issues to add to the selected collection
        if request.GET['which_issues'] == 'all_issues':
            issues = series.active_issues()
        elif request.GET['which_issues'] == 'variant_issues':
            issues = series.active_issues().exclude(variant_of=None)
        data = {'issue': True,
                'allowed_selects': ['issue',],
                'return': add_selected_issues_to_collection,
                'cancel': HttpResponseRedirect(urlresolvers\
                            .reverse('show_series',
                                     kwargs={'series_id': series_id}))}
        select_key = store_select_data(request, None, data)
        context = {'select_key': select_key,
                'multiple_selects': True,
                'item_name': 'issue',
                'plural_suffix': 's',
                'no_bulk_edit': True,
                'all_pre_selected': True,
                'heading': 'Issues'
            }
        return paginate_response(request, issues,
                                 'gcd/search/issue_list.html', context,
                                 per_page=issues.count())


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


@login_required
def mycomics_settings(request):
    """
    View for editing user settings. First request comes as GET,
    which results in displaying page with form. Second request with POST saves
    this form.
    """
    if request.method == 'POST':
        settings_form = CollectorForm(request.user.collector, request.POST)
        if settings_form.is_valid():
            settings_form.save()
            messages.success(request, _('Settings saved.'))
            return HttpResponseRedirect(
                urlresolvers.reverse('mycomics_settings'))
    else:
        settings_form = CollectorForm(request.user.collector)

    location_form = LocationForm(instance=Location(user=request.user.collector))
    purchase_location_form = PurchaseLocationForm(
        instance=PurchaseLocation(user=request.user.collector))
    locations = Location.objects.filter(user=request.user.collector)
    purchase_locations = PurchaseLocation.objects.filter(
        user=request.user.collector)

    return render_to_response(SETTINGS_TEMPLATE,
                              {'settings_form' : settings_form,
                               'location_form' : location_form,
                               'purchase_location_form' : purchase_location_form,
                               'locations' : locations,
                               'purchase_locations' : purchase_locations},
                              context_instance=RequestContext(request))


def _edit_location(request, location_class, location_form_class, location_id):
    if location_id:
        location = get_object_or_404(location_class, id=location_id,
                                     user=request.user.collector)
    else:
        location = location_class(user=request.user.collector)
    form = location_form_class(request.POST, instance=location)
    if form.is_valid():
        form.save()
        messages.success(request, _('Location saved.'))
    else:
        #Since there is no real validation, this should't happen anyway
        messages.error(_('Entered data was incorrect.'))

    return HttpResponseRedirect(urlresolvers.reverse('mycomics_settings'))


@login_required
def edit_location(request, id=None):
    return _edit_location(request, Location, LocationForm, id)


@login_required
def edit_purchase_location(request, id=None):
    return _edit_location(request, PurchaseLocation, PurchaseLocationForm, id)


def _delete_location(request, location_class, location_id):
    location = get_object_or_404(location_class, id=location_id,
                                 user=request.user.collector)
    location.delete()
    messages.success(request, _('Location deleted.'))
    return HttpResponseRedirect(urlresolvers.reverse('mycomics_settings'))


@login_required
def delete_location(request, location_id):
    return _delete_location(request, Location, location_id)


@login_required
def delete_purchase_location(request, location_id):
    return _delete_location(request, PurchaseLocation, location_id)

