from django.db.models import Count, Sum
from django.db.models import F

# from apps.stddata.models import Country, Language
from apps.gcd.models import Publisher, Issue, StoryType, Series, Story, Creator
from apps.gcd.views import paginate_response
from apps.projects.forms import IssuesWithCoversForm


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
        issues = issues.filter(series__publisher__id=709) #need to keep #issues smaller
        # for the pagination bar and select box
        vars['query_string'] = 'publisher=709'
        get_copy = request.GET.copy()
        get_copy['items'] = [('publisher', 709),]
        request.GET = get_copy
    issues = issues.filter(**qargs).order_by(*qorder)
    vars['form'] = form
    vars['advanced_search'] = True

    return paginate_response(request, issues,
                             'projects/issues_with_several_covers.html', vars, per_page=50)
