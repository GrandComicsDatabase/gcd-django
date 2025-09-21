# -*- coding: utf-8 -*-

from django import forms
from django.conf import settings
from django.forms.models import inlineformset_factory

from dal import autocomplete, forward

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, HTML
from crispy_forms.utils import render_field
from crispy_forms.bootstrap import (
    Tab,
    TabHolder,
)
from markdownx.widgets import MarkdownxWidget

from apps.oi.models import (
    get_reprint_field_list, get_story_field_list, remove_leading_article,
    BiblioEntryRevision, ReprintRevision, StoryRevision, StoryArcRevision,
    StoryArcRelationRevision, StoryCreditRevision, StoryCharacterRevision,
    StoryGroupRevision)


from apps.gcd.models import CreatorNameDetail, CreatorSignature, StoryType, \
                            Feature, FeatureLogo, CharacterNameDetail, \
                            GroupNameDetail, CharacterRole, StoryArc, \
                            StoryArcRelationType, Universe, \
                            STORY_TYPES, NON_OPTIONAL_TYPES, \
                            OLD_TYPES, CREDIT_TYPES, INDEXED
from apps.gcd.models.support import GENRES
from apps.gcd.models.story import NO_FEATURE_TYPES, NO_GENRE_TYPES

from .custom_layout_object import Formset
from .support import (
    _get_comments_form_field, _set_help_labels, _clean_keywords,
    combine_reverse_relations, GENERIC_ERROR_MESSAGE, NO_CREATOR_CREDIT_HELP,
    KEYWORDS_HELP, BaseForm, SEQUENCE_HELP_LINKS,
    BIBLIOGRAPHIC_ENTRY_HELP_LINKS, KeywordBaseForm,
    BIBLIOGRAPHIC_ENTRY_HELP_TEXT, HiddenInputWithHelp, PageCountInput)


def get_reprint_revision_form(revision=None, user=None):
    class RuntimeReprintRevisionForm(ReprintRevisionForm):
        def as_table(self):
            # TODO: Why is there commented-out code?
            # if not user or user.indexer.show_wiki_links:
            #   _set_help_labels(self, REPRINT_HELP_LINKS)
            return super(RuntimeReprintRevisionForm, self).as_table()
    return RuntimeReprintRevisionForm


class ReprintRevisionForm(forms.ModelForm):
    class Meta:
        model = ReprintRevision
        fields = get_reprint_field_list()


class GenreCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    option_template_name = 'forms/widgets/checkbox_option.html'


def _genre_choices(language=None, additional_genres=None):
    fantasy_id = GENRES['en'].index('fantasy')
    if language and language.code != 'en' and language.code in GENRES:
        choices = [[g, g + ' / ' + h]
                   for g, h in zip(GENRES['en'], GENRES[language.code])]
        choices[fantasy_id] = [
            'fantasy',
            ('fantasy-supernatural / %s' %
             GENRES[language.code][fantasy_id])
        ]
    else:
        choices = [[g, g] for g in GENRES['en']]
        choices[fantasy_id] = ['fantasy', 'fantasy-supernatural']
    if additional_genres:
        additional_genres.reverse()
        for genre in additional_genres:
            choices.insert(0, [genre, genre + ' (deprecated)'])
    return forms.MultipleChoiceField(
        required=False,
        widget=GenreCheckboxSelectMultiple(attrs={
          'class': 'overflow-y-auto max-h-60 border border-gray-500 '
                   'px-1 inline-block'}),
        choices=choices)


def get_story_revision_form(revision=None, user=None,
                            issue_revision=None):
    extra = {}
    additional_genres = []
    selected_genres = []
    current_type_not_allowed_id = None
    # either there is a revision (editing a sequence) or
    # an issue_revision (adding a sequence)
    if revision is not None:
        changeset = revision.changeset
        # Don't allow blanking out the type field.  However, when its a
        # new story make indexers consciously choose a type by allowing
        # an empty initial value.  So only set None if there is an existing
        # story revision.
        extra['empty_label'] = None
        if revision.issue:
            issue = revision.issue
        else:
            # stories for variants in variant-add next to issue have issue
            if getattr(revision.my_issue_revision, 'other_issue_revision'):
                issue = revision.my_issue_revision.other_issue_revision.issue
            else:
                issue = revision.my_issue_revision.variant_of
        series = issue.series
        if revision.genre:
            genres = revision.genre.split(';')
            for genre in genres:
                genre = genre.strip().lower()
                if genre not in GENRES['en']:
                    additional_genres.append(genre)
                selected_genres.append(genre)
            revision.genre = selected_genres
    else:
        issue = issue_revision.issue
        series = issue_revision.series
        changeset = issue_revision.changeset
    is_comics_publication = series.is_comics_publication
    has_about_comics = series.has_about_comics
    language = series.language

    # for variants we can only have cover sequences (for now)
    if (revision and (revision.issue is None or revision.issue.variant_of))\
       or (revision is None and issue_revision.issue is None):
        queryset = StoryType.objects.filter(name='cover')
        # an added story can have a different type, do not overwrite
        if revision and revision.type not in queryset:
            current_type_not_allowed_id = revision.type.id
            queryset = queryset | StoryType.objects.filter(id=revision.type.id)
    elif not is_comics_publication:
        sequence_filter = ['comic story', 'photo story', 'cartoon',
                           'cover reprint (on interior page)',
                           'comics-form advertising',
                           'preview (from the publisher)']
        if has_about_comics is True:
            sequence_filter.append('about comics')
            if issue.is_indexed == INDEXED['full']:
                sequence_filter.extend(['cover',
                                        'illustration'])
            elif issue.is_indexed == INDEXED['ten_percent']:
                sequence_filter.extend(['cover',])
        queryset = StoryType.objects.filter(name__in=sequence_filter)
        # an added story can have a different type, do not overwrite
        if revision and revision.type not in queryset:
            current_type_not_allowed_id = revision.type.id
            queryset = queryset | StoryType.objects.filter(id=revision.type.id)
    else:
        special_types = ['filler', ]
        if has_about_comics is False:
            special_types.append('about comics')
        special_types.extend([i for i in OLD_TYPES])
        queryset = StoryType.objects.all()
        if revision is None or (revision is not None and
                                revision.type.name not in special_types):
            queryset = queryset.exclude(name__in=special_types)
        else:
            queryset = queryset.exclude(name__in=OLD_TYPES)

    class RuntimeStoryRevisionForm(StoryRevisionForm):
        type = forms.ModelChoiceField(queryset=queryset, **extra)
        genre = _genre_choices(language=language,
                               additional_genres=additional_genres)
        language_code = forms.CharField(widget=forms.HiddenInput,
                                        initial=language.code)

        def __init__(self, *args, **kwargs):
            kwargs['user'] = user
            super(RuntimeStoryRevisionForm, self).__init__(*args, **kwargs)
            if revision and revision.feature != '':
                self.fields['feature'].label = \
                  '<btn class="btn-blue-editing inline">' \
                  '<input type="submit" name="save_migrate_feature"' \
                  ' value="Migrate"></btn></td> Feature'

        def save(self, commit=True):
            instance = super(RuntimeStoryRevisionForm,
                             self).save(commit=commit)
            if instance.id:
                self.save_characters(instance)
            return instance

        def save_characters(self, instance):
            appearing_characters = self.cleaned_data['appearing_characters']
            if self.cleaned_data['use_universe'] and \
               self.cleaned_data['universe'].count() == 1:
                universe = self.cleaned_data['universe'].get()
            else:
                universe = None
            if appearing_characters:
                additional_information = self.cleaned_data[
                  'appearing_characters_additional_information']
                if additional_information:
                    role = self.cleaned_data['appearing_characters_role']
                    flashback = self.cleaned_data[
                      'appearing_characters_flashback']
                    origin = self.cleaned_data['appearing_characters_origin']
                    death = self.cleaned_data['appearing_characters_death']
                    notes = self.cleaned_data['appearing_characters_notes']
                else:
                    role = None
                    flashback = False
                    origin = False
                    death = False
                    notes = ''
                for character in appearing_characters:
                    story_character = StoryCharacterRevision(
                      character=character,
                      universe=universe,
                      role=role,
                      is_flashback=flashback,
                      is_origin=origin,
                      is_death=death,
                      notes=notes,
                      story_revision=instance,
                      changeset=changeset)
                    story_character.save()
            group_name = self.cleaned_data['group_name']
            if group_name:
                group_members = self.cleaned_data['group_members']
                story_group = StoryGroupRevision(group_name=group_name,
                                                 universe=universe,
                                                 story_revision=instance,
                                                 changeset=changeset)
                story_group.save()
                additional_information = self.cleaned_data[
                  'group_members_additional_information']
                if additional_information:
                    role = self.cleaned_data['group_members_role']
                    flashback = self.cleaned_data['group_members_flashback']
                    origin = self.cleaned_data['group_members_origin']
                    death = self.cleaned_data['group_members_death']
                    notes = self.cleaned_data['group_members_notes']
                else:
                    role = None
                    flashback = False
                    origin = False
                    death = False
                    notes = ''
                for member in group_members:
                    story_character = StoryCharacterRevision(
                      character=member,
                      role=role,
                      is_flashback=flashback,
                      is_origin=origin,
                      is_death=death,
                      notes=notes,
                      universe=universe,
                      group_universe=universe,
                      story_revision=instance,
                      changeset=changeset)
                    story_character.save()
                    story_character.group_name.add(group_name)

        def clean_type(self):
            if queryset:
                type = self.cleaned_data['type']
                sequence_queryset = queryset.exclude(
                  id=current_type_not_allowed_id)
                if type not in sequence_queryset:
                    raise forms.ValidationError(
                      ['Sequence type not allowed for this issue or series.'])
            return type
    return RuntimeStoryRevisionForm


class StoryCreditRevisionForm(forms.ModelForm):
    class Meta:
        model = StoryCreditRevision
        fields = ['creator', 'credit_type', 'is_credited', 'credited_as',
                  'is_signed', 'signature', 'signed_as', 'uncertain',
                  'is_sourced', 'sourced_by', 'credit_name']
        help_texts = {
            'credit_type':
                'Selecting multi-credit entries such as <i>pencil and inks</i>'
                ', or <i>pencils, inks, and colors</i>, will after saving '
                'create credit entries for the different credit types. '
                'Selecting <i>painting</i> will add also a credit '
                'description.',
            'credit_name':
                'Enter here additional specifications for the credit, for '
                'example <i>finishes</i>, <i>flats</i>, or <i>pages 1-3</i>.',
            'is_credited':
                'Check in case the creator is credited. The credited name '
                'shall correspond to the selected name. You can also enter '
                'the credited name in the unfolded <i>credited as</i> field.',
            'credited_as':
                'You can enter here the credited name. If the entered text '
                'matches an existing name for the selected creator a database '
                'link will be generated on approval. '
                'Unusual or one-off credited names do not get a name record.',
            'is_signed':
                'Check in case the creator did sign.',
            'signed_as':
                'If the signature is not available you can enter a '
                'transcription of the text of the signature here, without any '
                'description of the visual, added years, etc. On approval'
                ' a generic textual signature will be auto-created. If '
                ' you want to record the visuals of the signature, you first '
                'have to upload an image in a separate signature change.',
            'uncertain':
                'Check in case the credit is uncertain.',
            'is_sourced':
                'Check in case the entered credit has external sources.',
            'sourced_by':
                'A concise and clear description of the external source of '
                'the credit.'
        }
        labels = {'credit_name': 'Credit description'}
        widgets = {
            'sourced_by': forms.TextInput(attrs={'class': 'w-full lg:w-4/5'}),
        }

    def __init__(self, *args, **kwargs):
        super(StoryCreditRevisionForm, self).__init__(*args, **kwargs)
        # If we want to use the helper, need to change formset.html to
        # use crispy. Need to investigate the interplay with dynamic
        # formset if one does more than simple layout changes in the helper.
        # For example, 'add another' clears entries in the form, so one
        # would need IDs in it ?!
        # The helper is currently not used !
        self.helper = FormHelper()
        self.helper.form_tag = False
        # self.helper.disable_csrf = True
        self.formset_helper = StoryFormSetHelper()
        fields = list(self.fields)
        fields.append('id')
        field_list = [BaseField(Field(field,
                                      template='oi/bits/uni_field.html'))
                      for field in fields]
        self.helper.layout = Layout(*(f for f in field_list))
        if self.instance.id:
            self.fields['credit_type'].empty_label = None
            self.fields['credit_type'].help_text = ''

    creator = forms.ModelChoiceField(
      queryset=CreatorNameDetail.objects.all(),
      widget=autocomplete.ModelSelect2(url='creator_name_autocomplete',
                                       attrs={'class': 'w-full lg:w-4/5',
                                              'style': 'width: 80%'},
                                       ),
      required=True,
      help_text='By entering (any part of) a name select a creator from the'
                ' database. Search for the name of the ghosted creator for '
                'ghost work.',
      label='<button hx-get="/select/creator/by_detail/" type="button" '
            'hx-vals="js:{\'name_detail_id\': getSelectValue(event)}" '
            'hx-on="htmx:afterRequest: setSelectValue(event)" '
            'hx-swap="none" class="mx-0 btn-blue-editing inline">To Official'
            '</button> Creator'
    )

    signature = forms.ModelChoiceField(
      queryset=CreatorSignature.objects.all(),
      widget=autocomplete.ModelSelect2(url='creator_signature_autocomplete',
                                       attrs={'data-html': True,
                                              'class': 'w-full lg:w-4/5',
                                              'style': 'width: 80%'},
                                       forward=['creator']),
      help_text='Select an existing signature for the creator.',
      required=False,
    )

    def clean(self):
        cd = self.cleaned_data
        if cd['credited_as'] and not cd['is_credited']:
            cd['credited_as'] = ""

        if cd['credited_as'] and 'creator' not in cd:
            raise forms.ValidationError(
              ['Name entered in "credited as" without selecting creator.']
            )

        if cd['credited_as'] and cd['credited_as'] == cd['creator'].name:
            raise forms.ValidationError(
              ['Name entered as "credited as" is identical to the creator '
               'name.']
            )

        if cd['signed_as'] and not cd['is_signed']:
            cd['signed_as'] = ""

        if cd['signature'] and not cd['is_signed']:
            cd['signature'] = None

        if cd['signature'] and cd['signed_as']:
            raise forms.ValidationError(
              ['Either select a signature or enter a transcription of the '
               'text of the signature, but not both']
            )

        if cd['signature'] and 'creator' in cd:
            if cd['signature'].creator != cd['creator'].creator:
                raise forms.ValidationError(
                  ['Creator of selected signature differs from selected '
                   'creator.']
                )


class StoryFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_tag = False
        self.disable_csrf = True


StoryRevisionFormSet = inlineformset_factory(
    StoryRevision, StoryCreditRevision, form=StoryCreditRevisionForm,
    can_delete=True, extra=1)


class StoryCharacterRevisionForm(forms.ModelForm):
    class Meta:
        model = StoryCharacterRevision
        fields = ['character', 'additional_information', 'role', 'universe',
                  'group_name', 'group_universe',
                  'is_flashback', 'is_origin', 'is_death', 'notes']
        help_texts = {
            'role':
                'You can enter what role the character played in the story',
            'group_name':
                'Character is appearing as a member of these groups.',
        }
        labels = {'is_flashback': 'Flashback',
                  'is_origin': 'Origin',
                  'is_death': 'Death'}
        widgets = {
            'notes': forms.TextInput(attrs={'class': 'w-full lg:w-4/5'}),
        }

    def __init__(self, *args, **kwargs):
        super(StoryCharacterRevisionForm, self).__init__(*args, **kwargs)
        # The helper is currently not used !
        # See comments above for the StoryCreditRevisionForm
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.formset_helper = StoryFormSetHelper()
        fields = list(self.fields)
        fields.append('id')
        field_list = [BaseField(Field(field,
                                      template='oi/bits/uni_field.html'))
                      for field in fields]
        self.helper.layout = Layout(*(f for f in field_list))
        instance = kwargs.get('instance', None)
        if instance:
            if instance.role or instance.group_name.exists() or \
               instance.universe or \
               instance.is_flashback or instance.is_origin or \
               instance.is_death or instance.notes:
                self.fields['additional_information'].initial = True

    character = forms.ModelChoiceField(
      queryset=CharacterNameDetail.objects.all(),
      widget=autocomplete.ModelSelect2(url='character_name_autocomplete',
                                       forward=['language_code'],
                                       attrs={'class': 'w-full lg:w-4/5',
                                              'style': 'width: 80%'}),
      required=True,
      help_text='By entering (any part of) a name select a character from the'
                ' database.'
    )

    group_name = forms.ModelMultipleChoiceField(
      queryset=GroupNameDetail.objects.all(),
      widget=autocomplete.ModelSelect2Multiple(
        url='group_name_autocomplete',
        attrs={'data-html': True, 'class': 'w-full lg:w-4/5',
               'style': 'width: 80%'},
        forward=[forward.Field('character', 'character_name'),
                 'language_code']),
      help_text='Select a group the character is appearing as a member of.',
      required=False,
    )

    additional_information = forms.BooleanField(
      required=False,
      help_text='Click to enter role, group, flashback, origin, death, or '
                'notes.')

    universe = forms.ModelChoiceField(
      queryset=Universe.objects.all(),
      widget=autocomplete.ModelSelect2(
                          url='universe_autocomplete',
                          attrs={'class': 'w-full lg:w-4/5',
                                 'style': 'width: 80%'}),
      required=False,
      help_text='Select the universe, if any, from which the character '
                'originates. Use "mainstream" for the principal universe '
                'of a publisher.'
    )

    group_universe = forms.ModelChoiceField(
      queryset=Universe.objects.all(),
      widget=autocomplete.ModelSelect2(
                          url='universe_autocomplete',
                          attrs={'class': 'w-full lg:w-4/5',
                                 'style': 'width: 80%'}),
      required=False,
      help_text='Select the universe, if any, for the group of the character. '
                'If left empty, the value will default to the selected '
                'universe for the character.'
    )

    def clean(self):
        cd = self.cleaned_data
        if cd['group_universe'] and not cd['group_name']:
            raise forms.ValidationError(
              ['Cannot select a group universe without a group.'])


StoryCharacterRevisionFormSet = inlineformset_factory(
    StoryRevision, StoryCharacterRevision, form=StoryCharacterRevisionForm,
    can_delete=True, extra=1)


class StoryGroupRevisionForm(forms.ModelForm):
    class Meta:
        model = StoryCharacterRevision
        fields = ['group_name', 'universe', 'notes']
        widgets = {
            'notes': forms.TextInput(attrs={'class': 'w-full lg:w-4/5'}),
        }

    def __init__(self, *args, **kwargs):
        super(StoryGroupRevisionForm, self).__init__(*args, **kwargs)
        # The helper is currently not used !
        # See comments above for the StoryCreditRevisionForm
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.formset_helper = StoryFormSetHelper()
        fields = list(self.fields)
        fields.append('id')
        field_list = [BaseField(Field(field,
                                      template='oi/bits/uni_field.html'))
                      for field in fields]
        self.helper.layout = Layout(*(f for f in field_list))

    group_name = forms.ModelChoiceField(
      queryset=GroupNameDetail.objects.all(),
      widget=autocomplete.ModelSelect2(url='group_name_autocomplete',
                                       forward=['language_code'],
                                       attrs={'class': 'w-full lg:w-4/5',
                                              'style': 'width: 80%'}),
      required=True,
      help_text='By entering (any part of) a name select a group from the'
                ' database.'
    )

    universe = forms.ModelChoiceField(
      queryset=Universe.objects.all(),
      widget=autocomplete.ModelSelect2(
                          url='universe_autocomplete',
                          attrs={'class': 'w-full lg:w-4/5',
                                 'style': 'width: 80%'}),
      required=False,
      help_text='Select the universe, if any, from which the group '
                'originates. Use "mainstream" for the principal universe '
                'of a publisher.'
    )


StoryGroupRevisionFormSet = inlineformset_factory(
    StoryRevision, StoryGroupRevision, form=StoryGroupRevisionForm,
    can_delete=True, extra=1)


# check with crispy 2.0, why here and in custom_layout ?
class BaseField(Field):
    def render(self, form, context, renderer=None,
               template_pack=None):
        fields = ''
        for field in self.fields:
            fields += render_field(field, form, context,
                                   template_pack=template_pack)
        return fields


class StoryRevisionForm(KeywordBaseForm):
    class Meta:
        model = StoryRevision
        fields = get_story_field_list()
        sequence_type_list = ['script', 'pencils', 'inks', 'colors',
                              'letters', 'editing']
        sequence_type_list.reverse()
        for seq_type in sequence_type_list:
            fields.pop(fields.index('no_%s' % seq_type))
            fields.insert(fields.index('page_count_uncertain')+1,
                          'no_%s' % seq_type)

        fields.insert(fields.index('no_script'), 'no_creator_help')
        fields.insert(fields.index('script'), 'creator_help')
        fields.insert(fields.index('characters'), 'character_help')
        fields.insert(fields.index('characters'), 'universe')
        fields.insert(fields.index('characters'), 'use_universe')
        fields.insert(fields.index('characters'), 'appearing_characters')
        fields.insert(fields.index('characters'),
                      'appearing_characters_additional_information')
        fields.insert(fields.index('characters'), 'appearing_characters_role')
        fields.insert(fields.index('characters'),
                      'appearing_characters_flashback')
        fields.insert(fields.index('characters'),
                      'appearing_characters_origin')
        fields.insert(fields.index('characters'), 'appearing_characters_death')
        fields.insert(fields.index('characters'), 'appearing_characters_notes')
        fields.insert(fields.index('characters'), 'group_name')
        fields.insert(fields.index('group_name')+1, 'group_members')
        fields.insert(fields.index('characters'),
                      'group_members_additional_information')
        fields.insert(fields.index('characters'), 'group_members_role')
        fields.insert(fields.index('characters'), 'group_members_flashback')
        fields.insert(fields.index('characters'), 'group_members_origin')
        fields.insert(fields.index('characters'), 'group_members_death')
        fields.insert(fields.index('characters'), 'group_members_notes')
        fields.insert(fields.index('characters'), 'one_character_help')
        widgets = {
            'feature': forms.TextInput(attrs={'class': 'w-full lg:w-4/5'}),
        }
        help_texts = {
            'keywords':
                KEYWORDS_HELP,
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        super(StoryRevisionForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-md-3 create-label'
        self.helper.field_class = 'col-md-9'
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.fields['characters'].label = 'd) Characters'
        fields = list(self.fields)
        genres = fields.index('genre')
        field_list = [BaseField(Field(field,
                                      template='oi/bits/uni_field.html'))
                      for field in fields[:genres]]
        field_list.append(HTML(
          '<tr class="mb-2"><th>Selected Genre:</th>'
          '<td id="selected-genres"></td></tr>'))

        credits_start = fields.index('creator_help')
        # field_list = [BaseField(Field(field,
        #                               template='oi/bits/uni_field.html'))
        #               for field in fields[:credits_start-7]]
        field_list.extend([BaseField(Field(field,
                                     template='oi/bits/uni_field.html'))
                           for field in fields[genres:credits_start-7]])
        field_list.append(HTML(
          '<tr><th><hr style="height:2px; background-color:#000;">&nbsp;'
          '<strong>Creator Credits:</strong></th>'
          '<td class="align-top">'
          '<hr style="height:2px; background-color:#000;"></td></tr>'))
        field_list.extend([BaseField(Field(field,
                                     template='oi/bits/uni_field.html'))
                           for field in fields[credits_start-7:credits_start]])
        field_list.append(Formset('credits_formset'))
        credits_end = len(field_list)
        characters_start = fields.index('characters')
        field_list.extend([BaseField(Field(field,
                                           template='oi/bits/uni_field.html'))
                           for field in fields[credits_start:
                                               characters_start-19]])
        field_list.append(HTML(
          '<tr><th><hr style="height:2px; background-color:#000;">&nbsp;'
          '<strong>Characters:</strong></th>'
          '<td class="align-top">'
          '<hr style="height:2px; background-color:#000;"></td></tr>'))
        field_list.extend([BaseField(Field(field,
                                           template='oi/bits/uni_field.html'))
                           for field in fields[characters_start-19:
                                               characters_start-1]])
        field_list.append(HTML(
          '<tr><th><input type="submit" name="save_and_set_universe"'
          ' class="mx-0 btn-blue-editing inline"'
          ' value="Set Character Universe"></th>'
          '<td>Set the above universe for the characters below that '
          'do not already have an assigned universe.</td></tr>'))
        field_list.extend([BaseField(Field(field,
                                           template='oi/bits/uni_field.html'))
                           for field in fields[characters_start-1:
                                               characters_start]])
        field_list.append(Formset('characters_formset'))
        field_list.append(Field(fields[characters_start],
                                template='oi/bits/uni_field.html'))
        field_list.append(Formset('groups_formset'))
        characters_end = len(field_list)
        field_list.extend([BaseField(Field(field,
                                           template='oi/bits/uni_field.html'))
                           for field in fields[characters_start+1:]])
        # characters_end += 1
        if not user.indexer.use_tabs:
            self.helper.layout = Layout(*(f for f in field_list))
        else:
            self.helper.layout = Layout(TabHolder(
              Tab('Sequence Details',
                  *(f for f in field_list[:credits_start-6]),
                  *(f for f in field_list[characters_end:-2]),
                  template='oi/bits/tab.html',
                  ),
              Tab('Creator Credits',
                  *(f for f in field_list[credits_start-5:credits_end+7]),
                  template='oi/bits/tab.html',
                  ),
              Tab('Characters',
                  *(f for f in field_list[credits_end+8:characters_end]),
                  template='oi/bits/tab.html',
                  ),
              template='oi/bits/tab-bar.html',
            ),
              HTML('<table class="editing">'),
              *(f for f in field_list[-2:]),
              HTML('</table>'))
        self.helper.doc_links = SEQUENCE_HELP_LINKS
    # The sequence number can only be changed through the reorder form, but
    # for new stories we add it through the initial value of a hidden field.
    sequence_number = forms.IntegerField(widget=forms.HiddenInput)

    title = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'w-full lg:w-4/5',
                                      'autofocus': ''}),
        required=False,
        help_text='If no title can be determined from a story, our '
                  'documentation gives a list of possible choices.')
    title_inferred = forms.BooleanField(
        required=False, label='Unofficial title', help_text='')

    first_line = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'w-full lg:w-4/5',
                                      'autofocus': ''}),
        required=False,
        help_text='First line of text/dialogue in the first panel of the '
                  ' story, ignoring reoccurring blurbs or promotional text.')

    page_count = forms.DecimalField(widget=PageCountInput, required=False,
                                    max_digits=10, decimal_places=3)

    feature_object = forms.ModelMultipleChoiceField(
      queryset=Feature.objects.all(),
      widget=autocomplete.ModelSelect2Multiple(
                          url='feature_autocomplete',
                          forward=['language_code', 'type'],
                          attrs={'class': 'w-full lg:w-4/5'}),
      required=False,
      help_text='Only features for the series language can be selected. Enter '
                '"&lt;space&gt;[&lt;text&gt;" to search the disambiguation. '
                '[l] marks letter page features, [i] stands for in-house '
                'columns, [a] stands for ad features.'
     )

    feature_logo = forms.ModelMultipleChoiceField(
      queryset=FeatureLogo.objects.all(),
      widget=autocomplete.ModelSelect2Multiple(
                          url='feature_logo_autocomplete',
                          forward=['language_code', 'type'],
                          attrs={'data-html': True,
                                 'class': 'w-full lg:w-4/5'}),
      required=False,
      help_text='Only select a feature logo if it is present <b>directly</b> '
                'on the sequence. The feature corresponding to the selected '
                'feature logos will be added automatically.'
      )

    story_arc = forms.ModelMultipleChoiceField(
      queryset=StoryArc.objects.all(),
      widget=autocomplete.ModelSelect2Multiple(
                          url='story_arc_autocomplete',
                          forward=['language_code', 'type'],
                          attrs={'class': 'w-full lg:w-4/5'}),
      required=False,
      help_text='Only story arcs for the series language can be selected. '
                'Enter "&lt;space&gt;[&lt;text&gt;" to search the '
                'disambiguation.'
     )

    no_creator_help = forms.CharField(
      widget=HiddenInputWithHelp,
      required=False,
      help_text='For sequence types with non-optional fields the '
                'corresponding no-field is to be checked in case the type '
                'of credit does not apply.<br>If a credit field is not '
                'required for a sequence type it can be left unset or blank.',
      label='')

    creator_help = forms.CharField(
        widget=HiddenInputWithHelp,
        required=False,
        help_text='Text credits can be used for creators not currently in '
                  'the database or for special credit entries. Otherwise, '
                  'please use the above autocomplete to link to the creator '
                  'records. If needed, you can enter the relevant creator '
                  'credits in the following fields, where multiple credits '
                  'are separated by semi-colons.<br>If the credit applies to a'
                  ' sequence type, but the creator is unknown enter a question'
                  ' mark.<p>Existing text credits should be migrated, either '
                  'using the migrate button on the issue change overview page'
                  ' or by editing on this page.',
        label='')

    character_help = forms.CharField(
        widget=HiddenInputWithHelp,
        required=False,
        help_text='Characters can be entered in several ways:'
                  '<ul class="list-[lower-alpha] list-outside ps-4">'
                  '<li>select several characters in the first autocomplete '
                  '<i>Appearing characters</i>, each without additional '
                  'details about the appearance,</li>'
                  '<li>select a group in the second autocomplete <i>Group</i>'
                  ' with the appearing group members in the third autocomplete'
                  ' <i>Group members</i>, again '
                  'without additional details about the appearance,</li>'
                  '<li>each character (with its groups) separately, where '
                  'additional details about the appearance can be entered.'
                  '</li><li>the old text field for characters,</li></ul>'
                  'For a selected superhero the linked civilian identity will '
                  'be added automatically. In the later character display both'
                  ' are shown together as <i>Superhero [Civilian Name]</i>, '
                  'but they appear as two entries in this editing form. '
                  'You can also select an alternative civilian name, if '
                  'needed.<br>Note that data from a) and'
                  ' b) will appear in section c) after a save.',
        label='')

    one_character_help = forms.CharField(
        widget=HiddenInputWithHelp,
        required=False,
        label_suffix='',
        label='c)')

    universe = forms.ModelMultipleChoiceField(
      queryset=Universe.objects.all(),
      widget=autocomplete.ModelSelect2Multiple(
                          url='universe_autocomplete',
                          attrs={'class': 'w-full lg:w-4/5',
                                 'style': 'width: 80%'}),
      required=False,
      help_text='Select the universes, if any, in which the story takes place.'
                ' Use "mainstream" for the principal universe of a publisher.'
    )

    use_universe = forms.BooleanField(
        required=False,
        initial=True,
        help_text='The selected universe is the universe the characters and '
                  'groups entered under a) and b) originate from. '
                  'If more than one universe is selected above, this '
                  'flag has no effect.')

    script = forms.CharField(widget=forms.TextInput(attrs={'class':
                                                           'w-full lg:w-4/5'}),
                             required=False,
                             help_text='')
    pencils = forms.CharField(widget=forms.TextInput(attrs={
      'class': 'w-full lg:w-4/5'}),
                              required=False,
                              help_text='')
    inks = forms.CharField(widget=forms.TextInput(attrs={'class':
                                                         'w-full lg:w-4/5'}),
                           required=False,
                           help_text='')
    colors = forms.CharField(widget=forms.TextInput(attrs={'class':
                                                           'w-full lg:w-4/5'}),
                             required=False,
                             help_text='')
    letters = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'w-full lg:w-4/5'}),
        required=False,
        help_text='If the lettering is produced as normal printed text rather '
                  'than comic-style lettering, enter the word "typeset" here.')
    editing = forms.CharField(widget=forms.TextInput(attrs={
      'class': 'w-full lg:w-4/5'}),
                              required=False,
                              help_text='')

    no_script = forms.BooleanField(
        required=False,
        help_text=NO_CREATOR_CREDIT_HELP % (
            'script or plot',
            ', e.g. for a cover or single-page illustration,',
            'script'))
    no_pencils = forms.BooleanField(
        required=False,
        help_text=NO_CREATOR_CREDIT_HELP % (
            'pencils',
            ', e.g. for an unillustrated text article,',
            'pencils'))
    no_inks = forms.BooleanField(
        required=False,
        help_text=NO_CREATOR_CREDIT_HELP % (
            'inks',
            ', e.g. for a '
            'story colored straight from pencils,',
            'inks'))
    no_colors = forms.BooleanField(
        required=False,
        help_text=NO_CREATOR_CREDIT_HELP % (
            'colors',
            ', e.g. for '
            'a black-and-white comic,',
            'colors'))
    no_letters = forms.BooleanField(
        required=False,
        help_text=NO_CREATOR_CREDIT_HELP % ('letters', '', 'letters'))
    no_editing = forms.BooleanField(
        required=False,
        help_text='Check this box if there is no separate editor for this '
                  'sequence. This is common when there is an editor for the '
                  'whole issue.<br><br>'
                  'If a creator cannot be found in the creator box, '
                  'the corresponding credit field can also be used.')

    characters = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'w-full lg:w-4/5',
                                     'rows': 6}),
        required=False,
        )

    reprint_notes = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'w-full lg:w-4/5',
                                     'rows': 4}),
        required=False,
        help_text='Textual reprint notes can be used for comic material that '
                  'is not in our database, either because the issue is not '
                  'indexed at all or because it cannot such as newspaper '
                  'strips.<br>For newspaper strips the format is '
                  '<i>from &lt;comic strip&gt; (&lt;syndicate name&gt;) '
                  '&lt;date&gt;</i>, example:<br> '
                  '<i>from Calvin and Hobbes daily (Universal Press Syndicate)'
                  ' 1985-11-18 - 1988-10-01</i>.'

        )

    synopsis = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'w-full lg:w-4/5',
                                     'rows': 6}),
        required=False,
        help_text='A brief description of the contents. Do not use any text '
                  'that may be copyrighted, such as solicitation or other '
                  'promotional text.')

    group_name = forms.ModelChoiceField(
      queryset=GroupNameDetail.objects.all(),
      widget=autocomplete.ModelSelect2(
        url='group_name_autocomplete',
        attrs={'data-html': True, 'class': 'w-full lg:w-4/5',
               'style': 'width: 80%'},
        forward=['language_code']),
      help_text='Select a group and enter its characters.',
      label='b) Group',
      required=False,
    )

    group_members = forms.ModelMultipleChoiceField(
      queryset=CharacterNameDetail.objects.all(),
      widget=autocomplete.ModelSelect2Multiple(
        url='character_name_autocomplete',
        attrs={'data-html': True, 'class': 'w-full lg:w-4/5',
               'style': 'width: 80%'},
        forward=['language_code', 'group_name']),
      help_text='Select the appearing members of the group.',
      required=False,
    )

    appearing_characters = forms.ModelMultipleChoiceField(
      queryset=CharacterNameDetail.objects.all(),
      widget=autocomplete.ModelSelect2Multiple(
        url='character_name_autocomplete',
        attrs={'data-html': True, 'class': 'w-full lg:w-4/5',
               'style': 'width: 80%'},
        forward=['language_code', ]),
      help_text='Select one or more appearing characters without additional '
                'details.',
      label='a) Appearing characters',
      required=False,
    )

    appearing_characters_additional_information = forms.BooleanField(
      required=False,
      help_text='Click to enter role, flashback, origin, death, or '
                'notes for all appearing characters.')
    appearing_characters_role = forms.ModelChoiceField(
      queryset=CharacterRole.objects.all(),
      required=False)
    appearing_characters_flashback = forms.BooleanField(
        required=False)
    appearing_characters_origin = forms.BooleanField(
        required=False)
    appearing_characters_death = forms.BooleanField(
        required=False)
    appearing_characters_notes = forms.CharField(required=False)

    group_members_additional_information = forms.BooleanField(
      required=False,
      help_text='Click to enter role, flashback, origin, death, or '
                'notes for all group members.')
    group_members_role = forms.ModelChoiceField(
      queryset=CharacterRole.objects.all(),
      required=False)
    group_members_flashback = forms.BooleanField(
        required=False)
    group_members_origin = forms.BooleanField(
        required=False)
    group_members_death = forms.BooleanField(
        required=False)
    group_members_notes = forms.CharField(required=False)

    comments = _get_comments_form_field()

    def clean_keywords(self):
        return _clean_keywords(self.cleaned_data)

    def clean_genre(self):
        genre = self.cleaned_data['genre']
        if len(genre) > 10:
            raise forms.ValidationError(['Up to 10 genres can be selected.'])
        return genre

    def clean(self):
        cd = self.cleaned_data

        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)

        cd['title'] = cd['title'].strip()
        cd['feature'] = cd['feature'].strip()
        cd['script'] = cd['script'].strip()
        cd['pencils'] = cd['pencils'].strip()
        cd['inks'] = cd['inks'].strip()
        cd['colors'] = cd['colors'].strip()
        cd['letters'] = cd['letters'].strip()
        cd['editing'] = cd['editing'].strip()
        cd['characters'] = cd['characters'].strip()
        cd['job_number'] = cd['job_number'].strip()
        cd['reprint_notes'] = cd['reprint_notes'].strip()
        cd['synopsis'] = cd['synopsis'].strip()
        cd['notes'] = cd['notes'].strip()
        cd['comments'] = cd['comments'].strip()

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

        if cd['title_inferred'] and cd['title'] == "":
            raise forms.ValidationError(
                ['Empty titles cannot be unofficial.'])

        if cd['title'].startswith('[') and cd['title'].endswith(']'):
            raise forms.ValidationError(
                ['Do not use [] around unofficial story titles, check the '
                 'unofficial checkbox instead.'])

        if (cd['feature'] or cd['feature_object'] or cd['feature_logo']) and \
           cd['type'].id in NO_FEATURE_TYPES:
            raise forms.ValidationError(
                ['The sequence type cannot have a feature.'])

        if cd['story_arc'] and cd['type'].id != STORY_TYPES['comic story']:
            raise forms.ValidationError(
                ['The sequence type cannot have a story arc.'])

        if cd['genre'] and cd['type'].id in NO_GENRE_TYPES:
            raise forms.ValidationError(
                ['The sequence type cannot have a genre.'])

        if cd['feature'] and (cd['feature_object'] or cd['feature_logo']):
            raise forms.ValidationError(
                ['Either use the text feature field or the database objects.'])

        if cd['feature_object']:
            for feature in cd['feature_object']:
                if cd['type'].id == STORY_TYPES['letters_page']:
                    if not feature.feature_type.id == 2:
                        raise forms.ValidationError(
                          ['Select the correct feature for a letters page.'])
                elif cd['type'].id == STORY_TYPES['in-house column']:
                    if not feature.feature_type.id == 4:
                        raise forms.ValidationError(
                          ['Select the correct feature for an in-house '
                           'column.'])
                elif feature.feature_type.id == 3:
                    if not cd['type'].id in [STORY_TYPES['ad'],
                                             STORY_TYPES['comics-form ad']]:
                        raise forms.ValidationError(
                          ['Incorrect feature for this sequence.'])
                elif feature.feature_type.id in [2, 4]:
                    raise forms.ValidationError(
                      ['Incorrect feature for this sequence.'])

        if cd['feature_logo']:
            if cd['type'].id == STORY_TYPES['cover']:
                raise forms.ValidationError(
                  ['No feature logos for cover sequences.'])
            for feature_logo in cd['feature_logo']:
                if cd['type'].id == STORY_TYPES['letters_page']:
                    if not feature_logo.feature.filter(feature_type__id=2)\
                                               .count():
                        raise forms.ValidationError(
                          ['Select the correct feature logo for a '
                           'letters page.'])
                elif cd['type'].id == STORY_TYPES['in-house column']:
                    if not feature_logo.feature.filter(feature_type__id=4)\
                                               .count():
                        raise forms.ValidationError(
                          ['Select the correct feature logo for an '
                           'in-house column.'])
                elif feature_logo.feature.filter(feature_type__id=3).count():
                    if not cd['type'].id in [STORY_TYPES['ad'],
                                             STORY_TYPES['comics-form ad']]:
                        raise forms.ValidationError(
                          ['Incorrect feature logo for this sequence.'])
                elif feature_logo.feature.filter(feature_type_id__in=[2, 4])\
                                         .count():
                    raise forms.ValidationError(
                      ['Incorrect feature logo for this sequence.'])

        for seq_type in ['script', 'pencils', 'inks', 'colors', 'letters',
                         'editing']:
            nr_credit_forms = self.data['story_credit_revisions-TOTAL_FORMS']
            seq_type_found = False
            for i in range(int(nr_credit_forms)):
                delete_i = 'story_credit_revisions-%d-DELETE' % i
                form_deleted = False
                if delete_i in self.data:
                    if self.data[delete_i]:
                        form_deleted = True
                if not form_deleted and \
                   'story_credit_revisions-%d-credit_type' % i in self.data:
                    credit_type = \
                      self.data['story_credit_revisions-%d-credit_type' % i]
                    if credit_type == str(CREDIT_TYPES[seq_type]):
                        seq_type_found = True
                    elif seq_type == 'script' and credit_type in ['10', '11',
                                                                  '12', '13']:
                        seq_type_found = True
                    elif (seq_type in ['pencils', 'inks'] and
                          credit_type in ['7', '8', '9', '10',
                                          '11', '12', '13', '14']):
                        seq_type_found = True
                    elif seq_type == 'colors' and credit_type in ['8', '9',
                                                                  '11', '13']:
                        seq_type_found = True
                    elif seq_type == 'letters' and credit_type in ['12', '13',
                                                                   '14']:
                        seq_type_found = True

            if cd['type'].id in NON_OPTIONAL_TYPES:
                if not cd['no_%s' % seq_type] and cd[seq_type] == "" \
                   and not seq_type_found:
                    raise forms.ValidationError(
                        ['%s field or No %s checkbox must be filled in.' %
                         (seq_type.capitalize(), seq_type.capitalize())])

            if cd['no_%s' % seq_type] and (cd[seq_type] != "" or
                                           seq_type_found):
                raise forms.ValidationError(
                    ['%s field and No %s checkbox cannot both be filled in.' %
                     (seq_type.capitalize(), seq_type.capitalize())])

        synopsis_length = len(' '.join(cd['synopsis'].split()))
        if (synopsis_length > settings.LIMIT_SYNOPSIS_LENGTH and
                (self.instance is None or
                 self.instance.synopsis.strip() != cd['synopsis'])):

            raise forms.ValidationError(
                ['The synopsis field may not be longer than %d characters.' %
                 settings.LIMIT_SYNOPSIS_LENGTH])

        if (cd['page_count'] is None and not cd['page_count_uncertain'] and
                cd['type'].id != STORY_TYPES['insert']):
            raise forms.ValidationError(
                ['Page count uncertain must be checked if the page count '
                 'is not filled in.'])

        return cd


def get_biblio_revision_form(revision=None, user=None):
    class RuntimeBiblioRevisionForm(BiblioRevisionForm):
        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, BIBLIOGRAPHIC_ENTRY_HELP_LINKS)
            return super(BiblioRevisionForm, self).as_table()

    return RuntimeBiblioRevisionForm


class BiblioRevisionForm(forms.ModelForm):
    class Meta:
        model = BiblioEntryRevision
        fields = ['page_began', 'page_ended', 'abstract', 'doi']
        help_texts = BIBLIOGRAPHIC_ENTRY_HELP_TEXT

    doi = forms.CharField(widget=forms.TextInput(attrs={'class':
                                                        'w-full lg:w-4/5'}),
                          required=False, label='DOI',
                          help_text=BIBLIOGRAPHIC_ENTRY_HELP_TEXT['doi'])

    def clean(self):
        cd = self.cleaned_data

        if cd['page_ended'] and not cd['page_began']:
            raise forms.ValidationError(
              ["Page ended can only be entered with Page began."])
        elif cd['page_ended'] and cd['page_began']:
            if cd['page_ended'] < cd['page_began']:
                raise forms.ValidationError(
                  ["Page ended must be larger than Page began."])


def get_story_arc_revision_form(revision=None, user=None):
    class RuntimeStoryArcRevisionForm(StoryArcRevisionForm):
        pass

    return RuntimeStoryArcRevisionForm


class StoryArcRevisionForm(BaseForm):
    class Meta:
        model = StoryArcRevision
        fields = model._base_field_list

    description = forms.CharField(widget=MarkdownxWidget(
      attrs={'class': 'w-full lg:w-4/5', 'rows': 7}), required=False,
      help_text='A concise description. '
                'For visual structure, one can use the '
                '<a href="https://commonmark.org/help/">markdown syntax</a>. '
                'See below after notes for more information.')

    def clean(self):
        cd = self.cleaned_data
        if 'name' in cd:
            cd['name'] = cd['name'].strip()
            if (cd['leading_article'] and
                    cd['name'] == remove_leading_article(cd['name'])):
                raise forms.ValidationError(
                    'The name is only one word, you cannot specify '
                    'a leading article in this case.')
        return cd


def get_story_arc_relation_revision_form(revision=None, user=None):
    class RuntimeStoryArcRelationRevisionForm(StoryArcRelationRevisionForm):
        choices = list(StoryArcRelationType.objects.values_list('id',
                                                                'description'))
        additional_choices = StoryArcRelationType.objects.values_list(
                             'id', 'reverse_description')
        choices = combine_reverse_relations(choices, additional_choices)
        relation_type = forms.ChoiceField(choices=choices)

        def as_table(self):
            # if not user or user.indexer.show_wiki_links:
            #     _set_help_labels(self, CREATOR_RELATION_HELP_LINKS)
            return super(RuntimeStoryArcRelationRevisionForm, self).as_table()

    return RuntimeStoryArcRelationRevisionForm


class StoryArcRelationRevisionForm(forms.ModelForm):
    class Meta:
        model = StoryArcRelationRevision
        fields = model._base_field_list
        # help_texts = STORY_ARC_RELATION_HELP_TEXTS
        labels = {'from_story_arc': 'Story Arc A', 'relation_type': 'Relation',
                  'to_story_arc': 'Story Arc B'}

    from_story_arc = forms.ModelChoiceField(
        queryset=StoryArc.objects.filter(deleted=False),
        widget=autocomplete.ModelSelect2(url='story_arc_autocomplete',
                                         attrs={'style': 'min-width: 45em'})
    )

    to_story_arc = forms.ModelChoiceField(
        queryset=StoryArc.objects.filter(deleted=False),
        widget=autocomplete.ModelSelect2(url='story_arc_autocomplete',
                                         attrs={'style': 'min-width: 45em'})
    )

    comments = _get_comments_form_field()

    def clean(self):
        cd = self.cleaned_data
        type = int(cd['relation_type'])
        if type < 0:
            stash = cd['from_story_arc']
            cd['from_story_arc'] = cd['to_story_arc']
            cd['to_story_arc'] = stash
            cd['relation_type'] = StoryArcRelationType.objects.get(id=-type)
        else:
            cd['relation_type'] = StoryArcRelationType.objects.get(id=type)
        return cd
