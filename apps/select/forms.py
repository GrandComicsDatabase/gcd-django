from datetime import date

from django import forms
from django.forms.widgets import HiddenInput, RadioSelect
from django.utils.safestring import mark_safe

from dal import autocomplete, forward

from apps.gcd.templatetags.display import absolute_url
from apps.gcd.models import Publisher, Series


def get_select_cache_form(cached_issues=None, cached_stories=None,
                          cached_covers=None, exclude_issue_id=None):

    class SelectCacheForm(forms.Form):
        fields = []
        disabled_choices = []
        if cached_issues:
            for cached_issue in cached_issues:
                choice = 'issue_%d' % cached_issue.id
                fields.append((choice,
                              mark_safe(
                                'issue: %s' % absolute_url(cached_issue))))
                if cached_issue.id == exclude_issue_id:
                    disabled_choices.append(choice)
        if cached_stories:
            for cached_story in cached_stories:
                choice = 'story_%d' % cached_story.id
                fields.append((choice,
                              mark_safe('story: %d. %s in %s' %
                                        (cached_story.sequence_number,
                                         absolute_url(cached_story),
                                         absolute_url(cached_story.issue)))))
                if cached_story.issue_id == exclude_issue_id:
                    disabled_choices.append(choice)
        if cached_covers:
            for cached_cover in cached_covers:
                choice = 'cover_%d' % cached_cover.id
                fields.append((choice,
                              mark_safe('cover %s of issue: %s' % (
                                absolute_url(cached_cover),
                                absolute_url(cached_cover.issue)))))
                if cached_cover.issue_id == exclude_issue_id:
                    disabled_choices.append(choice)
        disabled_choices = tuple(disabled_choices)
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
                                      min_value=1800,
                                      max_value=date.today().year)
        if search_issue or search_story or search_cover:
            number = forms.CharField(label='Issue Number',
                                     required=True)
        if search_story or search_cover:
            sequence_number = forms.IntegerField(label='Sequence Number',
                                                 required=False, min_value=0)
        select_key = forms.CharField(widget=HiddenInput)
    return SelectSearchForm


def get_select_issue_story_form(return_type_='reprint'):
    class SelectSearchIssueStoryForm(forms.Form):
        publisher_auto = forms.ModelChoiceField(
          queryset=Publisher.objects.all(),
          widget=autocomplete.ModelSelect2(url='publisher_autocomplete',
                                           attrs={'class': 'w-full'}),
          label='Publisher', required=False)

        series_auto = forms.ModelChoiceField(
          queryset=Series.objects.all(),
          widget=autocomplete.ModelSelect2(
            url='series_autocomplete',
            forward=[forward.Field('publisher_auto', 'publisher'),
                     forward.Field('series_year_auto', 'series_year'),
                     forward.Field('issue_number', 'issue_number')],
            attrs={'class': 'w-full'}), label='Series', required=False)
        series_year_auto = forms.IntegerField(label='Series Year',
                                              required=False,
                                              min_value=1800,
                                              max_value=date.today().year)
        issue_number = forms.CharField(
          label='Issue Number',
          help_text='(use [nn] for unnumbered singleton series.)',
          required=False)
        select_key = forms.CharField(widget=HiddenInput)
    return SelectSearchIssueStoryForm


def get_filter_form(countries=None, languages=None, publishers=None):
    class FilterSearchForm(forms.Form):
        if countries:
            country = forms.MultipleChoiceField(choices=countries,
                                                required=False)
        if languages:
            language = forms.MultipleChoiceField(choices=languages,
                                                 required=False)
        if publishers:
            publisher = forms.MultipleChoiceField(choices=publishers,
                                                  required=False)
    return FilterSearchForm
