# -*- coding: utf-8 -*-
import unicodedata as ucd
from collections import OrderedDict
from django import forms
from django.forms.models import inlineformset_factory
from django.forms.widgets import HiddenInput

from dal import autocomplete

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field

from apps.oi.models import CreatorRevision, CreatorNameDetailRevision, \
                           CreatorArtInfluenceRevision, \
                           CreatorDegreeRevision, \
                           CreatorNonComicWorkRevision, \
                           CreatorSchoolRevision, \
                           CreatorMembershipRevision, \
                           CreatorRelationRevision, \
                           CreatorSignatureRevision, get_creator_field_list, \
                           _get_creator_sourced_fields, _check_year
from apps.gcd.models import NameType, CreatorNameDetail, School
from apps.stddata.models import Country

from .custom_layout_object import Formset, FormAsField, BaseField
from .support import (GENERIC_ERROR_MESSAGE, CREATOR_MEMBERSHIP_HELP_TEXTS,
                      CREATOR_HELP_TEXTS, CREATOR_ARTINFLUENCE_HELP_TEXTS,
                      CREATOR_NONCOMICWORK_HELP_TEXTS,
                      CREATOR_RELATION_HELP_TEXTS, CREATOR_HELP_LINKS,
                      CREATOR_ARTINFLUENCE_HELP_LINKS,
                      CREATOR_DEGREE_HELP_LINKS, CREATOR_MEMBERSHIP_HELP_LINKS,
                      CREATOR_NONCOMICWORK_HELP_LINKS,
                      CREATOR_RELATION_HELP_LINKS, CREATOR_SCHOOL_HELP_LINKS,
                      CREATOR_SIGNATURE_HELP_TEXTS,
                      _set_help_labels, _get_comments_form_field,
                      init_data_source_fields, insert_data_source_fields,
                      _create_embedded_image_revision,
                      _save_runtime_embedded_image_revision,
                      BaseForm, HiddenInputWithHelp, ModifiedPagedownWidget)


# if we want/need to have more specific control, we can use
# str.maketrans with a map that encodes our needs
# https://stackoverflow.com/questions/65833714/how-to-remove-accents-from-a-string-in-python
def remove_diacritics(input_str):
    nfkd_form = ucd.normalize('NFKD', input_str)
    return u"".join([c for c in nfkd_form if not ucd.combining(c)])


def _generic_data_source_clean(form, cd, field=''):
    data_source_type = cd['%s_source_type' % field]
    data_source_description = cd['%s_source_description' % field]
    if data_source_type or data_source_description:
        if not data_source_type or not data_source_description:
            form.add_error(
              '%s_source_description' % field,
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
        self.fields['sort_name'].help_text = "In the Western culture usually "\
                                             " 'family name, given name'."
        if self.instance.creator_name_detail:
            if self.instance.creator_name_detail.type and \
               self.instance.creator_name_detail.type.id in [1, 3, 4, 6, 9]:
                self.fields['type'].queryset |= NameType.objects.filter(
                  id=self.instance.creator_name_detail.type.id)
            if self.instance.creator_name_detail.storycredit_set\
                                                .filter(deleted=False).count()\
                or self.instance.creator_name_detail.issuecredit_set\
                                                .filter(deleted=False).count()\
                or self.instance.creator_name_detail.storycreditrevision_set\
                                                    .active_set().exists()\
                or self.instance.creator_name_detail.issuecreditrevision_set\
                                                    .active_set().exists():
                self.no_delete = True
                self.fields['name'].help_text = \
                    'Creator names with existing credits cannot be removed.'
            if self.instance.creator_name_detail.storycredit_set.filter(
               is_credited=True, credited_as='', deleted=False).count():
                self.fields['name'].widget.attrs['readonly'] = 'true'
                self.fields['name'].help_text = \
                  'The name of a creator name with existing credits marked as'\
                  ' "is_credited" cannot be changed, nor can the creator name'\
                  ' be removed.'
                self.no_delete = True
            if self.instance.creator_name_detail.is_official_name:
                self.no_delete = True

    def clean(self):
        cd = self.cleaned_data
        if (not cd['type'] or cd['type'].id not in [2, 10, 11]) and \
           (cd['family_name'] or cd['given_name']):
            raise forms.ValidationError(
              "Family or given name can only be entered for 'name at birth', "
              "'changed name', or 'common alternate name'.")


class CustomInlineFormSet(forms.BaseInlineFormSet):
    def _should_delete_form(self, form):
        # TODO workaround, better to not allow the removal, see above
        if form.instance.creator_name_detail:
            if form.instance.creator_name_detail.storycredit_set\
                                                .filter(deleted=False).count()\
              or form.instance.creator_name_detail.issuecredit_set\
                                                .filter(deleted=False).count()\
              or form.instance.creator_name_detail.storycreditrevision_set\
                                                  .active_set().exists()\
              or form.instance.creator_name_detail.issuecreditrevision_set\
                                                  .active_set().exists():
                form.cleaned_data['DELETE'] = False
                return False
        if form.instance.creator_name_detail:
            if form.instance.creator_name_detail.is_official_name:
                form.cleaned_data['DELETE'] = False
                return False
        return super(CustomInlineFormSet, self)._should_delete_form(form)

    def clean(self):
        super(CustomInlineFormSet, self).clean()
        gcd_official_count = 0
        names = []
        for form in self.forms:
            cd = form.cleaned_data
            if 'is_official_name' in cd and cd['is_official_name'] and \
               not cd['DELETE']:
                gcd_official_count += 1
            if 'name' in cd and not cd['DELETE'] and (
              cd['id'] is None or cd['id'].creator is None):
                if remove_diacritics(cd['name']) in names:
                    raise forms.ValidationError(
                      "Name %s is entered twice, or already exists "
                      "with/without accents or umlauts." % cd['name'])
            if 'name' in cd and 'DELETE' in cd and not cd['DELETE']:
                names.append(remove_diacritics(cd['name']))
        if gcd_official_count != 1:
            raise forms.ValidationError(
              "Exactly one name needs to selected as the gcd_official_name.")


CreatorRevisionFormSet = inlineformset_factory(
    CreatorRevision, CreatorNameDetailRevision,
    form=CreatorNameDetailRevisionForm, can_delete=True, extra=1,
    formset=CustomInlineFormSet)


def get_creator_revision_form(revision=None, user=None):
    class RuntimeCreatorRevisionForm(CreatorRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeCreatorRevisionForm, self).__init__(*args, **kwargs)
            if revision:
                for field in _get_creator_sourced_fields():
                    init_data_source_fields(field, revision, self.fields)

    return RuntimeCreatorRevisionForm


class CreatorRevisionForm(BaseForm):
    class Meta:
        model = CreatorRevision
        fields = get_creator_field_list()
        fields.remove('birth_date')
        fields.remove('death_date')
        help_texts = CREATOR_HELP_TEXTS
        labels = {'bio': 'Biography', 'whos_who': "Who's Who",
                  'birth_province': 'Birth province or state',
                  'death_province': 'Death province or state'}
        widgets = {'bio': ModifiedPagedownWidget(attrs={'class':
                                                        'w-full lg:w-4/5',
                                                        'rows': 7})}

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
        field_list.extend([BaseField(Field(field,
                                           template='oi/bits/uni_field.html'))
                           for field in fields[:1]])
        field_list.append(FormAsField('birth_date_form'))
        death_start = fields.index('death_country')
        field_list.extend([BaseField(Field(field,
                                           template='oi/bits/uni_field.html'))
                           for field in fields[1:death_start]])
        field_list.append(FormAsField('death_date_form'))
        whos_link = fields.index('whos_who')
        field_list.extend([BaseField(Field(field,
                                           template='oi/bits/uni_field.html'))
                           for field in fields[death_start:whos_link+1]])
        field_list.append(Formset('external_link_formset'))
        field_list.extend([BaseField(Field(field,
                                           template='oi/bits/uni_field.html'))
                           for field in fields[whos_link+1:-1]])
        self.helper.layout = Layout(*(f for f in field_list))
        self.helper.doc_links = CREATOR_HELP_LINKS

    birth_country = forms.ModelChoiceField(
        queryset=Country.objects.exclude(code='xx'), required=False)
    death_country = forms.ModelChoiceField(
        queryset=Country.objects.exclude(code='xx'), required=False)

    creator_help = forms.CharField(
        widget=HiddenInputWithHelp,
        required=False,
        help_text="<ul class='list-disc list-outside ps-4'>"
                  "<li>All commonly known names for a creator can be "
                  "recorded, where we use various types of names.</li>"
                  "Besides legal names we use 'pen name' and 'common "
                  "alternative name' for known alias and common name "
                  "variations."
                  "<li>One of the names has to be selected as the GCD "
                  "official name by selecting 'Is official name'.</li>"
                  "<li>An existing GCD official name cannot be deleted, "
                  "but it can be changed. The delete is a second change.</li>"
                  "<li>For each name the given and family name(s) are "
                  "recorded.</li> For alphabetical sorting we use the "
                  "sort name, which often is 'family name, given name'."
                  "<li>For each name we record the script, e.g. 'Japanese' "
                  "for the name of a creator from Japan given in Japanese "
                  "script.</li>'Latin' script is the default and for example "
                  "used in West and Central Europe and the Americas."
                  "<li>The types 'Family', 'Given (birth)', 'GCD official', "
                  "and the language types are deprecated and need to be "
                  "removed from old creator records, they are not available "
                  "as selections for new ones.</li></ul>",
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

    school = forms.ModelChoiceField(
        queryset=School.objects.all(),
        widget=autocomplete.ModelSelect2(url='school_autocomplete',
                                         attrs={'style': 'min-width: 60em'}),
    )

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


def get_creator_signature_revision_form(revision=None, user=None):
    class RuntimeCreatorSignatureRevisionForm(CreatorSignatureRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeCreatorSignatureRevisionForm,
                  self).__init__(*args, **kwargs)
            if revision:
                init_data_source_fields('', revision, self.fields)

            if revision.image_revision or (revision.source and
                                           revision.source.signature):
                self.fields['signature'].help_text = \
                  'Select a file if you want to replace the existing image.'

        if revision.source:
            if revision.source.generic:
                signature = forms.ImageField(widget=HiddenInput,
                                             required=False)
            generic = forms.BooleanField(widget=HiddenInput, required=False)

        def save(self, commit=True):
            instance = super(RuntimeCreatorSignatureRevisionForm,
                             self).save(commit=commit)
            if instance.image_revision and revision:
                if revision.source:
                    image = revision.creator_signature.signature
                else:
                    image = None
                instance = _save_runtime_embedded_image_revision(instance,
                                                                 revision,
                                                                 image)
            return instance

        def clean(self):
            cd = self.cleaned_data

            if not cd['generic'] and not cd['signature'] and \
               not revision.image_revision and not revision.source:
                raise forms.ValidationError('Either mark the signature as '
                                            'generic or upload an image.')
            if cd['generic'] and cd['signature']:
                raise forms.ValidationError('Either mark the signature as '
                                            'generic or upload an image.')
            if cd['generic'] and revision.image_revision:
                raise forms.ValidationError('Signature image exists, cannot '
                                            'mark the signature as generic.')
            if self._errors:
                raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
            _generic_data_source_clean(self, cd)

        def as_table(self):
            # if not user or user.indexer.show_wiki_links:
            #     _set_help_labels(self, CREATOR_DEGREE_HELP_LINKS)
            return super(CreatorSignatureRevisionForm, self).as_table()

    return RuntimeCreatorSignatureRevisionForm


class CreatorSignatureRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorSignatureRevision
        fields = model._base_field_list
        help_texts = CREATOR_SIGNATURE_HELP_TEXTS

    def __init__(self, *args, **kwargs):
        super(CreatorSignatureRevisionForm, self).__init__(*args, **kwargs)
        ordering = list(self.fields)
        ordering.insert(1, 'signature')
        insert_data_source_fields('', ordering, self.fields,
                                  'signature')
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields

    signature = forms.ImageField(widget=forms.FileInput, required=False)

    comments = _get_comments_form_field()

    def save(self, commit=True):
        instance = super(CreatorSignatureRevisionForm, self).save(
                                                             commit=commit)
        signature = self.cleaned_data['signature']
        if signature:
            instance = _create_embedded_image_revision(instance,
                                                       signature,
                                                       'CreatorSignature')
        return instance

    def clean(self):
        cd = self.cleaned_data

        if not cd['generic'] and not cd['signature']:
            raise forms.ValidationError('Either mark the signature as generic '
                                        'or upload an image.')
        if cd['generic'] and cd['signature']:
            raise forms.ValidationError('Either mark the signature as generic '
                                        'or upload an image.')
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

    school = forms.ModelChoiceField(
        queryset=School.objects.all(),
        widget=autocomplete.ModelSelect2(url='school_autocomplete',
                                         attrs={'style': 'min-width: 60em'}),
    )

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
            if 'influence_link' in self.initial and \
               self.initial['influence_link']:
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
        if creator:
            return creator.creator
        else:
            return None

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
      queryset=CreatorNameDetail.objects.filter(type__id__in=[5, 8, 12, 13],
                                                deleted=False),
      widget=autocomplete.ModelSelect2Multiple(
        url='creator_name_4_relation_autocomplete',
        attrs={'style': 'min-width: 60em'},
        forward=['from_creator']),
      help_text='For employee, ghosts, or user of house name relations also '
                'add the involved creator name(s).',
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

        if cd['creator_name'] and not cd['relation_type'].id in [2, 3, 4, 9]:
            self.add_error(
              'creator_name', 'Select a creator name only for owners or '
                              'employees of a studio or for house names.')
        if cd['creator_name'] and cd['relation_type'].id in [2, 3, 4, 9]:
            for creator_name in cd['creator_name']:
                if creator_name.creator != cd['from_creator']:
                    self.add_error(
                      'creator_name',
                      'Selected creator name is from a different creator.')
        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        _generic_data_source_clean(self, cd)
