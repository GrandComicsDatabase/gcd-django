"""View methods for pages displaying entity details."""

import re
from urllib.request import urlopen
from datetime import date, timedelta

from django.db.models import Q
from django.conf import settings
from django.core.paginator import QuerySetPaginator
from django.shortcuts import render_to_response, \
                             get_object_or_404, \
                             get_list_or_404
from django.http import HttpResponseRedirect

from apps.inducks.models import Series, Issue, Country

def issue(request, issue_id):
    """Display the issue details page, including story details."""
    
    issue = get_object_or_404(Issue, id = issue_id)
    stories = list(issue.story_set.order_by('sequence_number'))

    return render_to_response('inducks/issue.html', {
      'issue' : issue,
      'stories' : stories,
    })

def series(request, series_id):
    """Display the details page for a series."""
    
    series = get_object_or_404(Series, id = series_id)
    issues = list(series.issue_set.order_by('number'))
    print(len(issues))
    
    return render_to_response('inducks/series.html', {
      'series' : series,
      'issues' : issues,
    })
