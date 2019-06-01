# -*- coding: utf-8 -*-

from collections import OrderedDict
from django import forms

from apps.gcd.models.support import GENRES

from apps.oi.models import FeatureRevision, FeatureLogoRevision

from .support import (GENERIC_ERROR_MESSAGE, #FEATURE_HELP_LINKS,
                      _set_help_labels, _clean_keywords,
                      _get_comments_form_field, init_data_source_fields,
                      insert_data_source_fields, HiddenInputWithHelp)
from .story import _genre_choices


def get_feature_revision_form(revision=None, user=None):
    class RuntimeFeatureRevisionForm(FeatureRevisionForm):
        language = None
        if revision is not None:
            if revision.language:
                language = revision.language
            if revision.genre:
                selected_genres = []
                genres = revision.genre.split(';')
                for genre in genres:
                    genre = genre.strip().lower()
                    if genre not in GENRES['en']:
                        additional_genres.append(genre)
                    selected_genres.append(genre)
                revision.genre = selected_genres

        genre = _genre_choices(language=language) 
        def as_table(self):
            #if not user or user.indexer.show_wiki_links:
                #_set_help_labels(self, AWARD_HELP_LINKS)
            return super(FeatureRevisionForm, self).as_table()

    return RuntimeFeatureRevisionForm


class FeatureRevisionForm(forms.ModelForm):
    class Meta:
        model = FeatureRevision
        fields = model._base_field_list

    comments = _get_comments_form_field()

    def clean_keywords(self):
        return _clean_keywords(self.cleaned_data)

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
            cd['genre'] = u''


def get_feature_logo_revision_form(revision=None, user=None):
    class RuntimeFeatureRevisionForm(FeatureLogoRevisionForm):
        def as_table(self):
            #if not user or user.indexer.show_wiki_links:
                #_set_help_labels(self, AWARD_HELP_LINKS)
            return super(FeatureLogoRevisionForm, self).as_table()

    return RuntimeFeatureRevisionForm


class FeatureLogoRevisionForm(forms.ModelForm):
    class Meta:
        model = FeatureLogoRevision
        fields = model._base_field_list

    comments = _get_comments_form_field()
