import hashlib
from random import random

from haystack.forms import FacetedSearchForm

from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.db.models import BooleanField, Exists, ExpressionWrapper, \
                             OuterRef, Q, Value, IntegerField, F
from django.db.models.functions import Replace
import django.urls as urlresolvers
from django.http import HttpResponse, HttpResponseBadRequest, \
                        HttpResponseRedirect, JsonResponse
from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.utils.datastructures import MultiValueDictKeyError
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django import forms

from django_filters import FilterSet, ModelChoiceFilter, \
                           ModelMultipleChoiceFilter

from dal import autocomplete
from taggit.models import Tag

from apps.gcd.models import Publisher, Series, Issue, Story, StoryType, \
                            Creator, CreatorNameDetail, CreatorSignature, \
                            Feature, FeatureNameDetail, FeatureLogo, \
                            IndiciaPrinter, School, \
                            Character, CharacterNameDetail, Group, \
                            GroupNameDetail, Universe, StoryArc, Brand, \
                            BrandGroup, \
                            STORY_TYPES, DEPRECATED_TYPES, CORE_TYPES
from apps.stddata.models import Country, Language
from apps.gcd.templatetags.credits import get_native_language_name
from apps.gcd.models.issue import IssuePublisherTable
from apps.gcd.models.publisher import PublisherSearchTable
from apps.gcd.models.series import SeriesPublisherTable
from apps.gcd.models.story import StoryTable
from apps.indexer.views import render_error
from apps.select.forms import get_select_cache_form, get_select_search_form, \
                              get_select_issue_story_form, series_label


##############################################################################
# helper functions
##############################################################################


def _cant_get_key(request):
    return render_error(
      request,
      'Internal data for selecting objects is corrupted. If this message '
      'persists try logging out and logging in.', redirect=False)


##############################################################################
# cache and select objects
##############################################################################


def store_select_data(request, select_key, data):
    if not select_key:
        salt = hashlib.sha1(str(random()).encode('utf8')).hexdigest()[:5]
        select_key = hashlib.sha1(
            (salt + str(request.user)).encode('utf8')).hexdigest()
    for item in data:
        request.session['%s_%s' % (select_key, item)] = data[item]
    request.session['%s_items' % select_key] = list(data)
    return select_key


def get_select_data(request, select_key):
    keys = request.session['%s_items' % select_key]
    data = {}
    for item in keys:
        data[item] = request.session['%s_%s' % (select_key, item)]
    return data


def get_select_forms(request, initial, data, publisher=False,
                     series=False, issue=False, story=False, cover=False,
                     exclude_issue_id=None):
    """Return the row search form, the results form and the cache form."""
    if issue:
        cached_issues = get_cached_issues(request)
    else:
        cached_issues = None
    if story:
        cached_stories = get_cached_stories(request)
    else:
        cached_stories = None
    if story or cover:
        cached_covers = get_cached_covers(request)
    else:
        cached_covers = None

    search_form = get_select_search_form(search_publisher=publisher,
                                         search_series=series,
                                         search_issue=issue,
                                         search_story=story,
                                         search_cover=cover)
    new_search_form = get_select_issue_story_form()(initial=initial)
    if data:
        search_form = search_form(data)
    else:
        search_form = search_form(initial=initial)

    cache_form = get_select_cache_form(cached_issues=cached_issues,
                                       cached_stories=cached_stories,
                                       cached_covers=cached_covers,
                                       exclude_issue_id=exclude_issue_id)()

    return search_form, new_search_form, cache_form


@permission_required('indexer.can_reserve')
def process_multiple_selects(request, select_key):
    try:
        data = get_select_data(request, select_key)
    except KeyError:
        return _cant_get_key(request)

    allowed_selects = data['allowed_selects']
    choices = request.POST.getlist('object_choice')
    selections = {}
    for allowed in allowed_selects:
        selections[allowed] = []
    for select in choices:
        object_type, object_id = select.split('_')
        if object_type in allowed_selects:
            selections[object_type].append(int(object_id))
    data['selections'] = selections
    store_select_data(request, select_key, data)
    # all return functions for multiple selects are in mycomics.views.py
    import apps.mycomics.views  # here to avoid circular imports
    return_function = getattr(apps.mycomics.views, data['return'])
    return return_function(request, data)


@permission_required('indexer.can_reserve')
def process_select_search_haystack(request, select_key):
    from apps.gcd.views.search_haystack import GcdSearchQuerySet, \
                                               PaginatedFacetedSearchView
    try:
        data = get_select_data(request, select_key)
    except KeyError:
        return _cant_get_key(request)

    form = FacetedSearchForm(request.GET)
    if not form.is_valid():  # do not think this can happen
        raise ValueError
    cd = form.cleaned_data
    if cd['q']:
        context = {'select_key': select_key}
        allowed_selects = []
        for select in ['publisher', 'series', 'issue', 'story']:
            if data.get(select, False):
                allowed_selects.append(select)
        context['allowed_selects'] = allowed_selects
        sqs = GcdSearchQuerySet().facet('facet_model_name')
        # the row of what the selector does not take would have no button
        if allowed_selects:
            sqs = sqs.filter(facet_model_name__in=allowed_selects)
        return PaginatedFacetedSearchView(
          searchqueryset=sqs, template='search/tw_search.html')(
            request, context=context)
    else:
        return HttpResponseRedirect(
          urlresolvers.reverse(data.get('selection_view', 'select_object'),
                               kwargs={'select_key': select_key})
          + '?' + request.META['QUERY_STRING'])


# Values or results listed at most: with more the page asks to narrow them.
FEW_RESULTS = 20
TOO_MANY_VALUES = 'Too many results: write more.'
# Left out when series names are compared, so that "xmen" finds "X-Men". The
# other dashes and apostrophes are in hundreds of names.
NAME_SEPARATORS = ('-', '\u2013', '\u2014', '\u2015', ' ', '.', "'", '\u2018',
                   '\u2019', ':', ',', '/')
# Series read to tell how many are left, before dropping the deleted ones.
SERIES_READ = 20000


def _without_separators(field):
    """Return the field as a database expression without separators."""
    expression = F(field)
    for separator in NAME_SEPARATORS:
        expression = Replace(expression, Value(separator), Value(''))
    return expression


def _separators_removed(text):
    """Return the text without separators."""
    for separator in NAME_SEPARATORS:
        text = text.replace(separator, '')
    return text


def _number_query(number, prefix=''):
    """Return the query of a number and of those that go on after it."""
    return Q(**{f'{prefix}number': number}) \
        | Q(**{f'{prefix}number__istartswith': number + ' '})


def _few_rows(rows):
    """Return how many rows there are, reading no more than the limit needs."""
    return len(rows.order_by().values_list('pk', flat=True)[:FEW_RESULTS + 1])


def _has_one_issue(series):
    """Return whether the series has one issue, so a number narrows nothing."""
    return Issue.objects.filter(series_id=series,
                                deleted=False)[:2].count() == 1


def _menu_id(request, menu):
    """Return the id chosen in a menu of the form, if the value is an id."""
    value = request.GET.get(menu, '').strip()
    return value if value.isdecimal() else None


def _search_object(request):
    """Return what the form lists: all, story, cover or issue."""
    search_object = request.GET.get('search_object')
    if search_object in ('story', 'cover', 'issue'):
        return search_object
    return 'all'


@permission_required('indexer.can_reserve', raise_exception=True)
def process_htmx_select_search(request, select_key):
    """
    List what the form finds, or ask for the next field if too much.

    search_object chooses what: all, story, cover or issue. A selector that
    takes no stories has no such choice and lists issues, whatever is asked.
    """
    try:
        data = get_select_data(request, select_key)
    except KeyError:
        # the page writes a failing status; an error page would be swapped in
        return HttpResponseBadRequest('This selection is no longer available.')
    search_object = _search_object(request) if data.get('story') else 'issue'
    publisher = _menu_id(request, 'publisher_auto')
    series = _menu_id(request, 'series_auto')
    series_year = request.GET.get('series_year_auto', '').strip()
    issue_number = request.GET.get('issue_number', '').strip()
    filters = {}
    if series:
        # the chosen series says it all: a publisher or a year that disagree
        # with it would only empty the list
        filters['series_id'] = series
    else:
        if publisher:
            filters['series__publisher_id'] = publisher
        if series_year.isdecimal():
            filters['series__year_began'] = series_year

    def issue_query(prefix=''):
        """Return the query of the issues, seen from the given relation."""
        query = Q(**{prefix + field: filters[field] for field in filters})
        if filters and issue_number:
            # with something else to go by it also finds the numbers that go
            # on after it, such as "1 [Cover A]"
            query &= _number_query(issue_number, prefix)
        elif issue_number:
            query &= Q(**{f'{prefix}number': issue_number})
        return query

    stories = Story.objects.filter(issue_query('issue__'), deleted=False)
    issues = Issue.objects.filter(issue_query(), deleted=False)
    if search_object == 'cover':
        stories = stories.filter(type=STORY_TYPES['cover'])
    elif search_object == 'all':
        # they have no row among the stories, and they are most of the issues
        issues = issues.filter(
          ~Exists(Story.objects.filter(issue=OuterRef('pk'), deleted=False)))

    from apps.gcd.views.details import generic_sortable_list

    def listing(search, table_format, select_target, order_by='issue'):
        """Return the response with the table of the given objects."""
        table = table_format(
            search,
            template_name='gcd/bits/tw_sortable_table.html',
            order_by=order_by)
        table.no_export = True
        table.orderable = False
        return generic_sortable_list(
            request, search, table, 'select/search_results.html',
            {'item_name': 'objects',
             'plural_suffix': '',
             'select_key': select_key,
             'select_target': select_target,
             'select_issue': select_target in ('story', 'cover'),
             'no_bulk_edit': True})

    def found():
        """Return the tables of what the form finds, or ask for more."""
        if not filters and not issue_number:
            # a year that is no number narrows nothing
            if series_year:
                return HttpResponse(
                  '<p>Too many results: choose a Series.</p>')
            return HttpResponse('')
        # with a series and its number there is nothing left to narrow down
        if not (series and issue_number):
            rows = 0 if search_object == 'issue' else _few_rows(stories)
            # read only if needed: among all the issues of a publisher or of a
            # number they take seconds
            if search_object in ('all', 'issue') and rows <= FEW_RESULTS:
                rows += _few_rows(issues)
            if rows > FEW_RESULTS and not (series and _has_one_issue(series)):
                wanted = 'write the Issue Number.' if series \
                    else 'choose a Series.'
                return HttpResponse('<p>Too many results: %s</p>' % wanted)

        if search_object in ('story', 'cover'):
            return listing(stories, StoryTable, search_object)
        if search_object == 'issue':
            return listing(issues, IssuePublisherTable, 'issue')
        # the links to the pages of a table ask for that table only
        paged_table = request.headers.get('HX-Target')
        if paged_table == 'story-results':
            return listing(stories, StoryTable, 'story')
        if paged_table == 'issue-results':
            return listing(issues, IssuePublisherTable, 'issue')
        if not issues.exists():
            return listing(stories, StoryTable, 'story')
        issue_list = listing(issues, IssuePublisherTable, 'issue')
        if not stories.exists():
            return issue_list
        return HttpResponse(listing(stories, StoryTable, 'story').content
                            + issue_list.content)

    response = found()
    # a link to a page of a table asks for that table only
    if 'page' not in request.GET:
        # a selector that takes series can choose this one
        if series and data.get('series'):
            response.content = listing(
              Series.objects.filter(id=series, deleted=False),
              SeriesPublisherTable, 'series', 'name').content \
              + response.content
        # Back and reload find the search in the address of the page
        response['HX-Replace-Url'] = '%s?%s' % (
          urlresolvers.reverse('select_object',
                               kwargs={'select_key': select_key}),
          request.META['QUERY_STRING'])
    return response


@permission_required('indexer.can_reserve')
def process_select_search(request, select_key):
    try:
        data = get_select_data(request, select_key)
    except KeyError:
        return _cant_get_key(request)
    publisher = data.get('publisher', False)
    series = data.get('series', False)
    issue = data.get('issue', False)
    story = data.get('story', False)
    cover = data.get('cover', False)
    if 'search_series' in request.GET:
        issue = False
    search_form = get_select_search_form(search_publisher=publisher,
                                         search_series=series,
                                         search_issue=issue,
                                         search_story=story,
                                         search_cover=cover)(request.GET)
    if not search_form.is_valid():
        return HttpResponseRedirect(
          urlresolvers.reverse(data.get('selection_view', 'select_object'),
                               kwargs={'select_key': select_key})
          + '?' + request.META['QUERY_STRING'])
    cd = search_form.cleaned_data

    if issue:
        select_issue = True
    else:
        select_issue = False

    publisher_name = cd.get('publisher') or '?'
    series_name = cd.get('series') or ''
    number = cd.get('number') or ''
    year = cd.get('year') or ''

    if 'search_story' in request.GET or 'search_cover' in request.GET:
        search = Story.objects.filter(
          issue__number=number,
          deleted=False,
          issue__series__name__icontains=series_name,
          issue__series__publisher__name__icontains=cd['publisher']) \
            .select_related('issue__series__publisher', 'type')
        if year:
            search = search.filter(issue__series__year_began=year)
            heading = '%s (%s, %d series) #%s' % (series_name,
                                                  publisher_name,
                                                  year,
                                                  number)
        else:
            heading = '%s (%s, ? series) #%s' % (series_name,
                                                 publisher_name,
                                                 number)
        if cd['sequence_number']:
            search = search.filter(sequence_number=cd['sequence_number'])
            heading += ', seq.# ' + str(cd['sequence_number'])
        if 'search_cover' in request.GET:
            # ? make StoryType.objects.get(name='cover').id a CONSTANT ?
            search = search.filter(type=StoryType.objects.get(name='cover'))
            base_name = 'cover'
            plural_suffix = 's'
        else:
            base_name = 'stor'
            plural_suffix = 'y,ies'
        heading = 'Search for: ' + heading
        search = search.order_by("issue__series__name",
                                 "issue__series__year_began",
                                 "issue__key_date",
                                 "sequence_number")
        table_format = StoryTable
        order_by = 'issue'
        select_target = 'story'
    elif 'search_issue' in request.GET:
        search = Issue.objects.filter(
          number=number,
          deleted=False,
          series__name__icontains=series_name,
          series__publisher__name__icontains=cd['publisher']) \
            .select_related('series__publisher')
        if year:
            search = search.filter(series__year_began=year)
            heading = '%s (%s, %d series) #%s' % (series_name, publisher_name,
                                                  year, number)
        else:
            heading = '%s (%s, ? series) #%s' % (series_name, publisher_name,
                                                 number)
        heading = 'matching search for: ' + heading
        base_name = 'issue'
        plural_suffix = 's'
        search = search.order_by("series__name", "series__year_began",
                                 "key_date")
        table_format = IssuePublisherTable
        order_by = 'issue'
        select_target = 'issue'
    elif 'search_series' in request.GET:
        search = Series.objects.filter(
          deleted=False,
          name__icontains=series_name,
          publisher__name__icontains=cd['publisher']) \
            .select_related('publisher', 'country', 'language')
        heading = 'Series search for: ' + series_name
        if year:
            search = search.filter(year_began=year)
            heading = '%s (%s, %d series)' % (series_name, publisher_name,
                                              year)
        base_name = 'series'
        plural_suffix = ''
        search = search.order_by("name")
        table_format = SeriesPublisherTable
        order_by = 'name'
        select_target = 'series'
    elif 'search_publisher' in request.GET:
        search = Publisher.objects.filter(deleted=False,
                                          name__icontains=cd['publisher']) \
            .select_related('country')
        heading = 'matching search for: ' + cd['publisher']
        base_name = 'publisher'
        plural_suffix = 's'
        search = search.order_by("name")
        table_format = PublisherSearchTable
        order_by = 'name'
        select_target = 'publisher'

    from apps.gcd.views.details import generic_sortable_list
    table = table_format(
        search,
        template_name='gcd/bits/tw_sortable_table.html',
        order_by=order_by)
    context = {
      'item_name': base_name,
      'plural_suffix': plural_suffix,
      'heading': heading,
      'select_key': select_key,
      'select_target': select_target,
      'select_issue': select_issue and select_target == 'story',
      'no_bulk_edit': True,
      'publisher': cd.get('publisher') or '',
      'series': series_name,
      'year': year,
      'number': number
    }
    return generic_sortable_list(
        request, search, table, 'gcd/search/tw_list_sortable.html', context)


@permission_required('indexer.can_reserve')
def select_object(request, select_key):
    return _select_object(request, select_key)


@permission_required('indexer.can_reserve')
def select_multiple_sequences(request, select_key):
    return _select_object(request, select_key, multiple_sequences=True)


def _select_object(request, select_key, multiple_sequences=False):
    """Show the page of the selector, or go on with the object chosen on it."""
    try:
        data = get_select_data(request, select_key)
    except KeyError:
        return _cant_get_key(request)
    if (not multiple_sequences and
            data.get('selection_view') == 'select_multiple_sequences'):
        if request.method == 'GET':
            destination = urlresolvers.reverse(
                'select_multiple_sequences', kwargs={'select_key': select_key})
            query = request.META.get('QUERY_STRING', '')
            return HttpResponseRedirect(
                destination + ('?' + query if query else ''))
        return _select_object(request, select_key, multiple_sequences=True)
    if multiple_sequences and (data.get('issue') or data.get('publisher') or
                               data.get('series') or not (
                                   data.get('story') or data.get('cover'))):
        return HttpResponseBadRequest('This selection requires sequences '
                                      'only.')
    selection_view = ('select_multiple_sequences' if multiple_sequences
                      else 'select_object')
    if request.method == 'GET':
        if 'refine_search' in request.GET or 'search_issue' in request.GET:
            request_data = request.GET
        else:
            request_data = None
        # the form writes its last search in the address, always with a number
        if 'issue_number' in request.GET:
            initial = request.GET.dict()
            # given what is no id, a menu writes all its rows in the page
            for menu in ('publisher_auto', 'series_auto'):
                initial[menu] = _menu_id(request, menu)
        else:
            initial = data.get('initial', {})
        initial['select_key'] = select_key
        publisher = data.get('publisher', False)
        series = data.get('series', False)
        issue = data.get('issue', False)
        story = data.get('story', False)
        cover = data.get('cover', False)
        exclude_issue_id = data.get('exclude_issue_id')
        disabled_choice_title = data.get('disabled_choice_title', '')
        disabled_choice_help = data.get('disabled_choice_help', '')
        search_form, new_search_form, cache_form = get_select_forms(
          request,
          initial,
          request_data,
          publisher=publisher,
          series=series,
          issue=issue,
          story=story,
          cover=cover,
          exclude_issue_id=(
            exclude_issue_id))
        haystack_form = FacetedSearchForm()
        # sent empty it would reload the page and empty the form below it
        haystack_form.fields['q'].required = True
        cache_choices = []
        if 'object_choice' in cache_form.fields:
            radios = list(cache_form['object_choice'])
            for radio in radios:
                kind = radio.data['value'].split('_')[0]
                if kind not in ('cover', 'story', 'issue'):
                    continue
                cache_choices.append({
                    'radio': radio,
                    'kind': kind,
                })
        cache_choices.sort(key=lambda choice: {
            'story': 0, 'cover': 1, 'issue': 2}[choice['kind']])
        cache_groups = [
            {'kind': kind, 'label': label,
             'choices': [choice for choice in cache_choices
                         if choice['kind'] == kind]}
            for kind, label in [('story', 'Stories'), ('cover', 'Covers'),
                                ('issue', 'Issues')]]
        for index, choice in enumerate(cache_choices, 1):
            choice['help_id'] = 'disabled-choice-%d' % index
        can_copy_multiple = data.get('return') == '_selected_copy_sequence'
        template = ('select/select_cached_sequences.html' if multiple_sequences
                    else 'select/select_object.html')
        # without its cache the session comes back from JSON, without the mark
        return render(request, template,
                      {'heading': mark_safe(data['heading']),
                       'note': data.get('note'),
                       'select_key': select_key,
                       'cache_form': cache_form,
                       'cache_choices': cache_choices,
                       'cache_groups': cache_groups,
                       'cache_size': request.user.indexer.cache_size,
                       'has_cached_objects': any(
                          request.session.get(key)
                          for key in ('cached_issues', 'cached_stories',
                                      'cached_covers')),
                       'show_cache': issue or story or cover,
                       'can_copy_multiple': can_copy_multiple,
                       'disabled_choice_title': disabled_choice_title,
                       'disabled_choice_help': disabled_choice_help,
                       'search_form': search_form,
                       'new_search_form': new_search_form,
                       'search_object': _search_object(request),
                       'haystack_form': haystack_form,
                       'publisher': publisher,
                       'series': series,
                       'issue': issue,
                       'story': story,
                       'cover': cover,
                       'target': data['target']
                       })

    if 'cancel' in request.POST:
        return HttpResponseRedirect(data['cancel'])
    elif 'reorder_cached_objects' in request.POST:
        kind = request.POST['reorder_cached_objects']
        getters = {'story': get_cached_stories, 'cover': get_cached_covers}
        if kind not in getters or not (
                data.get('story') or (kind == 'cover' and data.get('cover'))):
            return JsonResponse({'error':
                                 'This category cannot be reordered.'},
                                status=400)
        choices = request.POST.getlist('ordered_objects')
        try:
            parts = [choice.split('_') for choice in choices]
            ids = [int(pk) for category, pk in parts if category == kind]
        except ValueError:
            return JsonResponse({'error': 'Invalid cache order.'}, status=400)
        if (len(ids) != len(choices) or len(set(ids)) != len(ids)
                or not ids or any(pk <= 0 for pk in ids)):
            return JsonResponse({'error': 'Invalid cache order.'}, status=400)
        current = [obj.id for obj in getters[kind](request) or []]
        if set(ids) != set(current):
            return JsonResponse({
                'error':
                'The cache changed. Reload the page before reordering.'},
                status=409)
        key = 'cached_stories' if kind == 'story' else 'cached_covers'
        request.session[key + '_order'] = ids
        return JsonResponse({'saved': True})
    elif ('copy_selected_cached_objects' in request.POST or
          'confirm_bulk_copy' in request.POST):
        if data.get('return') != '_selected_copy_sequence':
            return HttpResponseBadRequest(
                'This selection does not support copying.')
        from apps.oi.views import copy_cached_sequences
        return copy_cached_sequences(request, data, select_key)
    elif 'remove_selected_cached_objects' in request.POST:
        cache_keys = {'issue': 'cached_issues', 'story': 'cached_stories',
                      'cover': 'cached_covers'}
        kind = request.POST['remove_selected_cached_objects']
        choices = request.POST.getlist('cached_objects')
        if kind in ('all', 'cover'):
            choices += request.POST.getlist('selected_covers')
        if kind not in (*cache_keys, 'all') or not choices:
            return HttpResponseBadRequest('Select cached objects to remove.')
        selected_ids = {}
        for choice in choices:
            try:
                choice_kind, object_id = choice.split('_')
                object_id = int(object_id)
            except ValueError:
                return HttpResponseBadRequest('Invalid cached object.')
            if (choice_kind not in cache_keys or object_id <= 0 or
                    (kind != 'all' and choice_kind != kind)):
                return HttpResponseBadRequest('Invalid cache category or '
                                              'object.')
            selected_ids.setdefault(choice_kind, set()).add(object_id)
        # Validate the whole selection before changing the session. Repeated
        # submissions are harmless: removing an absent ID has no effect.
        for choice_kind, ids in selected_ids.items():
            key = cache_keys[choice_kind]
            request.session[key] = [pk for pk in request.session.get(key, [])
                                    if pk not in ids]
            _sync_cached_order(request, key)
        return HttpResponseRedirect(urlresolvers.reverse(
            selection_view, kwargs={'select_key': select_key}))
    elif 'clear_cache' in request.POST or \
         'remove_cached_object' in request.POST:
        cache_keys = {'issue': 'cached_issues', 'story': 'cached_stories',
                      'cover': 'cached_covers'}
        if 'clear_cache' in request.POST:
            kind = request.POST['clear_cache']
            if kind == 'all':
                for key in cache_keys.values():
                    request.session.pop(key, None)
                    request.session.pop(key + '_order', None)
            elif kind in cache_keys:
                request.session.pop(cache_keys[kind], None)
                request.session.pop(cache_keys[kind] + '_order', None)
            else:
                return HttpResponseBadRequest('Unknown cache category.')
        else:
            try:
                kind, object_id = request.POST['remove_cached_object']\
                                         .split('_')
                key = cache_keys[kind]
                object_id = int(object_id)
            except (ValueError, KeyError):
                return HttpResponseBadRequest('Invalid cached object.')
            request.session[key] = [
                pk for pk in request.session.get(key, []) if pk != object_id]
            _sync_cached_order(request, key)
        return HttpResponseRedirect(urlresolvers.reverse(
            selection_view, kwargs={'select_key': select_key}))
    elif 'select_object' in request.POST:
        try:
            choice = request.POST['object_choice']
            object_type, selected_id = choice.split('_')
            if object_type == 'cover':
                object_type = 'story'
        except MultiValueDictKeyError:
            return render_error(request,
                                'You did not select a cached object. '
                                'Please use the back button to return.',
                                redirect=False)
    elif 'search_select' in request.POST:
        choice = request.POST['object_choice']
        object_type, selected_id = choice.split('_')
        # a cover is chosen as its story
        if object_type == 'cover':
            object_type = 'story'
        # a return function can take any id for the object it expects, as a
        # series bond does with an issue
        if (object_type not in ('publisher', 'series', 'issue', 'story') or
                not (data.get(object_type) or
                     (object_type == 'story' and data.get('cover')))):
            return HttpResponseBadRequest(
              'This selection does not take this kind of object.')
    elif 'entered_issue_id' in request.POST:
        object_type = 'issue'
        try:
            selected_id = int(request.POST['entered_issue_id'])
        except ValueError:
            return render_error(request,
                                'Entered Id must be an integer number. '
                                'Please use the back button to return.',
                                redirect=False)
    elif 'entered_story_id' in request.POST:
        object_type = 'story'
        try:
            selected_id = int(request.POST['entered_story_id'])
        except ValueError:
            return render_error(request,
                                'Entered Id must be an integer number. '
                                'Please use the back button to return.',
                                redirect=False)
    else:
        return render_error(request,
                            'Data for processing the selection is incomplete.',
                            redirect=False)
    # right now all return functions for single selects are in oi.views.py
    import apps.oi.views  # here to avoid circular imports
    return_function = getattr(apps.oi.views, data['return'])
    return return_function(request, data, object_type, selected_id)


def _get_unique_cached_ids(request, key):
    cached_ids = request.session.get(key, [])
    unique_ids = list(dict.fromkeys(cached_ids or []))
    if unique_ids != cached_ids:
        request.session[key] = unique_ids
    return unique_ids


def get_ordered_cached_ids(request, key):
    """Display order is independent of the oldest-first eviction queue."""
    ids = _get_unique_cached_ids(request, key)
    saved_order = request.session.get(key + '_order', [])
    return list(dict.fromkeys([pk for pk in saved_order if pk in ids] + ids))


def _sync_cached_order(request, key):
    if key + '_order' in request.session:
        request.session[key + '_order'] = get_ordered_cached_ids(request, key)


def get_cached_issues(request):
    cached_issues_list = _get_unique_cached_ids(request, 'cached_issues')
    if cached_issues_list:
        cached_issues = []
        for i in range(len(cached_issues_list)):
            try:
                cached_issue = Issue.objects.get(id=cached_issues_list[i],
                                                 deleted=False)
            except Issue.DoesNotExist:
                continue
            cached_issues.append(cached_issue)
        return cached_issues
    else:
        return None


def _process_cached_stories(cached_stories_list):
    if cached_stories_list:
        cached_stories = []
        for i in range(len(cached_stories_list)):
            try:
                cached_story = Story.objects.get(id=cached_stories_list[i],
                                                 deleted=False)
            except Story.DoesNotExist:
                continue
            cached_stories.append(cached_story)
        return cached_stories
    else:
        return None


def get_cached_stories(request):
    cached_stories_list = get_ordered_cached_ids(request, 'cached_stories')
    return _process_cached_stories(cached_stories_list)


def get_cached_covers(request):
    cached_covers_list = get_ordered_cached_ids(request, 'cached_covers')
    return _process_cached_stories(cached_covers_list)


def _process_caching(cached_list, object_id, cache_size):
    """
    Remember each object once, refreshing its position when remembered again.
    """
    cached_list = list(dict.fromkeys(cached_list or []))
    cached_list = [pk for pk in cached_list if pk != object_id]
    cached_list.append(object_id)
    return cached_list[-cache_size:] if cache_size > 0 else []


@permission_required('indexer.can_reserve')
def cache_content(request, issue_id=None, story_id=None, cover_story_id=None):
    """
    Store an issue_id, story_id, or cover_id in the session.
    """
    cache_size = request.user.indexer.cache_size
    # Older profile forms allowed non-positive limits. Do not silently empty
    # the cache when such an account remembers its next object.
    if cache_size is None or cache_size < 1:
        cache_size = 3

    if issue_id:
        cached_issues = request.session.get('cached_issues', None)
        request.session['cached_issues'] = _process_caching(cached_issues,
                                                            issue_id,
                                                            cache_size)
    if story_id:
        cached_stories = request.session.get('cached_stories', None)
        request.session['cached_stories'] = _process_caching(cached_stories,
                                                             story_id,
                                                             cache_size)
        _sync_cached_order(request, 'cached_stories')
        if 'HTTP_REFERER' in request.META:
            return HttpResponseRedirect(request.META['HTTP_REFERER'] + '#%s' %
                                        story_id)
    if cover_story_id:
        cached_covers = request.session.get('cached_covers', None)
        request.session['cached_covers'] = _process_caching(cached_covers,
                                                            cover_story_id,
                                                            cache_size)
        _sync_cached_order(request, 'cached_covers')
    if 'HTTP_REFERER' in request.META:
        return HttpResponseRedirect(request.META['HTTP_REFERER'])
    if not issue_id:
        issue_id = get_object_or_404(
          Story, id=story_id or cover_story_id).issue_id
    return HttpResponseRedirect(urlresolvers.reverse(
      'show_issue', kwargs={'issue_id': issue_id}))


##############################################################################
# auto-complete objects
##############################################################################

def _filter_and_sort(qs, query, field='name', creator_detail=False,
                     disambiguation=False, parent_disambiguation=None,
                     interactive=True, chrono_sort=''):
    if query:
        if disambiguation or parent_disambiguation:
            if query.find(' [') >= 0:
                pos = query.find(' [')
                disambiguation = query[pos+2:query.find(']') if
                                       query.find(']') > 1 else None]
                dis_query = query[:pos]
                if parent_disambiguation:
                    qs_contains = qs.filter(Q(**{
                      '%s__icontains' % field: dis_query,
                      '%s__disambiguation__istartswith'
                      % parent_disambiguation:
                      disambiguation}))
                else:
                    qs_contains = qs.filter(Q(**{'%s__icontains' % field:
                                                 dis_query,
                                                 'disambiguation__istartswith':
                                                 disambiguation}))
                qs_contains |= qs.filter(Q(**{'%s__icontains' % field: query}))
            else:
                qs_contains = qs.filter(Q(**{'%s__icontains' % field: query}))
        else:
            qs_contains = qs.filter(Q(**{'%s__icontains' % field: query}))
        qs_return = None
        if interactive and query.isdigit():
            qs_match_id = qs.filter(Q(**{'id': query}))
            if qs_match_id:
                qs_return = qs_match_id.union(qs_contains)
        if not qs_return:
            if interactive:
                qs_match = qs.filter(Q(**{'%s' % field: query}))
            else:
                qs_match = None
            if qs_match:
                if chrono_sort:
                    qs_contains = qs_contains.exclude(Q(**{'%s' % field:
                                                           query}))
                    qs_match = qs_match.annotate(chrono=F(chrono_sort))\
                                       .annotate(qs_order=Value(1,
                                                 IntegerField()))
                    # remove items from qs_match since due to annotate
                    # duplicates are not filtered out by union
                    qs_contains = qs_contains.annotate(chrono=F(chrono_sort))\
                                             .annotate(qs_order=Value(2,
                                                       IntegerField()))
                    # right now special case for CharacterNameDetail
                    if parent_disambiguation:
                        qs_return = qs_match.union(qs_contains)\
                                            .order_by('qs_order',
                                                      'sort_name',
                                                      'chrono',
                                                      parent_disambiguation)
                    else:
                        qs_return = qs_match.union(qs_contains)\
                                            .order_by('qs_order',
                                                      'sort_name',
                                                      'chrono')
                else:
                    qs_return = qs_match.union(qs_contains)
            else:
                if creator_detail:
                    qs_return = qs_contains.select_related('creator')
                else:
                    qs_return = qs_contains
        return qs_return
    return qs


class CreatorAutocomplete(LoginRequiredMixin,
                          autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Creator.objects.filter(deleted=False)

        qs = _filter_and_sort(qs, self.q, field='gcd_official_name')

        return qs


class CreatorNameAutocomplete(LoginRequiredMixin,
                              autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = CreatorNameDetail.objects.filter(deleted=False)\
                                      .exclude(type__id__in=[3, 4])
        year = self.forwarded.get('year', None)
        if year:
            qs = qs.filter(creator__birth_date__year__lte=year) | \
                 qs.filter(creator__birth_date__year__startswith='?')

        qs = _filter_and_sort(qs, self.q, creator_detail=True,
                              parent_disambiguation='creator')

        return qs


class CreatorName4RelationAutocomplete(LoginRequiredMixin,
                                       autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = CreatorNameDetail.objects.filter(deleted=False,
                                              type__id__in=[5, 8, 12, 13])

        creator_id = self.forwarded.get('from_creator', None)

        if creator_id:
            qs = qs.filter(creator__creator_names__id=creator_id)

        qs = _filter_and_sort(qs, self.q)

        return qs


class CreatorSignatureAutocomplete(LoginRequiredMixin,
                                   autocomplete.Select2QuerySetView):
    def get_result_label(self, creator_signature):
        if creator_signature.signature:
            return format_html(
              '%s <img class="inline" src="%s">' % (
                creator_signature.name,
                creator_signature.signature.icon.url))
        else:
            return format_html('%s [generic]' % creator_signature.name)

    def get_queryset(self):
        qs = CreatorSignature.objects.filter(deleted=False)

        creator_id = self.forwarded.get('creator', None)

        if creator_id:
            qs = qs.filter(creator__creator_names__id=creator_id)

        qs = _filter_and_sort(qs, self.q)

        return qs


class SchoolAutocomplete(LoginRequiredMixin,
                         autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = School.objects.all()

        qs = _filter_and_sort(qs, self.q, field='school_name')

        return qs


class FeatureAutocomplete(LoginRequiredMixin,
                          autocomplete.Select2QuerySetView):
    def get_queryset(self, interactive=True):
        qs = Feature.objects.filter(deleted=False)

        language = self.forwarded.get('language_code', None)
        type = self.forwarded.get('type', None)

        if language and language not in ['zxx', 'und']:
            qs = qs.filter(language__code__in=[language, 'zxx'])

        if type:
            type = int(type)
            if type == STORY_TYPES['letters_page']:
                qs = qs.filter(feature_type__id=2)
            else:
                qs = qs.exclude(feature_type__id=2)
            if type == STORY_TYPES['in-house column']:
                qs = qs.filter(feature_type__id=4)
            else:
                qs = qs.exclude(feature_type__id=4)
            if type not in [STORY_TYPES['ad'], STORY_TYPES['comics-form ad']]:
                qs = qs.exclude(feature_type__id=3)

        qs = _filter_and_sort(qs, self.q, disambiguation=True,
                              interactive=interactive)

        return qs


class FeatureNameAutocomplete(LoginRequiredMixin,
                              autocomplete.Select2QuerySetView):
    def get_queryset(self, interactive=True):
        qs = FeatureNameDetail.objects.filter(deleted=False)

        language = self.forwarded.get('language_code', None)
        type = self.forwarded.get('type', None)

        if language and language not in ['zxx', 'und']:
            qs = qs.filter(feature__language__code__in=[language, 'zxx'])

        if type:
            type = int(type)
            if type == STORY_TYPES['letters_page']:
                qs = qs.filter(feature__feature_type__id=2)
            else:
                qs = qs.exclude(feature__feature_type__id=2)
            if type == STORY_TYPES['in-house column']:
                qs = qs.filter(feature__feature_type__id=4)
            else:
                qs = qs.exclude(feature__feature_type__id=4)
            if type not in [STORY_TYPES['ad'], STORY_TYPES['comics-form ad']]:
                qs = qs.exclude(feature__feature_type__id=3)

        qs = _filter_and_sort(qs, self.q, parent_disambiguation='feature',
                              interactive=interactive)

        return qs


class FeatureLogoAutocomplete(LoginRequiredMixin,
                              autocomplete.Select2QuerySetView):
    def get_result_label(self, feature_logo):
        if feature_logo.logo:
            return format_html(
              '%s <img src="%s">' % (feature_logo.name,
                                     feature_logo.logo.icon.url))
        else:
            if feature_logo.generic:
                return format_html('%s [generic]' % feature_logo.name)
            else:
                return format_html('%s' % feature_logo.name)

    def get_queryset(self):
        qs = FeatureLogo.objects.filter(deleted=False)

        language = self.forwarded.get('language_code', None)
        type = self.forwarded.get('type', None)

        if language and language not in ['zxx', 'und']:
            qs = qs.filter(feature_name__feature__language__code__in=[language,
                                                                      'zxx'])

        if type:
            type = int(type)
            if type == STORY_TYPES['cover']:
                qs = FeatureLogo.objects.none()
            elif type == STORY_TYPES['letters_page']:
                qs = qs.filter(feature_name__feature__feature_type__id=2)
            else:
                qs = qs.exclude(feature_name__feature__feature_type__id=2)
            if type not in [STORY_TYPES['ad'], STORY_TYPES['comics-form ad']]:
                qs = qs.exclude(feature_name__feature__feature_type__id=3)

        qs = _filter_and_sort(qs, self.q)

        return qs


class StoryArcAutocomplete(LoginRequiredMixin,
                           autocomplete.Select2QuerySetView):
    def get_queryset(self, interactive=True):
        qs = StoryArc.objects.filter(deleted=False)

        language = self.forwarded.get('language_code', None)

        if language and language not in ['zxx', 'und']:
            qs = qs.filter(language__code__in=[language, 'zxx'])

        qs = _filter_and_sort(qs, self.q, disambiguation=True,
                              interactive=interactive)

        return qs


class CharacterAutocomplete(LoginRequiredMixin,
                            autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Character.objects.filter(deleted=False)

        language = self.forwarded.get('language_code', None)
        relation_type = self.forwarded.get('relation_type', None)

        if language and relation_type:
            if relation_type not in ['1', '-1']:
                qs = qs.filter(language__code__in=[language, 'zxx'])
            elif relation_type in ['1', '-1']:
                qs = qs.exclude(language__code=language)

        qs = _filter_and_sort(qs, self.q, chrono_sort='year_first_published')

        return qs


class CharacterNameAutocomplete(LoginRequiredMixin,
                                autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = CharacterNameDetail.objects.filter(deleted=False)
        qs = qs.exclude(character__universe__isnull=False,
                        character__from_related_character__isnull=False,
                        character__from_related_character__relation_type__id=6)

        language = self.forwarded.get('language_code', None)
        group_name = self.forwarded.get('group_name', None)
        current_character_id = self.forwarded.get('current_character_id', None)

        if language and language not in ['zxx', 'und']:
            qs = qs.filter(character__language__code__in=[language, 'zxx'])

        if group_name:
            if not isinstance(group_name, list):
                group_name = [group_name]
            group_name = [g for g in group_name if g]
            if group_name:
                qs = qs.filter(
                    character__memberships__group__group_names__in=group_name
                ).distinct()

        if current_character_id:
            character = Character.objects.get(
              character_names__id=current_character_id)
            qs = qs.filter(character__id=character.id)

        qs = _filter_and_sort(qs, self.q, parent_disambiguation='character',
                              chrono_sort='character__year_first_published')

        return qs


class GroupAutocomplete(LoginRequiredMixin,
                        autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Group.objects.filter(deleted=False)
        qs = qs.exclude(universe__isnull=False)

        language = self.forwarded.get('language_code', None)
        character_name = self.forwarded.get('character_name', None)
        relation_type = self.forwarded.get('relation_type', None)

        if language and relation_type:
            if relation_type not in ['1', '-1']:
                qs = qs.filter(language__code__in=[language, 'zxx'])
            elif relation_type in ['1', '-1']:
                qs = qs.exclude(language__code=language)

        if character_name:
            qs = qs.filter(members__character__character_names=character_name)\
                   .distinct()

        qs = _filter_and_sort(qs, self.q)

        return qs


class GroupNameAutocomplete(LoginRequiredMixin,
                            autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = GroupNameDetail.objects.filter(deleted=False)
        qs = qs.exclude(group__universe__isnull=False)

        language = self.forwarded.get('language_code', None)
        character_name = self.forwarded.get('character_name', None)

        if language and language not in ['zxx', 'und']:
            qs = qs.filter(group__language__code__in=[language, 'zxx'])

        if character_name:
            qs = qs.filter(
              group__members__character__character_names=character_name)\
                   .distinct()

        qs = _filter_and_sort(qs, self.q)

        return qs


class UniverseAutocomplete(LoginRequiredMixin,
                           autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Universe.objects.filter(deleted=False)
        if self.q.lower().startswith('marvel'):
            qs = qs.filter(verse__id=2)
            query = self.q[6:].strip()
        elif self.q.lower().startswith('dc'):
            qs = qs.filter(verse__id=1)
            query = self.q[2:].strip()
        else:
            query = self.q

        qs = qs.filter(Q(**{'name__icontains': query}) |
                       Q(**{'designation__icontains': query}))

        return qs


class KeywordAutocomplete(LoginRequiredMixin,
                          autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Tag.objects.all()
        qs = qs.filter(Q(**{'name__icontains': self.q})).order_by('name')

        return qs

    def has_add_permission(self, request):
        """Return True if the user has the permission to add a model.
           We allow any member to add a keyword.
        """
        auth = request.user.is_authenticated

        if not auth:
            return False

        if request.user.has_perm('gcd.can_vote'):
            return True

        return False

    def validate(self, text):
        for c in ['<', '>', '{', '}', ':', '/', '\\', '|', '@', ',', '\n',
                  '’']:
            if c in text:
                raise forms.ValidationError({
                  'name': 'The following characters are not allowed in a '
                  'keyword: < > { } : / \\ | @ , ’'},
                  code="invalid",
                )
        return super(KeywordAutocomplete, self).validate(text)


class FewResultsMixin:
    """
    List the first values of a menu, and say so below them if there are others.
    With no text typed only say so: the first values would be any values.
    """
    paginate_by = None
    note = ''
    too_many_named = TOO_MANY_VALUES

    def few_values(self, found, named=0):
        """Return the values to list and note what to say about the others."""
        if len(found) <= FEW_RESULTS:
            return found
        # writing more would leave out the values the text names whole
        self.note = self.too_many_named if named > FEW_RESULTS \
            else TOO_MANY_VALUES
        return found[:FEW_RESULTS] if (self.q or '').strip() else []

    def get_results(self, context):
        """Return the values, with the note as a line below them."""
        results = super().get_results(context)
        if self.note:
            # not an empty id: Select2 would take it for its placeholder
            results.append({'id': 'note', 'disabled': True,
                            'text': self.note})
        return results


def _named_by_text(text, whole_name):
    """Return the query of the values the text names: whole name, or id."""
    return whole_name | Q(id=text) if text.isdecimal() else whole_name


class PublisherAutocomplete(LoginRequiredMixin,
                            autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Publisher.objects.filter(deleted=False)

        qs = _filter_and_sort(qs, self.q, field='name')

        return qs


class PublisherFewAutocomplete(FewResultsMixin, PublisherAutocomplete):
    """The publishers of the form of a selector: few, or it says so."""

    def get_queryset(self):
        """Return the publishers to list for the typed text."""
        text = (self.q or '').strip()
        named = _named_by_text(text, Q(name=text))
        # the publishers the text names come first: no limit leaves them out
        return self.few_values(
          Publisher.objects.filter(named | Q(name__icontains=text),
                                   deleted=False)
          .annotate(named=ExpressionWrapper(named,
                                            output_field=BooleanField()))
          .order_by('-named', 'name')[:FEW_RESULTS + 1])


class BrandGroupAutocomplete(LoginRequiredMixin,
                             autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = BrandGroup.objects.filter(deleted=False)
        qs = _filter_and_sort(qs, self.q)
        return qs

    def get_result_label(self, brand_group):
        return "%s @ %s" % (brand_group, brand_group.parent)


class BrandEmblemAutocomplete(LoginRequiredMixin,
                              autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Brand.objects.filter(deleted=False)

        publisher_id = self.forwarded.get('publisher_id', None)
        year_began = self.forwarded.get('year_began', 1)
        year_ended = self.forwarded.get('year_ended', 10000)

        # filter by publisher and year range
        if publisher_id:
            qs = qs.filter(in_use__publisher__id=publisher_id).distinct()
            if year_began == year_ended:
                started_before = Q(in_use__year_began__lte=year_began,
                                   in_use__publisher__id=publisher_id)
                no_start = Q(in_use__year_began=None,
                             in_use__publisher__id=publisher_id)
                not_ended_before = (Q(in_use__year_ended__gte=year_ended,
                                    in_use__publisher__id=publisher_id) |
                                    Q(in_use__year_ended=None,
                                    in_use__publisher__id=publisher_id))
                qs = qs.filter((started_before & not_ended_before) |
                               (no_start & not_ended_before))
            else:
                if year_began:
                    qs = qs.exclude(year_ended__lt=year_began)
                if year_ended:
                    qs = qs.exclude(year_began__gt=year_ended)
        qs = _filter_and_sort(qs, self.q)
        return qs

    def get_result_label(self, brand_emblem):
        if brand_emblem.emblem and not settings.FAKE_IMAGES:
            return format_html(
              '<img class="inline" src="%s"> %s' % (
                brand_emblem.emblem.icon.url, brand_emblem.name))
        else:
            if brand_emblem.generic:
                return format_html('%s [generic]' % brand_emblem.name)
            else:
                return format_html('%s' % brand_emblem.name)


class IndiciaPrinterAutocomplete(LoginRequiredMixin,
                                 autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = IndiciaPrinter.objects.filter(deleted=False)

        qs = _filter_and_sort(qs, self.q)

        return qs


class SeriesAutocomplete(LoginRequiredMixin,
                         autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Series.objects.filter(deleted=False)
        publisher_id = self.forwarded.get('publisher', None)
        if publisher_id:
            qs = qs.filter(publisher__id=publisher_id)
        series_year = self.forwarded.get('series_year', None)
        if series_year:
            qs = qs.filter(year_began=series_year)
        qs = _filter_and_sort(qs, self.q, field='name')

        return qs


class SeriesFewAutocomplete(FewResultsMixin, SeriesAutocomplete):
    """The series of the form of a selector: few, or it says so."""

    too_many_named = ('Too many results: write more, or choose a Publisher '
                      'or a Series Year.')

    def get_queryset(self):
        """Return the series to list for the text and the other fields."""
        # Deleted series are dropped afterwards: that filter makes MySQL read
        # the table row by row through its index, far slower than reading it
        # whole, when the name is compared without separators.
        qs = Series.objects.order_by()
        publisher_id = self.forwarded.get('publisher', None)
        if publisher_id:
            qs = qs.filter(publisher__id=publisher_id)
        series_year = str(self.forwarded.get('series_year', '')).strip()
        if series_year.isdecimal():
            qs = qs.filter(year_began=series_year)
        # Only among the series of a publisher or a year: among all of them it
        # would take seconds at each key.
        number = str(self.forwarded.get('issue_number', '')).strip()
        by_number = number and (publisher_id or series_year.isdecimal())
        if by_number:
            qs = qs.filter(id__in=Issue.objects.order_by().filter(
              _number_query(number), deleted=False).values('series_id'))
        text = (self.q or '').strip()
        if text:
            key = _separators_removed(text)
            # the series the text names come first: no limit leaves them out
            qs = qs.annotate(name_key=_without_separators('name')) \
                   .annotate(named=ExpressionWrapper(
                     _named_by_text(text, Q(name_key=key)),
                     output_field=BooleanField())) \
                   .filter(_named_by_text(text, Q(name_key__icontains=key))) \
                   .order_by('-named', 'sort_name', 'year_began')
        else:
            qs = qs.annotate(named=Value(False))
        rows = [row for row
                in qs.values_list('id', 'deleted', 'named')[:SERIES_READ]
                if not row[1]]
        if by_number and not rows:
            self.note = ('No series with this name and this Issue Number.'
                         if text else 'No series with this Issue Number.')
        named_ids = [row[0] for row in rows if row[2]]
        ids = self.few_values([row[0] for row in rows], len(named_ids))
        found = Series.objects.filter(id__in=ids) \
                              .select_related('publisher', 'country') \
                              .order_by('sort_name', 'year_began',
                                        'publisher__name')
        # first the series the text names, then the alphabetical order
        return sorted(found, key=lambda series: series.id not in named_ids)

    def get_result_label(self, series):
        """Return the text of a value of the menu."""
        return series_label(series)


##############################################################################
# filtering of objects in lists
##############################################################################

def process_story_type_filter_from_request(request):
    story_types = [str(t) for t in CORE_TYPES]
    if story_types_val := request.GET.getlist('story_type'):
        try:
            for t in story_types_val:
                int(t)
            story_types = story_types_val
        except ValueError:
            pass
    request.GET = request.GET.copy()
    request.GET.setlist('story_type', story_types)
    return story_types


class CommonFilter(FilterSet):
    def __init__(self, *args, **kwargs):
        country = kwargs.pop('country', None)
        language = kwargs.pop('language', None)
        publisher = kwargs.pop('publisher', None)
        super(CommonFilter, self).__init__(*args, **kwargs)
        needed_values = []
        if country:
            needed_values.append(country)
        if language:
            needed_values.append(language)
        if publisher:
            needed_values.append(publisher)
        data = set(self.qs.values_list(*needed_values))
        countries = []
        languages = []
        publishers = []
        for i in data:
            cnt = 0
            if country:
                countries.append(i[cnt])
                cnt += 1
            if language:
                languages.append(i[cnt])
                cnt += 1
            if publisher:
                publishers.append(i[cnt])
        if countries:
            qs = Country.objects.filter(id__in=countries)
            self.form['country'].field.queryset = qs
        if languages:
            qs = Language.objects.filter(id__in=languages)
            self.form['language'].field.queryset = qs
        if publishers:
            qs = Publisher.objects.filter(id__in=publishers)
            self.form['publisher'].field.queryset = qs


class FilterForLanguage(CommonFilter):
    language = ModelMultipleChoiceFilter(queryset=Language.objects.all())

    class Meta:
        model = Series
        fields = ['language',]


class PublisherFilter(CommonFilter):
    country = ModelMultipleChoiceFilter(queryset=Country.objects.all())

    class Meta:
        model = Series
        fields = ['country',]


class SeriesFilter(CommonFilter):
    country = ModelMultipleChoiceFilter(queryset=Country.objects.all())
    language = ModelMultipleChoiceFilter(queryset=Language.objects.all())
    publisher = ModelMultipleChoiceFilter(queryset=Publisher.objects.all())

    class Meta:
        model = Series
        fields = ['country', 'language', 'publisher']


class IssueFilter(CommonFilter):
    from apps.mycomics.models import Collection
    country = ModelMultipleChoiceFilter(field_name='series__country',
                                        label='Country',
                                        queryset=Country.objects.all())
    language = ModelMultipleChoiceFilter(field_name='series__language',
                                         label='Language',
                                         queryset=Language.objects.all())
    publisher = ModelMultipleChoiceFilter(field_name='series__publisher',
                                          label='Publisher',
                                          queryset=Publisher.objects.all())
    story_type = ModelMultipleChoiceFilter(
      field_name='story__type',
      label='Story Type',
      queryset=StoryType.objects.exclude(id__in=DEPRECATED_TYPES))
    collection = ModelMultipleChoiceFilter(
      field_name='collectionitem__collections',
      label='In Collection',
      queryset=Collection.objects.all())

    class Meta:
        model = Issue
        fields = ['country', 'language', 'publisher']

    def __init__(self, *args, **kwargs):
        from apps.mycomics.models import Collection
        if 'collections' in kwargs:
            collections = kwargs.pop('collections')
        else:
            collections = None
        story_type_filter = kwargs.pop('story_type_filter', None)
        language_filter = kwargs.pop('language_filter', None)
        super(IssueFilter, self).__init__(*args, **kwargs)
        if collections:
            qs = Collection.objects.filter(id__in=collections)
            self.form['collection'].field.queryset = qs
        else:
            self.form.fields.pop('collection')
        if not story_type_filter:
            self.form.fields.pop('story_type')
        if not language_filter:
            self.form.fields.pop('language')


class CoverFilter(CommonFilter):
    country = ModelMultipleChoiceFilter(field_name='issue__series__country',
                                        label='Country',
                                        queryset=Country.objects.all())
    language = ModelMultipleChoiceFilter(field_name='issue__series__language',
                                         label='Language',
                                         queryset=Language.objects.all())
    publisher = ModelMultipleChoiceFilter(
      field_name='issue__series__publisher',
      label='Publisher',
      queryset=Publisher.objects.all())

    class Meta:
        model = Issue
        fields = ['country', 'language', 'publisher']


class SequenceFilter(CommonFilter):
    country = ModelMultipleChoiceFilter(field_name='issue__series__country',
                                        label='Country',
                                        required=False,
                                        queryset=Country.objects.all())
    language = ModelMultipleChoiceFilter(field_name='issue__series__language',
                                         label='Language',
                                         required=False,
                                         blank=True,
                                         queryset=Language.objects.all())
    publisher = ModelMultipleChoiceFilter(
      field_name='issue__series__publisher',
      label='Publisher',
      required=False,
      queryset=Publisher.objects.all())
    story_type = ModelMultipleChoiceFilter(
      field_name='type',
      label='Story Type',
      queryset=StoryType.objects.exclude(id__in=DEPRECATED_TYPES))

    class Meta:
        model = Issue
        fields = ['country', 'language', 'publisher', 'story_type']

    def __init__(self, *args, **kwargs):
        language_filter = kwargs.pop('language_filter', None)
        super(SequenceFilter, self).__init__(*args, **kwargs)
        if not language_filter:
            self.form.fields.pop('language')


class KeywordUsedFilter(FilterSet):
    content_type = ModelChoiceFilter(field_name='content_type',
                                     label='Object',
                                     queryset=ContentType.objects.all())

    class Meta:
        model = Issue
        fields = ['content_type',]

    def __init__(self, *args, **kwargs):
        if 'content_type' in kwargs:
            content_type = kwargs.pop('content_type')
        else:
            content_type = None
        super(KeywordUsedFilter, self).__init__(*args, **kwargs)
        if content_type:
            qs = ContentType.objects.filter(id__in=content_type)
            self.filters['content_type'].queryset = qs


def filter_publisher(request, publisher):
    filter = PublisherFilter(request.GET,
                             queryset=publisher,
                             country='country'
                             )
    return filter


def filter_series(request, series):
    filter = SeriesFilter(request.GET,
                          queryset=series,
                          country='country',
                          language='language',
                          publisher='publisher'
                          )
    return filter


def filter_issues(request, issues, story_type_filter=False,
                  language_filter=True):
    if settings.MYCOMICS and request.user.is_authenticated:
        collections = request.user.collector.collections.all()\
                             .order_by('name').values_list('id', flat=True)
    else:
        collections = None
    filter = IssueFilter(request.GET,
                         queryset=issues,
                         country='series__country',
                         language='series__language',
                         publisher='series__publisher',
                         collections=collections,
                         story_type_filter=story_type_filter,
                         language_filter=language_filter
                         )
    issues = filter.qs
    if not issues:
        filter.form.fields.pop('publisher', None)
        filter.form.fields.pop('country', None)
        filter.form.fields.pop('language', None)

    return filter, issues


def filter_covers(request, covers):
    filter = CoverFilter(request.GET,
                         queryset=covers,
                         country='issue__series__country',
                         language='issue__series__language',
                         publisher='issue__series__publisher')
    return filter


def filter_sequences(request, sequences, language_filter=True):
    filter = SequenceFilter(request.GET,
                            queryset=sequences,
                            country='issue__series__country',
                            language='issue__series__language',
                            publisher='issue__series__publisher',
                            language_filter=language_filter)
    sequences = filter.qs
    if not sequences:
        filter.form.fields.pop('publisher', None)
        filter.form.fields.pop('country', None)
        filter.form.fields.pop('language', None)

    return filter, sequences


def filter_facets(request, things, fields, size=100):
    for field in fields:
        things = things.facet(field, size=size)
        if request.GET.get(field, ''):
            things = things.filter(**{
              field + '__in': [x.replace('"', '\\"')
                               for x in request.GET.getlist(field)]
                               })
    if 'dates' in request.GET:
        things = things.filter(**{
              'year__in': [x
                           for x in request.GET.getlist('dates')]
                           })
    return things


def form_filter_facets(things, fields, content_call={}, dates=False):
    class FilterSearchForm(forms.Form):
        def __init__(self, *args, **kwargs):
            super(FilterSearchForm, self).__init__(*args, **kwargs)
            for field in fields:
                values = []
                for value in things.facet_counts()['fields'][field]:
                    if content_call.get(field, None):
                        label = content_call[field](value[0])
                    else:
                        label = value[0]
                    values.append((value[0], '%s (%d)' % (label,
                                                          value[1])))
                self.fields[field] = forms.MultipleChoiceField(
                    choices=values,
                    required=False
                )
            if dates and 'dates' in things.facet_counts():
                values = []
                for value in things.facet_counts()['dates']['date']:
                    if value[1] > 0:
                        values.append((value[0].strftime("%Y"),
                                       '%s (%d)' % (value[0].strftime("%Y"),
                                                    value[1])))
                self.fields['dates'] = forms.MultipleChoiceField(
                  choices=values,
                  required=False)
    return FilterSearchForm


def filter_haystack(request, sqs):
    fields = ['country', 'language', 'publisher']
    things = filter_facets(request, sqs, fields)
    filter_form = form_filter_facets(things,
                                     fields,
                                     {'language': get_native_language_name})
    return things, filter_form(request.GET)


##############################################################################
# selecting of objects
##############################################################################


def creator_for_detail(request):
    name_detail_id = request.GET['name_detail_id']
    qs = Creator.objects.filter(creator_names__id=name_detail_id)
    if qs:
        creator_name = qs.get().creator_names.get(is_official_name=True)
        data = [{'creator_id': creator_name.id,
                 'creator_name': str(creator_name)}]
    else:
        data = [{'creator_id': -1}]
    return JsonResponse(data, safe=False)
