# -*- coding: utf-8 -*-

from collections import OrderedDict
from django import forms

from apps.oi.models import CreatorRevision, CreatorMembershipRevision, \
                           CreatorAwardRevision, CreatorArtInfluenceRevision, \
                           CreatorNonComicWorkRevision, CreatorSchoolDetailRevision, \
                           get_creator_field_list,\
                           CreatorDataSourceRevision, CreatorDegreeDetailRevision, \
                           _get_creator_sourced_fields, _check_year

from .support import (GENERIC_ERROR_MESSAGE, CREATOR_MEMBERSHIP_HELP_TEXTS,
                      CREATOR_HELP_TEXTS, CREATOR_ARTINFLUENCE_HELP_TEXTS,
                      CREATOR_NONCOMICWORK_HELP_TEXTS, CREATOR_AWARD_HELP_LINKS,
                      CREATOR_ARTINFLUENCE_HELP_LINKS, CREATOR_HELP_LINKS,
                      CREATOR_DEGREE_HELP_LINKS, CREATOR_MEMBERSHIP_HELP_LINKS,
                      CREATOR_NONCOMICWORK_HELP_LINKS,
                      CREATOR_SCHOOL_HELP_LINKS,
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

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, CREATOR_HELP_LINKS)
            return super(CreatorRevisionForm, self).as_table()

    return RuntimeCreatorRevisionForm


class CreatorRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorRevision
        fields = get_creator_field_list()
        fields.remove('birth_date')
        fields.remove('death_date')
        help_texts = CREATOR_HELP_TEXTS
        labels = {'bio': 'Biography', 'whos_who': "Who's Who",
                  'birth_province': 'Birth province or state',
                  'death_province': 'Death province or state'}

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
        self.fields['bio_source_description'].label = \
          "Biography source description"
        self.fields['bio_source_type'].label = \
          "Biography source type"

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

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, CREATOR_SCHOOL_HELP_LINKS)
            return super(CreatorSchoolRevisionForm, self).as_table()

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

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, CREATOR_DEGREE_HELP_LINKS)
            return super(CreatorDegreeRevisionForm, self).as_table()

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

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, CREATOR_MEMBERSHIP_HELP_LINKS)
            return super(CreatorMembershipRevisionForm, self).as_table()

    return RuntimeCreatorMembershipRevisionForm


class CreatorMembershipRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorMembershipRevision
        exclude = ['creator', 'creator_membership', 'changeset', 'deleted',]
        help_texts = CREATOR_MEMBERSHIP_HELP_TEXTS

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

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, CREATOR_AWARD_HELP_LINKS)
            return super(CreatorAwardRevisionForm, self).as_table()

    return RuntimeCreatorAwardRevisionForm


class CreatorAwardRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorAwardRevision
        fields = model._base_field_list

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

        if (not cd['award_name'] and not cd['no_award_name']):
            self.add_error('award_name',
              'Either enter the award name or check no award name.')

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

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, CREATOR_ARTINFLUENCE_HELP_LINKS)
            return super(CreatorArtInfluenceRevisionForm, self).as_table()

    return RuntimeCreatorArtInfluenceRevisionForm


class CreatorArtInfluenceRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorArtInfluenceRevision
        exclude = ['creator', 'creator_artinfluence','changeset', 'deleted',]
        help_texts = CREATOR_ARTINFLUENCE_HELP_TEXTS

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
        if cd['influence_name'] and cd['influence_link']:
            self.add_error('influence_name',
                'Enter either the name of an influence or a link to an '
                'influence, but not both.')
        if not cd['influence_name'] and not cd['influence_link']:
            self.add_error('influence_name',
                'Either the name of an influence or a link to an '
                'influence needs to be given.')


def get_creator_non_comic_work_revision_form(revision=None, user=None):
    class RuntimeCreatorNonComicWorkRevisionForm(\
                 CreatorNonComicWorkRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeCreatorNonComicWorkRevisionForm, self)\
                         .__init__(*args, **kwargs)

            if revision:
                init_data_source_fields('', revision, self.fields)

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, CREATOR_NONCOMICWORK_HELP_LINKS)
            return super(CreatorNonComicWorkRevisionForm, self).as_table()

    return RuntimeCreatorNonComicWorkRevisionForm


class CreatorNonComicWorkRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorNonComicWorkRevision
        fields = model._base_field_list
        help_texts = CREATOR_NONCOMICWORK_HELP_TEXTS

    def __init__(self, *args, **kwargs):
        super(CreatorNonComicWorkRevisionForm, self).__init__(*args, **kwargs)
        ordering = self.fields.keys()
        insert_data_source_fields('', ordering, self.fields, 'notes')
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields

    comments = _get_comments_form_field()

    def clean_work_years(self):
        value = self.cleaned_data['work_years']
        try:
            for year in value.split(';'):
                range_split = year.split('-')
                if len(range_split) == 2:
                    year_began = _check_year(range_split[0])
                    year_end = _check_year(range_split[1])
                    if year_began > year_end:
                        raise forms.ValidationError(
                                    "Years in range do not validata.")
                else:
                    _check_year(year)
        except ValueError:
            raise forms.ValidationError("Enter years separated by ';'.")
        return value

    def clean(self):
        cd = self.cleaned_data

        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        _generic_data_source_clean(self, cd)
