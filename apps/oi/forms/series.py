# -*- coding: utf-8 -*-


from django import forms

from .support import (
    _get_comments_form_field, _set_help_labels, _clean_keywords,
    SERIES_HELP_LINKS, SERIES_HELP_TEXTS, GENERIC_ERROR_MESSAGE)

from apps.oi.models import (
    SeriesRevision, SeriesBondRevision, get_series_field_list,
    get_series_bond_field_list, remove_leading_article)

from apps.stddata.models import Country
from apps.gcd.models import BOND_TRACKING, SeriesBondType


def get_series_revision_form(publisher=None, source=None, user=None):
    if source is None:
        if user is not None and user.indexer.can_reserve_another_ongoing():
            can_request = True
        else:
            can_request = False

        class RuntimeAddSeriesRevisionForm(SeriesRevisionForm):
            class Meta(SeriesRevisionForm.Meta):
                exclude = SeriesRevisionForm.Meta.exclude + ['imprint',
                                                             'format']
                if can_request:
                    fields = SeriesRevisionForm.Meta.fields
                    fields = ['reservation_requested'] + fields

            if can_request:
                reservation_requested = forms.BooleanField(
                    required=False,
                    label='Request reservation',
                    help_text='Check this box to have the ongoing reservation '
                              'for this series assigned to you when it is '
                              'approved, unless you have gone over your '
                              'ongoing reservation limit at that time.')

            def as_table(self):
                if not user or user.indexer.show_wiki_links:
                    _set_help_labels(self, SERIES_HELP_LINKS)
                return super(SeriesRevisionForm, self).as_table()

        return RuntimeAddSeriesRevisionForm

    else:
        class RuntimeSeriesRevisionForm(SeriesRevisionForm):
            class Meta(SeriesRevisionForm.Meta):
                exclude = SeriesRevisionForm.Meta.exclude
                exclude.append('imprint')
                exclude.append('format')

            def __init__(self, *args, **kwargs):
                # Don't allow country and language to be un-set:
                super(RuntimeSeriesRevisionForm, self).__init__(*args,
                                                                **kwargs)
                self.fields['country'].empty_label = None
                self.fields['language'].empty_label = None

            if user.has_perm('indexer.can_approve'):
                move_to_publisher_with_id = forms.IntegerField(
                    required=False,
                    help_text="Only editors can move a series. A "
                              "confirmation page will follow to confirm the "
                              "move.<br>"
                              "The move of a series is only possible if no "
                              "issues are reserved. Brand and indicia "
                              "publisher entries of the issues will be reset.")

            def as_table(self):
                if not user or user.indexer.show_wiki_links:
                    _set_help_labels(self, SERIES_HELP_LINKS)
                return super(SeriesRevisionForm, self).as_table()

        return RuntimeSeriesRevisionForm


class SeriesRevisionForm(forms.ModelForm):

    class Meta:
        model = SeriesRevision
        fields = get_series_field_list()
        exclude = ['publisher']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'wide', 'autofocus': ''}),
            'year_began': forms.TextInput(attrs={'class': 'year'}),
            'year_ended': forms.TextInput(attrs={'class': 'year'}),
            'color': forms.TextInput(attrs={'class': 'wide'}),
            'dimensions': forms.TextInput(attrs={'class': 'wide'}),
            'paper_stock': forms.TextInput(attrs={'class': 'wide'}),
            'binding': forms.TextInput(attrs={'class': 'wide'}),
            'publishing_format': forms.TextInput(attrs={'class': 'wide'})
        }
        labels = {
            'has_isbn': 'Has ISBN',
            'has_rating': "Has Publisher's age guidelines ",
        }
        help_texts = SERIES_HELP_TEXTS

    def __init__(self, *args, **kwargs):
        super(SeriesRevisionForm, self).__init__(*args, **kwargs)
        self.fields['country'].queryset = Country.objects.exclude(code='xx')

    comments = _get_comments_form_field()

    def clean_keywords(self):
        return _clean_keywords(self.cleaned_data)

    def clean(self):
        cd = self.cleaned_data
        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        if 'name' in cd:
            cd['name'] = cd['name'].strip()
            if (cd['leading_article'] and
                    cd['name'] == remove_leading_article(cd['name'])):
                raise forms.ValidationError(
                    'The series name is only one word, you cannot specify '
                    'a leading article in this case.')

        cd['color'] = cd['color'].strip()
        cd['dimensions'] = cd['dimensions'].strip()
        cd['paper_stock'] = cd['paper_stock'].strip()
        cd['binding'] = cd['binding'].strip()
        cd['publishing_format'] = cd['publishing_format'].strip()
        cd['comments'] = cd['comments'].strip()
        if 'reservation_requested' in cd and cd['reservation_requested'] and \
                (not cd['is_current'] and not cd['is_singleton']):
            raise forms.ValidationError(
                'A reservation can only be requested for currently ongoing '
                'series.')
        # some status checks for singleton series
        if cd['is_singleton'] and cd['has_issue_title']:
            raise forms.ValidationError(
                'Singleton series cannot have an issue title.')
        if cd['is_singleton'] and cd['notes']:
            raise forms.ValidationError(
                'Notes for singleton series are stored on the issue level.')
        if cd['is_singleton'] and cd['tracking_notes']:
            raise forms.ValidationError(
                'Singleton series cannot have tracking notes.')
        if cd['is_singleton'] and cd['is_current']:
            raise forms.ValidationError(
                'Singleton series do not continue and therefore cannot be '
                'current in our sense.')

        # TODO How to get to series ?
        # Then we could check the number of issues for singletons
        return cd


def _get_series_has_fields_off_note(series, field):
    off_note = (
        'The %s field is turned off for %s. To enter a value for %s this '
        'setting for the series has to be changed.' % (field, series, field))
    return (off_note,
            forms.BooleanField(widget=forms.HiddenInput, required=False))


def get_series_bond_revision_form(revision=None, user=None):
    class RuntimeSeriesBondRevisionForm(SeriesBondRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeSeriesBondRevisionForm, self).__init__(*args,
                                                                **kwargs)
            self.fields['bond_type'].queryset = \
                SeriesBondType.objects.filter(id__in=BOND_TRACKING)

        def as_table(self):
            # TODO: add help links
            return super(RuntimeSeriesBondRevisionForm, self).as_table()

    return RuntimeSeriesBondRevisionForm


class SeriesBondRevisionForm(forms.ModelForm):
    class Meta:
        model = SeriesBondRevision
        fields = get_series_bond_field_list()
        widgets = {
            'notes': forms.TextInput(attrs={'class': 'wide'})
        }
        help_texts = {
            'notes': 'Notes about the series bond.',
        }

    comments = _get_comments_form_field()
