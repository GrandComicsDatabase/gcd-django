# -*- coding: utf-8 -*-

from django import forms
from django.forms.models import inlineformset_factory

from collections import OrderedDict

from dal import autocomplete

from apps.gcd.models import Character, Group, CharacterRelationType, \
                            GroupRelationType, Universe

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field
from .custom_layout_object import Formset, BaseField

from apps.oi.models import (CharacterRevision, CharacterNameDetailRevision,
                            CharacterRelationRevision, GroupRevision,
                            GroupNameDetailRevision,
                            GroupMembershipRevision, GroupRelationRevision,
                            UniverseRevision)

from .support import (_get_comments_form_field, HiddenInputWithHelp,
                      GENERIC_ERROR_MESSAGE, CharacterBaseForm,
                      combine_reverse_relations, CHARACTER_HELP_LINKS)


def get_universe_revision_form(revision=None, user=None):
    class RuntimeUniverseRevisionForm(UniverseRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeUniverseRevisionForm, self).__init__(*args, **kwargs)

    return RuntimeUniverseRevisionForm


class UniverseRevisionForm(CharacterBaseForm):
    class Meta:
        model = UniverseRevision
        fields = model._base_field_list
        help_texts = {
            'multiverse':
                'The name of the multiverse the universe belongs to, '
                'e.g. DC or Marvel.',
            'name':
                'A description or common name for the universe, '
                'e.g. mainstream, Ultimate, Absolute, MC2',
            'designation':
                'The designation of the universe, e.g. Earth-1610, '
                'Earth 1, Earth-982'
        }

    def clean(self):
        cd = self.cleaned_data
        if not cd['name'] and not cd['designation']:
            raise forms.ValidationError(
              ['Either a name or a designation needs to be entered']
            )

        return cd


class CharacterNameDetailRevisionForm(forms.ModelForm):
    class Meta:
        model = CharacterNameDetailRevision
        fields = model._base_field_list
        widgets = {
            'name': forms.TextInput(attrs={'autofocus': ''}),
            }

    def __init__(self, *args, **kwargs):
        super(CharacterNameDetailRevisionForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.layout = Layout(*(f for f in self.fields))
        self.fields['sort_name'].help_text = "In the Western culture usually "\
                                             " 'family name, given name'."

        if self.instance.character_name_detail:
            if self.instance.character_name_detail.storycharacter_set\
                                                  .filter(deleted=False)\
                                                  .count():
                # TODO How can the 'remove'-link not be shown in this case ?
                self.fields['name'].help_text = \
                    'Character names with existing credits cannot be removed.'


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


class CharacterRevisionForm(CharacterBaseForm):
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
        description_pos = fields.index('description')
        field_list.extend([BaseField(Field(field,
                                           template='oi/bits/uni_field.html'))
                           for field in fields[:description_pos]])
        field_list.append(Formset('external_link_formset'))
        field_list.extend([BaseField(Field(field,
                                           template='oi/bits/uni_field.html'))
                           for field in fields[description_pos:-1]])
        self.helper.layout = Layout(*(f for f in field_list))
        self.helper.doc_links = CHARACTER_HELP_LINKS

    additional_names_help = forms.CharField(
        widget=HiddenInputWithHelp,
        required=False,
        help_text="Several names for the character can be entered "
                  "(for example a common name vs. a formal full name, "
                  "or a maiden vs. a married name). One name is marked "
                  "as the official name.",
        label='')

    universe = forms.ModelChoiceField(
      queryset=Universe.objects.all(),
      widget=autocomplete.ModelSelect2(
                          url='universe_autocomplete',
                          attrs={'class': 'w-full lg:w-4/5', }),
      required=False,
      help_text='Select the universe, if any, from which the character '
                'originates.'
    )


class GroupNameDetailRevisionForm(forms.ModelForm):
    class Meta:
        model = GroupNameDetailRevision
        fields = model._base_field_list


class GroupInlineFormSet(forms.BaseInlineFormSet):
    def _should_delete_form(self, form):
        # TODO workaround, better to not allow the removal, see above
        if form.instance.group_name_detail:
            if form.instance.group_name_detail.storygroup_set\
                            .filter(deleted=False).count():
                form.cleaned_data['DELETE'] = False
                return False
        return super(GroupInlineFormSet, self)._should_delete_form(form)

    def clean(self):
        super(GroupInlineFormSet, self).clean()
        gcd_official_count = 0
        for form in self.forms:
            cd = form.cleaned_data
            if 'is_official_name' in cd and cd['is_official_name'] and \
               not cd['DELETE']:
                gcd_official_count += 1
        if gcd_official_count != 1:
            raise forms.ValidationError(
              "Exactly one name needs to selected as the gcd_official_name.")


GroupRevisionFormSet = inlineformset_factory(
    GroupRevision, GroupNameDetailRevision,
    form=GroupNameDetailRevisionForm, can_delete=True, extra=1,
    formset=GroupInlineFormSet)


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

    def __init__(self, *args, **kwargs):
        super(GroupRevisionForm, self).__init__(*args, **kwargs)

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
        field_list.append(Formset('group_names_formset'))
        field_list.extend([BaseField(Field(field,
                                           template='oi/bits/uni_field.html'))
                           for field in fields[:-1]])
        self.helper.layout = Layout(*(f for f in field_list))

    additional_names_help = forms.CharField(
        widget=HiddenInputWithHelp,
        required=False,
        help_text="Several names for the group can be entered "
                  "(for example a common name vs. a formal name, "
                  "or different translations). One name is marked "
                  "as the official name.",
        label='')


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
    if revision is not None:
        code = revision.from_character.language.code
    else:
        code = None

    class RuntimeCharacterRelationRevisionForm(CharacterRelationRevisionForm):
        language_code = forms.CharField(widget=forms.HiddenInput,
                                        initial=code)
        choices = list(CharacterRelationType.objects.values_list('id', 'type'))
        additional_choices = CharacterRelationType.objects.exclude(id__in=[3,
                                                                           4])\
                                                  .values_list('id',
                                                               'reverse_type')
        choices = combine_reverse_relations(choices, additional_choices)
        relation_type = forms.ChoiceField(choices=choices)

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

    to_character = forms.ModelChoiceField(
        queryset=Character.objects.filter(deleted=False),
        widget=autocomplete.ModelSelect2(url='character_autocomplete',
                                         forward=['language_code',
                                                  'relation_type'],
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

        if cd['from_character'].language != cd['to_character'].language:
            if cd['relation_type'].id != 1:
                raise forms.ValidationError(
                  "Characters have a different language.")
        else:
            if cd['relation_type'].id == 1:
                raise forms.ValidationError(
                  "Characters have the same language.")
        return cd


def get_group_relation_revision_form(revision=None, user=None):
    if revision is not None:
        code = revision.from_group.language.code
    else:
        code = None

    class RuntimeGroupRelationRevisionForm(GroupRelationRevisionForm):
        language_code = forms.CharField(widget=forms.HiddenInput,
                                        initial=code)
        choices = list(GroupRelationType.objects.values_list('id', 'type'))
        additional_choices = GroupRelationType.objects.exclude(id=2)\
                                              .values_list('id',
                                                           'reverse_type')
        choices = combine_reverse_relations(choices, additional_choices)
        relation_type = forms.ChoiceField(choices=choices)

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
                                         forward=['language_code',
                                                  'relation_type'],
                                         attrs={'style': 'min-width: 45em'}),
        label='Group B'
    )

    comments = _get_comments_form_field()

    def clean(self):
        cd = self.cleaned_data

        type = int(cd['relation_type'])
        if type < 0:
            stash = cd['from_group']
            cd['from_group'] = cd['to_group']
            cd['to_group'] = stash
            cd['relation_type'] = GroupRelationType.objects.get(id=-type)
        else:
            cd['relation_type'] = GroupRelationType.objects.get(id=type)

        if cd['from_group'].language != cd['to_group'].language:
            if cd['relation_type'].id != 1:
                raise forms.ValidationError(
                  "Groups have a different language.")
        else:
            if cd['relation_type'].id == 1:
                raise forms.ValidationError(
                  "Groups have the same language.")
        return cd
