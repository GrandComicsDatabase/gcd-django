# -*- coding: utf-8 -*-

from collections import OrderedDict
from django import forms

from apps.oi.models import CreatorRevision, CreatorMembershipRevision, \
                           CreatorAwardRevision, CreatorArtInfluenceRevision, \
                           CreatorNonComicWorkRevision, CreatorSchoolDetailRevision, \
                           get_creator_field_list,\
                           CreatorDataSourceRevision, CreatorDegreeDetailRevision, \
                           _get_creator_sourced_fields

from .support import (GENERIC_ERROR_MESSAGE, 
                      _set_help_labels, _get_comments_form_field,
                      init_data_source_fields, insert_data_source_fields,
                      HiddenInputWithHelp)


def _generic_data_source_clean(form, cd):
    data_source_type = cd['_source_type']
    data_source_description = cd['_source_description']
    if data_source_type or data_source_description:
        if not data_source_type or not data_source_description:
            form.add_error('_source_description',
              'Source description and source type must both be set.')

# TODO add help links as for other forms

def get_creator_revision_form(revision=None, user=None):
    class RuntimeCreatorRevisionForm(CreatorRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeCreatorRevisionForm, self).__init__(*args, **kwargs)
            if revision:
                for field in _get_creator_sourced_fields():
                    init_data_source_fields(field, revision, self.fields)
    return RuntimeCreatorRevisionForm


class CreatorRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorRevision
        fields = get_creator_field_list()
        fields.remove('birth_date')
        fields.remove('death_date')

    def __init__(self, *args, **kwargs):
        super(CreatorRevisionForm, self).__init__(*args, **kwargs)
        ordering = self.fields.keys()
        creator_sourced_fields = _get_creator_sourced_fields()
        for field in creator_sourced_fields:
            insert_data_source_fields(field, ordering, self.fields,
                                      creator_sourced_fields[field])
        # in django 1.9 there is Form.order_fields
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields

    comments = _get_comments_form_field()

    def clean(self):
        cd = self.cleaned_data

        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        for field in _get_creator_sourced_fields():
            data_source_type = cd['%s_source_type' % field]
            data_source_description = cd['%s_source_description' % field]
            if data_source_type or data_source_description:
                if not data_source_type or not data_source_description:
                    self.add_error(
                      '%s_source_description' % field,
                      'Source description and source type must both be set.')


def get_creator_school_revision_form(revision=None, user=None):
    class RuntimeCreatorSchoolRevisionForm(CreatorSchoolRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeCreatorSchoolRevisionForm, self)\
                         .__init__(*args, **kwargs)
            if revision:
                init_data_source_fields('', revision, self.fields)
    return RuntimeCreatorSchoolRevisionForm


class CreatorSchoolRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorSchoolDetailRevision
        fields = model._base_field_list

    def __init__(self, *args, **kwargs):
        super(CreatorSchoolRevisionForm, self).__init__(*args, **kwargs)
        ordering = self.fields.keys()
        insert_data_source_fields('', ordering, self.fields,
                                  'notes')
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields

    comments = _get_comments_form_field()

    def clean(self):
        cd = self.cleaned_data

        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        _generic_data_source_clean(self, cd)


def get_creator_degree_revision_form(revision=None, user=None):
    class RuntimeCreatorDegreeRevisionForm(CreatorDegreeRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeCreatorDegreeRevisionForm, self)\
                         .__init__(*args, **kwargs)
            if revision:
                init_data_source_fields('', revision, self.fields)
    return RuntimeCreatorDegreeRevisionForm


class CreatorDegreeRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorDegreeDetailRevision
        fields = model._base_field_list

    def __init__(self, *args, **kwargs):
        super(CreatorDegreeRevisionForm, self).__init__(*args, **kwargs)
        ordering = self.fields.keys()
        insert_data_source_fields('', ordering, self.fields,
                                  'notes')
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields

    comments = _get_comments_form_field()

    def clean(self):
        cd = self.cleaned_data

        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        _generic_data_source_clean(self, cd)


def get_creator_membership_revision_form(revision=None, user=None):
    class RuntimeCreatorMembershipRevisionForm(CreatorMembershipRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeCreatorMembershipRevisionForm, self)\
                         .__init__(*args, **kwargs)
            if revision:
                init_data_source_fields('', revision, self.fields)
    return RuntimeCreatorMembershipRevisionForm


class CreatorMembershipRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorMembershipRevision
        exclude = ['creator', 'creator_membership', 'changeset', 'deleted',]

    def __init__(self, *args, **kwargs):
        super(CreatorMembershipRevisionForm, self).__init__(*args, **kwargs)
        ordering = self.fields.keys()
        insert_data_source_fields('', ordering, self.fields,
                                  'notes')
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields

    comments = _get_comments_form_field()

    def clean(self):
        cd = self.cleaned_data

        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        _generic_data_source_clean(self, cd)


def get_creator_award_revision_form(revision=None, user=None):
    class RuntimeCreatorAwardRevisionForm(CreatorAwardRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeCreatorAwardRevisionForm, self)\
                         .__init__(*args, **kwargs)
            if revision:
                init_data_source_fields('', revision, self.fields)
    return RuntimeCreatorAwardRevisionForm


class CreatorAwardRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorAwardRevision
        exclude = ['creator', 'creator_award','changeset', 'deleted',]

    def __init__(self, *args, **kwargs):
        super(CreatorAwardRevisionForm, self).__init__(*args, **kwargs)
        ordering = self.fields.keys()
        insert_data_source_fields('', ordering, self.fields,
                                  'notes')
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields

    comments = _get_comments_form_field()

    def clean(self):
        cd = self.cleaned_data

        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        _generic_data_source_clean(self, cd)


def get_creator_art_influence_revision_form(revision=None, user=None):
    class RuntimeCreatorArtInfluenceRevisionForm(\
                 CreatorArtInfluenceRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeCreatorArtInfluenceRevisionForm, self)\
                         .__init__(*args, **kwargs)
            if revision:
                init_data_source_fields('', revision, self.fields)
    return RuntimeCreatorArtInfluenceRevisionForm


class CreatorArtInfluenceRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorArtInfluenceRevision
        exclude = ['creator', 'creator_artinfluence','changeset', 'deleted',]

    def __init__(self, *args, **kwargs):
        super(CreatorArtInfluenceRevisionForm, self).__init__(*args, **kwargs)
        ordering = self.fields.keys()
        insert_data_source_fields('', ordering, self.fields,
                                  'notes')
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields

    comments = _get_comments_form_field()

    def clean(self):
        cd = self.cleaned_data

        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        _generic_data_source_clean(self, cd)


def get_creator_non_comic_work_revision_form(revision=None, user=None):
    class RuntimeCreatorNonComicWorkRevisionForm(\
                 CreatorNonComicWorkRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeCreatorNonComicWorkRevisionForm, self)\
                         .__init__(*args, **kwargs)
            #if revision:
                #for field in _get_creator_sourced_fields():
                    #init_data_source_fields(field, revision, self.fields)
    return RuntimeCreatorNonComicWorkRevisionForm


class CreatorNonComicWorkRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorNonComicWorkRevision
        exclude = ['creator', 'creator_noncomicwork','changeset', 'deleted',]

    comments = _get_comments_form_field()
