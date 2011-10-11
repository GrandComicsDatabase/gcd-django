from django.db.models import Count, Sum
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.db.models import F

from apps.gcd.models import Publisher, Country, Language, Issue, StoryType, Series
from apps.gcd.views import paginate_response
from apps.projects.forms import ImprintsInUseForm, IssuesWithCoversForm, IssueCoverNotesForm


def imprints_in_use(request):
    """
    This project is geared towards clearing out the old imprint field so we can
    either remove it or start over with a new 'imprint' concept with a consistent
    definition.  For this we need a list of imprints in use that can be filtered
    and sorted by a few basic attributes.
    """

    imprints = Publisher.objects.filter(deleted=0, is_master=0)

    qargs = {'deleted': 0, 'is_master': 0}
    qorder = ['series_count', 'parent__name', 'name']

    vars = {
        'heading': 'Imprints',
        'search_item': 'In Use',
        'item_name': 'imprint',
        'plural_suffix': 's',
    }

    if (request.GET):
        form = ImprintsInUseForm(request.GET)
        form.is_valid()
        if form.is_valid():
            data = form.cleaned_data

            # Extra filters
            if data['parent']:
                qargs['parent'] = data['parent']
            if data['parent_country']:
                qargs['parent__country'] = data['parent_country']
            if data['imprint_country']:
                qargs['country'] = data['imprint_country']

            # Override order
            if data['order1'] or data['order2'] or data['order3']:
                qorder = []
                if data['order1']:
                    qorder.append(data['order1'])
                if data['order2']:
                    qorder.append(data['order2'])
                if data['order3']:
                    qorder.append(data['order3'])
    else:
        form = ImprintsInUseForm(auto_id=True,
          initial=dict(zip(('order1', 'order2', 'order3'), qorder)))

    imprints = imprints.filter(**qargs).order_by(*qorder)
    vars['form'] = form

    return paginate_response(request, imprints,
                             'projects/imprints_in_use.html', vars)

def issues_with_several_covers(request):
    """
    This project is geared towards moving variant covers into variant issues.
    For this we need a list of such issues that can be filtered and sorted
    by a few basic attributes.
    """

    issues=Issue.objects.annotate(covers=Count('cover'))
    issues=issues.annotate(covers_deleted=Sum('cover__deleted'))
    issues=issues.filter(covers__gt=1+F('covers_deleted'), deleted=False)

    qargs = {'deleted': False}
    qorder = ['series__name', 'series__year_began', 'number']

    vars = {
        'heading': 'Issues',
        'search_item': 'with several covers',
        'item_name': 'issue',
        'plural_suffix': 's',
    }

    if (request.GET):
        form = IssuesWithCoversForm(request.GET)
        form.is_valid()
        if form.is_valid():
            data = form.cleaned_data

            # Extra filters
            if data['publisher']:
                qargs['series__publisher__id'] = data['publisher']

        get_copy = request.GET.copy()
        get_copy.pop('page', None)
        vars['query_string'] = get_copy.urlencode()
    else:
        form = IssuesWithCoversForm()
        issues = issues.filter(series__publisher__id=54) # initial is DC, need to keep #issues smaller
        # for the pagination bar and select box
        vars['query_string'] = 'publisher=54'
        get_copy = request.GET.copy()
        get_copy['items'] = [(u'publisher', 54),]
        request.GET = get_copy
    issues = issues.filter(**qargs).order_by(*qorder)
    vars['form'] = form
    vars['advanced_search'] = True

    return paginate_response(request, issues,
                             'projects/issues_with_several_covers.html', vars, page_size=50)


def issue_cover_notes(request):
    """
    This project is geared towards cleaning up identical cover and issue notes.
    For this we need a list of such issues that can be filtered and sorted
    by a few basic attributes.
    """
    cover = StoryType.objects.get(name='cover')
    issues = Issue.objects.exclude(notes__exact='').\
             filter(story__type=cover, story__notes=F('notes'),
                    story__deleted=False, deleted=False).all()

    qargs = {'deleted': False}
    qorder = ['series__sort_name', 'series__year_began', 'sort_code', 'number']

    vars = {
        'heading': 'Issues',
        'search_item': 'with identical notes and cover notes',
        'item_name': 'issue',
        'plural_suffix': 's',
    }

    if (request.GET):
        form = IssueCoverNotesForm(request.GET)
        form.is_valid()
        if form.is_valid():
            data = form.cleaned_data

            # Extra filters
            if data['publisher']:
                qargs['series__publisher__id'] = data['publisher']
            if data['country']:
                qargs['series__country'] = data['country']
            if data['language']:
                qargs['series__language'] = data['language']

        get_copy = request.GET.copy()
        get_copy.pop('page', None)
        vars['query_string'] = get_copy.urlencode()
    else:
        form = IssueCoverNotesForm()
    issues = issues.filter(**qargs).order_by(*qorder)
    vars['form'] = form
    vars['advanced_search'] = True

    return paginate_response(request, issues,
                             'projects/issue_cover_notes.html', vars, page_size=50)

def series_with_isbn(request):
    series = Series.objects.filter(notes__icontains='ISBN',deleted=False).\
             exclude(notes__icontains='ISBN 91-88334-36-8')

    qargs = {'deleted': False}
    qorder = ['sort_name', 'year_began']

    vars = {
        'heading': 'Series',
        'search_item': 'with ISBN in notes',
        'item_name': 'series',
        'plural_suffix': '',
    }

    if (request.GET):
        get_copy = request.GET.copy()
        get_copy.pop('page', None)
        vars['query_string'] = get_copy.urlencode()
    series = series.filter(**qargs).order_by(*qorder)
    vars['advanced_search'] = True

    return paginate_response(request, series,
                             'projects/series_with_isbn.html', vars, page_size=50)

