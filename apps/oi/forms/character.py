# -*- coding: utf-8 -*-

from django import forms
from django.forms.models import inlineformset_factory

from collections import OrderedDict

from dal import autocomplete

from apps.gcd.models import Character, Group, CharacterRelationType

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field
from crispy_forms.utils import render_field
from .custom_layout_object import Formset

from apps.oi.models import (CharacterRevision, CharacterNameDetailRevision,
                            CharacterRelationRevision, GroupRevision,
                            GroupMembershipRevision, GroupRelationRevision)

from .support import (_get_comments_form_field, HiddenInputWithHelp,
                      GENERIC_ERROR_MESSAGE, BaseForm,
                      combine_reverse_relations)


class CharacterNameDetailRevisionForm(forms.ModelForm):
    class Meta:
        model = CharacterNameDetailRevision
        fields = model._base_field_list

    def __init__(self, *args, **kwargs):
        super(CharacterNameDetailRevisionForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.layout = Layout(*(f for f in self.fields))
        self.fields['sort_name'].help_text = "In the Western culture usually "\
                                             " 'family name, given name'."


class CharacterInlineFormSet(forms.BaseInlineFormSet):
    def _should_delete_form(self, form):
        # TODO workaround, better to not allow the removal, see above
        if form.instance.character_name_detail:
            if form.instance.character_name_detail.storycharacter_set\
                                                  .filter(deleted=False).count():
                form.cleaned_data['DELETE'] = False
                return False
        return super(CharacterInlineFormSet, self)._should_delete_form(form)

    def clean(self):
        super(CharacterInlineFormSet, self).clean()
        gcd_official_count = 0
        for form in self.forms:
            cd = form.cleaned_data
            if 'is_official_name' in cd and cd['is_official_name'] and \
               not cd['DELETE']:
                gcd_official_count += 1
        if gcd_official_count != 1:
            raise forms.ValidationError(
              "Exactly one name needs to selected as the gcd_official_name.")


CharacterRevisionFormSet = inlineformset_factory(
    CharacterRevision, CharacterNameDetailRevision,
    form=CharacterNameDetailRevisionForm, can_delete=True, extra=1,
    formset=CharacterInlineFormSet)


def get_character_revision_form(revision=None, user=None):
    class RuntimeCharacterRevisionForm(CharacterRevisionForm):
        def as_table(self):
            # if not user or user.indexer.show_wiki_links:
            # _set_help_labels(self, FEATURE_HELP_LINKS)
            return super(CharacterRevisionForm, self).as_table()

    return RuntimeCharacterRevisionForm


class BaseField(Field):
    def render(self, form, form_style, context, template_pack=None):
        fields = ''

        for field in self.fields:
            fields += render_field(field, form, form_style, context,
                                   template_pack=template_pack)
        return fields


class CharacterRevisionForm(BaseForm):
    class Meta:
        model = CharacterRevision
        fields = model._base_field_list

    def __init__(self, *args, **kwargs):
        super(CharacterRevisionForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-md-3 create-label'
        self.helper.field_class = 'col-md-9'
        self.helper.form_tag = False
        ordering = list(self.fields)
        # in django 1.9 there is Form.order_fields
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields
        fields = list(self.fields)
        field_list = [BaseField(Field('additional_names_help',
                                    template='oi/bits/uni_field.html'))]
        field_list.append(Formset('character_names_formset'))
        field_list.extend([BaseField(Field(field,
                                           template='oi/bits/uni_field.html'))
                           for field in fields])
        self.helper.layout = Layout(*(f for f in field_list))

    additional_names_help = forms.CharField(
        widget=HiddenInputWithHelp,
        required=False,
        help_text="Several names for the character can be entered "
                  "(for example a common name vs. a formal full name, "
                  "or a maiden vs. a married name). One name is marked "
                  "as the official name.",
        label='')


def get_group_revision_form(revision=None, user=None):
    class RuntimeGroupRevisionForm(GroupRevisionForm):
        def as_table(self):
            # if not user or user.indexer.show_wiki_links:
            # _set_help_labels(self, FEATURE_HELP_LINKS)
            return super(GroupRevisionForm, self).as_table()

    return RuntimeGroupRevisionForm


class GroupRevisionForm(CharacterRevisionForm):
    class Meta:
        model = GroupRevision
        fields = model._base_field_list


def get_group_membership_revision_form(revision=None, user=None):
    if revision is not None:
        code = revision.character.language.code
    else:
        code = None

    class RuntimeGroupMembershipRevisionForm(GroupMembershipRevisionForm):
        language_code = forms.CharField(widget=forms.HiddenInput,
                                        initial=code)

        def as_table(self):
            # if not user or user.indexer.show_wiki_links:
            #     _set_help_labels(self, CREATOR_MEMBERSHIP_HELP_LINKS)
            return super(GroupMembershipRevisionForm, self).as_table()

    return RuntimeGroupMembershipRevisionForm


class GroupMembershipRevisionForm(forms.ModelForm):
    class Meta:
        model = GroupMembershipRevision
        fields = model._base_field_list
        # help_texts = CREATOR_MEMBERSHIP_HELP_TEXTS

    comments = _get_comments_form_field()

    character = forms.ModelChoiceField(
        queryset=Character.objects.filter(deleted=False),
        widget=autocomplete.ModelSelect2(url='character_autocomplete',
                                         forward=['language_code'],
                                         attrs={'style': 'min-width: 45em'}),
    )

    group = forms.ModelChoiceField(
        queryset=Group.objects.filter(deleted=False),
        widget=autocomplete.ModelSelect2(url='group_autocomplete',
                                         forward=['language_code'],
                                         attrs={'style': 'min-width: 45em'}),
    )

    def clean(self):
        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)


def get_character_relation_revision_form(revision=None, user=None):
    class RuntimeCharacterRelationRevisionForm(CharacterRelationRevisionForm):
        def as_table(self):
            # if not user or user.indexer.show_wiki_links:
            # _set_help_labels(self, CREATOR_RELATION_HELP_LINKS)
            return super(CharacterRelationRevisionForm, self).as_table()

    return RuntimeCharacterRelationRevisionForm


class CharacterRelationRevisionForm(forms.ModelForm):
    class Meta:
        model = CharacterRelationRevision
        fields = model._base_field_list
        # help_texts = FEATURE_RELATION_HELP_TEXTS
        labels = {'relation_type': 'Relation', }

    from_character = forms.ModelChoiceField(
        queryset=Character.objects.filter(deleted=False),
        widget=autocomplete.ModelSelect2(url='character_autocomplete',
                                         attrs={'style': 'min-width: 45em'}),
        label='Character A'
    )

    choices = list(CharacterRelationType.objects.values_list('id', 'type'))
    additional_choices = CharacterRelationType.objects.exclude(id__in=[3, 4])\
                                              .values_list('id',
                                                           'reverse_type')
    choices = combine_reverse_relations(choices, additional_choices)
    relation_type = forms.ChoiceField(choices=choices)

    to_character = forms.ModelChoiceField(
        queryset=Character.objects.filter(deleted=False),
        widget=autocomplete.ModelSelect2(url='character_autocomplete',
                                         attrs={'style': 'min-width: 45em'}),
        label='Character B'
    )

    comments = _get_comments_form_field()

    def clean(self):
        cd = self.cleaned_data
        type = int(cd['relation_type'])
        if type < 0:
            stash = cd['from_character']
            cd['from_character'] = cd['to_character']
            cd['to_character'] = stash
            cd['relation_type'] = CharacterRelationType.objects.get(id=-type)
        else:
            cd['relation_type'] = CharacterRelationType.objects.get(id=type)
        return cd


def get_group_relation_revision_form(revision=None, user=None):
    class RuntimeGroupRelationRevisionForm(GroupRelationRevisionForm):
        def as_table(self):
            # if not user or user.indexer.show_wiki_links:
            # _set_help_labels(self, CREATOR_RELATION_HELP_LINKS)
            return super(GroupRelationRevisionForm, self).as_table()

    return RuntimeGroupRelationRevisionForm


class GroupRelationRevisionForm(forms.ModelForm):
    class Meta:
        model = GroupRelationRevision
        fields = model._base_field_list
        # help_texts = FEATURE_RELATION_HELP_TEXTS
        labels = {'relation_type': 'Relation', }

    from_group = forms.ModelChoiceField(
        queryset=Group.objects.filter(deleted=False),
        widget=autocomplete.ModelSelect2(url='group_autocomplete',
                                         attrs={'style': 'min-width: 45em'}),
        label='Group A'
    )

    to_group = forms.ModelChoiceField(
        queryset=Group.objects.filter(deleted=False),
        widget=autocomplete.ModelSelect2(url='group_autocomplete',
                                         attrs={'style': 'min-width: 45em'}),
        label='Group B'
    )

    comments = _get_comments_form_field()
