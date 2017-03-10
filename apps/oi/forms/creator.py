# -*- coding: utf-8 -*-

from django import forms

from apps.oi.models import CreatorRevision, CreatorMembershipRevision, \
                            CreatorAwardRevision, CreatorArtInfluenceRevision, \
                            CreatorNonComicWorkRevision

from .support import (GENERIC_ERROR_MESSAGE, ISSUE_HELP_LINKS,
                      VARIANT_NAME_HELP_TEXT, ISSUE_LABELS, ISSUE_HELP_TEXTS,
                      _set_help_labels, _init_no_isbn, _init_no_barcode,
                      _get_comments_form_field, _clean_keywords,
                      HiddenInputWithHelp, PageCountInput, BrandEmblemSelect)

class CreatorRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorRevision
        exclude = ['gcd_official_name','changeset', 'creator', 'deleted', 'schools', 'degrees']

    comments = _get_comments_form_field()


class CreatorMembershipRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorMembershipRevision
        exclude = ['creator','creator_membership','changeset', 'deleted',]

    comments = _get_comments_form_field()


class CreatorAwardRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorAwardRevision
        exclude = ['creator','creator_award','changeset', 'deleted',]

    comments = _get_comments_form_field()


class CreatorArtInfluenceRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorArtInfluenceRevision
        exclude = ['creator','creator_artinfluence','changeset', 'deleted',]

    comments = _get_comments_form_field()


class CreatorNonComicWorkRevisionForm(forms.ModelForm):
    class Meta:
        model = CreatorNonComicWorkRevision
        exclude = ['creator','creator_noncomicwork','changeset', 'deleted',]

    comments = _get_comments_form_field()