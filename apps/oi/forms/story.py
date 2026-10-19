# -*- coding: utf-8 -*-

import json
import re

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
from taggit.models import Tag

from apps.oi.models import (
    get_keywords, get_reprint_field_list, get_story_field_list,
    remove_leading_article,
    BiblioEntryRevision, ReprintRevision, StoryRevision, StoryArcRevision,
    StoryArcRelationRevision, StoryCreditRevision, StoryCharacterRevision,
    StoryGroupRevision)


from apps.gcd.models import CreatorNameDetail, CreatorSignature, StoryType, \
                            FeatureLogo, FeatureNameDetail, \
                            CharacterNameDetail, \
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
          'class': 'overflow-y-auto max-h-60 border border-gray-400 '
                   'px-1 inline-block rounded'}),
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
            elif issue.is_indexed >= INDEXED['ten_percent']:
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
        series_has_about_comics = has_about_comics
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
                                       attrs={'class': 'w-full'}),
      required=True,
      help_text='By entering (any part of) a name select a creator from the'
                ' database. Search for the name of the ghosted creator for '
                'ghost work.',
      label='<button hx-get="/select/creator/by_detail/" type="button" '
            'hx-vals="js:{\'name_detail_id\': getSelectValue(event)}" '
            'hx-on:htmx:after-request="setSelectValue(event)" '
            'hx-swap="none" class="mx-0 btn-blue-editing inline">To Official'
            '</button> Creator'
    )

    signature = forms.ModelChoiceField(
      queryset=CreatorSignature.objects.all(),
      widget=autocomplete.ModelSelect2(url='creator_signature_autocomplete',
                                       attrs={'data-html': True,
                                              'class': 'w-full'},
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

        if cd['sourced_by'] and not cd['is_sourced']:
            cd['sourced_by'] = ""

        # only new or changed credits, old ones stay editable
        if cd['is_sourced'] and not cd['sourced_by'].strip() and \
           (self.instance.pk is None or self.has_changed()):
            raise forms.ValidationError(
              ['Enter the source in "Sourced by", or uncheck "Is sourced". '
               'Wiki "Credits", Sourced: "When "Is sourced" is checked, the '
               '"Sourced by" text box must be filled in."']
            )

        if cd['credit_name']:
            if cd['credit_name'].strip() == "credited":
                raise forms.ValidationError(
                    ['"Credit description" cannot be "credited". Please tick '
                     '"Is credited" instead.']
                )

            elif cd['credit_name'].strip().endswith("(credited"):
                raise forms.ValidationError(
                    ['"Credit description" cannot end with "(credited". '
                     'Please tick "Is credited" instead.']
                )

            elif cd['credit_name'].strip().endswith(", credited"):
                raise forms.ValidationError(
                    ['"Credit description" cannot end with ", credited". '
                     'Please tick "Is credited" instead.']
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
            if instance.characterorderrevision_set.exists():
                self.no_delete = True
                self.fields['character'].help_text = \
                    'Characters that are part of a character order cannot be '\
                    'removed.'
                if self.instance and self.instance.character:
                    self.fields['character'].widget.forward = [
                        forward.Const(self.instance.character.id,
                                      'current_character_id')
                    ]

    character = forms.ModelChoiceField(
      queryset=CharacterNameDetail.objects.all(),
      widget=autocomplete.ModelSelect2(url='character_name_autocomplete',
                                       forward=['language_code', 'group_name'],
                                       attrs={'class': 'w-full'}),
      required=True,
      help_text='By entering (any part of) a name select a character from the'
                ' database.'
    )

    group_name = forms.ModelMultipleChoiceField(
      queryset=GroupNameDetail.objects.all(),
      widget=autocomplete.ModelSelect2Multiple(
        url='group_name_autocomplete',
        attrs={'class': 'w-full'},
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
                          attrs={'class': 'w-full'}),
      required=False,
      help_text='Select the universe, if any, from which the character '
                'originates. Use "mainstream" for the principal universe '
                'of a publisher.'
    )

    group_universe = forms.ModelChoiceField(
      queryset=Universe.objects.all(),
      widget=autocomplete.ModelSelect2(
                          url='universe_autocomplete',
                          attrs={'class': 'w-full'}),
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

        if cd['group_name'] and cd['character']:
            character_groups = cd['character'].character.active_memberships()
            character_groups = character_groups.values_list('group', flat=True)
            for group in cd['group_name']:
                if group.group_id not in character_groups:
                    raise forms.ValidationError(
                      ['%s is not member of the group %s' % (
                        cd['character'].character, group.group)]
                    )


class BaseStoryCharacterRevisionFormSet(forms.models.BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = kwargs.get('queryset')
        if queryset:
            order_map = queryset.order_map
            for form in self.forms:
                form.order = order_map.get(form.instance.id, 99999)
            if self.queryset:
                self.forms.sort(key=lambda form: form.order)


StoryCharacterRevisionFormSet = inlineformset_factory(
    StoryRevision, StoryCharacterRevision,
    form=StoryCharacterRevisionForm,
    formset=BaseStoryCharacterRevisionFormSet,
    can_delete=True, extra=1)


class StoryGroupRevisionForm(forms.ModelForm):
    class Meta:
        model = StoryGroupRevision
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
                                       attrs={'class': 'w-full'}),
      required=True,
      help_text='By entering (any part of) a name select a group from the'
                ' database.'
    )

    universe = forms.ModelChoiceField(
      queryset=Universe.objects.all(),
      widget=autocomplete.ModelSelect2(
                          url='universe_autocomplete',
                          attrs={'class': 'w-full'}),
      required=False,
      help_text='Select the universe, if any, from which the group '
                'originates. Use "mainstream" for the principal universe '
                'of a publisher.'
    )


StoryGroupRevisionFormSet = inlineformset_factory(
    StoryRevision, StoryGroupRevision, form=StoryGroupRevisionForm,
    can_delete=True, extra=1)


# credit types counting as script credits, as in StoryRevisionForm.clean()
SCRIPT_CREDIT_TYPES = [CREDIT_TYPES['script'], 10, 11, 12, 13]


def _formset_has_rows(data, prefix, field):
    """Whether a not deleted row of the posted formset has a value in field."""
    for i in range(int(data.get('%s-TOTAL_FORMS' % prefix, 0))):
        if data.get('%s-%d-DELETE' % (prefix, i)):
            continue
        if data.get('%s-%d-%s' % (prefix, i, field)):
            return True
    return False


def _has_script(story):
    """Whether the approved story has a script entry or No Script."""
    return (story.script != '' or story.no_script or
            story.active_credits.filter(
              credit_type_id__in=SCRIPT_CREDIT_TYPES).exists())


def _blank_page_content(story):
    """The kinds of content of the approved story a blank page cannot have."""
    content = []
    if any(getattr(story, credit) for credit in CREDIT_TYPES) or \
       story.active_credits.exists():
        content.append('credits')
    if story.characters or story.active_characters.exists() or \
       story.active_groups.exists():
        content.append('characters')
    if story.synopsis:
        content.append('a synopsis')
    return content


CREDIT_TEXT_FIELDS = ['script', 'pencils', 'inks', 'colors', 'letters',
                      'editing']

# wiki format rules a program can tell, refused for new or changed values:
# (fields, pattern of a wrong value, message quoting the rule)
FORMAT_RULES = [
    (CREDIT_TEXT_FIELDS,
     re.compile(r'(?:^|;)\s*(?:n/?a|none)\s*(?:;|$)', re.IGNORECASE),
     'Do not enter "n/a" or "none": check the No box if the credit does not '
     'apply, or enter "?" if the creator is unknown. Wiki "Credits", Using '
     'the text format: "Do not use "n/a" or "none" or leave the field '
     'blank."'),
    (CREDIT_TEXT_FIELDS, re.compile(r';(?!\s|$)'),
     'Put a space after each semicolon. Wiki "Credits", Using the text '
     'format: "Multiple creators are separated by a semi-colon and space."'),
    (CREDIT_TEXT_FIELDS, re.compile(r'[^\s;?\[(]\?'),
     'Put a space before the question mark of an uncertain credit, as in '
     '"Joe Kubert ?". Wiki "Credits", Using the text format: "If there is '
     'uncertainty about a credit, note it with a space and a question mark '
     'after the name."'),
    (['letters'], re.compile(r'\b(?:Typeset|TYPESET)\b'),
     'Write "typeset" in lower case. Wiki "Style Guide", Credits and '
     'Creators: "The word “typeset,” used in the letters field to indicate '
     'type instead of lettering, is not capitalized."'),
    (CREDIT_TEXT_FIELDS + ['characters'],
     re.compile(r',\s*(?:Jr|Sr)\b|\b(?:Jr|Sr)\b(?!\.)'),
     'Write Jr. and Sr. with a period and without a comma before them. Wiki '
     '"Style Guide", Credits and Creators: "Do not use a comma beforehand, '
     'but use a period behind the identifiers Jr. or Sr."'),
]

# a wrong ellipsis in a title: a space before it, spaced or two, four or more
# periods, the character …, no space or two spaces after it
TITLE_ELLIPSIS = re.compile(
    r'''\s\.{3}|\.\s\.\s\.|(?<!\.)\.\.(?!\.)|\.{4,}|…|'''
    r'''\.{3}(?=[^\s.,;:!?)\]"“”'’»›」』])|\.{3} {2,}''')
TITLE_ELLIPSIS_MESSAGE = (
    'Enter an ellipsis as three periods. Wiki "Style Guide", Story titles: '
    '"When transcribing it for the database, enter it with no preceding '
    'space, no space between the periods, and one space following the '
    'ellipsis."')


def _is_new_value(cd, story, field):
    """Whether the value of field is new: added sequence or changed value."""
    return story is None or getattr(story, field).strip() != cd[field]


def _format_errors(cd, story):
    """The format rules broken by new or changed values of text fields."""
    errors = []
    for fields, pattern, message in FORMAT_RULES:
        for field in fields:
            if _is_new_value(cd, story, field) and pattern.search(cd[field]):
                errors.append('%s: %s' % (field.capitalize(), message))
    if _is_new_value(cd, story, 'title'):
        for match in TITLE_ELLIPSIS.finditer(cd['title']):
            # the wiki does not say whether a leading ellipsis is followed
            # by a space
            if match.start() == 0 and match.group() == '...':
                continue
            errors.append('Title: ' + TITLE_ELLIPSIS_MESSAGE)
            break
    return errors


def _without_brackets(value):
    """The value without its parts in ( ) and [ ], innermost first."""
    previous = None
    while previous != value:
        previous, value = value, re.sub(r'\([^()\[\]]*\)|\[[^()\[\]]*\]', '',
                                        value)
    return value


def _sections(value):
    """The parts of the value between semicolons outside ( ) and [ ]."""
    sections, depth, section = [], 0, ''
    for character in value:
        if character in '([':
            depth += 1
        elif character in ')]':
            depth -= 1
        if character == ';' and depth == 0:
            sections.append(section)
            section = ''
        else:
            section += character
    return sections + [section]


def _search(pattern, flags=0):
    """A check whether the pattern occurs in a value."""
    return re.compile(pattern, flags).search


def _search_outside_brackets(pattern):
    """A check whether the pattern occurs outside ( ) and [ ] of a value."""
    search = re.compile(pattern).search
    return lambda value: search(_without_brackets(value))


REPRINT_SECTION_START = re.compile(
    r'^\s*(?:from|in|de|dans|fra|i|Original em|Reimpresso em)\b|'
    r'^\s*\d{4}-\d{2}-\d{2}')
COMICS_REPRINT_SECTION = re.compile(
    r'^\s*(?:from|in)\s+(?!\?)(?!.*\d{4}-\d{2}-\d{2}).*')
SERIES_DESIGNATION = re.compile(r'\([^()]*,\s*\d{4}\s+[Ss]eries\)\s*#\S+')
QUOTED = r'^["“”„«»‹›\'‘’‚「『].*["“”«»‹›\'‘’」』]$'


def _reprint_section_start(value):
    """Whether a reprint section starts neither with from/in nor a date."""
    return any(not REPRINT_SECTION_START.search(section)
               for section in _sections(value) if section.strip())


def _reprint_without_series(value):
    """Whether a comics reprint section lacks (Publisher, YYYY series) #."""
    return any(COMICS_REPRINT_SECTION.search(section) and
               not SERIES_DESIGNATION.search(section)
               for section in _sections(value))


# wiki format rules where a person has to judge whether a value breaks
# them: (fields, check of a value, wiki page, section, rule, sequence types
# the rule does not apply to), shown as notes that do not block
FORMAT_NOTES = [
    (['title'], _search(QUOTED), 'Style Guide', 'Story titles',
     'In the story title field, do not use quotation marks unless they '
     'occur within the title.', ()),
    # a leading ellipsis, which the refusal of _format_errors() skips
    (['title'], _search(r'^\.{3}(?=[^\s.,;:!?)\]"“”\'’»›」』])'),
     'Style Guide', 'Story titles',
     'When transcribing it for the database, enter it with no preceding '
     'space, no space between the periods, and one space following the '
     'ellipsis.', ()),
    (['first_line'], _search(QUOTED), 'Title', 'First Line field',
     'Also in such cases, the Unofficial Title box should not be checked, '
     'and quotation marks are not used.', ()),
    (['feature'], _search(r'\S/|/\S'), 'Feature', 'Feature Names',
     'If the name of a feature contains a "/" to separate two individual '
     'name components, use a space before and after the "/", regardless of '
     'the presence or absence of spaces around the "/" in print. No spaces '
     'are used if the "/" is an integral part of the name.', ()),
    (['feature'], _search(r',\s*(?:The|A|An)\s*(?:;|$)', re.IGNORECASE),
     'Feature', 'Feature Use',
     'Leave articles at the front of the Feature title:  "The Shadow", not '
     '"Shadow, The"', ()),
    (['feature'] + CREDIT_TEXT_FIELDS, _search_outside_brackets(','),
     'Formatting Documentation', 'General Indexing Format Rules',
     'Separate multiple entries in the same field (such as stories with more '
     'than one penciller) with a semicolon (";"), not a comma.', ()),
    # wiki "Letters and Fan Art" asks for commas between fan-art characters
    (['characters'], _search_outside_brackets(','),
     'Formatting Documentation', 'General Indexing Format Rules',
     'Separate multiple entries in the same field (such as stories with more '
     'than one penciller) with a semicolon (";"), not a comma.',
     (STORY_TYPES['letters_page'],)),
    (['characters'], _search_outside_brackets(','), 'Character Appearances',
     'Entering Character Appearances using text',
     'Characters in the Characters field (of a Sequence editing page) should '
     'be separated with a semi-colon (;).', (STORY_TYPES['letters_page'],)),
    (CREDIT_TEXT_FIELDS, _search(r'\)[\s,]*\('), 'Credits',
     'Using the text format',
     'If there are multiple notes, these should be placed within a single '
     'set of parentheses, such as (signed, painted).', ()),
    (CREDIT_TEXT_FIELDS, _search(r'\(as\s'), 'Formatting Documentation',
     'General Indexing Format Rules',
     'Use square brackets for a creator\'s pseudonym such as "[as Joe King]" '
     'per Credits or for information that is not actually in the comic.',
     ()),
    (CREDIT_TEXT_FIELDS, _search(r'\b[A-Z]\.[A-Z]\.'), 'Credits',
     'Using the text format',
     'In case multiple initials are used they should be separated by '
     'spaces.', ()),
    (CREDIT_TEXT_FIELDS,
     _search(r'\bpgs?\.?\s*\d|\bpag\.?\s*\d|\bpp?(?!\.)\s+\d', re.IGNORECASE),
     'Credits', 'Using the text format',
     'If it is known which pages were done by specific creators, include '
     'those pages in parentheses after each name using the terms page, '
     'pages, p. or pp.', ()),
    (CREDIT_TEXT_FIELDS, _search(r'\)\s*\[as\s'), 'Credits',
     'Using the text format',
     'The general form for a credit is "Who\'s Who form" [as "Credited or '
     'signed form"] (signed)".', ()),
    (CREDIT_TEXT_FIELDS, _search(r'\b(?:Typeset|TYPESET|Painting|Painted)\b'),
     'Formatting Documentation', 'General Indexing Format Rules',
     'Do not capitalize genres, credit clarifications (such as "painting" or '
     '"typeset"), etc., per a September 2012 clarification of when to use '
     'capitalization.', ()),
    (['editing'], _search(r'\([A-Z]{2,5}\)'), 'Editing', '',
     'Only specific, pre-approved exceptions will be permitted, and all '
     'other abbreviations must be expanded.', ()),
    (CREDIT_TEXT_FIELDS,
     _search(r'(?:^|;)\s*(?:unknown|unk\.?)\s*(?:;|$)', re.IGNORECASE),
     'Credits', 'Using the text format',
     'If a credit is unknown, enter only a question mark: "?". Do not use '
     '"n/a" or leave the field blank.', ()),
    (['characters'], _search(r'\([^()]*;[^()]*\)'), 'Character Appearances',
     'Standard Format for Groups and Notes',
     'Multiple notes should be separated with a comma: "Superman '
     '(introduction, origin)".', ()),
    (['characters'], _search(r'\((?:[A-Z](?:,\s*)?)+\)'),
     'Character Appearances', 'Standard Format for Groups and Notes',
     'Abbreviations, such as O for Origin, should not be used.', ()),
    (['characters'], _search(r'\b[A-Z][a-z]+ (?:I{1,3}|IV)\b(?!\])'),
     'Character Appearances', 'Entering Character Appearances using text',
     'An older format seen in some sequences, where different versions of a '
     'character were numbered with Roman numerals, such as "Wildcat I" and '
     '"Wildcat II", is not allowed and should be corrected to the named '
     'form, as in "Wildcat" [Ted Grant]" and "Wildcat [Yolanda Montez]".',
     ()),
    (['characters'], _search(r'\b(?:Gen|Sgt|Capt|Col|Lt|Maj|Sen)\.'),
     'Style Guide', 'Characters',
     'If you are going to use personal titles, such as military ranks, in '
     'the character field, spell them out.', ()),
    (['synopsis'], _search('!'), 'Style Guide', 'Synopses',
     'Do not use exclamation points in synopses.', ()),
    (['synopsis'], _search(r'\.\.\.|…'), 'Style Guide', 'Synopses',
     'Do not use the ellipsis in a synopsis.', ()),
    (['synopsis'], _search(r'\b(?:Spidey|Wolvie|Supes)\b'), 'Style Guide',
     'Synopses',
     'Names such as “Spidey” or “Wolvie” or “Supes” are inappropriate and '
     'should not be used.', ()),
    (['reprint_notes'], _reprint_section_start, 'Reprints',
     'Textual Reprint Notes',
     'the first word in each section in this field must be either "from" or '
     '"in".  The equivalent of "from" or "in" in languages other than '
     'English may also be used.', ()),
    (['reprint_notes'], _search_outside_brackets(r',\s*(?:from|in)\s'),
     'Reprints', 'Textual Reprint Notes',
     'Multiple sections of the field are separated by semicolons (;).', ()),
    (['reprint_notes'], _reprint_without_series, 'Reprints',
     'Textual Reprint Notes',
     'Format for comics reprinted from or in other comics is: in/from Series '
     'Title (Original publisher, YYYY series) #number (optional exact date '
     'of publication) [optional short notes].', ()),
    (['reprint_notes'], _search(r'\[(?:[^\]\s]+\s+){12,}[^\]]*\]'),
     'Reprints', 'Textual Reprint Notes',
     'Most details about the reprint (such as editing or a title change) '
     'belong in the Notes field.  Short notes of less than about 10 words '
     'can be put in square brackets after the reprint info.', ()),
    (['reprint_notes'],
     _search(r'\b\d{1,2}([-./])\d{1,2}\1(?:\d{4}|\d{2})\b|'
             r'\b\d{4}([./])\d{1,2}\2\d{1,2}\b|\b\d{4}-\d(?!\d)|'
             r'\b\d{4}-\d{2}-\d(?!\d)|\b\d{4}-\d{2}-\d{2}(?! - \d)\s*-\s*\d'),
     'Style Guide', 'General rules',
     'Reprint Notes shall be formatted using hyphens in the style '
     '“YYYY-MM-DD” for a single date, or “YYYY-MM-DD - YYYY-MM-DD” for a '
     'range of dates, or “YYYY-MM-DD; YYYY-MM-DD - YYYY-MM-DD; YYYY-MM-DD” '
     'for a group of separate dates.', ()),
    (['reprint_notes'],
     _search(r'(?<!#)\bv\d+\s*#|#v\d+\s+#|\bvol(?:ume)?\.?\s*\d+\s*#',
             re.IGNORECASE),
     'Reprints', 'Textual Reprint Notes',
     'Format for the number of issues that show their volume number with the '
     'issue number is #v2#1 (including the leading #).', ()),
    (['notes'],
     _search(r'\bcredits by\b|\bidentification from\b', re.IGNORECASE),
     'Style Guide', 'Credits and Creators',
     'In notes, the acceptable phrases for the source of credits are:  '
     '“credits from” or “identification by.”  Do not mix and match:  '
     '“credits by” or “identification from” are incorrect.', ()),
    (['notes'],
     _search(r'(?<!letter )\b(?:writer|inker|penciller|penciler|colorist|'
             r'letterer)s?\b', re.IGNORECASE),
     'Style Guide', 'Credits and Creators',
     'Note the names of the GCD credits fields and use those in your notes: '
     'script not writer; inks not inker.', ()),
    (['notes'], _search(r'(?<![Ss]eries\) )(?<!#v\d)(?<!#v\d\d)#\d'),
     'Style Guide', "Series' titles",
     'When referring to a series, always use the full GCD designation of '
     'official series title, followed by the publisher name and the year the '
     'series began, in parentheses: The Amazing Spider-Man (Marvel, 1963 '
     'series) or Kalle Anka & C:o (Egmont, 1997 series).', ()),
    (['notes', 'synopsis'],
     _search(r'\b(?:[A-Z][a-z]?\.){2,}(?![^\[\]]*\])'), 'Style Guide',
     'General rules',
     'use no periods with abbreviations that appear in full capitals, even '
     'if lowercase letters appear: NASA, AD, PhD', ()),
    (['notes', 'synopsis'], _search('[$€£¥]'), 'Style Guide',
     'General rules',
     'Currencies are only to be referred to by their currency code.', ()),
    (['title'] + CREDIT_TEXT_FIELDS + ['reprint_notes', 'notes', 'synopsis'],
     _search(r'(?<![\d-])#?\d+(?: - ?|- )#?\d+(?![\d-])'), 'Style Guide',
     'General rules',
     'Use the hyphen when indicating continuing numbers, with no space '
     'before or after the hyphen', ()),
    (['title', 'first_line', 'feature'] + CREDIT_TEXT_FIELDS +
     ['job_number', 'characters', 'synopsis', 'reprint_notes', 'notes',
      'keywords'],
     _search('[‒–—―−]'), 'Style Guide', 'General rules',
     'There are a variety of dashes in typography but in the GCD, we only '
     'use one: the hyphen.', ()),
    (['keywords'], _search(r'[()\[\]]'), 'Keywords', 'Notes',
     'Do not group items with parentheses or brackets.', ()),
    (['keywords'],
     _search(r'\b(?:WW ?I{1,2}|WW ?[12]|First World War|Second World War|'
             r'War of Northern Aggression|War Between the States)\b',
             re.IGNORECASE),
     'Style Guide', 'Keywords',
     'World War I and World War II should be used in place of WWI, WWII, or '
     'First World War, etc.', ()),
]


def _new_value(revision, story, field):
    """Whether the revision has a new or changed value in field."""
    if story is None:
        return True
    old = get_keywords(story) if field == 'keywords' \
        else getattr(story, field)
    return old.strip() != getattr(revision, field).strip()


def _entries(value):
    """The entries of a text field, without notes in ( ) and [ ]."""
    return {_without_brackets(entry).strip(' ?').lower()
            for entry in value.split(';')} - {''}


# credit types counting for each text credit field, as in
# StoryRevisionForm.clean()
CREDIT_FIELD_TYPES = {
    'script': SCRIPT_CREDIT_TYPES,
    'pencils': [CREDIT_TYPES['pencils']] + list(range(7, 15)),
    'inks': [CREDIT_TYPES['inks']] + list(range(7, 15)),
    'colors': [CREDIT_TYPES['colors'], 8, 9, 11, 13],
    'letters': [CREDIT_TYPES['letters'], 12, 13, 14],
    'editing': [CREDIT_TYPES['editing']],
}


def _credits_also_in_records(revision, story):
    """
    Text credit fields naming a creator who has a credit record of the
    field, by the official or an alternate name of the creator.
    """
    if revision.pk is None:
        return []
    records = list(revision.story_credit_revisions.exclude(deleted=True)
                           .select_related('creator__creator'))
    flagged = []
    for field, credit_types in CREDIT_FIELD_TYPES.items():
        names = _entries(getattr(revision, field))
        field_records = [record for record in records
                         if record.credit_type_id in credit_types]
        if not names or not field_records or \
           not (_new_value(revision, story, field) or
                any(record.story_credit_id is None
                    for record in field_records)):
            continue
        for record in field_records:
            if names & {name.lower() for name in record.creator.creator
                        .creator_names.values_list('name', flat=True)}:
                flagged.append(field)
                break
    return flagged


SEE_NOTES = re.compile(r'\([^()]*\bsee notes\b[^()]*\)', re.IGNORECASE)
SEE_NOTES_FIELDS = ['title', 'first_line', 'feature'] + CREDIT_TEXT_FIELDS + \
                   ['job_number', 'characters', 'synopsis', 'reprint_notes']


def _see_notes_without_notes(revision, story):
    """Fields with "(see notes)" while Notes is empty."""
    if revision.notes.strip():
        return []
    notes_changed = _new_value(revision, story, 'notes')
    return [field for field in SEE_NOTES_FIELDS
            if SEE_NOTES.search(getattr(revision, field)) and
            (notes_changed or _new_value(revision, story, field))]


def _keywords_in_other_fields(revision, story):
    """
    Keywords equal to the title, a feature, a story arc, a genre or a
    character or group of the sequence.
    """
    keywords = _entries(revision.keywords)
    if not keywords or not _new_value(revision, story, 'keywords'):
        return []
    others = {revision.title.strip().lower()} | \
        _entries(revision.feature) | _entries(revision.genre) | \
        _entries(revision.characters)
    if revision.pk is not None:
        for names in [
          revision.feature_name.values_list('name', flat=True),
          revision.story_arc.values_list('name', flat=True),
          revision.story_character_revisions.exclude(deleted=True)
                  .values_list('character__name', flat=True),
          revision.story_group_revisions.exclude(deleted=True)
                  .values_list('group_name__name', flat=True)]:
            others |= {name.lower() for name in names if name}
    return ['keywords'] if keywords & others else []


# wiki rules checked on the whole revision, also against its records:
# (check giving the fields that may break the rule, page, section, rule)
REVISION_NOTES = [
    (_credits_also_in_records, 'Credits', 'Missing Creator Record',
     'BE CAREFUL NOT TO ENTER THE SAME CREDIT USING BOTH THE CREATOR RECORD '
     'AND TEXT CREDITS.'),
    (_see_notes_without_notes, 'Notes (Sequence)', '',
     'Direct comments about other fields to here with a "(see notes)" '
     'comment.'),
    (_keywords_in_other_fields, 'Keywords', '',
     'Do not put anything in the keyword field that should be put in another '
     'field. An exception is made for real-world comic event names and '
     'initiatives, which can be included in the Keywords even if they are '
     'also in another field'),
]


def _note(fields, page, section, rule):
    """A note quoting the wiki rule that values of the fields may break."""
    return 'Note on %s: wiki "%s"%s: "%s"' % (
        ', '.join(field.replace('_', ' ').capitalize() for field in fields),
        page, ', ' + section if section else '', rule)


def format_notes(revision):
    """
    Notes on the wiki format rules that new or changed values of a sequence
    revision may break, where a person has to judge.
    """
    story = revision.story
    notes = []
    for fields, check, page, section, rule, skipped_types in FORMAT_NOTES:
        if revision.type_id in skipped_types:
            continue
        flagged = [field for field in fields
                   if getattr(revision, field).strip() and
                   _new_value(revision, story, field) and
                   check(getattr(revision, field).strip())]
        if flagged:
            notes.append(_note(flagged, page, section, rule))
    for check, page, section, rule in REVISION_NOTES:
        flagged = check(revision, story)
        if flagged:
            notes.append(_note(flagged, page, section, rule))
    return notes


NO_CREDIT_BOXES = ['no_script', 'no_pencils', 'no_inks', 'no_colors',
                   'no_letters']

# rows of the sequence form for fields that do not apply to a type, as
# (rows, fields whose value keeps the rows shown, so that old values can be
# removed); a name is a form field, a formset prefix or the data-field of a
# row
FEATURE_ROWS = [(['feature'], ['feature']),
                (['feature_name', 'feature_genres'], ['feature_name'])]
FEATURE_LOGO_ROWS = [(['feature_logo'], ['feature_logo'])]
GENRE_ROWS = [(['genre', 'selected_genres'], ['genre'])]
CHARACTER_FIELDS = ['universe', 'appearing_characters', 'group_name',
                    'group_members', 'story_character_revisions',
                    'characters', 'story_group_revisions']
BLANK_PAGE_ROWS = [
    (['title', 'title_inferred'], ['title']),
    (['first_line'], ['first_line']),
    (['story_arc'], ['story_arc']),
    (['job_number'], ['job_number']),
    (['creator_help'] + CREDIT_TEXT_FIELDS + ['story_credit_revisions'],
     CREDIT_TEXT_FIELDS + ['story_credit_revisions']),
    (CHARACTER_FIELDS +
     ['characters_heading', 'character_help', 'use_universe',
      'save_and_set_universe', 'one_character_help', 'character_order'] +
     ['%s_%s' % (field, detail)
      for field in ['appearing_characters', 'group_members']
      for detail in ['additional_information', 'role', 'flashback',
                     'origin', 'death', 'notes']],
     CHARACTER_FIELDS),
    (['synopsis'], ['synopsis']),
    (['reprint_notes'], ['reprint_notes']),
    (['keywords', 'keyword_objects'], ['keywords', 'keyword_objects']),
]


def _hidden_rows():
    """
    The rows of the sequence form each type hides, by type id: the wiki
    Not applicable and Forbidden fields of the type.
    """
    hidden = {STORY_TYPES['cover']: list(FEATURE_LOGO_ROWS),
              STORY_TYPES['blank']: list(BLANK_PAGE_ROWS)}
    for type_id in NO_FEATURE_TYPES:
        hidden.setdefault(type_id, []).extend(FEATURE_ROWS +
                                              FEATURE_LOGO_ROWS)
    for type_id in NO_GENRE_TYPES:
        hidden.setdefault(type_id, []).extend(GENRE_ROWS)
    return hidden


# TODO check with crispy 2.0, why here and in custom_layout ?
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
        fields.insert(fields.index('keywords') + 1, 'keyword_objects')
        widgets = {
            'feature': forms.TextInput(attrs={'class': 'w-full lg:w-4/5'}),
        }
        help_texts = {
            'keywords':
                KEYWORDS_HELP,
        }

    # set by get_story_revision_form() from the series of the sequence
    series_has_about_comics = None

    def __init__(self, *args, **kwargs):
        """
        Initialize the StoryRevisionForm with custom layout and field
        organization.

        This form constructor creates a complex layout with multiple sections
        for story revision, including sequence details, creator credits, and
        character information. The layout can be organized either as a single
        form or with tabs based on user preferences.

        Args:
            *args: Variable length argument list passed to parent form.
            **kwargs: Arbitrary keyword arguments. Must include:
                user: The user object with indexer preferences (use_tabs flag).

        The form includes:
            - sequence details section with genre information
            - creator credits section with formset support
            - characters section with universe assignment and formsets
            - dynamic HTML elements for genre display
            - dynamic HTML elements for character universe management
            - conditional buttons for character appearance order
            - tab-based or linear layout based on user preferences
            - custom field templates and Bootstrap horizontal form styling

        Layout Organization:
            - If use_tabs is False: All fields are displayed linearly
            - If use_tabs is True: Fields are organized into three tabs:
            1. Sequence Details: Main story information and remaining fields
            2. Creator Credits: Creator formset and related fields
            3. Characters: Character formsets, groups, and universe management
        """
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
            '<tr class="mb-2" data-field="feature_genres">'
            '<th>Genre from Feature:</th>'
            '<td><div id="feature-genres"></div></td></tr>'))
        field_list.append(HTML(
          '<tr class="mb-2" data-field="selected_genres">'
          '<th>Selected Genre:</th>'
          '<td id="selected-genres"></td></tr>'))

        credits_start = fields.index('creator_help')
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
          '<tr data-field="characters_heading">'
          '<th><hr style="height:2px; background-color:#000;">&nbsp;'
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
        has_appearance_order = False
        has_importance_order = False
        if 'instance' in kwargs and kwargs['instance'] and \
           kwargs['instance'].id:
            if kwargs['instance'].character_order_revisions.filter(type__id=1):
                has_appearance_order = True
            if kwargs['instance'].character_order_revisions.filter(type__id=2):
                has_importance_order = True
        character_order_html = '<tr data-field="character_order"><th></th><td>'
        if has_appearance_order:
            character_order_html += '<input type="submit" ' \
              'name="edit_appearance_order"' \
              ' value="Save And Edit Appearance Order" ' \
              'class="m-0 btn-blue-editing inline"/>'
        else:
            character_order_html += '<input type="submit" ' \
              'name="create_appearance_order"' \
              ' value="Save And Create Appearance Order" ' \
              'class="m-0 btn-blue-editing inline"/>'
        if has_importance_order:
            character_order_html += '<input type="submit" ' \
              'name="edit_importance_order"' \
              ' value="Save And Edit Importance Order" ' \
              'class="m-0 btn-blue-editing inline"/>'
        else:
            character_order_html += '<input type="submit" ' \
              'name="create_importance_order"' \
              ' value="Save And Create Importance Order" ' \
              'class="m-0 btn-blue-editing inline"/>'
        field_list.append(HTML(character_order_html + '</td></tr>'))
        characters_end = len(field_list)
        field_list.extend([BaseField(Field(field,
                                           template='oi/bits/uni_field.html'))
                           for field in fields[characters_start+1:]])
        if not user.indexer.use_tabs:
            self.helper.layout = Layout(*(f for f in field_list))
        else:
            self.helper.layout = Layout(TabHolder(
              Tab('Sequence Details',
                  *(f for f in field_list[:credits_start-5]),
                  *(f for f in field_list[characters_end:-2]),
                  template='oi/bits/tab.html',
                  ),
              Tab('Creator Credits',
                  *(f for f in field_list[credits_start-4:credits_end+7]),
                  template='oi/bits/tab.html',
                  ),
              Tab('Characters',
                  *(f for f in field_list[credits_end+8:characters_end]),
                  template='oi/bits/tab.html',
                  ),
              template='oi/bits/tab-bar.html',
            ),
              HTML('<table class="editing w-full">'),
              *(f for f in field_list[-2:]),
              HTML('</table>'))
        self.helper.doc_links = SEQUENCE_HELP_LINKS
        # for storyrevision_form_utils.js: the rows each type hides, and the
        # No boxes it checks when a sequence becomes a blank page
        story = self.instance.story
        self.fields['type'].widget.attrs.update({
          'data-hidden-rows': json.dumps(_hidden_rows()),
          'data-blank-type': STORY_TYPES['blank'],
          'data-approved-type': story.type_id if story else ''})
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

    feature_name = forms.ModelMultipleChoiceField(
      queryset=FeatureNameDetail.objects.all(),
      widget=autocomplete.ModelSelect2Multiple(
                          url='feature_name_autocomplete',
                          forward=['language_code', 'type'],
                          attrs={'class': 'w-full'}),
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
                          attrs={'data-html': True, 'class': 'w-full'}),
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
                          attrs={'class': 'w-full'}),
      required=False,
      help_text='Only story arcs for the series language can be selected. '
                'Enter "&lt;space&gt;[&lt;text&gt;" to search the '
                'disambiguation.'
     )

    keyword_objects = forms.ModelMultipleChoiceField(
      queryset=Tag.objects.all(),
      widget=autocomplete.ModelSelect2Multiple(
                          url='keyword_autocomplete',
                          attrs={'class': 'w-full'}),
      required=False,
      label='Keywords',
      help_text='Select existing keywords that apply to this story.'
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
                          attrs={'class': 'w-full'}),
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
                  'the corresponding credit field can also be used. '
                  '<br>Creator and credit type are required fields '
                  'for each individual credit.')

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
        attrs={'class': 'w-full'},
        forward=['language_code']),
      help_text='Select a group and enter its characters.',
      label='b) Group',
      required=False,
    )

    group_members = forms.ModelMultipleChoiceField(
      queryset=CharacterNameDetail.objects.all(),
      widget=autocomplete.ModelSelect2Multiple(
        url='character_name_autocomplete',
        attrs={'class': 'w-full'},
        forward=['language_code', 'group_name']),
      help_text='Select the appearing members of the group.',
      required=False,
    )

    appearing_characters = forms.ModelMultipleChoiceField(
      queryset=CharacterNameDetail.objects.all(),
      widget=autocomplete.ModelSelect2Multiple(
        url='character_name_autocomplete',
        attrs={'class': 'w-full'},
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

    def clean_keyword_objects(self):
        for keyword in self.cleaned_data['keyword_objects']:
            for c in ['<', '>', '{', '}', ':', '/', '\\', '|', '@', ',', '\n',
                      '’']:
                if c in keyword.name:
                    raise forms.ValidationError(
                      'The following characters are not allowed in a keyword: '
                      '< > { } : / \\ | @ , ’')
        return self.cleaned_data['keyword_objects']

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

        if (cd['feature'] or cd['feature_name'] or cd['feature_logo']) and \
           cd['type'].id in NO_FEATURE_TYPES:
            raise forms.ValidationError(
                ['The sequence type cannot have a feature.'])

        if cd['story_arc'] and cd['type'].id != STORY_TYPES['comic story']:
            raise forms.ValidationError(
                ['The sequence type cannot have a story arc.'])

        if cd['genre'] and cd['type'].id in NO_GENRE_TYPES:
            raise forms.ValidationError(
                ['The sequence type cannot have a genre.'])

        if cd['feature'] and (cd['feature_name'] or cd['feature_logo']):
            raise forms.ValidationError(
                ['Either use the text feature field or the database objects.'])

        if cd['feature_name']:
            for feature_name in cd['feature_name']:
                if cd['type'].id == STORY_TYPES['letters_page']:
                    if not feature_name.feature.feature_type.id == 2:
                        raise forms.ValidationError(
                          ['Select the correct feature for a letters page.'])
                elif cd['type'].id == STORY_TYPES['in-house column']:
                    if not feature_name.feature.feature_type.id == 4:
                        raise forms.ValidationError(
                          ['Select the correct feature for an in-house '
                           'column.'])
                elif feature_name.feature.feature_type.id == 3:
                    if not cd['type'].id in [STORY_TYPES['ad'],
                                             STORY_TYPES['comics-form ad']]:
                        raise forms.ValidationError(
                          ['Incorrect feature for this sequence.'])
                elif feature_name.feature.feature_type.id in [2, 4]:
                    raise forms.ValidationError(
                      ['Incorrect feature for this sequence.'])

        if cd['feature_logo']:
            if cd['type'].id == STORY_TYPES['cover']:
                raise forms.ValidationError(
                  ['No feature logos for cover sequences.'])
            for feature_logo in cd['feature_logo']:
                if cd['type'].id == STORY_TYPES['letters_page']:
                    if not feature_logo.feature_name\
                                       .filter(feature__feature_type__id=2)\
                                       .exists():
                        raise forms.ValidationError(
                          ['Select the correct feature logo for a '
                           'letters page.'])
                elif cd['type'].id == STORY_TYPES['in-house column']:
                    if not feature_logo.feature_name\
                                       .filter(feature__feature_type__id=4)\
                                       .exists():
                        raise forms.ValidationError(
                          ['Select the correct feature logo for an '
                           'in-house column.'])
                elif feature_logo.feature_name\
                                 .filter(feature__feature_type__id=3).exists():
                    if not cd['type'].id in [STORY_TYPES['ad'],
                                             STORY_TYPES['comics-form ad']]:
                        raise forms.ValidationError(
                          ['Incorrect feature logo for this sequence.'])
                elif feature_logo.feature_name\
                                 .filter(feature__feature_type_id__in=[2, 4])\
                                 .exists():
                    raise forms.ValidationError(
                      ['Incorrect feature logo for this sequence.'])

        if cd['keyword_objects']:
            for keyword in cd['keyword_objects']:
                if cd['keywords']:
                    cd['keywords'] += '; '
                cd['keywords'] += keyword.name

        credits_found = {}
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
            credits_found[seq_type] = seq_type_found

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

        # the approved sequence, None for an added one
        story = self.instance.story

        if cd['type'].id == STORY_TYPES['letters_page'] and \
           not cd['no_script'] and cd['script'] == '' and \
           not credits_found['script']:
            # older letters pages without a script entry stay editable
            if story is None or \
               story.type_id != STORY_TYPES['letters_page'] or \
               _has_script(story):
                raise forms.ValidationError(
                    ['Enter the people answering the letters in the Script '
                     'field, or check No Script if there are no answers. '
                     'Wiki "Letters and Fan Art", Letter Column Script and '
                     'Editorial Comment Credits: "If there is no response, '
                     'then the NO script check-box must be checked."'])

        if cd['type'].id == STORY_TYPES['blank']:
            content = []
            if any(cd[credit] or credits_found[credit]
                   for credit in CREDIT_TYPES):
                content.append('credits')
            if cd['characters'] or cd['appearing_characters'] or \
               cd['group_name'] or cd['group_members'] or \
               _formset_has_rows(self.data, 'story_character_revisions',
                                 'character') or \
               _formset_has_rows(self.data, 'story_group_revisions',
                                 'group_name'):
                content.append('characters')
            if cd['synopsis']:
                content.append('a synopsis')
            # older blank pages with such content stay editable
            if story is not None and story.type_id == STORY_TYPES['blank']:
                approved = _blank_page_content(story)
                content = [c for c in content if c not in approved]
            if content:
                raise forms.ValidationError(
                    ['A blank page cannot have %s. Wiki "Type", Blank '
                     'Page(s): "Empty page with no content." If the page '
                     'shows art, a logo or text, choose a matching type, '
                     'e.g. Illustration.' % ' or '.join(content)])
            # checked by storyrevision_form_utils.js when a sequence becomes
            # a blank page, required for copies and imports
            if (story is None or story.type_id != STORY_TYPES['blank']) and \
               not all(cd[box] for box in NO_CREDIT_BOXES):
                raise forms.ValidationError(
                    ['Check No Script, No Pencils, No Inks, No Colors and No '
                     'Letters: no credit applies to a blank page. Wiki '
                     '"Formatting Documentation", General Indexing Format '
                     'Rules: "If credits are not applicable to a sequence '
                     '(colorist for black & white stories, writer or letterer '
                     'for pinups), check the No script (or No pencils, No '
                     'inks, etc.) checkbox".'])

        format_errors = _format_errors(cd, story)
        if format_errors:
            raise forms.ValidationError(format_errors)

        # types only old sequences keep: no new filler, and no new about
        # comics in a series without "has about comics" (copies, imports)
        old_type_id = story.type_id if story is not None else None
        if cd['type'].id == STORY_TYPES['filler'] and \
           old_type_id != STORY_TYPES['filler']:
            raise forms.ValidationError(
                ['Choose another type. Wiki "Type", Filler (types no longer '
                 'used): "The type "filler" has been eliminated."'])
        if cd['type'].id == STORY_TYPES['about comics'] and \
           self.series_has_about_comics is False and \
           old_type_id != STORY_TYPES['about comics']:
            raise forms.ValidationError(
                ['Choose another type, or ask for "has about comics" on the '
                 'series. Wiki "About Comics": "The \'Has about comics\' box '
                 'must be checked at the series level in order to add '
                 '\'about comics\' sequences to an issue."'])

        # compared with the approved sequence, so that a synopsis brought in
        # by a copy is checked too
        synopsis_length = len(' '.join(cd['synopsis'].split()))
        if (synopsis_length > settings.LIMIT_SYNOPSIS_LENGTH and
                (story is None or story.synopsis.strip() != cd['synopsis'])):

            raise forms.ValidationError(
                ['The synopsis field may not be longer than %d characters.' %
                 settings.LIMIT_SYNOPSIS_LENGTH])

        if cd['page_count'] is None and not cd['page_count_uncertain']:
            # older inserts without a page count stay editable
            if cd['type'].id != STORY_TYPES['insert'] or story is None or \
               story.type_id != STORY_TYPES['insert'] or \
               story.page_count is not None or story.page_count_uncertain:
                raise forms.ValidationError(
                    ['Page count uncertain must be checked if the page count '
                     'is not filled in. Wiki "Page Count": "This is a '
                     'required field for sequences, and either a number '
                     'must be entered or the Uncertain box must be '
                     'checked."'])

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
        if 'from_story_arc' in cd and 'to_story_arc' in cd and \
           cd['from_story_arc'] == cd['to_story_arc']:
            raise forms.ValidationError(
              'Story Arc A and Story Arc B cannot be the same story arc.')
        return cd
