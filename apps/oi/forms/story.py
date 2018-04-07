# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django import forms
from django.conf import settings
from django.contrib.admin.widgets import FilteredSelectMultiple

from apps.oi.models import (
    GENRES, get_reprint_field_list, get_story_field_list,
    ReprintRevision, StoryRevision)

from apps.gcd.models import StoryType, STORY_TYPES, OLD_TYPES

# TODO: Should not be reaching inside gcd.models sub-package.
#       This should either be exported thorugh gcd.models or
#       we should not be using it here.
from apps.gcd.models.story import NON_OPTIONAL_TYPES

from .support import (
    _get_comments_form_field, _set_help_labels, _clean_keywords,
    GENERIC_ERROR_MESSAGE, NO_CREATOR_CREDIT_HELP,
    SEQUENCE_HELP_LINKS, HiddenInputWithHelp, PageCountInput)


def get_reprint_revision_form(revision=None, user=None):
    class RuntimeReprintRevisionForm(ReprintRevisionForm):
        def as_table(self):
            # TODO: Why is there commented-out code?
            # if not user or user.indexer.show_wiki_links:
                # _set_help_labels(self, REPRINT_HELP_LINKS)
            return super(RuntimeReprintRevisionForm, self).as_table()
    return RuntimeReprintRevisionForm


class ReprintRevisionForm(forms.ModelForm):
    class Meta:
        model = ReprintRevision
        fields = get_reprint_field_list()


def get_story_revision_form(revision=None, user=None,
                            is_comics_publication=True,
                            language=None):
    extra = {}
    additional_genres = []
    selected_genres = []
    if revision is not None:
        # Don't allow blanking out the type field.  However, when its a
        # new store make indexers consciously choose a type by allowing
        # an empty initial value.  So only set None if there is an existing
        # story revision.
        extra['empty_label'] = None
        if (revision.issue and
                revision.issue.series.is_comics_publication is False):
            is_comics_publication = False
        if revision.genre:
            genres = revision.genre.split(';')
            for genre in genres:
                genre = genre.strip().lower()
                if genre not in GENRES['en']:
                    additional_genres.append(genre)
                selected_genres.append(genre)
            revision.genre = selected_genres
        if revision.issue:
            language = revision.issue.series.language
        else:
            language = None
    # for variants we can only have cover sequences (for now)
    if revision and (revision.issue is None or revision.issue.variant_of):
        queryset = StoryType.objects.filter(name='cover')
        # an added story can have a different type, do not overwrite
        # TODO prevent adding of non-covers directly in the form cleanup
        if revision.type not in queryset:
            queryset = queryset | StoryType.objects.filter(id=revision.type.id)
    elif not is_comics_publication:
        queryset = StoryType.objects.filter(name__in=['comic story',
                                                      'photo story',
                                                      'cartoon'])
        if revision and revision.type not in queryset:
            queryset = queryset | StoryType.objects.filter(id=revision.type.id)

    else:
        special_types = ['filler', ]
        special_types.extend([i for i in OLD_TYPES])
        queryset = StoryType.objects.all()
        if revision is None or (revision is not None and
                                revision.type.name not in special_types):
            queryset = queryset.exclude(name__in=special_types)
        else:
            queryset = queryset.exclude(name__in=OLD_TYPES)

    class RuntimeStoryRevisionForm(StoryRevisionForm):
        type = forms.ModelChoiceField(queryset=queryset, **extra)

        fantasy_id = GENRES['en'].index(u'fantasy')
        if language and language.code != 'en' and language.code in GENRES:
            choices = [[g, g + ' / ' + h]
                       for g, h in zip(GENRES['en'], GENRES[language.code])]
            choices[fantasy_id] = [
                u'fantasy',
                (u'fantasy-supernatural / %s' %
                 GENRES[language.code][fantasy_id])
            ]
        else:
            choices = [[g, g] for g in GENRES['en']]
            choices[fantasy_id] = [u'fantasy', u'fantasy-supernatural']
        if additional_genres:
            additional_genres.reverse()
            for genre in additional_genres:
                choices.insert(0, [genre, genre + ' (deprecated)'])
        genre = forms.MultipleChoiceField(
            required=False,
            widget=FilteredSelectMultiple('Genres', False),
            choices=choices)

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, SEQUENCE_HELP_LINKS)
            return super(StoryRevisionForm, self).as_table()
    return RuntimeStoryRevisionForm


class StoryRevisionForm(forms.ModelForm):
    class Meta:
        model = StoryRevision
        fields = get_story_field_list()
        fields.insert(fields.index('job_number') + 1, 'creator_help')
        widgets = {
            'feature': forms.TextInput(attrs={'class': 'wide'}),
        }
        help_texts = {
            'keywords':
                'Significant objects, locations, or themes (NOT characters) '
                'depicted in the content, such as "Phantom Zone", '
                '"red kryptonite", "Vietnam". or "time travel".  Multiple '
                'entries are to be separated by semi-colons.',
        }

    # The sequence number can only be changed through the reorder form, but
    # for new stories we add it through the initial value of a hidden field.
    sequence_number = forms.IntegerField(widget=forms.HiddenInput)

    title = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'wide', 'autofocus': ''}),
        required=False,
        help_text='If no title can be determined from the issue, follow '
                  ' our instructions to determine a title and check '
                  'unofficial title if needed.')
    title_inferred = forms.BooleanField(
        required=False, label='Unofficial title', help_text='')

    page_count = forms.DecimalField(widget=PageCountInput, required=False,
                                    max_digits=10, decimal_places=3)
    page_count_uncertain = forms.BooleanField(required=False)

    creator_help = forms.CharField(
        widget=HiddenInputWithHelp,
        required=False,
        help_text='Enter the relevant creator credits in the following '
                  'fields, where multiple credits are separated by '
                  'semi-colons. Notes are in () and aliases in []. If the '
                  'credit applies to a sequence type, but the creator is '
                  'unknown enter a question mark. If a field is not required '
                  'for a sequence type it can be left blank.',
        label='')

    script = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                             required=False,
                             help_text='')
    pencils = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                              required=False,
                              help_text='')
    inks = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                           required=False,
                           help_text='')
    colors = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                             required=False,
                             help_text='')
    letters = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'wide'}),
        required=False,
        help_text='If the lettering is produced as normal printed text rather '
                  'than comic-style lettering, enter the word "typeset" here.')
    editing = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
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
                  'whole issue.')
    synopsis = forms.CharField(
        widget=forms.Textarea(attrs={'style': 'height: 9em'}),
        required=False,
        help_text='A brief description of the contents. No text under '
                  'copyright, such as solicitation or other promotional text, '
                  'may be used without clear permission and credit.')
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
            cd['genre'] = u''

        if cd['title_inferred'] and cd['title'] == "":
            raise forms.ValidationError(
                ['Empty titles cannot be unofficial.'])

        if cd['title'].startswith('[') and cd['title'].endswith(']'):
            raise forms.ValidationError(
                ['Do not use [] around unofficial story titles, check the '
                 'unofficial checkbox instead.'])

        for seq_type in ['script', 'pencils', 'inks', 'colors', 'letters',
                         'editing']:
            if cd['type'].id in NON_OPTIONAL_TYPES:
                if not cd['no_%s' % seq_type] and cd[seq_type] == "":
                    raise forms.ValidationError(
                        ['%s field or No %s checkbox must be filled in.' %
                         (seq_type.capitalize(), seq_type.capitalize())])

            if cd['no_%s' % seq_type] and cd[seq_type] != "":
                raise forms.ValidationError(
                    ['%s field and No %s checkbox cannot both be filled in.' %
                     (seq_type.capitalize(), seq_type.capitalize())])

        if (len(cd['synopsis']) > settings.LIMIT_SYNOPSIS_LENGTH and
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
