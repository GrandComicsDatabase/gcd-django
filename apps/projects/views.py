from django.db.models import Count, Sum
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.db.models import F

from apps.gcd.models import Publisher, Country, Language, Issue, StoryType, \
                            Series, Story
from apps.gcd.views import paginate_response
from apps.projects.forms import ImprintsInUseForm, IssuesWithCoversForm, \
                                ReprintInspectionForm


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
        issues = issues.filter(series__publisher__id=78) # initial is Marvel, need to keep #issues smaller
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


def story_reprint_inspection(request):
    stories = Story.objects.filter(deleted=False,
      migration_status__reprint_needs_inspection=True)

    qargs = {'deleted': False}
    qorder = ['issue__series__sort_name', 'issue__series__year_began', 'issue__sort_code', 'issue__number', 'sequence_number']

    vars = {
        'heading': 'Sequences',
        'search_item': 'whose migrated reprint notes need inspection',
        'item_name': 'sequence',
        'plural_suffix': 's',
    }

    if (request.GET):
        form = ReprintInspectionForm(request.GET)
        form.is_valid()
        if form.is_valid():
            data = form.cleaned_data

            # Extra filters
            if data['publisher']:
                qargs['issue__series__publisher__id'] = data['publisher']
            if data['country']:
                qargs['issue__series__country'] = data['country']
            if data['language']:
                qargs['issue__series__language'] = data['language']

        get_copy = request.GET.copy()
        get_copy.pop('page', None)
        vars['query_string'] = get_copy.urlencode()
    else:
        form = ReprintInspectionForm()
    stories = stories.filter(**qargs).order_by(*qorder)
    print stories.count()
    vars['form'] = form
    vars['advanced_search'] = True

    return paginate_response(request, stories,
                             'projects/story_reprint_inspection.html', vars, page_size=50)
