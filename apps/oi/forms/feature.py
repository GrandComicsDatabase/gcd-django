# -*- coding: utf-8 -*-
from django import forms
from django.forms import inlineformset_factory
from django.forms.widgets import HiddenInput

from dal import autocomplete

from collections import OrderedDict

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, HTML

from apps.gcd.models import Feature, FeatureNameDetail, FeatureRelationType
from apps.gcd.models.support import GENRES

from apps.oi.models import (FeatureRevision, FeatureLogoRevision, FeatureType,
                            FeatureRelationRevision, FeatureNameDetailRevision,
                            remove_leading_article)

from .support import (CharacterBaseForm, FEATURE_HELP_LINKS,
                      HiddenInputWithHelp,
                      _get_comments_form_field, combine_reverse_relations,
                      GENERIC_ERROR_MESSAGE, _create_embedded_image_revision,
                      _save_runtime_embedded_image_revision)
from .story import _genre_choices
from .custom_layout_object import Formset, BaseField


def get_feature_revision_form(revision=None, user=None):
    class RuntimeFeatureRevisionForm(FeatureRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeFeatureRevisionForm, self).__init__(*args, **kwargs)
            if revision:
                self.fields['feature_type'].empty_label = None

                if revision.source and revision.source.active_stories()\
                                                      .exists():
                    self.fields['feature_type'].queryset = \
                      FeatureType.objects.filter(id=revision.feature_type.id)

        language = None
        if revision is not None:
            if revision.language:
                language = revision.language
            if revision.genre:
                selected_genres = []
                genres = revision.genre.split(';')
                for genre in genres:
                    genre = genre.strip().lower()
                    selected_genres.append(genre)
                revision.genre = selected_genres

        genre = _genre_choices(language=language)

    return RuntimeFeatureRevisionForm


class FeatureNameDetailRevisionForm(forms.ModelForm):
    class Meta:
        model = FeatureNameDetailRevision
        fields = model._base_field_list
        widgets = {
            'name': forms.TextInput(attrs={'autofocus': ''}),
            }

    def __init__(self, *args, **kwargs):
        super(FeatureNameDetailRevisionForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.layout = Layout(*(f for f in self.fields))
        if self.instance.feature_name_detail:
            if self.instance.feature_name_detail.story_set\
                                                .filter(deleted=False)\
                                                .count():
                self.no_delete = True
                self.fields['name'].help_text = \
                    'Feature names with existing credits cannot be removed.'

            if self.instance.feature_name_detail.is_official_name:
                self.no_delete = True


class FeatureInlineFormSet(forms.BaseInlineFormSet):
    def _should_delete_form(self, form):
        # TODO check if still needed, we do not allow the removal, see above
        if form.instance.feature_name_detail:
            if form.instance.feature_name_detail.story_set\
                            .filter(deleted=False).count():
                form.cleaned_data['DELETE'] = False
                return False
        if form.instance.feature_name_detail:
            if form.instance.feature_name_detail.is_official_name:
                form.cleaned_data['DELETE'] = False
                return False
        return super(FeatureInlineFormSet, self)._should_delete_form(form)

    def clean(self):
        super(FeatureInlineFormSet, self).clean()
        gcd_official_count = 0
        for form in self.forms:
            cd = form.cleaned_data
            if 'is_official_name' in cd and cd['is_official_name'] and \
               not cd['DELETE']:
                gcd_official_count += 1
        if gcd_official_count != 1:
            raise forms.ValidationError(
              "Exactly one name needs to selected as the gcd_official_name.")


FeatureRevisionFormSet = inlineformset_factory(
    FeatureRevision, FeatureNameDetailRevision,
    form=FeatureNameDetailRevisionForm, can_delete=True, extra=1,
    formset=FeatureInlineFormSet)


class FeatureRevisionForm(CharacterBaseForm):
    class Meta:
        model = FeatureRevision
        fields = model._base_field_list

    def __init__(self, *args, **kwargs):
        super(FeatureRevisionForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-md-3 create-label'
        self.helper.field_class = 'col-md-9'
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        fields = list(self.fields)
        genres = fields.index('genre')

        field_list = [BaseField(Field('additional_names_help',
                                      template='oi/bits/uni_field.html'))]
        field_list.append(Formset('feature_names_formset'))
        field_list.extend(BaseField(Field(field,
                                    template='oi/bits/uni_field.html'))
                          for field in fields[:genres])
        field_list.append(HTML(
          '<tr class="mb-2"><th>Selected Genre:</th>'
          '<td id="selected-genres"></td></tr>'))
        description_pos = fields.index('description')

        field_list.extend([BaseField(Field(field,
                                           template='oi/bits/uni_field.html'))
                           for field in fields[genres:description_pos]])
        field_list.append(Formset('external_link_formset'))
        field_list.extend([BaseField(Field(field,
                                           template='oi/bits/uni_field.html'))
                           for field in fields[description_pos:-1]])
        self.helper.layout = Layout(*(f for f in field_list))
        self.helper.doc_links = FEATURE_HELP_LINKS

    additional_names_help = forms.CharField(
        widget=HiddenInputWithHelp,
        required=False,
        help_text="Multiple significantly distinct names for the feature can "
                  "be entered, where the feature fundamentally remains "
                  "unchanged under the different names. One name is marked "
                  "as the official name.",
        label='')

    def clean(self):
        cd = self.cleaned_data
        if cd['genre']:
            if len(cd['genre']) == 1:
                genres = cd['genre'][0]
            else:
                genre_dict = {}
                for genre in cd['genre']:
                    genre = genre.strip()
                    if genre in GENRES['en']:
                        genre_dict[GENRES['en'].index(genre)] = genre
                    else:
                        genre_dict[-1] = genre
                genres = ''
                for order in sorted(genre_dict):
                    genres += genre_dict[order] + '; '
                genres = genres[:-2]
            cd['genre'] = genres
        else:
            cd['genre'] = ''

        if 'name' in cd:
            cd['name'] = cd['name'].strip()
            if (cd['leading_article'] and
                    cd['name'] == remove_leading_article(cd['name'])):
                raise forms.ValidationError(
                    'The name is only one word, you cannot specify '
                    'a leading article in this case.')
        return cd


def get_feature_logo_revision_form(revision=None, user=None):
    class RuntimeFeatureLogoRevisionForm(FeatureLogoRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeFeatureLogoRevisionForm,
                  self).__init__(*args, **kwargs)

            if revision and (revision.image_revision or (revision.source and
                             revision.source.logo)):
                self.fields['feature_logo_image'].help_text = \
                  'Select a file if you want to replace the existing image.'
                self.fields['generic'] = forms.BooleanField(widget=HiddenInput,
                                                            required=False)

        if revision and revision.source:
            if revision.source.generic:
                feature_logo_image = forms.ImageField(widget=HiddenInput,
                                                      required=False)
                generic = forms.BooleanField(widget=HiddenInput,
                                             required=False)

        def save(self, commit=True):
            instance = super(RuntimeFeatureLogoRevisionForm,
                             self).save(commit=commit)
            if instance.image_revision and revision:
                if revision.source:
                    image = revision.feature_logo.logo
                else:
                    image = None
                instance = _save_runtime_embedded_image_revision(instance,
                                                                 revision,
                                                                 image)
            return instance

        def clean(self):
            cd = self.cleaned_data

            if cd['generic'] and cd['feature_logo_image']:
                raise forms.ValidationError(
                  'Either mark the feature logo as generic or upload an '
                  'image, not both.')
            if cd['generic'] and revision and revision.image_revision:
                raise forms.ValidationError(
                  'Feature logo image exists, cannot mark the feature logo '
                  'as generic.')
            if self._errors:
                raise forms.ValidationError(GENERIC_ERROR_MESSAGE)

        def as_table(self):
            # if not user or user.indexer.show_wiki_links:
            #     _set_help_labels(self, AWARD_HELP_LINKS)
            return super(FeatureLogoRevisionForm, self).as_table()

    return RuntimeFeatureLogoRevisionForm


class FeatureLogoRevisionForm(forms.ModelForm):
    class Meta:
        model = FeatureLogoRevision
        fields = model._base_field_list

    def __init__(self, *args, **kwargs):
        super(FeatureLogoRevisionForm, self).__init__(*args, **kwargs)
        ordering = list(self.fields)
        ordering.insert(3, 'feature_logo_image')
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields

    feature_name = forms.ModelMultipleChoiceField(
        queryset=FeatureNameDetail.objects.filter(deleted=False),
        widget=autocomplete.ModelSelect2Multiple(
          url='feature_name_autocomplete')
    )
    generic = forms.BooleanField(
        required=False,
        help_text="A generic feature logo is used to record the printed name "
                  "of a feature as presented on the story, without recording "
                  "a specific visual appearance of the name."
    )

    feature_logo_image = forms.ImageField(widget=forms.FileInput,
                                          required=False)

    comments = _get_comments_form_field()

    def save(self, commit=True):
        instance = super(FeatureLogoRevisionForm, self).save(commit=commit)
        feature_logo_image = self.cleaned_data['feature_logo_image']
        if feature_logo_image:
            instance = _create_embedded_image_revision(instance,
                                                       feature_logo_image,
                                                       'FeatureLogo')
        return instance

    def clean_feature(self):
        languages = self.cleaned_data['feature'].values('language')
        if languages.count() != languages.distinct().count():
            raise forms.ValidationError(
                'Only one feature can be assigned per language.')
        return self.cleaned_data['feature']

    def clean_feature_name(self):
        languages = self.cleaned_data['feature_name']\
                        .values('feature__language')
        if languages.count() != languages.distinct().count():
            raise forms.ValidationError(
                'Only one feature can be assigned per language.')
        return self.cleaned_data['feature_name']

    def clean(self):
        cd = self.cleaned_data

        if 'name' in cd:
            cd['name'] = cd['name'].strip()
            if (cd['leading_article'] and
                    cd['name'] == remove_leading_article(cd['name'])):
                raise forms.ValidationError(
                    'The feature name is only one word, you cannot specify '
                    'a leading article in this case.')
        return cd


def get_feature_relation_revision_form(revision=None, user=None):
    class RuntimeFeatureRelationRevisionForm(FeatureRelationRevisionForm):
        choices = list(FeatureRelationType.objects.values_list('id',
                                                               'description'))
        additional_choices = FeatureRelationType.objects.values_list(
                             'id', 'reverse_description')
        choices = combine_reverse_relations(choices, additional_choices)
        relation_type = forms.ChoiceField(choices=choices)

        def as_table(self):
            # if not user or user.indexer.show_wiki_links:
            #     _set_help_labels(self, CREATOR_RELATION_HELP_LINKS)
            return super(FeatureRelationRevisionForm, self).as_table()

    return RuntimeFeatureRelationRevisionForm


class FeatureRelationRevisionForm(forms.ModelForm):
    class Meta:
        model = FeatureRelationRevision
        fields = model._base_field_list
        # help_texts = FEATURE_RELATION_HELP_TEXTS
        labels = {'from_feature': 'Feature A', 'relation_type': 'Relation',
                  'to_feature': 'Feature B'}

    from_feature = forms.ModelChoiceField(
        queryset=Feature.objects.filter(deleted=False),
        widget=autocomplete.ModelSelect2(url='feature_autocomplete',
                                         attrs={'style': 'min-width: 45em'})
    )

    to_feature = forms.ModelChoiceField(
        queryset=Feature.objects.filter(deleted=False),
        widget=autocomplete.ModelSelect2(url='feature_autocomplete',
                                         attrs={'style': 'min-width: 45em'})
    )

    comments = _get_comments_form_field()

    def clean(self):
        cd = self.cleaned_data
        type = int(cd['relation_type'])
        if type < 0:
            stash = cd['from_feature']
            cd['from_feature'] = cd['to_feature']
            cd['to_feature'] = stash
            cd['relation_type'] = FeatureRelationType.objects.get(id=-type)
        else:
            cd['relation_type'] = FeatureRelationType.objects.get(id=type)
        if 'from_feature' in cd and 'to_feature' in cd and \
           cd['from_feature'] == cd['to_feature']:
            raise forms.ValidationError(
              'Feature A and Feature B cannot be the same feature.')
        return cd
