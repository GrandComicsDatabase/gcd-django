"""View methods for pages displaying entity details."""

import re
from urllib import urlopen

from django.db.models import Q
from django.conf import settings
from django.shortcuts import render_to_response, \
                             get_object_or_404, \
                             get_list_or_404
from django.http import HttpResponseRedirect

from apps.gcd.models import Publisher, Series, Issue, Story, \
                            Country, Indexer, IndexCredit
from apps.gcd.views.covers import get_image_tag, \
                                  ZOOM_SMALL, \
                                  ZOOM_MEDIUM, \
                                  ZOOM_LARGE


def publisher(request, publisher_id):
    """Display the details page for a Publisher."""
    p = get_object_or_404(Publisher, id = publisher_id)
    s = p.series_set.all().order_by('name')
    vars = { 'publisher' : p,
             'series_set' : s,
             'media_url' : settings.MEDIA_URL }
    return render_to_response('publisher_detail.html', vars)


def series(request, series_id):
    """Display the details page for a series."""
    
    series = get_object_or_404(Series, id = series_id)
    image_tag = get_image_tag(series_id = int(series_id),
                              issue_id = series.issue_set.all()[0].id,
                              zoom_level = ZOOM_MEDIUM,
                              alt_text = 'First Issue Cover')
    country = Country.objects.get(code__iexact = series.country_code)

    # TODO: Fix language table hookup- why is this not a foreign key?
    # language = Language.objects.get(code__iexact = series.language_code)

    return render_to_response('series.html', {
      'series' : series,
      'image_tag' : image_tag,
      'country' : country.country or series.country_code,
      'language' : series.language_code, #language.name or series.language_code,
      'media_url' : settings.MEDIA_URL })

def issue_form(request):
    """Redirect form-style URL used by the drop-down menu on the series
    details page into a standard issue details URL."""
    return HttpResponseRedirect("/gcd/issue/" + request.GET["id"])


def issue(request, issue_id):
    """Display the issue details page, including story details."""
    issue = get_object_or_404(Issue, id = issue_id)
    image_tag = get_image_tag(series_id = issue.series.id,
                              issue_id = int(issue_id),
                              zoom_level = ZOOM_SMALL,
                              alt_text = 'Cover Thumbnail')
    
    series = issue.series
    #get sorted issue_set for series and find previous and next issue
    issue_list = series.issue_set.all().order_by('key_date')

    earlier_issues = \
      series.issue_set.filter(key_date__lt = issue.key_date)
    earlier_issues = earlier_issues.order_by('-key_date')
    
    later_issues = series.issue_set.filter(key_date__gt = issue.key_date)
    later_issues = later_issues.order_by('key_date')
    
    try:
        prev_issue = earlier_issues[0]
    except IndexError:
        prev_issue = None
    try:
        next_issue = later_issues[0]
    except IndexError:
        next_issue = None
    
    if issue.index_status <= 1: # only skeleton
        # TODO: create a special empty page (with the cover if existing)
        # TODO: could vary accord. to (un)reserved/part.indexed/submitted
        return render_to_response('issue.html', {
          'issue' : issue,
          'prev_issue' : prev_issue,
          'next_issue' : next_issue,
          'image_tag' : image_tag,
          'media_url' : settings.MEDIA_URL })
    
    cover_story = issue.story_set.get(sequence_number = 0)
    
    stories = issue.story_set.filter(sequence_number__gt = 0)
    stories = stories.order_by("sequence_number")
    
    return render_to_response('issue.html', {
      'issue' : issue,
      'prev_issue' : prev_issue,
      'next_issue' : next_issue,
      'cover_story' : cover_story,
      'stories' : stories,
      'image_tag' : image_tag,
      'media_url' : settings.MEDIA_URL })

