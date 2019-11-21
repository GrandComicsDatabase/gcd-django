# -*- coding: utf-8 -*-

from collections import OrderedDict
from django import forms
from django.forms.models import inlineformset_factory

from dal import autocomplete

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field
from crispy_forms.utils import render_field

from apps.oi.models import CreatorRevision, CreatorNameDetailRevision,\
                           CreatorArtInfluenceRevision, CreatorDegreeRevision,\
                           CreatorNonComicWorkRevision, CreatorSchoolRevision,\
                           CreatorMembershipRevision, CreatorRelationRevision,\
                           get_creator_field_list,\
                           _get_creator_sourced_fields, _check_year

from apps.gcd.models import NameType, CreatorNameDetail
from apps.stddata.models import Country

from .custom_layout_object import Formset, FormAsField
from .support import (GENERIC_ERROR_MESSAGE, CREATOR_MEMBERSHIP_HELP_TEXTS,
                      CREATOR_HELP_TEXTS, CREATOR_ARTINFLUENCE_HELP_TEXTS,
                      CREATOR_NONCOMICWORK_HELP_TEXTS,
                      CREATOR_RELATION_HELP_TEXTS, CREATOR_HELP_LINKS,
                      CREATOR_ARTINFLUENCE_HELP_LINKS,
                      CREATOR_DEGREE_HELP_LINKS, CREATOR_MEMBERSHIP_HELP_LINKS,
                      CREATOR_NONCOMICWORK_HELP_LINKS,
                      CREATOR_RELATION_HELP_LINKS, CREATOR_SCHOOL_HELP_LINKS,
                      _set_help_labels, _get_comments_form_field,
                      init_data_source_fields, insert_data_source_fields,
                      HiddenInputWithHelp)


def _generic_data_source_clean(form, cd):
    data_source_type = cd['_source_type']
    data_source_description = cd['_source_description']
    if data_source_type or data_source_description:
        if not data_source_type or not data_source_description:
            form.add_error(
              '_source_description',
              'Source description and source type must both be set.')


class CreatorNameDetailRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorNameDetailRevision
        fields = ['name', 'sort_name', 'is_official_name', 'given_name',
                  'family_name', 'type', 'in_script']

    def __init__(self, *args, **kwargs):
        super(CreatorNameDetailRevisionForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.layout = Layout(*(f for f in self.fields))
        self.fields['type'].queryset = NameType.objects.exclude(id__in=[1, 3,
                                                                        4, 6,
                                                                        9])
        if self.instance.creator_name_detail:
            if self.instance.creator_name_detail.type.id in [1, 3, 4, 6, 9]:
                self.fields['type'].queryset |= NameType.objects.filter(
                  id=self.instance.creator_name_detail.type.id)
            if self.instance.creator_name_detail.storycredit_set.count():
                # TODO How can the 'remove'-link not be shown in this case ?
                self.fields['name'].help_text = \
                    'Creator names with existing credits cannot be removed.'
            if self.instance.creator_name_detail.storycredit_set.filter(
               is_credited=True, credit_name='').count():
                self.fields['name'].widget.attrs['readonly'] = 'true'
                self.fields['name'].help_text = \
                  'The name of a creator name with existing credits marked as'\
                  ' "is_credited" cannot be changed, nor can the creator name'\
                  ' be removed.'


class CustomInlineFormSet(forms.BaseInlineFormSet):
    def _should_delete_form(self, form):
        # TODO workaround, better to not allow the removal, see above
        if form.instance.creator_name_detail:
            if form.instance.creator_name_detail.storycredit_set.count():
                form.cleaned_data['DELETE'] = False
                return False
        return super(CustomInlineFormSet, self)._should_delete_form(form)

    def clean(self):
        super(CustomInlineFormSet, self).clean()
        gcd_official_count = 0
        for form in self.forms:
            cd = form.cleaned_data
            if 'is_official_name' in cd and cd['is_official_name'] and \
               not cd['DELETE']:
                gcd_official_count += 1
        if gcd_official_count != 1:
            raise forms.ValidationError(
              "Exactly one name needs to selected as the gcd_official_name.")


CreatorRevisionFormSet = inlineformset_factory(
    CreatorRevision, CreatorNameDetailRevision,
    form=CreatorNameDetailRevisionForm, can_delete=True, extra=1,
    formset=CustomInlineFormSet)


class BaseField(Field):
    def render(self, form, form_style, context, template_pack=None):
        fields = ''

        for field in self.fields:
            fields += render_field(field, form, form_style, context,
                                   template_pack=template_pack)
        return fields


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
        help_texts = CREATOR_HELP_TEXTS
        labels = {'bio': 'Biography', 'whos_who': "Who's Who",
                  'birth_province': 'Birth province or state',
                  'death_province': 'Death province or state'}

    def __init__(self, *args, **kwargs):
        super(CreatorRevisionForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-md-3 create-label'
        self.helper.field_class = 'col-md-9'
        self.helper.form_tag = False
        ordering = list(self.fields)
        creator_sourced_fields = _get_creator_sourced_fields()
        for field in creator_sourced_fields:
            insert_data_source_fields(field, ordering, self.fields,
                                      creator_sourced_fields[field])
        # in django 1.9 there is Form.order_fields
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields
        self.fields['bio_source_description'].label = \
          "Biography source description"
        self.fields['bio_source_type'].label = "Biography source type"
        fields = list(self.fields)
        field_list = [BaseField(Field('creator_help',
                                      template='oi/bits/uni_field.html'))]
        field_list.append(Formset('creator_names_formset'))
        field_list.append(FormAsField('birth_date_form'))
        death_start = fields.index('death_country')
        field_list.extend([BaseField(Field(field,
                                           template='oi/bits/uni_field.html'))
                           for field in fields[:death_start]])
        field_list.append(FormAsField('death_date_form'))
        field_list.extend([BaseField(Field(field,
                                           template='oi/bits/uni_field.html'))
                           for field in fields[death_start:-1]])
        self.helper.layout = Layout(*(f for f in field_list))
        self.helper.doc_links = CREATOR_HELP_LINKS

    birth_country = forms.ModelChoiceField(
        queryset=Country.objects.exclude(code='xx'), required=False)
    death_country = forms.ModelChoiceField(
        queryset=Country.objects.exclude(code='xx'), required=False)

    comments = _get_comments_form_field()

    creator_help = forms.CharField(
        widget=HiddenInputWithHelp,
        required=False,
        help_text="<ul><li>All commonly known names for a creator can be "
                  "recorded, where we use various types of names.</li>"
                  "Besides legal names we use 'pen name' and 'common "
                  "alternative name' for known alias and common name "
                  "variations."
                  "<li>One of the names has to be selected as the official "
                  "name.</li>"
                  "<li>For each name the given and family name(s) are "
                  "recorded.</li> For alphabetical sorting we use the "
                  "sort name, which often is 'family name, given name'."
                  "<li>For each name we record the script, e.g. 'Japanese' "
                  "for the name of a creator from Japan given in Japanese "
                  "script. 'Latin' script is the default.</li>"
                  "<li>The types 'Family', 'Given (birth)', 'GCD official', "
                  "and the language types are deprecated.</li></ul>",
        label='')

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
        model = CreatorSchoolRevision
        fields = model._base_field_list

    def __init__(self, *args, **kwargs):
        super(CreatorSchoolRevisionForm, self).__init__(*args, **kwargs)
        ordering = list(self.fields)
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
        model = CreatorDegreeRevision
        fields = model._base_field_list

    def __init__(self, *args, **kwargs):
        super(CreatorDegreeRevisionForm, self).__init__(*args, **kwargs)
        ordering = list(self.fields)
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
        fields = model._base_field_list
        help_texts = CREATOR_MEMBERSHIP_HELP_TEXTS

    def __init__(self, *args, **kwargs):
        super(CreatorMembershipRevisionForm, self).__init__(*args, **kwargs)
        ordering = list(self.fields)
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
    class RuntimeCreatorArtInfluenceRevisionForm(
                 CreatorArtInfluenceRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeCreatorArtInfluenceRevisionForm, self)\
                         .__init__(*args, **kwargs)
            if revision:
                init_data_source_fields('', revision, self.fields)
            if 'influence_link' in self.initial:
                self.initial['influence_link'] = CreatorNameDetail.objects.get(
                  creator__id=self.initial['influence_link'],
                  is_official_name=True, deleted=False).id

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, CREATOR_ARTINFLUENCE_HELP_LINKS)
            return super(CreatorArtInfluenceRevisionForm, self).as_table()

    return RuntimeCreatorArtInfluenceRevisionForm


class CreatorArtInfluenceRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorArtInfluenceRevision
        fields = model._base_field_list
        help_texts = CREATOR_ARTINFLUENCE_HELP_TEXTS

    influence_link = forms.ModelChoiceField(
        queryset=CreatorNameDetail.objects.filter(deleted=False),
        widget=autocomplete.ModelSelect2(url='creator_name_autocomplete',
                                         attrs={'style': 'min-width: 60em'}),
        required=False
    )

    def __init__(self, *args, **kwargs):
        super(CreatorArtInfluenceRevisionForm, self).__init__(*args, **kwargs)
        ordering = list(self.fields)
        insert_data_source_fields('', ordering, self.fields,
                                  'notes')
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields

    comments = _get_comments_form_field()

    def clean_influence_link(self):
        creator = self.cleaned_data['influence_link']
        return creator.creator

    def clean(self):
        cd = self.cleaned_data

        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        _generic_data_source_clean(self, cd)
        if 'influence_name' in cd and cd['influence_name'] \
           and cd['influence_link']:
            self.add_error(
              'influence_name', 'Enter either the name of an influence or a '
                                'link to an influence, but not both.')
        if not cd['influence_link'] and ('influence_name' not in cd or
                                         not cd['influence_name']):
            self.add_error(
              'influence_name', 'Either the name of an influence or a link to'
                                ' an influence needs to be given.')


def get_creator_non_comic_work_revision_form(revision=None, user=None):
    class RuntimeCreatorNonComicWorkRevisionForm(
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
        ordering = list(self.fields)
        insert_data_source_fields('', ordering, self.fields, 'notes')
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields

    comments = _get_comments_form_field()

    def clean_work_years(self):
        value = self.cleaned_data['work_years']
        if not value:
            return value
        try:
            for year in value.split(';'):
                range_split = year.split('-')
                if len(range_split) == 2:
                    year_began = _check_year(range_split[0])
                    year_end = _check_year(range_split[1])
                    if year_began > year_end:
                        raise forms.ValidationError(
                                    "Years in range do not validate.")
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


def get_creator_relation_revision_form(revision=None, user=None):
    class RuntimeCreatorRelationRevisionForm(CreatorRelationRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeCreatorRelationRevisionForm, self)\
                         .__init__(*args, **kwargs)
            if revision:
                init_data_source_fields('', revision, self.fields)
            if 'to_creator' in self.initial:
                self.initial['to_creator'] = CreatorNameDetail.objects.get(
                  creator__id=self.initial['to_creator'],
                  is_official_name=True, deleted=False).id
            if 'from_creator' in self.initial:
                self.initial['from_creator'] = CreatorNameDetail.objects.get(
                  creator__id=self.initial['from_creator'],
                  is_official_name=True, deleted=False).id

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, CREATOR_RELATION_HELP_LINKS)
            return super(CreatorRelationRevisionForm, self).as_table()

    return RuntimeCreatorRelationRevisionForm


class CreatorRelationRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorRelationRevision
        fields = model._base_field_list
        help_texts = CREATOR_RELATION_HELP_TEXTS
        labels = {'from_creator': 'Creator A', 'relation_type': 'Relation',
                  'to_creator': 'Creator B'}

    def __init__(self, *args, **kwargs):
        super(CreatorRelationRevisionForm, self).__init__(*args, **kwargs)
        ordering = list(self.fields)
        insert_data_source_fields('', ordering, self.fields, 'notes')
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields

    from_creator = forms.ModelChoiceField(
        queryset=CreatorNameDetail.objects.filter(deleted=False),
        widget=autocomplete.ModelSelect2(url='creator_name_autocomplete',
                                         attrs={'style': 'min-width: 60em'})
    )

    to_creator = forms.ModelChoiceField(
        queryset=CreatorNameDetail.objects.filter(deleted=False),
        widget=autocomplete.ModelSelect2(url='creator_name_autocomplete',
                                         attrs={'style': 'min-width: 60em'})
    )

    creator_name = forms.ModelMultipleChoiceField(
      queryset=CreatorNameDetail.objects.filter(type__id=8, deleted=False),
      widget=autocomplete.ModelSelect2Multiple(
        url='creator_name_4_relation_autocomplete',
        attrs={'style': 'min-width: 60em'}),
      help_text='For employee or user of house name relations also add the '
                'involved creator name.',
      required=False
      )

    comments = _get_comments_form_field()

    def clean_from_creator(self):
        creator = self.cleaned_data['from_creator']
        return creator.creator

    def clean_to_creator(self):
        creator = self.cleaned_data['to_creator']
        return creator.creator

    def clean(self):
        cd = self.cleaned_data

        if cd['creator_name'] and not cd['relation_type'].id in [3, 4]:
            self.add_error(
              'creator_name', 'Select a creator name only for employees of a '
                              'studio or for house names.')
        if cd['creator_name'] and cd['relation_type'].id in [3, 4]:
            for creator_name in cd['creator_name']:
                if creator_name.creator != cd['from_creator']:
                    self.add_error(
                      'creator_name',
                      'Selected creator name is from a different creator.')
        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        _generic_data_source_clean(self, cd)
