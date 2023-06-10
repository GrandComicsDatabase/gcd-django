import os
import tempfile
import chardet

from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
import django.urls as urlresolvers
from django.http import HttpResponseRedirect, Http404
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.utils.html import conditional_escape as esc
from django.utils.html import mark_safe

from djqscsv import render_to_csv_response
import csv

from apps.indexer.views import render_error, ErrorWithMessage
from apps.gcd.models import Issue, Series
from apps.gcd.views import ResponsePaginator, paginate_response
from apps.gcd.views.details import do_on_sale_weekly
from apps.gcd.templatetags.credits import show_keywords_comma
from apps.gcd.views.search_haystack import PaginatedFacetedSearchView, \
    GcdSearchQuerySet

from apps.select.views import store_select_data

from apps.mycomics.forms import CollectionForm, CollectionItemForm, \
                                CollectionSelectForm, CollectorForm, \
                                LocationForm, PurchaseLocationForm
from apps.stddata.models import Date
from apps.stddata.forms import DateForm
from apps.mycomics.models import Collection, CollectionItem, Subscription, \
                                 Location, PurchaseLocation, \
                                 CollectionItemFilter
from django.utils.translation import ugettext as _

INDEX_TEMPLATE = 'mycomics/index.html'
COLLECTION_TEMPLATE = 'mycomics/collection.html'
COLLECTION_SERIES_TEMPLATE = 'mycomics/collection_series.html'
COLLECTION_LIST_TEMPLATE = 'mycomics/collections.html'
COLLECTION_FORM_TEMPLATE = 'mycomics/collection_form.html'
COLLECTION_ITEM_TEMPLATE = 'mycomics/collection_item.html'
COLLECTION_SUBSCRIPTIONS_TEMPLATE = 'mycomics/collection_subscriptions.html'
MESSAGE_TEMPLATE = 'mycomics/message.html'
SETTINGS_TEMPLATE = 'mycomics/settings.html'
DEFAULT_PER_PAGE = 25


def index(request):
    """Generates the front index page."""
    if request.user:
        return HttpResponseRedirect(urlresolvers.reverse('collections_list'))
    vars = {'next': urlresolvers.reverse('collections_list')}
    return render(request, INDEX_TEMPLATE, vars)


@login_required
def display_message(request):
    """Generates a page displaying only a message set in messages framework."""
    return render(request, MESSAGE_TEMPLATE, {})


@login_required
def collections_list(request):
    def_have = request.user.collector.default_have_collection
    def_want = request.user.collector.default_want_collection
    collection_list = request.user.collector.collections.exclude(
        id=def_have.id).exclude(id=def_want.id).order_by('name')
    vars = {'collection_list': collection_list}

    return render(request, COLLECTION_LIST_TEMPLATE, vars)


def view_collection(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)
    if request.user.is_authenticated and \
       collection.collector == request.user.collector:
        collection_list = request.user.collector.ordered_collections()
    elif collection.public is True:
        collection_list = Collection.objects.none()
    elif not request.user.is_authenticated:
        return redirect('%s?next=%s' % (settings.LOGIN_URL, request.path))
    else:
        raise PermissionDenied

    items = collection.items.all().select_related('issue__series')
    base_url = urlresolvers.reverse('view_collection',
                                    kwargs={'collection_id': collection_id})
    needed_covers_url = urlresolvers.reverse("process_advanced_search") + \
                        "?target=issue&method=iexact&logic=False" \
                        "&cover_needed=on&in_collection=%s" \
                        "&in_selected_collection=on" \
                        "&order1=series&order2=date" % collection_id
    unindexed_issues_url = urlresolvers.reverse("process_advanced_search") + \
                           "?target=issue&method=iexact&logic=False" \
                           "&is_indexed=False&in_collection=%s" \
                           "&in_selected_collection=on" \
                           "&order1=series&order2=date" % collection_id
    vars = {'collection': collection,
            'collection_list': collection_list,
            'base_url': base_url,
            'needed_covers_url': needed_covers_url,
            'unindexed_issues_url': unindexed_issues_url}
    data = set(items.values_list('issue__series__publisher'))
    publishers = []
    for i in data:
        publishers.append(i[0])
    f = CollectionItemFilter(request.GET, queryset=items,
                             collection=collection, publishers=publishers)
    vars['filter'] = f
    paginator = ResponsePaginator(f.qs, vars=vars, per_page=DEFAULT_PER_PAGE,
                                  alpha=True)
    paginator.paginate(request)
    get_copy = request.GET.copy()
    get_copy.pop('page', None)
    if get_copy:
        extra_query_string = '&%s' % get_copy.urlencode()
    else:
        extra_query_string = ''
    vars['extra_query_string'] = extra_query_string

    return render(request, COLLECTION_TEMPLATE, vars)


def view_collection_series(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)
    if request.user.is_authenticated and \
       collection.collector == request.user.collector:
        collection_list = request.user.collector.ordered_collections()
    elif collection.public is True:
        collection_list = Collection.objects.none()
    elif not request.user.is_authenticated:
        return redirect('%s?next=%s' % (settings.LOGIN_URL, request.path))
    else:
        raise PermissionDenied

    items = collection.items.all().select_related('issue__series')
    series_ids = items.values_list('issue__series__id', flat=True)\
                      .order_by('issue__series__id')\
                      .distinct()
    series_list = Series.objects.filter(id__in=series_ids)
    base_url = urlresolvers.reverse('view_collection_series',
                                    kwargs={'collection_id': collection_id})
    needed_covers_url = urlresolvers.reverse("process_advanced_search") + \
                        "?target=issue&method=iexact&logic=False" \
                        "&cover_needed=on&in_collection=%s" \
                        "&in_selected_collection=on" \
                        "&order1=series&order2=date" % collection_id
    unindexed_issues_url = urlresolvers.reverse("process_advanced_search") + \
                           "?target=issue&method=iexact&logic=False" \
                           "&is_indexed=False&in_collection=%s" \
                           "&in_selected_collection=on" \
                           "&order1=series&order2=date" % collection_id
    vars = {'collection': collection,
            'collection_list': collection_list,
            'base_url': base_url,
            'needed_covers_url': needed_covers_url,
            'unindexed_issues_url': unindexed_issues_url}
    paginator = ResponsePaginator(series_list, vars=vars,
                                  per_page=DEFAULT_PER_PAGE, alpha=True)
    paginator.paginate(request)
    return render(request, COLLECTION_SERIES_TEMPLATE, vars)


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

    return render(request, COLLECTION_FORM_TEMPLATE, {'form': form})


@login_required
def delete_collection(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id,
                                   collector=request.user.collector)
    collection.delete()
    # Since above command doesn't delete any CollectionItems I just delete here
    # all collection items not belonging now to any collection.
    CollectionItem.objects.filter(collections=None).delete()
    messages.success(
      request,
      mark_safe(_('Collection <b>%s</b> deleted.' % esc(collection.name))))
    return HttpResponseRedirect(urlresolvers.reverse('collections_list'))


@login_required
def export_collection(request, collection_id):
    """
    Export of collections in csv-format. Only used fields are exported.
    """
    collection = get_object_or_404(Collection, id=collection_id,
                                   collector=request.user.collector)
    filename = str(collection).replace(' ', '_')

    export_data = ["issue__series__name", "issue__series__publisher__name",
                   "issue__series__year_began",
                   "issue"]
    field_header_map = {"issue__series__name": "series",
                        "issue__series__publisher__name": "publisher",
                        "issue__series__year_began": "series year",
                        "notes": "description",
                        "id": "tags"}
    field_serializer_map = {'issue':
                            (lambda x:
                             "%s" % Issue.objects.get(id=x).full_descriptor),
                            'id':
                            (lambda x:
                             "%s" % show_keywords_comma(CollectionItem
                                                        .objects.get(id=x))),
                            "acquisition_date":
                            (lambda x: "%s" % Date.objects.get(id=x)),
                            "sell_date":
                            (lambda x: "%s" % Date.objects.get(id=x)), }
    if collection.condition_used:
        export_data.append("grade")
    if collection.acquisition_date_used:
        export_data.append("acquisition_date")
    if collection.sell_date_used:
        export_data.append("sell_date")
    if collection.location_used:
        export_data.append("location")
    if collection.purchase_location_used:
        export_data.append("purchase_location")
    if collection.was_read_used:
        export_data.append("was_read")
    if collection.for_sale_used:
        export_data.append("for_sale")
    if collection.signed_used:
        export_data.append("signed")
    if collection.price_paid_used:
        export_data.append("price_paid")
        export_data.append("price_paid_currency__code")
        field_header_map["price_paid_currency__code"] = ""
    if collection.market_value_used:
        export_data.append("market_value")
        export_data.append("market_value_currency__code")
        field_header_map["market_value_currency__code"] = ""
    if collection.sell_price_used:
        export_data.append("sell_price")
        export_data.append("sell_price_currency__code")
        field_header_map["sell_price_currency__code"] = ""
    export_data.append("notes")
    export_data.append("id")

    items = collection.items.all()

    return render_to_csv_response(
      items.values(*export_data),
      append_datestamp=True,
      field_serializer_map=field_serializer_map,
      field_header_map=field_header_map,
      filename=filename)


def get_item_for_collector(item_id, collector):
    item = get_object_or_404(CollectionItem, id=item_id)
    # checking if this user can see this item
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


def get_collection_for_owner(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)
    if collection.collector.user != request.user:
        return None, render_error(
          request, 'Only the owner of a collection can add issues to it.',
          redirect=False)
    return collection, None


@login_required
def delete_item(request, item_id, collection_id):
    if request.method != 'POST':
        raise ErrorWithMessage("This page may only be accessed through the "
                               "proper form.")

    collection = get_object_or_404(Collection, id=collection_id)
    item = get_item_for_collector(item_id, request.user.collector)

    check_item_is_in_collection(request, item, collection)

    position = collection.items.filter(issue__series__sort_name__lte=
                                       item.issue.series.sort_name)\
                               .exclude(issue__series__sort_name=
                                        item.issue.series.sort_name,
                                        issue__series__year_began__gt=
                                        item.issue.series.year_began)\
                               .exclude(issue__series_id=
                                        item.issue.series.id,
                                        issue__sort_code__gte=
                                        item.issue.sort_code).count()

    collection.items.remove(item)
    messages.success(
      request,
      mark_safe(_("Item <b>%s</b> removed from %s" % (
                  esc(item.issue.full_name()),
                  esc(collection)))))
    if not item.collections.count():
        if item.acquisition_date:
            item.acquisition_date.delete()
        if item.sell_date:
            item.sell_date.delete()
        item.delete()
    else:
        return HttpResponseRedirect(urlresolvers.reverse(
          'view_item',
          kwargs={'item_id': item.id,
                  'collection_id': item.collections.all()[0].id}))

    return HttpResponseRedirect(urlresolvers.reverse('view_collection',
                                kwargs={'collection_id': collection_id}) +
                                "?page=%d" % (position / DEFAULT_PER_PAGE + 1))


@login_required
def move_item(request, item_id, collection_id):
    if request.method != 'POST':
        raise ErrorWithMessage("This page may only be accessed through the "
                               "proper form.")
    from_collection = get_object_or_404(Collection, id=collection_id)
    item = get_item_for_collector(item_id, request.user.collector)
    check_item_is_in_collection(request, item, from_collection)
    collection_form = CollectionSelectForm(request.user.collector, None,
                                           request.POST)
    if collection_form.is_valid():
        to_collection_id = collection_form.cleaned_data['collection']
        to_collection = get_object_or_404(Collection, id=to_collection_id)

        check_item_is_not_in_collection(request, item, to_collection)
        if 'move' in request.POST:
            from_collection.items.remove(item)
            item.collections.add(to_collection)
            messages.success(request, _("Item moved between collections"))
            if to_collection.own_used and to_collection.own_default is not None:
                if to_collection.own_default != item.own:
                    item.own = to_collection.own_default
                    item.save()
                    messages.warning(
                      request,
                      mark_safe(_("Item status for own/want differed from"
                                  " default of new collection <b>%s</b> and "
                                  "was changed." % esc(to_collection.name))))
            return HttpResponseRedirect(
              urlresolvers.reverse('view_item',
                                   kwargs={'item_id': item_id,
                                           'collection_id': to_collection_id}))
        elif 'copy' in request.POST:
            item.collections.add(to_collection)
            messages.success(request, _("Item copied between collections"))
            if to_collection.own_used and \
               to_collection.own_default is not None:
                if to_collection.own_default != item.own:
                    messages.warning(request, _("Own/want default for new "
                                     "collection differs from item status."))
        else:
            messages.error(request, _("Item unchanged"))
    else:
        messages.error(request, _("Item unchanged"))

    return HttpResponseRedirect(urlresolvers.reverse('view_item',
                                kwargs={'item_id': item_id,
                                        'collection_id': collection_id}))


def view_item(request, item_id, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)
    collector = collection.collector
    if request.user.is_authenticated and \
       collector == request.user.collector:
        item = get_item_for_collector(item_id, request.user.collector)
    elif collection.public is True:
        item = get_item_for_collector(item_id, collector)
    elif not request.user.is_authenticated:
        return redirect('%s?next=%s' % (settings.LOGIN_URL, request.path))
    else:
        raise PermissionDenied

    check_item_is_in_collection(request, item, collection)

    sell_date_form = None
    acquisition_date_form = None
    if request.user.is_authenticated and \
       collector == request.user.collector:
        initial = {}
        if collector.default_currency:
            if not item.price_paid_currency:
                initial['price_paid_currency'] = collector.default_currency
            if not item.sell_price_currency:
                initial['sell_price_currency'] = collector.default_currency
            if not item.market_value_currency:
                initial['market_value_currency'] = collector.default_currency
        item_form = CollectionItemForm(collector, instance=item,
                                       initial=initial)
        if item.collections.filter(sell_date_used=True).exists():
            sell_date_form = DateForm(instance=item.sell_date,
                                      prefix='sell_date')
            sell_date_form.fields['date'].label = _('Sell date')
        if item.collections.filter(acquisition_date_used=True).exists():
            acquisition_date_form = DateForm(instance=item.acquisition_date,
                                             prefix='acquisition_date')
            acquisition_date_form.fields['date'].label = _('Acquisition date')
        collection_form = CollectionSelectForm(
          collector, excluded_collections=item.collections.all())
        other_collections = item.collections.exclude(id=collection.id)
    else:
        item_form = None
        collection_form = None
        other_collections = None

    # TODO with django1.6 use first/last here
    item_before = collection.items.filter(issue__series__sort_name__lte=
                                          item.issue.series.sort_name)\
                                  .exclude(issue__series__sort_name=
                                           item.issue.series.sort_name,
                                           issue__series__year_began__gt=
                                           item.issue.series.year_began)\
                                  .exclude(issue__series_id=
                                           item.issue.series.id,
                                           issue__sort_code__gt=
                                           item.issue.sort_code)\
                                  .exclude(issue__series_id=
                                           item.issue.series.id,
                                           issue__sort_code=
                                           item.issue.sort_code,
                                           id__gte=item.id).reverse()

    if item_before:
        page = int(item_before.count() / DEFAULT_PER_PAGE + 1)
        item_before = item_before[0]
    else:
        page = 1
    item_after = collection.items.filter(issue__series__sort_name__gte=
                                         item.issue.series.sort_name)\
                                 .exclude(issue__series__sort_name=
                                          item.issue.series.sort_name,
                                          issue__series__year_began__lt=
                                          item.issue.series.year_began)\
                                 .exclude(issue__series_id=
                                          item.issue.series.id,
                                          issue__sort_code__lt=
                                          item.issue.sort_code)\
                                 .exclude(issue__series_id=
                                          item.issue.series.id,
                                          issue__sort_code=
                                          item.issue.sort_code,
                                          id__lte=item.id)
    if item_after:
        item_after = item_after[0]

    return render(request, COLLECTION_ITEM_TEMPLATE,
                  {'item': item, 'item_form': item_form,
                   'item_before': item_before,
                   'item_after': item_after,
                   'page': page,
                   'collection': collection,
                   'other_collections': other_collections,
                   'sell_date_form': sell_date_form,
                   'acquisition_date_form': acquisition_date_form,
                   'collection_form': collection_form})


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
            if sell_date_form_valid and acquisition_date_form_valid:
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
                return render(request, COLLECTION_ITEM_TEMPLATE,
                              {'item': item, 'item_form': item_form,
                               'collection': collection,
                               'sell_date_form': sell_date_form,
                               'acquisition_date_form': acquisition_date_form})
        else:
            messages.error(request, _('Some data was entered incorrectly.'))
            return render(request, COLLECTION_ITEM_TEMPLATE,
                          {'item': item, 'item_form': item_form,
                           'collection': collection,
                           'sell_date_form': sell_date_form,
                           'acquisition_date_form': acquisition_date_form})
        return HttpResponseRedirect(
            urlresolvers.reverse('view_item',
                                 kwargs={'item_id': item_id,
                                         'collection_id': collection_id}))

    raise Http404


def create_collection_item(issue, collection):
    collected = CollectionItem.objects.create(issue=issue)
    collected.collections.add(collection)
    if collection.own_used:
        collected.own = collection.own_default
        collected.save()
    return collected


def add_issues_to_collection(request, collection_id, issues, redirect,
                             post_process_selection=None):
    collection, error_return = get_collection_for_owner(request,
                                                        collection_id)
    if not collection:
        return error_return
    for issue in issues:
        collected = create_collection_item(issue, collection)
        if post_process_selection:
            post_process_selection(collected)
    request.session['collection_id'] = collection_id
    return HttpResponseRedirect(redirect)


@login_required
def add_single_issue_to_collection(request, issue_id):
    if not request.POST:
        raise ErrorWithMessage("No collection was selected.")
    issue = get_object_or_404(Issue, id=issue_id)
    collection, error_return = get_collection_for_owner(
      request, collection_id=int(request.POST['collection_id']))
    if not collection:
        return error_return
    collected = create_collection_item(issue, collection)
    messages.success(
      request,
      mark_safe("Issue <a href='%s'>%s</a> was added to your <b>%s</b> "
                "collection." % (collected.get_absolute_url(collection),
                                 esc(issue), esc(collection.name))))
    request.session['collection_id'] = collection.id
    return HttpResponseRedirect(urlresolvers.reverse('show_issue',
                                kwargs={'issue_id': issue_id}))


@login_required
def add_selected_issues_to_collection(request, data):
    selections = data['selections']
    issues = Issue.objects.filter(id__in=selections['issue'])
    if 'story' in selections:
        issues |= Issue.objects.filter(story__id__in=selections['story'])
    issues = issues.distinct()
    if not issues.count():
        raise ErrorWithMessage("No issues were selected.")

    post_process_selection = data.get('post_process_selection', None)
    if 'confirm_selection' in request.POST:
        collection_id = int(request.POST['collection_id'])
        return add_issues_to_collection(
          request, collection_id, issues,
          urlresolvers.reverse('view_collection',
                               kwargs={'collection_id': collection_id}),
          post_process_selection=post_process_selection)
    else:
        if 'collection_list' in data:
            collection_list = data['collection_list']
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
def select_issues_from_preselection(request, issues, cancel,
                                    post_process_selection=None,
                                    collection_list=None,
                                    not_found=None):
    if not issues.exists():
        raise ErrorWithMessage("No issues to select from.")
    data = {'issue': True,
            'allowed_selects': ['issue', ],
            'return': add_selected_issues_to_collection,
            'cancel': cancel}
    if post_process_selection:
        data['post_process_selection'] = post_process_selection
    if collection_list:
        data['collection_list'] = collection_list
    select_key = store_select_data(request, None, data)
    context = {'select_key': select_key,
               'multiple_selects': True,
               'item_name': 'issue',
               'plural_suffix': 's',
               'no_bulk_edit': True,
               'all_pre_selected': True,
               'heading': 'Issues found that can be selected for import.',
               'not_found': not_found
               }
    return paginate_response(request, issues,
                             'gcd/search/issue_list.html', context,
                             per_page=issues.count())


def select_from_on_sale_weekly(request, year=None, week=None):
    issues_on_sale, context = do_on_sale_weekly(request, year, week)
    if context is None:
        return issues_on_sale
    data = {'issue': True,
            'allowed_selects': ['issue'],
            'return': add_selected_issues_to_collection}
    select_key = store_select_data(request, None, data)
    context.update({'select_key': select_key,
                    'multiple_selects': True,
                    'item_name': 'issue',
                    'plural_suffix': 's',
                    'no_bulk_edit': True,
                    'all_pre_selected': True,
                    'heading': 'Issues'
                    })
    return paginate_response(request, issues_on_sale,
                             'gcd/status/issues_on_sale.html', context,
                             per_page=max(1, issues_on_sale.count()))


def file_len(fname):
    with open(fname, 'rb') as f:
        for i, l in enumerate(f):
            pass
    return i + 1


@login_required
def import_items(request):
    if 'import_my_issues' in request.FILES:
        # real file to be able to use pythons Universal Newline Support
        tmpfile_handle, tmpfile_name = tempfile.mkstemp(".mycomics_import")
        for chunk in request.FILES['import_my_issues'].chunks():
            os.write(tmpfile_handle, chunk)
        os.close(tmpfile_handle)

        number_of_lines = file_len(tmpfile_name)
        if number_of_lines > 501:
            messages.error(request, _('More than 500 lines. Please split'
                                      ' the import file into smaller chunks.'))
            return HttpResponseRedirect(urlresolvers.reverse(
                                        'collections_list'))
        rawdata = open(tmpfile_name, 'rb').read()
        result = chardet.detect(rawdata)
        encoding = result['encoding']

        tmpfile = open(tmpfile_name, encoding=encoding)
        upload = csv.reader(tmpfile)
        issues = Issue.objects.none()
        line = next(upload)
        not_found = ""
        if line[0] == 'Title' and line[1] == 'Issue Number':
            comicbookdb = True
            publisher_col = -1
            for i in range(2, len(line)):
                if line[i] == 'Publisher':
                    publisher_col = i
            if publisher_col < 0:
                raise ErrorWithMessage("We cannot find 'Publisher' in the "
                                       "list of columns")
        else:
            comicbookdb = False
            upload = csv.reader(tmpfile)
        for line in upload:
            if len(line) == 0:
                break
            issue = Issue.objects.none()
            if comicbookdb:
                if line[0][-1] == ')' and line[0][-6] == '(':
                    series = line[0][:-6].strip()
                else:
                    raise ErrorWithMessage("Cannot find '(year)')")
                try:
                    number = line[1].strip().lstrip('#')
                    publisher = line[publisher_col].strip()
                except IndexError:
                    raise ErrorWithMessage("Not enough columns")
                if publisher == "Image Comics Inc.":
                    publisher = "Image"
                elif publisher == "DC Comics":
                    publisher = "DC"
                elif publisher == "Valiant Entertainment LLC":
                    publisher = "Valiant Entertainment"
                elif publisher == "Archie Comic Publications Inc.":
                    publisher = "Archie"
                elif publisher == "IDW Publishing":
                    publisher = "IDW"
                issue = Issue.objects.filter(
                    series__name=series,
                    number=number,
                    series__publisher__name=publisher)
            else:
                if len(line) >= 2:
                    series = line[0].strip()
                    number = line[1].strip().lstrip('#')
                    if series != '' and number != '':
                        issue = Issue.objects.filter(
                                              series__name__icontains=series,
                                              number=number)
                    else:
                        issue = Issue.objects.none()
                if len(line) >= 3:
                    publisher = line[2].strip()
                    if publisher != '':
                        issue = issue.filter(
                                series__publisher__name__icontains=publisher)
                if len(line) >= 4:
                    language_code = line[3].strip()
                    if language_code != '':
                        issue = issue.filter(
                                series__language__code__iexact=language_code)
            if issue.count() == 0:
                not_found += '","'.join(line) + '\n'
            else:
                issues = issues | issue
        if 'import_my_issues_base_only' in request.POST:
            issues = issues.filter(variant_of=None)
        issues = issues.distinct()
        tmpfile.close()
        os.remove(tmpfile_name)
        cancel = HttpResponseRedirect(urlresolvers
                                      .reverse('collections_list'))
        return select_issues_from_preselection(request, issues, cancel,
                                               not_found=not_found)


@login_required
def add_series_issues_to_collection(request, series_id):
    series = get_object_or_404(Series, id=series_id)
    if 'confirm_selection' in request.POST:
        issues = series.active_base_issues()
        # add all issues (without variants) to the selected collection
        collection_id = int(request.POST['collection_id'])
        collection = get_object_or_404(Collection, id=collection_id)
        item_before = collection.items.filter(issue__series__sort_name__lt=
                                              series.sort_name).reverse()

        if item_before:
            page = "?page=%d" % (item_before.count() / DEFAULT_PER_PAGE + 1)
        else:
            page = ""
        messages.success(
          request,
          mark_safe("All issues added to your <a href='%s%s'>%s</a> "
                    "collection." % (collection.get_absolute_url(), page,
                                     esc(collection.name))))
        return add_issues_to_collection(
          request, collection_id, issues,
          urlresolvers.reverse('show_series', kwargs={'series_id': series_id}))
    else:
        issues = None
        if 'import_my_issues_to_series' in request.FILES:
            # real file to be able to use pythons Universal Newline Support
            tmpfile_handle, tmpfile_name = tempfile.mkstemp(".mycomics_import")
            for chunk in request.FILES['import_my_issues_to_series'].chunks():
                os.write(tmpfile_handle, chunk)
            os.close(tmpfile_handle)
            tmpfile = open(tmpfile_name, 'U')
            issue_numbers = []
            for line in tmpfile:
                issue_numbers.append(line.strip(' \n').lstrip('#'))
            issues = Issue.objects.filter(series__id=series_id,
                                          number__in=issue_numbers)
            issues = issues.distinct()
            tmpfile.close()
            os.remove(tmpfile_name)
        elif 'which_issues' in request.GET:
            # allow user to choose which issues to add to selected collection
            if request.GET['which_issues'] == 'base_issues':
                issues = series.active_base_issues()
            elif request.GET['which_issues'] == 'all_issues':
                issues = series.active_issues()
            elif request.GET['which_issues'] == 'variant_issues':
                issues = series.active_issues().exclude(variant_of=None)
        return_url = HttpResponseRedirect(urlresolvers.reverse('show_series',
                                          kwargs={'series_id': series_id}))
        if issues:
            return select_issues_from_preselection(request, issues, return_url)
        else:
            messages.warning(request, 'no corresponding issues found')
            return return_url


def post_process_subscription(item):
    # set last_pulled of a subscription to today for those series
    # for which at least one issue was added to the collection
    subscription = item.issue.series.subscription_set\
                                    .get(collection=item.collections.get())
    subscription.last_pulled = datetime.today()
    subscription.save()


@login_required
def subscriptions_collection(request, collection_id):
    collection, error_return = get_collection_for_owner(
      request, collection_id=collection_id)
    if not collection:
        return error_return
    subscriptions = collection.subscriptions.order_by('series__sort_name')
    return render(request, COLLECTION_SUBSCRIPTIONS_TEMPLATE,
                  {'collection': collection,
                   'subscriptions': subscriptions,
                   'collection_list': request.user.collector
                                             .ordered_collections()})


@login_required
def subscribed_into_collection(request, collection_id):
    collection, error_return = get_collection_for_owner(
      request, collection_id=collection_id)
    if not collection:
        return error_return
    issues = Issue.objects.none()
    for subscription in collection.subscriptions.all():
        new_issues = subscription.series.active_issues()\
          .filter(created__gte=subscription.last_pulled)\
          .exclude(collectionitem__collections=collection)
        issues |= new_issues
    return_url = HttpResponseRedirect(
      urlresolvers.reverse('subscriptions_collection',
                           kwargs={'collection_id': collection_id}))
    if issues:
        return select_issues_from_preselection(
          request, issues, return_url,
          post_process_selection=post_process_subscription,
          collection_list=[collection])
    else:
        messages.warning(request, 'No new issues for subscribed series found.')
        return return_url


@login_required
def subscribe_series(request, series_id):
    series = get_object_or_404(Series, id=series_id)
    collection_id = int(request.POST['collection_id'])
    collection, error_return = get_collection_for_owner(
      request, collection_id=collection_id)
    if not collection:
        return error_return
    subscription = Subscription.objects.filter(series=series,
                                               collection=collection)
    if subscription.exists():
        messages.error(
          request, mark_safe(_('Series %s is already subscribed for the '
                             'collection %s.' % (esc(series),
                                                 esc(collection)))))
    elif series.is_current:
        Subscription.objects.create(series=series,
                                    collection=collection,
                                    last_pulled=datetime.today())
        messages.success(
          request, mark_safe(_('Series %s is now subscribed for the '
                             'collection %s.' % (esc(series),
                                                 esc(collection)))))
    else:
        messages.error(request, _('Selected series is not ongoing.'))

    return HttpResponseRedirect(urlresolvers.reverse('show_series',
                                kwargs={'series_id': series_id}))


@login_required
def unsubscribe_series(request, subscription_id):
    subscription = get_object_or_404(Subscription, id=subscription_id)
    if subscription.collection.collector.user != request.user:
        return render_error(
          request, 'Only the owner of a collection can unsubscribe series.',
          redirect=False)
    subscription.delete()
    return HttpResponseRedirect(
             urlresolvers.reverse('subscriptions_collection',
                                  kwargs={'collection_id':
                                          subscription.collection.id}))


@login_required
def mycomics_search(request):
    sqs = GcdSearchQuerySet().facet('facet_model_name').facet('country') \
                             .facet('language').facet('publisher')

    allowed_selects = ['issue', 'story']
    data = {'issue': True,
            'story': True,
            'allowed_selects': allowed_selects,
            'return': add_selected_issues_to_collection,
            'cancel': HttpResponseRedirect(urlresolvers
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

    location_form = LocationForm(
      instance=Location(user=request.user.collector))
    purchase_location_form = PurchaseLocationForm(
        instance=PurchaseLocation(user=request.user.collector))
    locations = Location.objects.filter(user=request.user.collector)
    purchase_locations = PurchaseLocation.objects.filter(
        user=request.user.collector)

    return render(request, SETTINGS_TEMPLATE,
                  {'settings_form': settings_form,
                   'location_form': location_form,
                   'purchase_location_form': purchase_location_form,
                   'locations': locations,
                   'purchase_locations': purchase_locations})


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
        # Since there is no real validation, this should't happen anyway
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
