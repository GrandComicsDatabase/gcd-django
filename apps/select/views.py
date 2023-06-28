import hashlib
from random import random

from haystack.forms import FacetedSearchForm

from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
import django.urls as urlresolvers
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.utils.datastructures import MultiValueDictKeyError
from django.utils.html import format_html

from django_filters import FilterSet, ModelChoiceFilter

from dal import autocomplete

from apps.gcd.models import Publisher, Series, Issue, Story, StoryType, \
                            Creator, CreatorNameDetail, CreatorSignature, \
                            Feature, FeatureLogo, IndiciaPrinter, School, \
                            Character, CharacterNameDetail, Group, STORY_TYPES
from apps.stddata.models import Country, Language
from apps.gcd.views.search_haystack import GcdSearchQuerySet, \
                                           PaginatedFacetedSearchView
from apps.gcd.views import paginate_response
from apps.indexer.views import render_error
from apps.select.forms import get_select_cache_form, get_select_search_form


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
                     series=False, issue=False, story=False, cover=False):
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
    if data:
        search_form = search_form(data)
    else:
        search_form = search_form(initial=initial)

    cache_form = get_select_cache_form(cached_issues=cached_issues,
                                       cached_stories=cached_stories,
                                       cached_covers=cached_covers)()

    return search_form, cache_form


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
    return data['return'](request, data)


@permission_required('indexer.can_reserve')
def process_select_search_haystack(request, select_key):
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
        return PaginatedFacetedSearchView(searchqueryset=sqs)(request,
                                                              context=context)
    else:
        return HttpResponseRedirect(
          urlresolvers.reverse('select_object',
                               kwargs={'select_key': select_key})
          + '?' + request.META['QUERY_STRING'])


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
    if 'search_series' in request.GET:
        issue = False
    search_form = get_select_search_form(search_publisher=publisher,
                                         search_series=series,
                                         search_issue=issue,
                                         search_story=story)(request.GET)
    if not search_form.is_valid():
        return HttpResponseRedirect(
          urlresolvers.reverse('select_object',
                               kwargs={'select_key': select_key})
          + '?' + request.META['QUERY_STRING'])
    cd = search_form.cleaned_data

    if 'search_story' in request.GET or 'search_cover' in request.GET:
        search = Story.objects.filter(
          issue__number=cd['number'],
          deleted=False,
          issue__series__name__icontains=cd['series'],
          issue__series__publisher__name__icontains=cd['publisher'])
        publisher = cd['publisher'] if cd['publisher'] else '?'
        if cd['year']:
            search = search.filter(issue__series__year_began=cd['year'])
            heading = '%s (%s, %d series) #%s' % (cd['series'],
                                                  publisher,
                                                  cd['year'],
                                                  cd['number'])
        else:
            heading = '%s (%s, ? series) #%s' % (cd['series'],
                                                 publisher,
                                                 cd['number'])
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
        template = 'gcd/search/content_list.html'
        heading = 'Search for: ' + heading
        search = search.order_by("issue__series__name",
                                 "issue__series__year_began",
                                 "issue__key_date",
                                 "sequence_number")
    elif 'search_issue' in request.GET:
        search = Issue.objects.filter(
          number=cd['number'],
          deleted=False,
          series__name__icontains=cd['series'],
          series__publisher__name__icontains=cd['publisher'])
        publisher = cd['publisher'] if cd['publisher'] else '?'
        if cd['year']:
            search = search.filter(series__year_began=cd['year'])
            heading = '%s (%s, %d series) #%s' % (cd['series'], publisher,
                                                  cd['year'], cd['number'])
        else:
            heading = '%s (%s, ? series) #%s' % (cd['series'], publisher,
                                                 cd['number'])
        heading = 'Issue search for: ' + heading
        template = 'gcd/search/issue_list.html'
        base_name = 'issue'
        plural_suffix = 's'
        search = search.order_by("series__name", "series__year_began",
                                 "key_date")
    elif 'search_series' in request.GET:
        search = Series.objects.filter(
          deleted=False,
          name__icontains=cd['series'],
          publisher__name__icontains=cd['publisher'])
        heading = 'Series search for: ' + cd['series']
        if cd['year']:
            search = search.filter(year_began=cd['year'])
            heading = '%s (%s, %d series)' % (cd['series'], publisher,
                                              cd['year'])
        template = 'gcd/search/series_list.html'
        base_name = 'series'
        plural_suffix = ''
        search = search.order_by("name")
    elif 'search_publisher' in request.GET:
        search = Publisher.objects.filter(deleted=False,
                                          name__icontains=cd['publisher'])
        heading = 'Publisher search for: ' + cd['publisher']
        template = 'gcd/search/publisher_list.html'
        base_name = 'publisher'
        plural_suffix = 's'
        search = search.order_by("name")

    context = {
      'item_name': base_name,
      'plural_suffix': plural_suffix,
      'items': search,
      'heading': heading,
      'select_key': select_key,
      'no_bulk_edit': True,
      'query_string': request.META['QUERY_STRING'],
      'publisher': cd['publisher'] if cd['publisher'] else '',
      'series': cd['series'] if 'series' in cd and cd['series'] else '',
      'year': cd['year'] if 'year' in cd and cd['year'] else '',
      'number': cd['number'] if 'number' in cd and cd['number'] else ''
    }
    return paginate_response(request, search, template, context)


@permission_required('indexer.can_reserve')
def select_object(request, select_key):
    try:
        data = get_select_data(request, select_key)
    except KeyError:
        return _cant_get_key(request)
    if request.method == 'GET':
        if 'refine_search' in request.GET or 'search_issue' in request.GET:
            request_data = request.GET
        else:
            request_data = None
        initial = data.get('initial', {})
        initial['select_key'] = select_key
        publisher = data.get('publisher', False)
        series = data.get('series', False)
        issue = data.get('issue', False)
        story = data.get('story', False)
        cover = data.get('cover', False)
        search_form, cache_form = get_select_forms(request,
                                                   initial,
                                                   request_data,
                                                   publisher=publisher,
                                                   series=series,
                                                   issue=issue,
                                                   story=story,
                                                   cover=cover)
        haystack_form = FacetedSearchForm()
        return render(request, 'oi/edit/select_object.html',
                      {'heading': data['heading'],
                       'select_key': select_key,
                       'cache_form': cache_form,
                       'search_form': search_form,
                       'haystack_form': haystack_form,
                       'publisher': publisher,
                       'series': series,
                       'issue': issue,
                       'story': story,
                       'cover': cover,
                       'target': data['target']
                       })

    if 'cancel' in request.POST:
        return data['cancel']
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
        raise ValueError
    return data['return'](request, data, object_type, selected_id)


def get_cached_issues(request):
    cached_issues_list = request.session.get('cached_issues', None)
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
    cached_stories_list = request.session.get('cached_stories', None)
    return _process_cached_stories(cached_stories_list)


def get_cached_covers(request):
    cached_covers_list = request.session.get('cached_covers', None)
    return _process_cached_stories(cached_covers_list)


def _process_caching(cached_list, object_id):
    """
    Doing the caching. Limit of three might become a user option.
    """
    if not cached_list:
        cached_list = [object_id, ]
    elif len(cached_list) < 3:
        cached_list.append(object_id)
    else:
        cached_list.pop(0)
        cached_list.append(object_id)
    return cached_list


@permission_required('indexer.can_reserve')
def cache_content(request, issue_id=None, story_id=None, cover_story_id=None):
    """
    Store an issue_id, story_id, or cover_id in the session.
    """
    if issue_id:
        cached_issues = request.session.get('cached_issues', None)
        request.session['cached_issues'] = _process_caching(cached_issues,
                                                            issue_id)
    if story_id:
        cached_stories = request.session.get('cached_stories', None)
        request.session['cached_stories'] = _process_caching(cached_stories,
                                                             story_id)
        return HttpResponseRedirect(request.META['HTTP_REFERER'] + '#%s' %
                                    story_id)
    if cover_story_id:
        cached_covers = request.session.get('cached_covers', None)
        request.session['cached_covers'] = _process_caching(cached_covers,
                                                            cover_story_id)
    return HttpResponseRedirect(request.META['HTTP_REFERER'])


##############################################################################
# auto-complete objects
##############################################################################

def _filter_and_sort(qs, query, field='name', creator_detail=False,
                     disambiguation=False, parent_disambiguation=None,
                     interactive=True):
    if query:
        if disambiguation or parent_disambiguation:
            if query.find(' [') > 1:
                pos = query.find(' [')
                disambiguation = query[pos+2:query.find(']') if
                                       query.find(']') > 1 else None]
                dis_query = query[:pos]
                if parent_disambiguation:
                    qs_contains = qs.filter(Q(**{
                      '%s__icontains' % field: dis_query,
                      '%s__disambiguation__istartswith' % parent_disambiguation:
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
              '%s <img src="%s">' % (creator_signature.name,
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

        if language:
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

        if language:
            qs = qs.filter(feature__language__code__in=[language, 'zxx'])

        if type:
            type = int(type)
            if type == STORY_TYPES['cover']:
                qs = FeatureLogo.objects.none()
            elif type == STORY_TYPES['letters_page']:
                qs = qs.filter(feature__feature_type__id=2)
            else:
                qs = qs.exclude(feature__feature_type__id=2)
            if type not in [STORY_TYPES['ad'], STORY_TYPES['comics-form ad']]:
                qs = qs.exclude(feature__feature_type__id=3)

        qs = _filter_and_sort(qs, self.q)

        return qs


class CharacterAutocomplete(LoginRequiredMixin,
                            autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Character.objects.filter(deleted=False)

        language = self.forwarded.get('language_code', None)

        if language:
            qs = qs.filter(language__code__in=[language, 'zxx'])

        qs = _filter_and_sort(qs, self.q)

        return qs


class CharacterNameAutocomplete(LoginRequiredMixin,
                                autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = CharacterNameDetail.objects.filter(deleted=False)

        language = self.forwarded.get('language_code', None)
        group = self.forwarded.get('group', None)

        if language:
            qs = qs.filter(character__language__code__in=[language, 'zxx'])

        if group:
            qs = qs.filter(character__memberships__group=group)\
                   .distinct()
        qs = _filter_and_sort(qs, self.q, parent_disambiguation='character')

        return qs


class GroupAutocomplete(LoginRequiredMixin,
                        autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Group.objects.filter(deleted=False)

        language = self.forwarded.get('language_code', None)
        character_name = self.forwarded.get('character_name', None)

        if language:
            qs = qs.filter(language__code__in=[language, 'zxx'])

        if character_name:
            qs = qs.filter(members__character__character_names=character_name)\
                   .distinct()

        qs = _filter_and_sort(qs, self.q)

        return qs


class IndiciaPrinterAutocomplete(LoginRequiredMixin,
                                 autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = IndiciaPrinter.objects.filter(deleted=False)

        qs = _filter_and_sort(qs, self.q)

        return qs


##############################################################################
# filtering of objects in lists
##############################################################################

class SeriesFilter(FilterSet):
    country = ModelChoiceFilter(queryset=Country.objects.all())
    language = ModelChoiceFilter(queryset=Language.objects.all())
    publisher = ModelChoiceFilter(queryset=Publisher.objects.all())

    class Meta:
        model = Series
        fields = ['country', 'language', 'publisher']

    def __init__(self, *args, **kwargs):
        if 'countries' in kwargs:
            countries = kwargs.pop('countries')
        else:
            countries = None
        if 'languages' in kwargs:
            languages = kwargs.pop('languages')
        else:
            languages = None
        if 'publishers' in kwargs:
            publishers = kwargs.pop('publishers')
        else:
            publishers = None
        super(SeriesFilter, self).__init__(*args, **kwargs)
        if countries:
            qs = Country.objects.filter(id__in=countries)
            self.filters['country'].queryset = qs
        if languages:
            qs = Language.objects.filter(id__in=languages)
            self.filters['language'].queryset = qs
        if publishers:
            qs = Publisher.objects.filter(id__in=publishers)
            self.filters['publisher'].queryset = qs


class IssueFilter(FilterSet):
    country = ModelChoiceFilter(field_name='series__country',
                                label='Country',
                                queryset=Country.objects.all())
    language = ModelChoiceFilter(field_name='series__language',
                                 label='Language',
                                 queryset=Language.objects.all())
    publisher = ModelChoiceFilter(field_name='series__publisher',
                                  label='Publisher',
                                  queryset=Publisher.objects.all())

    class Meta:
        model = Issue
        fields = ['country', 'language', 'publisher']

    def __init__(self, *args, **kwargs):
        if 'countries' in kwargs:
            countries = kwargs.pop('countries')
        else:
            countries = None
        if 'languages' in kwargs:
            languages = kwargs.pop('languages')
        else:
            languages = None
        if 'publishers' in kwargs:
            publishers = kwargs.pop('publishers')
        else:
            publishers = None
        super(IssueFilter, self).__init__(*args, **kwargs)
        if countries:
            qs = Country.objects.filter(id__in=countries)
            self.filters['country'].queryset = qs
        if languages:
            qs = Language.objects.filter(id__in=languages)
            self.filters['language'].queryset = qs
        if publishers:
            qs = Publisher.objects.filter(id__in=publishers)
            self.filters['publisher'].queryset = qs


class SequenceFilter(FilterSet):
    country = ModelChoiceFilter(field_name='issue__series__country',
                                label='Country',
                                queryset=Country.objects.all())
    language = ModelChoiceFilter(field_name='issue__series__language',
                                 label='Language',
                                 queryset=Language.objects.all())
    publisher = ModelChoiceFilter(field_name='issue__series__publisher',
                                  label='Publisher',
                                  queryset=Publisher.objects.all())

    class Meta:
        model = Issue
        fields = ['country', 'language', 'publisher']

    def __init__(self, *args, **kwargs):
        if 'countries' in kwargs:
            countries = kwargs.pop('countries')
        else:
            countries = None
        if 'languages' in kwargs:
            languages = kwargs.pop('languages')
        else:
            languages = None
        if 'publishers' in kwargs:
            publishers = kwargs.pop('publishers')
        else:
            publishers = None
        super(SequenceFilter, self).__init__(*args, **kwargs)
        if countries:
            qs = Country.objects.filter(id__in=countries)
            self.filters['country'].queryset = qs
        if languages:
            qs = Language.objects.filter(id__in=languages)
            self.filters['language'].queryset = qs
        if publishers:
            qs = Publisher.objects.filter(id__in=publishers)
            self.filters['publisher'].queryset = qs


def filter_issues(request, issues):
    data = set(issues.values_list('series__country',
                                  'series__language',
                                  'series__publisher'))
    countries = []
    languages = []
    publishers = []
    for i in data:
        countries.append(i[0])
        languages.append(i[1])
        publishers.append(i[2])
    filter = IssueFilter(request.GET,
                         queryset=issues,
                         countries=countries,
                         languages=languages,
                         publishers=publishers)
    return filter


def filter_sequences(request, sequences):
    data = set(sequences.values_list('issue__series__country',
                                     'issue__series__language',
                                     'issue__series__publisher'))
    countries = []
    languages = []
    publishers = []
    for i in data:
        countries.append(i[0])
        languages.append(i[1])
        publishers.append(i[2])
    filter = SequenceFilter(request.GET,
                            queryset=sequences,
                            countries=countries,
                            languages=languages,
                            publishers=publishers)
    return filter

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
