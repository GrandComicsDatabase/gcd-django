# -*- coding: utf-8 -*-
from django import forms
from django.forms.widgets import HiddenInput

from dal import autocomplete

from collections import OrderedDict

from apps.gcd.models import Feature, FeatureRelationType
from apps.gcd.models.support import GENRES

from apps.oi.models import (FeatureRevision, FeatureLogoRevision, FeatureType,
                            FeatureRelationRevision, remove_leading_article)

from .support import (_set_help_labels, _clean_keywords, KeywordBaseForm,
                      _get_comments_form_field, combine_reverse_relations,
                      GENERIC_ERROR_MESSAGE, _create_embedded_image_revision,
                      _save_runtime_embedded_image_revision)
from .story import _genre_choices


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

        def as_table(self):
            # if not user or user.indexer.show_wiki_links:
            #       _set_help_labels(self, FEATURE_HELP_LINKS)
            return super(FeatureRevisionForm, self).as_table()

    return RuntimeFeatureRevisionForm


class FeatureRevisionForm(KeywordBaseForm):
    class Meta:
        model = FeatureRevision
        fields = model._base_field_list

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
                    'The series name is only one word, you cannot specify '
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

    feature = forms.ModelMultipleChoiceField(
        queryset=Feature.objects.filter(deleted=False),
        widget=autocomplete.ModelSelect2Multiple(url='feature_autocomplete')
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
        additional_choices = FeatureRelationType.objects\
                                                .values_list('id',
                                                             'reverse_description')
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
                  'to_creator': 'Feature B'}

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
        return cd
