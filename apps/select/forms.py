from django import forms
from django.forms.widgets import HiddenInput, RadioSelect
from django.utils.html import conditional_escape as esc
from django.utils.safestring import mark_safe

from apps.gcd.templatetags.display import show_story_short


def get_select_cache_form(cached_issues=None, cached_stories=None,
                          cached_covers=None):

    class SelectCacheForm(forms.Form):
        fields = []
        if cached_issues:
            for cached_issue in cached_issues:
                fields.append(('issue_%d' % cached_issue.id,
                              'issue: %s' % cached_issue))
        if cached_stories:
            for cached_story in cached_stories:
                fields.append(('story_%d' % cached_story.id,
                              mark_safe('story: %s in %s' %
                                        (show_story_short(cached_story),
                                         esc(cached_story.issue)))))
        if cached_covers:
            for cached_cover in cached_covers:
                fields.append(('cover_%d' % cached_cover.id,
                              'cover of issue: %s' % cached_cover.issue))
        if fields:
            object_choice = forms.ChoiceField(widget=RadioSelect,
                                              choices=fields, label='')
    return SelectCacheForm


def get_select_search_form(search_publisher=False, search_series=False,
                           search_issue=False, search_story=False,
                           search_cover=False,
                           changeset_id=None, story_id=None, issue_id=None,
                           revision_id=None, return_type_='reprint'):
    class SelectSearchForm(forms.Form):
        if search_publisher:
            publisher = forms.CharField(label='Publisher', required=True)
        else:
            publisher = forms.CharField(label='Publisher', required=False)
        if search_series or search_issue or search_story or search_cover:
            series = forms.CharField(label='Series', required=False)
            year = forms.IntegerField(label='Series year', required=False,
                                      min_value=1800, max_value=2025)
        if search_issue or search_story or search_cover:
            number = forms.CharField(label='Issue Number',
                                     required=True)
        if search_story or search_cover:
            sequence_number = forms.IntegerField(label='Sequence Number',
                                                 required=False, min_value=0)
        select_key = forms.CharField(widget=HiddenInput)
    return SelectSearchForm
