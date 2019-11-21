# -*- coding: utf-8 -*-

from collections import OrderedDict
from django import forms

from apps.oi.models import AwardRevision, ReceivedAwardRevision, \
                           DataSourceRevision, _check_year

from .support import (GENERIC_ERROR_MESSAGE, AWARD_HELP_LINKS,
                      CREATOR_AWARD_HELP_LINKS, _set_help_labels,
                      _get_comments_form_field, init_data_source_fields,
                      insert_data_source_fields, HiddenInputWithHelp)

from .creator import _generic_data_source_clean


def get_award_revision_form(revision=None, user=None):
    class RuntimeAwardRevisionForm(AwardRevisionForm):
        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, AWARD_HELP_LINKS)
            return super(AwardRevisionForm, self).as_table()

    return RuntimeAwardRevisionForm


class AwardRevisionForm(forms.ModelForm):
    class Meta:
        model = AwardRevision
        fields = model._base_field_list

    comments = _get_comments_form_field()


def get_received_award_revision_form(revision=None, user=None):
    class RuntimeReceivedAwardRevisionForm(ReceivedAwardRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeReceivedAwardRevisionForm, self)\
                         .__init__(*args, **kwargs)
            if revision:
                init_data_source_fields('', revision, self.fields)

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, CREATOR_AWARD_HELP_LINKS)
            return super(ReceivedAwardRevisionForm, self).as_table()

    if revision == None:
        class RuntimeAddReceivedAwardRevisionForm(RuntimeReceivedAwardRevisionForm):
            class Meta(RuntimeReceivedAwardRevisionForm.Meta):
                fields = list(RuntimeReceivedAwardRevisionForm.Meta.fields)
                fields.pop(fields.index('award'))
        return RuntimeAddReceivedAwardRevisionForm

    return RuntimeReceivedAwardRevisionForm


class ReceivedAwardRevisionForm(forms.ModelForm):
    class Meta:
        model = ReceivedAwardRevision
        fields = model._base_field_list
        #fields.pop(fields.index('award'))

    def __init__(self, *args, **kwargs):
        super(ReceivedAwardRevisionForm, self).__init__(*args, **kwargs)
        ordering = list(self.fields)
        insert_data_source_fields('', ordering, self.fields,
                                  'notes')
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields

    comments = _get_comments_form_field()

    def clean(self):
        cd = self.cleaned_data

        if (cd['award_name'] != '' and cd['no_award_name']):
            raise forms.ValidationError(['Award name and no award name checkbox cannot be both filled in.'])

        if (not cd['award_name'] and not cd['no_award_name']):
             raise forms.ValidationError(['Either enter the award name or check no award name.'])

        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        _generic_data_source_clean(self, cd)

        return cd

