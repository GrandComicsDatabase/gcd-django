import hashlib
from random import random

from haystack.forms import FacetedSearchForm

from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, Value, IntegerField, F
import django.urls as urlresolvers
from django.http import HttpResponseRedirect, JsonResponse
from django.conf import settings
from django.shortcuts import render
from django.utils.datastructures import MultiValueDictKeyError
from django.utils.html import format_html
from django import forms

from django_filters import FilterSet, ModelChoiceFilter, \
                           ModelMultipleChoiceFilter

from dal import autocomplete
from taggit.models import Tag

from apps.gcd.models import Publisher, Series, Issue, Story, StoryType, \
                            Creator, CreatorNameDetail, CreatorSignature, \
                            Feature, FeatureLogo, IndiciaPrinter, School, \
                            Character, CharacterNameDetail, Group, \
                            GroupNameDetail, Universe, StoryArc, Brand, \
                            BrandGroup, STORY_TYPES
from apps.stddata.models import Country, Language
from apps.gcd.templatetags.credits import get_native_language_name
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

    if issue:
        select_issue = True
    else:
        select_issue = False

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
        heading = 'matching search for: ' + heading
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
        heading = 'matching search for: ' + cd['publisher']
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
      'select_issue': select_issue,
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
        return render(request, 'select/select_object.html',
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


def _process_caching(cached_list, object_id, cache_size):
    """
    Doing the caching. Limit of three might become a user option.
    """
    if not cached_list:
        cached_list = [object_id, ]
    elif len(cached_list) < cache_size:
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
    cache_size = request.user.indexer.cache_size

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
        return HttpResponseRedirect(request.META['HTTP_REFERER'] + '#%s' %
                                    story_id)
    if cover_story_id:
        cached_covers = request.session.get('cached_covers', None)
        request.session['cached_covers'] = _process_caching(cached_covers,
                                                            cover_story_id,
                                                            cache_size)
    return HttpResponseRedirect(request.META['HTTP_REFERER'])


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

        if language and language not in ['zxx', 'und']:
            qs = qs.filter(character__language__code__in=[language, 'zxx'])

        if group_name:
            qs = qs.filter(
              character__memberships__group__group_names=group_name).distinct()
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
        year_began = self.forwarded.get('year_began', 10000)
        year_ended = self.forwarded.get('year_ended', 1)

        if publisher_id:
            qs = qs.filter(in_use__publisher__id=publisher_id).distinct()
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

        qs = _filter_and_sort(qs, self.q)
        return qs

    def get_result_label(self, brand_emblem):
        if brand_emblem.emblem:
            return format_html(
              '%s <img src="%s">' % (brand_emblem.name,
                                     brand_emblem.emblem.icon.url))
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


##############################################################################
# filtering of objects in lists
##############################################################################

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
        super(IssueFilter, self).__init__(*args, **kwargs)
        if collections:
            qs = Collection.objects.filter(id__in=collections)
            self.form['collection'].field.queryset = qs
        else:
            self.form.fields.pop('collection')


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

    class Meta:
        model = Issue
        fields = ['country', 'language', 'publisher']


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


def filter_issues(request, issues):
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
                         collections=collections
                         )
    return filter


def filter_covers(request, covers):
    filter = CoverFilter(request.GET,
                         queryset=covers,
                         country='issue__series__country',
                         language='issue__series__language',
                         publisher='issue__series__publisher')
    return filter


def filter_sequences(request, sequences):
    filter = SequenceFilter(request.GET,
                            queryset=sequences,
                            country='issue__series__country',
                            language='issue__series__language',
                            publisher='issue__series__publisher')
    return filter


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
