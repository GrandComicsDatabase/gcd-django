# -*- coding: utf-8 -*-
import re
from math import log10

from django import forms
from django.core import urlresolvers
from django.db.models import Count, F
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.forms.widgets import TextInput, HiddenInput, RadioSelect
from django.utils.safestring import mark_safe
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.utils.encoding import force_unicode
from django.utils.html import escape, conditional_escape

from apps.oi.models import *
from apps.gcd.models import *
from apps.gcd.models.seriesbond import BOND_TRACKING
from apps.gcd.models.story import NON_OPTIONAL_TYPES, STORY_TYPES
from apps.gcd.templatetags.credits import format_page_count

CREATOR_CREDIT_HELP = 'The %s and similar credits for this sequence, where ' \
  'multiple credits are separated with semicolons. If the credit applies to' \
  ' this sequence type but the creator is unknown, enter a question mark.'
NO_CREATOR_CREDIT_HELP = 'Check this box if %s does not apply to this ' \
                'sequence%s and leave the %s field blank. '
GENERIC_ERROR_MESSAGE = 'Please correct the field errors.  Scroll down to see '\
                        'the specific error message(s) next to each field.'

DOC_URL = 'http://docs.comics.org/wiki/'

PUBLISHER_HELP_LINKS = {
    'name' : 'Publisher_Name',
    'year_began': 'Years_of_Publication',
    'year_ended': 'Years_of_Publication',
    'year_began_uncertain': 'Years_of_Publication',
    'year_ended_uncertain': 'Years_of_Publication',
    'country': 'Country',
    'url': 'URL',
    'notes': 'Notes_%28on_Publisher_Screen%29',
    'keywords': 'Keywords',
    'comments': 'Comments '
}

BRAND_HELP_LINKS = {
    'name' : 'Brand',
    'year_began': 'Years_of_Use_%28Brand%29',
    'year_ended': 'Years_of_Use_%28Brand%29',
    'year_began_uncertain': 'Years_of_Use_%28Brand%29',
    'year_ended_uncertain': 'Years_of_Use_%28Brand%29',
    'url': 'URL_%28Brand%29',
    'notes': 'Notes_%28Brand%29',
    'keywords': 'Keywords',
    'comments': 'Comments '
}

INDICIA_PUBLISHER_HELP_LINKS = {
    'name' : 'Indicia_Publisher',
    'year_began': 'Years_of_Use_%28Indicia_publisher%29',
    'year_ended': 'Years_of_Use_%28Indicia_publisher%29',
    'year_began_uncertain': 'Years_of_Use_%28Indicia_publisher%29',
    'year_ended_uncertain': 'Years_of_Use_%28Indicia_publisher%29',
    'is_surrogate': 'Surrogate',
    'country': 'Country_%28Indicia_publisher%29',
    'url': 'URL_%28Indicia_publisher%29',
    'notes': 'Notes_%28Indicia_publisher%29',
    'keywords': 'Keywords',
    'comments': 'Comments '
}

ISSUE_HELP_LINKS = {
    'number': 'Issue_Numbers',
    'variant_name': 'Variant_Issues',
    'title': 'Issue_Title',
    'no_title': 'Issue_Title',
    'volume': 'Volume',
    'no_volume': 'Volume',
    'display_volume_with_number': 'Display_Volume_with_Issue_Number',
    'publication_date': 'Published_Date',
    'indicia_frequency': 'Indicia_frequency',
    'no_indicia_frequency': 'Indicia_frequency',
    'key_date': 'Keydate',
    'on_sale_date': 'On-sale_date',
    'year_on_sale': 'On-sale_date',
    'month_on_sale': 'On-sale_date',
    'day_on_sale': 'On-sale_date',
    'indicia_publisher': 'Indicia_publisher',
    'indicia_pub_not_printed': 'Indicia_publisher',
    'brand': 'Brand',
    'no_brand': 'Brand',
    'price': 'Cover_Price',
    'page_count': 'Page_Count',
    'page_count_uncertain': 'Page_Count',
    'editing': 'Editing',
    'no_editing': 'Editing',
    'isbn': 'ISBN',
    'no_isbn': 'ISBN',
    'barcode': 'Barcode',
    'no_barcode': 'Barcode',
    'rating': "Publisher's_Age_Guidelines",
    'no_rating': "Publisher's_Age_Guidelines",
    'notes': 'Notes_%28issue%29',
    'keywords': 'Keywords',
    'comments': 'Comments'
}

SEQUENCE_HELP_LINKS = {
    'type': 'Type',
    'title': 'Title',
    'title_inferred': 'Title',
    'feature': 'Feature',
    'page_count': 'Page_Count',
    'page_count_uncertain': 'Page_Count',
    'genre': 'Genre',
    'script': 'Script',
    'no_script': 'Script',
    'pencils': 'Pencils',
    'no_pencils': 'Pencils',
    'inks': 'Inks',
    'no_inks': 'Inks',
    'colors': 'Colors',
    'no_colors': 'Colors',
    'letters': 'Letters',
    'no_letters': 'Letters',
    'editing': 'Editing',
    'no_editing': 'Editing',
    'characters': 'Character_Appearances',
    'synopsis': 'Synopsis',
    'job_number': 'Job_Number',
    'reprint_notes': 'Reprints',
    'notes': 'Notes',
    'keywords': 'Keywords',
    'comments': 'Comments'
}

SERIES_HELP_LINKS = {
    'name': 'Book_Name',
    'leading_article': 'Book_Name',
    'year_began': 'Years_of_Publication',
    'year_began_uncertain': 'Years_of_Publication',
    'year_ended': 'Years_of_Publication',
    'year_ended_uncertain': 'Years_of_Publication',
    'is_current': 'Years_of_Publication',
    'country': 'Country',
    'language': 'Language',
    'tracking_notes': 'Tracking',
    'notes': 'Series_Notes',
    'keywords': 'Keywords',
    'format': 'Format',
    'color': 'Format',
    'dimensions': 'Format',
    'paper_stock': 'Format',
    'binding': 'Format',
    'publishing_format': 'Format',
    'is_comics_publication': 'Comics_Publication',
    'is_singleton': 'Is_Singleton',
    'publication_type': 'Publication_Type',
    'has_barcode': 'Barcode',
    'has_indicia_frequency': 'Indicia_frequency',
    'has_isbn': 'ISBN',
    'has_issue_title': 'Issue_Title',
    'has_rating': "Publisher's_Age_Guidelines",
    'has_volume': 'Volume',
    'comments': 'Comments'
}

def _set_help_labels(self, help_links):
    for field in self.fields:
        if field in help_links:
            if not self.fields[field].label:
                label =  forms.forms.pretty_name(field)
            else:
                label = self.fields[field].label
            self.fields[field].label = mark_safe(label + \
              u' <a href="%s%s" target=_blank>[?]</a>' %
              (DOC_URL, help_links[field]))

def _init_no_isbn(series, revision):
    """
    Set nice defaults for the no_isbn flag if we can figure out when this is.
    """
    if revision is not None and revision.issue is not None:
        return revision.issue.no_isbn

    if series.year_ended and series.year_ended < 1970:
        return True

    return False

def _init_no_barcode(series, revision):
    """
    Set nice defaults for the no_barcode flag if we can figure out when this is.
    """
    if revision is not None and revision.issue is not None:
        return revision.issue.no_barcode

    if series.year_ended and series.year_ended < 1974:
        return True

    return False

class HiddenInputWithHelp(forms.TextInput):
    input_type = 'hidden'

    def __init__(self, *args, **kwargs):
        super(HiddenInputWithHelp, self).__init__(*args, **kwargs)
        self.attrs = kwargs.get('attrs', {})
        self.key = self.attrs.get('key', False)

    def render(self, name, value, *args, **kwargs):
        return mark_safe(super(HiddenInputWithHelp, self).render(name, value,
                                                                 self.attrs))

def _get_comments_form_field():
    return forms.CharField(widget=forms.Textarea, required=False,
      help_text='Comments about the change. These are part of the change '
                'history, but not part of the regular display.')

def _clean_keywords(cleaned_data):
    keywords = cleaned_data['keywords']
    if keywords != None:
        not_allowed = False
        for c in ['<', '>', '{', '}', ':', '/', '\\', '|', '@' , ',']:
            if c in keywords:
                not_allowed = True
                break
        if not_allowed:
            raise forms.ValidationError('The following characters are '
            'not allowed in a keyword: < > { } : / \ | @ ,')

    return keywords


class PageCountInput(TextInput):
    def render(self, name, value, attrs=None):
        value = format_page_count(value)
        return super(PageCountInput, self).render(name, value, attrs)

def get_revision_form(revision=None, model_name=None, **kwargs):
    if revision is not None and model_name is None:
        model_name = revision.source_name

    if model_name == 'publisher':
        source = None
        if revision is not None:
            source = revision.source
        return get_publisher_revision_form(source=source, **kwargs)

    if model_name == 'indicia_publisher':
        source = None
        if revision is not None:
            source = revision.source
        return get_indicia_publisher_revision_form(source=source, **kwargs)

    if model_name == 'brand_group':
        return get_brand_group_revision_form(**kwargs)

    if model_name == 'brand':
        return get_brand_revision_form(revision=revision, **kwargs)

    if model_name == 'brand_use':
        return get_brand_use_revision_form(**kwargs)

    if model_name == 'series':
        if revision is None:
            return get_series_revision_form(**kwargs)
        if 'publisher' not in kwargs:
            kwargs['publisher'] = revision.publisher
        return get_series_revision_form(source=revision.source, **kwargs)

    if model_name == 'series_bond':
        return get_series_bond_revision_form(**kwargs)

    if model_name == 'issue':
        if revision is not None and 'publisher' not in kwargs:
            kwargs['publisher'] = revision.series.publisher
        return get_issue_revision_form(revision=revision, **kwargs)

    if model_name == 'story':
        return get_story_revision_form(revision, **kwargs)

    if model_name == 'reprint':
        return get_reprint_revision_form(revision, **kwargs)

    if model_name in ['cover', 'image']:
        return get_cover_revision_form(revision, **kwargs)

    raise NotImplementedError

class ForeignKeyField(forms.IntegerField):
    def __init__(self, queryset, target_name=None, **kwargs):
        forms.IntegerField.__init__(self, **kwargs)
        self.queryset = queryset
        if target_name is not None:
            self.target_name = target_name

    def clean(self, value):
        id = forms.IntegerField.clean(self, value)
        if id is None:
            return id
        try:
            return self.queryset.get(id=id)
        except ObjectDoesNotExist:
            raise forms.ValidationError, ("%d is not the ID of a valid %s" %
                               (id, self.target_name))
        except MultipleObjectsReturned:
            raise forms.ValidationError, (
              "%d matched multiple instances of %s" % (id, self.target_name))

class OngoingReservationForm(forms.ModelForm):
    class Meta:
        model = OngoingReservation
        fields = ('series',)
    series = ForeignKeyField(
      queryset=Series.objects.filter(ongoing_reservation__isnull=True,
                                     is_current=True),
      target_name='Available Series',
      help_text='The numeric database ID of a '
                'series that does not already '
                'have an ongoing reservation')

def get_publisher_revision_form(source=None, user=None):
    class RuntimePublisherRevisionForm(PublisherRevisionForm):
        if source is not None:
            # Don't allow country to be un-set:
            if source.country.code == 'xx':
                country_queryset = Country.objects.all()
            else:
                country_queryset = Country.objects.exclude(code='xx')
            country = forms.ModelChoiceField(queryset=country_queryset,
                                             empty_label=None)
        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, PUBLISHER_HELP_LINKS)
            return super(RuntimePublisherRevisionForm, self).as_table()
    return RuntimePublisherRevisionForm

def _get_publisher_fields(middle=None):
    first = ['name', 'year_began', 'year_began_uncertain',
                     'year_ended', 'year_ended_uncertain']
    last = ['url', 'notes', 'keywords']
    if middle is not None:
        first.extend(middle)
    first.extend(last)
    return first

class PublisherRevisionForm(forms.ModelForm):
    class Meta:
        model = PublisherRevision
        fields = _get_publisher_fields(middle=('country',))
        widgets = {'name': forms.TextInput(attrs={'autofocus':''})}

    country = forms.ModelChoiceField(queryset=Country.objects.exclude(code='xx'))
    comments = _get_comments_form_field()

    def clean_keywords(self):
        return _clean_keywords(self.cleaned_data)

    def clean(self):
        cd = self.cleaned_data
        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        if 'name' in cd:
            cd['name'] = cd['name'].strip()
        cd['notes'] = cd['notes'].strip()
        cd['comments'] = cd['comments'].strip()
        return cd

def get_indicia_publisher_revision_form(source=None, user=None):
    class RuntimeIndiciaPublisherRevisionForm(IndiciaPublisherRevisionForm):
        if source is not None:
            # Don't allow country to be un-set:
            country = forms.ModelChoiceField(empty_label=None,
              queryset=Country.objects.exclude(code='xx'))
        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, INDICIA_PUBLISHER_HELP_LINKS)
            return super(RuntimeIndiciaPublisherRevisionForm, self).as_table()
    return RuntimeIndiciaPublisherRevisionForm

class IndiciaPublisherRevisionForm(PublisherRevisionForm):
    class Meta:
        model = IndiciaPublisherRevision
        fields = _get_publisher_fields(middle=('is_surrogate', 'country'))

    name = forms.CharField(widget=forms.TextInput(attrs={'autofocus':''}),
      max_length=255, required=True,
      help_text='The name exactly as it appears in the indicia or colophon, '
                'including punctuation, abbreviations, suffixes like ", Inc.",'
                ' etc. Do not move articles to the end of the name.')

    is_surrogate = forms.BooleanField(required=False, label='Surrogate',
      help_text='Check if this was an independent company serving as a surrogate '
                'for the master publisher, rather than a company belonging to the '
                'master publisher.')

    def clean_keywords(self):
        return _clean_keywords(self.cleaned_data)

    def clean(self):
        cd = self.cleaned_data
        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        if 'name' in cd:
            cd['name'] = cd['name'].strip()
        cd['notes'] = cd['notes'].strip()
        cd['comments'] = cd['comments'].strip()
        return cd

def get_brand_group_revision_form(source=None, user=None):
    class RuntimeBrandGroupRevisionForm(BrandGroupRevisionForm):
        if source is None:
            name = forms.CharField(widget=forms.TextInput(attrs={'autofocus':''}),
              max_length=255, help_text='The name of the new brand group.')

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, BRAND_HELP_LINKS)
            return super(RuntimeBrandGroupRevisionForm, self).as_table()
    return RuntimeBrandGroupRevisionForm

class BrandGroupRevisionForm(forms.ModelForm):
    class Meta:
        model = BrandGroupRevision
        fields = _get_publisher_fields()

    name = forms.CharField(widget=forms.TextInput(attrs={'autofocus':''}),
      max_length=255, help_text='The name of the brand group.')

    year_began = forms.IntegerField(required=False,
      help_text='The first year the brand group was used.')
    year_began_uncertain = forms.BooleanField(required=False,
      help_text='Check if you are not certain of the first year the brand group '
                'was used.')

    year_ended = forms.IntegerField(required=False,
      help_text='The last year the brand group was used.  Leave blank if currently '
                'in use.')
    year_ended_uncertain = forms.BooleanField(required=False,
      help_text='Check if you are not certain of the last year the brand group '
                'was used, or if you are not certain whether it is still in use.')

    url = forms.URLField(required=False,
      help_text='The official web site of the brand.  Leave blank if the '
                'publisher does not have a specific web site for the brand group.')

    comments = _get_comments_form_field()

    def clean_keywords(self):
        return _clean_keywords(self.cleaned_data)

    def clean(self):
        cd = self.cleaned_data
        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        if 'name' in cd:
            cd['name'] = cd['name'].strip()
        cd['notes'] = cd['notes'].strip()
        cd['comments'] = cd['comments'].strip()
        return cd

def get_brand_revision_form(source=None, user=None, revision=None,
                            brand_group=None, publisher=None):
    initial = []
    groups = None

    if revision and revision.source:
        publishers = revision.source.in_use.all().values_list('publisher_id',
                                                              flat=True)
        groups = BrandGroup.objects.filter(parent__in=publishers, deleted=False)
    elif publisher:
        groups = BrandGroup.objects.filter(parent=publisher.id, deleted=False)

    if groups:
        choices = [[g.id, g] for g in groups]
    elif brand_group:
        initial = [brand_group.id]
        choices = [[brand_group.id, brand_group]]
    else:
        choices = []

    if revision and revision.group.count():
        for group in revision.group.all():
            if [group.id, group] not in choices:
                choices.append([group.id, group])

    class RuntimeBrandRevisionForm(BrandRevisionForm):
        def __init__(self, *args, **kw):
            super(BrandRevisionForm, self).__init__(*args, **kw)
            # brand_group_other_publisher_id is last field, move it after group
            self.fields.keyOrder.insert(self.fields.keyOrder.index('group') + 1,
                                        self.fields.keyOrder.pop())

        group = forms.MultipleChoiceField(required=True,
            widget=FilteredSelectMultiple('Brand Groups', False),
            choices=choices, initial=initial)
        # maybe only allow editors this to be less confusing to normal indexers
        brand_group_other_publisher_id = forms.IntegerField(required=False,
          label = "Add Brand Group",
          help_text="One can add a brand group from a different publisher by "
            "id. If an id is entered the submit will return for confirmation.")

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, BRAND_HELP_LINKS)
            return super(RuntimeBrandRevisionForm, self).as_table()
    return RuntimeBrandRevisionForm

class BrandRevisionForm(forms.ModelForm):
    class Meta:
        model = BrandRevision
        fields = _get_publisher_fields(middle=('group',))

    name = forms.CharField(widget=forms.TextInput(attrs={'autofocus':''}),
      max_length=255,
      help_text='The name of the brand emblem as it appears on the logo.  If '
                'the logo does not use words, then the name of the brand as '
                'it is commonly used.  Consult an editor if in doubt.')

    year_began = forms.IntegerField(required=False,
      help_text='The first year the brand emblem was used.')
    year_began_uncertain = forms.BooleanField(required=False,
      help_text='Check if you are not certain of the first year the brand '
                'emblem was used.')

    year_ended = forms.IntegerField(required=False,
      help_text='The last year the brand emblem was used.  Leave blank if '
                'currently in use.')
    year_ended_uncertain = forms.BooleanField(required=False,
      help_text='Check if you are not certain of the last year the brand emblem '
                'was used, or if you are not certain whether it is still in use.')

    url = forms.URLField(required=False,
      help_text='The official web site of the brand.  Leave blank if the '
                'publisher does not have a specific web site for the brand.')

    comments = _get_comments_form_field()

    def clean_keywords(self):
        return _clean_keywords(self.cleaned_data)

    def clean(self):
        cd = self.cleaned_data
        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        if 'name' in cd:
            cd['name'] = cd['name'].strip()
        cd['notes'] = cd['notes'].strip()
        cd['comments'] = cd['comments'].strip()
        if cd['brand_group_other_publisher_id']:
            brand_group = BrandGroup.objects.filter( \
              id=cd['brand_group_other_publisher_id'], deleted=False)
            if brand_group:
                brand_group = brand_group[0]
                # need to add directly to revision, otherwise validation fails
                self.instance.group.add(brand_group)
                choices = self.fields['group'].choices
                choices.append([brand_group.id, brand_group])
                # self.data is immutable, need copy
                data = self.data.copy()
                data['brand_group_other_publisher_id'] = None
                self.data = data
                # need to update with new choices
                self.fields['group'] = forms.MultipleChoiceField(required=True,
                    widget=FilteredSelectMultiple('Brand Groups', False),
                    choices=choices)
                # TODO maybe do this differently
                raise forms.ValidationError( \
                  "Please confirm selection of brand group '%s'." % brand_group)
            else:
                raise forms.ValidationError( \
                  "A brand group with id %d does not exist." % \
                  cd['brand_group_other_publisher_id'])
        return cd

def get_brand_use_revision_form(source=None, user=None):
    class RuntimeBrandUseRevisionForm(BrandUseRevisionForm):
        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, BRAND_HELP_LINKS)
            return super(RuntimeBrandUseRevisionForm, self).as_table()
    return RuntimeBrandUseRevisionForm

class BrandUseRevisionForm(forms.ModelForm):
    class Meta:
        model = BrandUseRevision
        fields = get_brand_use_field_list()

    year_began = forms.IntegerField(required=False,
      help_text='The first year the brand was at the publisher.')
    year_began_uncertain = forms.BooleanField(required=False,
      help_text='Check if you are not certain of the first year the brand '
                'was used.')

    year_ended = forms.IntegerField(required=False,
      help_text='The last year the brand was used at the publisher. '
                ' Leave blank if currently in use.')
    year_ended_uncertain = forms.BooleanField(required=False,
      help_text='Check if you are not certain of the last year the brand '
                'was used, or if you are not certain whether it is still in use.')

    comments = _get_comments_form_field()

    def clean(self):
        cd = self.cleaned_data
        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        cd['notes'] = cd['notes'].strip()
        cd['comments'] = cd['comments'].strip()
        return cd

def get_series_revision_form(publisher=None, source=None, user=None):
    if source is None:
        if user is not None and user.indexer.can_reserve_another_ongoing():
            can_request = True
        else:
            can_request = False

        class RuntimeAddSeriesRevisionForm(SeriesRevisionForm):
            class Meta:
                model = SeriesRevisionForm.Meta.model
                fields = SeriesRevisionForm.Meta.fields
                exclude = SeriesRevisionForm.Meta.exclude + ['imprint', 'format']
                widgets = SeriesRevisionForm.Meta.widgets
                if can_request:
                    fields = ['reservation_requested'] + fields

            if can_request:
                reservation_requested = forms.BooleanField(required=False,
                  label = 'Request reservation',
                  help_text='Check this box to have the ongoing reservation for '
                            'this series assigned to you when it is approved, '
                            'unless you have gone over your ongoing reservation '
                            'limit at that time.')

            def as_table(self):
                if not user or user.indexer.show_wiki_links:
                    _set_help_labels(self, SERIES_HELP_LINKS)
                return super(SeriesRevisionForm, self).as_table()

        return RuntimeAddSeriesRevisionForm

    else:
        class RuntimeSeriesRevisionForm(SeriesRevisionForm):
            class Meta:
                model = SeriesRevisionForm.Meta.model
                fields = SeriesRevisionForm.Meta.fields
                exclude = SeriesRevisionForm.Meta.exclude
                exclude = exclude + ['imprint']
                if not source.format:
                    exclude = exclude + ['format']
                widgets = SeriesRevisionForm.Meta.widgets

            def __init__(self, *args, **kwargs):
                # Don't allow country and language to be un-set:
                super(RuntimeSeriesRevisionForm, self).__init__(*args, **kwargs)
                self.fields['country'].empty_label = None
                self.fields['language'].empty_label = None

            if user.has_perm('gcd.can_approve'):
                move_to_publisher_with_id = forms.IntegerField(required=False,
                  help_text="Only editors can move a series. A confirmation "
                    "page will follow to confirm the move.<br>"
                    "The move of a series is only possible if no issues are "
                    "reserved. Brand and indicia publisher entries of the "
                    "issues will be reset. ")

            if source.format:
                format = forms.CharField(required=False,
                  widget=forms.TextInput(attrs={'class': 'wide'}),
                  help_text='This field is DEPRECATED.  Please move the '
                            'contents to the appropriate more specific fields '
                            '(color, dimensions, paper stock, binding, or '
                            'publishing format) or into the notes field if the '
                            'information does not fit anywhere else.')
            def as_table(self):
                if not user or user.indexer.show_wiki_links:
                    _set_help_labels(self, SERIES_HELP_LINKS)
                return super(SeriesRevisionForm, self).as_table()

        return RuntimeSeriesRevisionForm

class SeriesRevisionForm(forms.ModelForm):

    class Meta:
        model = SeriesRevision
        fields = get_series_field_list()
        exclude = ['publisher',]
        widgets = {
          'name': forms.TextInput(attrs={'class': 'wide', 'autofocus':''}),
          'year_began': forms.TextInput(attrs={'class': 'year'}),
          'year_ended': forms.TextInput(attrs={'class': 'year'}),
          'color': forms.TextInput(attrs={'class': 'wide'}),
          'dimensions': forms.TextInput(attrs={'class': 'wide'}),
          'paper_stock': forms.TextInput(attrs={'class': 'wide'}),
          'binding': forms.TextInput(attrs={'class': 'wide'}),
          'publishing_format': forms.TextInput(attrs={'class': 'wide'})
        }

    def __init__(self, *args, **kwargs):
        super(SeriesRevisionForm, self).__init__(*args, **kwargs)
        self.fields['country'].queryset = Country.objects.exclude(code='xx')


    comments = _get_comments_form_field()

    def clean_keywords(self):
        return _clean_keywords(self.cleaned_data)

    def clean(self):
        cd = self.cleaned_data
        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        if 'name' in cd:
            cd['name'] = cd['name'].strip()
            if (cd['leading_article'] and
                cd['name'] == remove_leading_article(cd['name'])):
                raise forms.ValidationError('The series name is only one word,'
                    ' you cannot specify a leading article in this case.')

        if 'format' in cd:
            cd['format'] = cd['format'].strip()
        cd['color'] = cd['color'].strip()
        cd['dimensions'] = cd['dimensions'].strip()
        cd['paper_stock'] = cd['paper_stock'].strip()
        cd['binding'] = cd['binding'].strip()
        cd['publishing_format'] = cd['publishing_format'].strip()
        cd['comments'] = cd['comments'].strip()
        if 'reservation_requested' in cd and cd['reservation_requested'] and \
            (not cd['is_current'] and not cd['is_singleton']):
            raise forms.ValidationError('A reservation can only be requested'
                    ' for currently ongoing series.')
        # some status checks for singleton series
        if cd['is_singleton'] and cd['has_issue_title']:
            raise forms.ValidationError('Singleton series cannot have '
              'an issue title.')
        if cd['is_singleton'] and cd['notes']:
            raise forms.ValidationError('Notes for singleton series are '
              'stored on the issue level.')
        if cd['is_singleton'] and cd['tracking_notes']:
            raise forms.ValidationError('Singleton series cannot have '
              'tracking notes.')
        if cd['is_singleton'] and cd['is_current']:
            raise forms.ValidationError('Singleton series do not continue '
              'and therefore cannot be current in our sense.')
        if cd['is_singleton'] and 'reservation_requested' in cd and \
          cd['reservation_requested']:
            raise forms.ValidationError('Reservations for the created issue '
              'of a singleton series are not supported for technical reasons.')

        # TODO How to get to series ? 
        # Then we could check the number of issues for singletons
        return cd

def _get_series_has_fields_off_note(series, field):
    return 'The %s field is turned off for %s. To enter a value for %s this ' \
           'setting for the series has to be changed.' % (field, series, field), \
           forms.BooleanField(widget=forms.HiddenInput, required=False)

class BrandEmblemSelect(forms.Select):
    def render_option(self, selected_choices, option_value, option_label):
        url = ''
        if option_value:
            brand = Brand.objects.get(id=option_value)
            if brand.emblem:
                url = brand.emblem.icon.url
        option_value = force_unicode(option_value)
        if option_value in selected_choices:
            selected_html = u' selected="selected"'
            if not self.allow_multiple_selected:
                # Only allow for a single selection.
                selected_choices.remove(option_value)
        else:
            selected_html = ''
        if url:
            return u'<option value="%s"%s data-image="%s" image-width="%d">' \
              '%s</option>' % (
              escape(option_value), selected_html, url, brand.emblem.icon.width,
              conditional_escape(force_unicode(option_label)))
        else:
            return u'<option value="%s"%s>%s</option>' % (
              escape(option_value), selected_html,
              conditional_escape(force_unicode(option_label)))


def get_series_bond_revision_form(revision=None, user=None):
    class RuntimeSeriesBondRevisionForm(SeriesBondRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeSeriesBondRevisionForm, self).__init__(*args, **kwargs)
            self.fields['bond_type'].queryset = \
                SeriesBondType.objects.filter(id__in=BOND_TRACKING)
        def as_table(self):
            # TODO: add help links
            return super(RuntimeSeriesBondRevisionForm, self).as_table()
    return RuntimeSeriesBondRevisionForm

class SeriesBondRevisionForm(forms.ModelForm):
    class Meta:
        model = SeriesBondRevision
        fields = get_series_bond_field_list()
        widgets = {
          'notes': forms.TextInput(attrs={'class': 'wide'})
        }

    comments = _get_comments_form_field()

def get_issue_revision_form(publisher, series=None, revision=None,
                            variant_of=None, user=None):
    if series is None and revision is not None:
        series = revision.series
    if revision is not None and revision.variant_of:
        variant_of = revision.variant_of

    class RuntimeIssueRevisionForm(IssueRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeIssueRevisionForm, self).__init__(*args, **kwargs)
            self.fields['brand'].queryset = \
              series.publisher.active_brand_emblems_no_pending()
            self.fields['indicia_publisher'].queryset = \
              series.publisher.active_indicia_publishers_no_pending()

            issue_year = None
            if revision and revision.key_date:
                issue_year = int(revision.key_date[:4])
            elif revision and revision.year_on_sale and \
                int(log10(revision.year_on_sale)) + 1 == 4:
                issue_year = revision.year_on_sale
            if issue_year:
                brands = self.fields['brand'].queryset
                brands = brands.filter(in_use__year_began__lte=issue_year,
                                in_use__year_ended=None,
                                in_use__publisher__id=series.publisher.id) | \
                         brands.filter(in_use__year_began=None,
                                in_use__year_ended__gte=issue_year,
                                in_use__publisher__id=series.publisher.id) | \
                         brands.filter(in_use__year_began=None,
                                in_use__year_ended=None,
                                in_use__publisher__id=series.publisher.id) | \
                         brands.filter(in_use__year_began__lte=issue_year,
                                in_use__year_ended__gte=issue_year,
                                in_use__publisher__id=series.publisher.id)
                self.fields['brand'].queryset = brands.distinct()
                self.fields['indicia_publisher'].queryset = \
                    self.fields['indicia_publisher'].queryset\
                    .exclude(year_ended__lt=issue_year)
                self.fields['indicia_publisher'].queryset = \
                    self.fields['indicia_publisher'].queryset\
                    .exclude(year_began__gt=issue_year)
            else:
                if series.year_began:
                    self.fields['brand'].queryset = \
                    self.fields['brand'].queryset\
                    .exclude(year_ended__lt=series.year_began)
                    self.fields['indicia_publisher'].queryset = \
                    self.fields['indicia_publisher'].queryset\
                    .exclude(year_ended__lt=series.year_began)
                if series.year_ended:
                    self.fields['brand'].queryset = \
                    self.fields['brand'].queryset\
                    .exclude(year_began__gt=series.year_ended)
                    self.fields['indicia_publisher'].queryset = \
                    self.fields['indicia_publisher'].queryset\
                    .exclude(year_began__gt=series.year_ended)
            if revision:
                if revision.brand and revision.brand not in self.fields['brand'].queryset:
                    self.fields['brand'].queryset = self.fields['brand'].queryset \
                      | Brand.objects.filter(id=revision.brand.id).distinct()
                if revision.indicia_publisher and revision.indicia_publisher not in \
                  self.fields['indicia_publisher'].queryset:
                    self.fields['indicia_publisher'].queryset = \
                      self.fields['indicia_publisher'].queryset \
                      | IndiciaPublisher.objects.filter(id=revision.indicia_publisher.id)

            self.fields['no_isbn'].initial = _init_no_isbn(series, None)
            self.fields['no_barcode'].initial = _init_no_barcode(series, None)

        turned_off_list = ''

        if not series.has_issue_title:
            no_title = forms.BooleanField(widget=forms.HiddenInput,
                                          required=False)
            title = forms.CharField(widget=HiddenInput, required=False)
            turned_off_list += 'title, '

        if not series.has_volume:
            no_volume = forms.BooleanField(widget=forms.HiddenInput,
                                          required=False)
            display_volume_with_number = forms.BooleanField(\
              widget=forms.HiddenInput, required=False)
            volume = forms.CharField(widget=HiddenInput, required=False)
            turned_off_list += 'volume, '

        if not series.has_indicia_frequency:
            no_indicia_frequency = forms.BooleanField(widget=forms.HiddenInput,
                                                      required=False)
            indicia_frequency = forms.CharField(widget=HiddenInput,
                                                required=False)
            turned_off_list += 'indicia_frequency, '

        if not series.has_isbn:
            no_isbn = forms.BooleanField(widget=forms.HiddenInput,
                                          required=False)
            isbn = forms.CharField(widget=HiddenInput, required=False)
            turned_off_list += 'isbn, '

        if not series.has_barcode:
            no_barcode = forms.BooleanField(widget=forms.HiddenInput,
                                          required=False)
            barcode = forms.CharField(widget=HiddenInput, required=False)
            turned_off_list += 'barcode, '

        if not series.has_rating:
            no_rating = forms.BooleanField(widget=forms.HiddenInput,
                                          required=False)
            rating = forms.CharField(widget=HiddenInput, required=False)
            turned_off_list += 'publisher age guidelines'

        if turned_off_list:
            turned_off_help = forms.CharField(widget=HiddenInputWithHelp,
              required=False, label='Deactivated fields',
              help_text='The fields "%s" are deactivated for this series. To '
                        'enter a value for one of these the corresponding '
                        'series setting has to be changed.' % turned_off_list)

        def clean_year_on_sale(self):
            year_on_sale = self.cleaned_data['year_on_sale']
            year_string = str(year_on_sale)[:2]
            if year_on_sale != None and (year_string < '18' or year_string > '20'):
                raise forms.ValidationError('Unreasonable year entered.')
            return year_on_sale

        def clean_month_on_sale(self):
            month_on_sale = self.cleaned_data['month_on_sale']

            if month_on_sale != None and not month_on_sale in range(1,13):
                raise forms.ValidationError(
                  'If entered, month needs to be between 1 and 12.')
            return month_on_sale

        def clean_day_on_sale(self):
            day_on_sale = self.cleaned_data['day_on_sale']

            if day_on_sale != None and not day_on_sale in range(1,32):
                raise forms.ValidationError(
                  'If entered, day needs to be between 1 and 31.')
            return day_on_sale

        def clean_key_date(self):
            key_date = self.cleaned_data['key_date']
            if key_date != None:
                key_date = key_date.replace('.', '-')
            return key_date

        def clean_keywords(self):
            return _clean_keywords(self.cleaned_data)

        def clean(self):
            cd = self.cleaned_data

            if self._errors:
                raise forms.ValidationError(GENERIC_ERROR_MESSAGE)

            cd['number'] = cd['number'].strip()
            cd['volume'] = cd['volume'].strip()
            cd['publication_date'] = cd['publication_date'].strip()
            cd['key_date'] = cd['key_date'].strip()
            cd['indicia_frequency'] = cd['indicia_frequency'].strip()
            cd['price'] = cd['price'].strip()
            cd['editing'] = cd['editing'].strip()
            cd['notes'] = cd['notes'].strip()
            cd['comments'] = cd['comments'].strip()
            cd['isbn'] = cd['isbn'].strip()

            if cd['volume'] != "" and cd['no_volume']:
                raise forms.ValidationError('You cannot specify a volume and '
                  'check "no volume" at the same time')

            if cd['no_title'] and cd['title']:
                raise forms.ValidationError(
                  'You cannot specify a title and check "no title" at the '
                  'same time.')

            if cd['editing'] != "" and cd['no_editing']:
                raise forms.ValidationError('You cannot specify an editing '
                  'credit and check "no editing" at the same time')

            if cd['no_brand'] and cd['brand'] is not None:
                raise forms.ValidationError(
                  'You cannot specify a brand and check "no brand" at the '
                  'same time.')

            if cd['no_indicia_frequency'] and cd['indicia_frequency']:
                raise forms.ValidationError(
                  'You cannot specify an indicia frequency and check '
                  '"no indicia frequency" at the same time.')

            if cd['no_isbn'] and cd['isbn']:
                raise forms.ValidationError(
                  'You cannot specify an isbn and check "no isbn" at the '
                  'same time.')

            if cd['on_sale_date'] and (cd['year_on_sale'] or \
                                       cd['month_on_sale'] or \
                                       cd['day_on_sale']):
                raise forms.ValidationError(
                  'You can only use either the on-sale date-field or the '
                  'three separate date fields, not both data entering options.')
            elif cd['on_sale_date']:
                # only full dates can be entered this way
                if cd['on_sale_date'].year < 1800 or \
                  cd['on_sale_date'].year >= 2100:
                    raise forms.ValidationError('Unreasonable year entered.')
                cd['year_on_sale'] = cd['on_sale_date'].year
                cd['month_on_sale'] = cd['on_sale_date'].month
                cd['day_on_sale'] = cd['on_sale_date'].day

            if cd['page_count_uncertain'] and not cd['page_count']:
                raise forms.ValidationError('You cannot check page count '
                  'uncertain without a page count.')

            if cd['no_barcode'] and cd['barcode']:
                raise forms.ValidationError(
                  'You cannot specify a barcode and check "no barcode" at '
                  'the same time.')

            if cd['barcode']:
                cd['barcode'] = cd['barcode'].replace('-', '').replace(' ', '')
                cd['barcode'] = cd['barcode'].replace(';', '; ')

            if cd['no_rating'] and cd['rating']:
                raise forms.ValidationError(
                  "You cannot specify a publisher's age guideline and check "
                  " no publisher's age guideline at the same time.")

            return cd

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, ISSUE_HELP_LINKS)
            return super(RuntimeIssueRevisionForm, self).as_table()

    if variant_of:
        class RuntimeAddVariantIssueRevisionForm(RuntimeIssueRevisionForm):
            class Meta:
                model = IssueRevision
                fields = RuntimeIssueRevisionForm.Meta.fields
                fields = fields[0:1] + ['variant_name'] + fields[1:]
                if revision is None or revision.source is None:
                    fields = ['after'] + fields
                widgets = RuntimeIssueRevisionForm.Meta.widgets
                widgets['variant_name'] = forms.TextInput(attrs={'class': 'wide'})
            def __init__(self, *args, **kwargs):
                super(RuntimeAddVariantIssueRevisionForm, self)\
                  .__init__(*args, **kwargs)
                # can add after one of the variants
                # TODO where to put later printings which come out later
                if 'after' in self.fields:
                    self.fields['after'].queryset = variant_of.variant_set.filter(deleted=False) \
                      | Issue.objects.filter(id=variant_of.id)
                    self.fields['after'].empty_label = None
                widgets = RuntimeIssueRevisionForm.Meta.widgets

        return RuntimeAddVariantIssueRevisionForm

    if revision is None or revision.source is None:
        class RuntimeAddIssueRevisionForm(RuntimeIssueRevisionForm):
            class Meta:
                model = IssueRevision
                fields = RuntimeIssueRevisionForm.Meta.fields
                fields = ['after'] + fields
                if series.get_ongoing_reservation() is None:
                    fields = ['reservation_requested'] + fields
                widgets = RuntimeIssueRevisionForm.Meta.widgets

            def __init__(self, *args, **kwargs):
                super(RuntimeAddIssueRevisionForm, self).__init__(*args, **kwargs)
                self.fields['after'].queryset = series.active_issues()
                self.fields['after'].empty_label = '[add as first issue]'

        return RuntimeAddIssueRevisionForm

    # the other issuerevision from 'variant_add' was taken care of above
    if revision.changeset.change_type == CTYPES['variant_add'] or \
      revision.issue.variant_set.count():
        class RuntimeBaseIssueRevisionForm(RuntimeIssueRevisionForm):
            class Meta:
                model = IssueRevision
                fields = RuntimeIssueRevisionForm.Meta.fields
                fields = fields[0:1] + ['variant_name'] + fields[1:]
                widgets = RuntimeIssueRevisionForm.Meta.widgets
                widgets['variant_name'] = forms.TextInput(attrs={'class': 'wide'})
        return RuntimeBaseIssueRevisionForm

    return RuntimeIssueRevisionForm

class IssueRevisionForm(forms.ModelForm):
    class Meta:
        model = IssueRevision
        fields = get_issue_field_list()
        fields.insert(fields.index('year_on_sale'), 'on_sale_date_help')
        fields.insert(fields.index('year_on_sale'), 'on_sale_date')
        fields.insert(fields.index('keywords') + 1, 'turned_off_help')
        widgets = {
          'number': forms.TextInput(attrs={'class': 'wide', 'autofocus':''}),
          'title': forms.TextInput(attrs={'class': 'wide'}),
          'volume': forms.TextInput(attrs={'class': 'wide'}),
          'key_date': forms.TextInput(attrs={'class': 'key_date'}),
          'indicia_frequency': forms.TextInput(attrs={'class': 'wide'}),
          'price': forms.TextInput(attrs={'class': 'wide'}),
          'editing': forms.TextInput(attrs={'class': 'wide' }),
          'isbn': forms.TextInput(attrs={'class': 'wide'}),
          'barcode': forms.TextInput(attrs={'class': 'wide'}),
          'page_count': PageCountInput,
          'brand': BrandEmblemSelect
        }

    comments = _get_comments_form_field()
    turned_off_help = forms.CharField(widget=HiddenInput)
    on_sale_date_help = forms.CharField(widget=HiddenInputWithHelp,
                                        required=False, label='',
      help_text='The on-sale (shipping) date can be entered in two ways: '
                'Either in the next field as YYYY-MM-DD, where all parts need '
                ' to be entered, or using the following three fields. If only'
                ' partial information is known you need to use the second '
                'option and enter the part of the date which is known. '
                'If you only know the decade you can enter the first three '
                'digits, e.g. 199 for the decade 1990-1999.')
    on_sale_date = forms.DateField(required=False, input_formats=['%Y-%m-%d'])

def get_bulk_issue_revision_form(series, method, user=None):
    if method == 'number':
        base = WholeNumberIssueRevisionForm
    elif method == 'volume':
        base = PerVolumeIssueRevisionForm
    elif method == 'year':
        base = PerYearIssueRevisionForm
    elif method == 'year_volume':
        base = PerYearVolumeIssueRevisionForm
    elif method == 'bulk_edit':
        base = BulkEditIssueRevisionForm
    else:
        return render_error(request, 'Unknown method of adding issues.')

    class RuntimeBulkIssueRevisionForm(base):
        def __init__(self, *args, **kwargs):
            super(RuntimeBulkIssueRevisionForm, self).__init__(*args, **kwargs)
            self.fields['brand'].queryset = \
              series.publisher.active_brand_emblems_no_pending()
            self.fields['indicia_publisher'].queryset = \
              series.publisher.active_indicia_publishers_no_pending()
            self.fields['no_isbn'].initial = _init_no_isbn(series, None)
            self.fields['no_barcode'].initial = _init_no_barcode(series, None)

        if method != 'bulk_edit':
            if not series.has_indicia_frequency:
                indicia_frequency = forms.CharField(widget=forms.HiddenInput,
                                                    required=False)
                no_indicia_frequency = forms.CharField(widget=forms.HiddenInput,
                                                    required=False)
            if not series.has_volume:
                volume = forms.CharField(widget=forms.HiddenInput,
                                         required=False)
                no_volume = forms.CharField(widget=forms.HiddenInput,
                                            required=False)
                display_volume_with_number = \
                  forms.CharField(widget=forms.HiddenInput, required=False)
            if not series.has_isbn:
                no_isbn = \
                  forms.CharField(widget=forms.HiddenInput, required=False)
            if not series.has_barcode:
                no_barcode = \
                  forms.CharField(widget=forms.HiddenInput, required=False)
            if not series.has_rating:
                rating = forms.CharField(widget=forms.HiddenInput,
                                         required=False)
                no_rating = \
                  forms.CharField(widget=forms.HiddenInput, required=False)

        after = forms.ModelChoiceField(required=False,
          queryset=Issue.objects.exclude(deleted=True).filter(series=series) \
            .order_by('sort_code'),
          empty_label="[add as initial issues]",
          label = "Add these issues after")

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, ISSUE_HELP_LINKS)
            return super(base, self).as_table()

    return RuntimeBulkIssueRevisionForm

class BulkIssueRevisionForm(forms.ModelForm):
    first_number = forms.IntegerField(required=False,
      help_text='If blank, starts with the number after the issue specified '
                'in the "Add issues after" field, or "1" if '
                'inserting issues at the beginning')

    number_of_issues = forms.IntegerField(min_value=1,
      widget=forms.TextInput(attrs={'autofocus':''}))

    comments = _get_comments_form_field()

    class Meta:
        model = IssueRevision
        fields = get_issue_field_list()
        exclude = ['number',]
        widgets = {
          'indicia_frequency': forms.TextInput(attrs={'class': 'wide'}),
          'editing': forms.TextInput(attrs={'class': 'wide'}),
          'page_count': PageCountInput,
          'brand': BrandEmblemSelect
        }

    def _shared_key_order(self):
        return ['indicia_publisher', 'indicia_pub_not_printed', 'brand',
                'no_brand', 'indicia_frequency', 'no_indicia_frequency',
                'price', 'page_count', 'page_count_uncertain',
                'editing', 'no_editing', 'no_isbn', 'no_barcode', 'rating',
                'no_rating', 'comments']

    def clean(self):
        cd = self.cleaned_data

        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)

        cd['indicia_frequency'] = cd['indicia_frequency'].strip()
        cd['price'] = cd['price'].strip()
        cd['editing'] = cd['editing'].strip()
        cd['comments'] = cd['comments'].strip()
        if 'volume' in cd:
            cd['volume'] = cd['volume'].strip()

            if cd['volume'] != "" and cd['no_volume']:
                raise forms.ValidationError('You cannot specify a volume and '
                    'check "no volume" at the same time')

        if cd['editing'] != "" and cd['no_editing']:
            raise forms.ValidationError('You cannot specify an editing credit and '
              'check "no editing" at the same time')

        if cd['no_brand'] and cd['brand'] is not None:
            raise forms.ValidationError(
              ['Brand field and No Brand checkbox cannot both be filled in.'])

        if cd['no_indicia_frequency'] and cd['indicia_frequency']:
            raise forms.ValidationError(
              ['Indicica Frequency field and No Indicia Frequency checkbox '
               'cannot both be filled in.'])

        if 'rating' in cd:
            cd['rating'] = cd['rating'].strip()

            if cd['rating'] != "" and cd['no_rating']:
                raise forms.ValidationError('You cannot specify a rating and '
                    'check "no rating" at the same time')

        return cd

class BulkEditIssueRevisionForm(BulkIssueRevisionForm):
    def __init__(self, *args, **kwargs):
        super(BulkEditIssueRevisionForm, self).__init__(*args, **kwargs)
        ordering = ['no_title', 'volume', 'display_volume_with_number',
                    'no_volume']
        ordering.extend(self._shared_key_order())
        self.fields.keyOrder = ordering

class WholeNumberIssueRevisionForm(BulkIssueRevisionForm):

    def __init__(self, *args, **kwargs):
        super(WholeNumberIssueRevisionForm, self).__init__(*args, **kwargs)
        ordering = ['after', 'number_of_issues', 'first_number',
                    'volume', 'display_volume_with_number', 'no_volume']
        ordering.extend(self._shared_key_order())
        self.fields.keyOrder = ordering

    def clean(self):
        cd = super(WholeNumberIssueRevisionForm, self).clean()

        if cd['first_number'] is None and cd['after'] is not None:
            try:
                cd['first_number'] = int(cd['after'].number) + 1
            except ValueError:
                raise forms.ValidationError('When adding new issues following  an '
                  'existing issue, the issue after which you are adding the new '
                  'issues must have a whole number as the issue number')
        elif cd['first_number'] is None:
            cd['first_number'] = 1

        return cd

class PerVolumeIssueRevisionForm(BulkIssueRevisionForm):
    first_volume = forms.IntegerField(required=False,
      help_text='If blank, first volume is calculated from the issue specified '
                'in the "Add issues after" field, or "1" if inserting at the '
                'beginning. Only numeric volumes allowed.')

    issues_per_volume = forms.IntegerField(min_value=1, initial=12,
      help_text='Number of issues in each volume')

    def __init__(self, *args, **kwargs):
        super(PerVolumeIssueRevisionForm, self).__init__(*args, **kwargs)
        ordering = ['after', 'number_of_issues', 'first_number',
                    'first_volume', 'issues_per_volume']
        ordering.extend(self._shared_key_order())
        self.fields.keyOrder = ordering

    def clean(self):
        cd = super(PerVolumeIssueRevisionForm, self).clean()

        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)

        basics = (cd['first_number'], cd['first_volume'])
        if None in basics and cd['after'] is not None:
            if filter(lambda x: x is not None, basics):
                raise forms.ValidationError('When adding issues following an '
                  'existing issue, both of "first number" and "first volume" '
                  'must be specified, or both must be left blank.')

        if cd['first_number'] is None and cd['after'] is not None:
            try:
                cd['first_number'] = ((int(cd['after'].number) + 1) %
                                      cd['issues_per_volume'])
                if cd['first_number'] == 0:
                    cd['first_number'] = cd['issues_per_volume']
            except ValueError:
                raise forms.ValidationError('When adding issues following an '
                  'existing issue, the issue after which you are inserting '
                  'the new issues must have a whole number for the issue '
                  'number (even if it displays like "v1#1")')

            if cd['after'].volume is None:
                raise forms.ValidationError('When adding issues following an '
                  'existing issue, the issue after which you are inserting '
                  'the new issues must have a volume.')

            cd['first_volume'] = cd['after'].volume
            if cd['first_number'] == 1:
                cd['first_volume'] += 1

        elif cd['after'] is None:
            if cd['first_number'] is None:
                cd['first_number'] = 1
            if cd['first_volume'] is None:
                cd['first_volume'] = 1

        return cd

class PerYearIssueRevisionForm(BulkIssueRevisionForm):
    first_number = forms.IntegerField(required=False,
      help_text='First issue number (the portion before the "/").  '
                'If blank, starts with the number after the issue specified '
                'in the "Add issues after" field, or "1" if inserting issues '
                'at the beginning.')
    first_year = forms.IntegerField(required=False,
      help_text='If blank, first year is calculated from the issue specified '
                'in the "Add issues after" field.  If inserting at the beginning '
                'of the series, this field is required')

    issues_per_year = forms.IntegerField(min_value=1, initial=12,
      help_text='Number of issues in each year')


    def __init__(self, *args, **kwargs):
        super(PerYearIssueRevisionForm, self).__init__(*args, **kwargs)
        ordering = ['after', 'number_of_issues',
                    'first_number', 'first_year', 'issues_per_year',
                    'volume', 'display_volume_with_number', 'no_volume']
        ordering.extend(self._shared_key_order())
        self.fields.keyOrder = ordering

    def clean(self):
        cd = super(PerYearIssueRevisionForm, self).clean()

        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)

        basics = (cd['first_number'], cd['first_year'])
        if None in basics and cd['after'] is not None:
            if filter(lambda x: x is not None, basics):
                raise forms.ValidationError('When adding issues following an '
                  'existing issue, both of "first number" and "first year" '
                  'must be specified, or both must be left blank.')

        if cd['after'] is None and cd['first_year'] is None:
            raise forms.ValidationError('When inserting issues at the beginning '
              'of a series, the first year must be specified.')

        if cd['first_number'] is None and cd['after'] is not None:
            cd = self._parse_year_and_number(cd, cd['issues_per_year'])
        elif cd['first_number'] is None:
            cd['first_number'] = 1

        return cd

    def _parse_year_and_number(self, cd, issues_per):
        previous = cd['after'].number
        m = re.match(r'(?P<number>\d+)/(?P<year>\d+)', previous)
        if m is None:
            raise forms.ValidationError('When adding based on the number of '
             'a previous issue, the issue must start with a number, then '
             'a forward slash, then a year, with no spaces: 1/1975')
        cd['first_number'] = ((int(m.group('number')) + 1) %
                              issues_per)
        if cd['first_number'] == 0:
            cd['first_number'] = issues_per

        cd['first_year'] = int(m.group('year'))
        if cd['first_number'] == 1:
            cd['first_year'] += 1
        return cd

class PerYearVolumeIssueRevisionForm(PerYearIssueRevisionForm):
    first_volume = forms.IntegerField(required=False,
      help_text='If blank, first volume is calculated from the issue specified '
                'in the "Add issues after" field, or "1" if inserting at the '
                'beginning. Only numeric volumes allowed.')

    issues_per_cycle = forms.IntegerField(min_value=1, initial=12,
      help_text='Number of issues in each year/volume')

    def __init__(self, *args, **kwargs):
        super(PerYearIssueRevisionForm, self).__init__(*args, **kwargs)
        ordering = ['after', 'number_of_issues',
                    'first_number', 'first_year', 'first_volume',
                    'issues_per_cycle', 'display_volume_with_number']
        ordering.extend(self._shared_key_order())
        self.fields.keyOrder = ordering

    def clean(self):
        cd = super(PerYearIssueRevisionForm, self).clean()

        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)

        basics = (cd['first_number'], cd['first_volume'], cd['first_year'])
        if None in basics and cd['after'] is not None:
            if filter(lambda x: x is not None, basics):
                raise forms.ValidationError('When adding issues following an '
                  'existing issue, all of "first number", "first volume" and '
                  '"first year" must be specified, or all must be left blank.')
        if cd['after'] is None and cd['first_year'] is None:
            raise forms.ValidationError('When inserting issues at the beginning '
              'of a series, the first year must be specified.')

        if cd['first_number'] is None and cd['after'] is not None:
            cd = self._parse_year_and_number(cd, cd['issues_per_cycle'])
            if cd['after'].volume is None:
                raise forms.ValidationError('When adding issues following an '
                  'existing issue, the issue after which you are inserting '
                  'the new issues must have a volume.')
            cd['first_volume'] = cd['after'].volume
            if cd['first_number'] == 1:
                cd['first_volume'] += 1

        elif cd['after'] is None:
            if cd['first_number'] is None:
                cd['first_number'] = 1
            if cd['first_volume'] is None:
                cd['first_volume'] = 1

        return cd

def get_reprint_revision_form(revision=None, user=None):
    class RuntimeReprintRevisionForm(ReprintRevisionForm):
        def as_table(self):
            #if not user or user.indexer.show_wiki_links:
                #_set_help_labels(self, REPRINT_HELP_LINKS)
            return super(RuntimeReprintRevisionForm, self).as_table()
    return RuntimeReprintRevisionForm

class ReprintRevisionForm(forms.ModelForm):
    class Meta:
        model = ReprintRevision
        fields = get_reprint_field_list()


def get_story_revision_form(revision=None, user=None, is_comics_publication=True,
                            language=None):
    extra = {}
    additional_genres = []
    selected_genres = []
    if revision is not None:
        # Don't allow blanking out the type field.  However, when its a new store
        # make indexers consciously choose a type by allowing an empty
        # initial value.  So only set None if there is an existing story revision.
        extra['empty_label'] = None
        if revision.issue and revision.issue.series.is_comics_publication == False:
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
    if revision and (revision.issue == None or revision.issue.variant_of):
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
        special_types = ['(backcovers) *do not use* / *please fix*', 'filler'] \
                        + [i for i in OLD_TYPES]
        queryset = StoryType.objects.all()
        if revision is None or (revision is not None and
                                revision.type.name not in special_types):
            queryset = queryset.exclude(name__in=special_types)

    class RuntimeStoryRevisionForm(StoryRevisionForm):
        type = forms.ModelChoiceField(queryset=queryset,
          **extra)

        fantasy_id = GENRES['en'].index(u'fantasy')
        if language and language.code != 'en' and language.code in GENRES:
            choices = [[g, g + ' / ' + h] for g,h in zip(GENRES['en'],
                                                    GENRES[language.code])]
            choices[fantasy_id] = [u'fantasy',
              u'fantasy-supernatural / %s' % GENRES[language.code][fantasy_id]]
        else:
            choices = [[g, g] for g in GENRES['en']]
            choices[fantasy_id] = [u'fantasy', u'fantasy-supernatural']
        if additional_genres:
            additional_genres.reverse()
            for genre in additional_genres:
                choices.insert(0, [genre, genre + ' (deprecated)'])
        genre = forms.MultipleChoiceField(required=False,
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
        fields.insert(fields.index('job_number')+1, 'creator_help')

    # The sequence number can only be changed through the reorder form, but
    # for new stories we add it through the initial value of a hidden field.
    sequence_number = forms.IntegerField(widget=forms.HiddenInput)

    title = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide',
                                                          'autofocus':''}),
                            required=False,
      help_text='If no title can be determined, preferably use here'
                ' the first line of text/dialogue in "quotation marks", or '
                'a made up title, and check unofficial title.')
    title_inferred = forms.BooleanField(required=False,
      label='Unofficial title',
      help_text='')

    page_count = forms.DecimalField(widget=PageCountInput, required=False,
                                    max_digits=10, decimal_places=3)
    page_count_uncertain = forms.BooleanField(required=False)

    creator_help = forms.CharField(widget=HiddenInputWithHelp, required=False,
      help_text='Enter the relevant creator credits in the following fields, '
                'where multiple credits are separated by semi-colons. Notes '
                'are in () and aliases in []. If the credit applies to a '
                'sequence type, but the creator is unknown enter a question '
                'mark. If a field is not required for a sequence type it can '
                'be left blank.', label='')

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
    letters = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                              required=False,
      help_text='If the lettering is produced as normal printed text rather '
                'than comic-style lettering, enter the word "typeset" here.')
    editing = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                             required=False,
                             help_text='')

    no_script = forms.BooleanField(required=False,
      help_text=NO_CREATOR_CREDIT_HELP % ('script or plot',
        ', e.g. for a cover or single-page illustration,', 'script'))
    no_pencils = forms.BooleanField(required=False,
      help_text=NO_CREATOR_CREDIT_HELP % ('pencils', ', e.g. for '
                'an unillustrated text article,', 'pencils'))
    no_inks = forms.BooleanField(required=False,
      help_text=NO_CREATOR_CREDIT_HELP % ('inks', ', e.g. for a '
                'story colored straight from pencils,', 'inks'))
    no_colors = forms.BooleanField(required=False,
      help_text=NO_CREATOR_CREDIT_HELP % ('colors', ', e.g. for '
                'a black-and-white comic,', 'colors'))
    no_letters = forms.BooleanField(required=False,
      help_text=NO_CREATOR_CREDIT_HELP % ('letters', '', 'letters'))
    no_editing = forms.BooleanField(required=False,
      help_text='Check this box if there is no separate editor for this sequence. '
                'This is common when there is an editor for the whole issue.')
    synopsis = forms.CharField(widget=forms.Textarea(attrs={'style': 'height: 9em'}),
                               required=False,
      help_text='A brief description of the contents. No text under copyright,'
                ' such as solicitation or other promotional text, may be used'
                ' without clear permission and credit.')
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
                      ['%s field or No %s checkbox must be filled in.' % \
                        (seq_type.capitalize(), seq_type.capitalize())])

            if cd['no_%s' % seq_type] and cd[seq_type] != "":
                raise forms.ValidationError(
                  ['%s field and No %s checkbox cannot both be filled in.'% \
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

def get_cover_revision_form(revision=None, user=None):
    compare_url = '<a href="' + urlresolvers.reverse('compare',
      kwargs={ 'id': revision.changeset.id }) + '">Compare Change</a>'

    class UploadScanCommentForm(forms.ModelForm):
        comments = forms.CharField(widget=forms.Textarea,
                                   required=False,
          help_text='Comments between the Indexer and Editor about the change. '
                    'These comments are part of the public change history, but '
                    'are not part of the regular display. <p>%s</p>' \
                    % compare_url)

        def clean(self):
            cd = self.cleaned_data
            cd['comments'] = cd['comments'].strip()
            return cd

    return UploadScanCommentForm

class UploadScanForm(forms.Form):
    """ Form for cover uploads. """

    scan = forms.ImageField(widget=forms.FileInput)
    source = forms.CharField(label='Source', required=True,
      help_text='If you upload a scan from another website, make sure you '
                'have permission to do that and mention the source. If you '
                'upload on behalf of someone else you can mention this here as'
                ' well. Otherwise, indicate that you scanned it yourself.')
    remember_source = forms.BooleanField(label='Remember the source',
                                         required=False,
      help_text="Tick only if you do multiple uploads from the source.")
    marked = forms.BooleanField(label="Mark cover for replacement", required=False,
      help_text='Uploads of sub-standard scans for older and/or rare comics '
                'are fine, but please mark them for replacement.')
    is_wraparound = forms.BooleanField(label="Wraparound cover",
                                       required=False,
      help_text='Cover is a standard wraparound cover: Two pages in width, '
                'the right half is the front cover and will be automatically '
                'selected.')
    is_gatefold = forms.BooleanField(label="Gatefold cover",
                                         required=False,
      help_text='Cover is a non-standard wraparound cover or a gatefold cover. '
                'After the upload you will select the front cover part. '
                'The selection will not work if JavaScript is turned off.')
    comments = _get_comments_form_field()

    def clean(self):
        cd = self.cleaned_data
        if 'source' in cd:
            cd['source'] = cd['source'].strip()
        cd['comments'] = cd['comments'].strip()
        if cd['is_wraparound'] and cd['is_gatefold']:
            raise forms.ValidationError(
              ['Wraparound cover and gatefold cover cannot be both selected. '
               'A cover that is both wraparound and gatefold should be '
               'submitted as a gatefold cover.'])
        return cd

class UploadVariantScanForm(UploadScanForm):
    def __init__(self, *args, **kwargs):
        super(UploadVariantScanForm, self).__init__(*args, **kwargs)
        ordering = self.fields.keyOrder
        ordering.remove('variant_name')
        ordering.remove('variant_artwork')
        ordering.remove('reservation_requested')
        ordering = ['variant_artwork'] + ordering
        ordering = ['variant_name'] + ordering
        ordering = ['reservation_requested'] + ordering
        self.fields.keyOrder = ordering

    is_gatefold = forms.CharField(widget=HiddenInputWithHelp, required=False,
      label="Gatefold cover",
      help_text='Gatefold uploads are currently not supported when creating '
        'a variant with a cover image upload. Please first create the '
        'variant issue before uploading a gatefold cover.')
    variant_name = forms.CharField(required=False,
      help_text='Name of this variant. Examples are: "Cover A" (if listed as '
        'such in the issue), "second printing", "newsstand", "direct", or the '
        'name of the artist if different from the base issue.')
    variant_artwork = forms.BooleanField(required=False, initial=True,
      label = 'Variant artwork',
      help_text='Check this box if the uploaded variant cover has artwork '
        'different from the base issue. If checked a cover sequence will '
        'be generated with question marks in the creator fields on approval.')
    reservation_requested = forms.BooleanField(required=False,
      label = 'Request variant reservation',
      help_text='Ideally you request a reservation for the new variant to later'
        ' fill in the missing data. Check this box to have the variant issue '
        'reserved to you automatically when it is approved.')

class GatefoldScanForm(forms.Form):
    """ Form for cover uploads. """

    left = forms.IntegerField(widget=forms.TextInput(attrs={'size':'4'}))
    width = forms.IntegerField(widget=forms.TextInput(attrs={'size':'4'}))
    real_width = forms.IntegerField(widget=forms.HiddenInput)
    top = forms.IntegerField(widget=forms.TextInput(attrs={'size':'4'}))
    height = forms.IntegerField(widget=forms.TextInput(attrs={'size':'4'}))
    cover_id = forms.IntegerField(widget=forms.HiddenInput, required=False)
    issue_id = forms.IntegerField(widget=forms.HiddenInput)
    scan_name = forms.CharField(widget=forms.HiddenInput)
    source = forms.CharField(widget=forms.HiddenInput, required=False)
    remember_source = forms.BooleanField(widget=forms.HiddenInput,
                                         required=False)
    marked = forms.BooleanField(widget=forms.HiddenInput, required=False)
    comments = forms.CharField(widget=forms.HiddenInput, required=False)

class UploadImageForm(forms.Form):
    """ Form for image uploads. """

    image = forms.ImageField(widget=forms.FileInput)

    marked = forms.BooleanField(label="Mark image for replacement", required=False,
      help_text='Uploads of sub-standard images for older and/or rare comics '
                'are fine, but please mark them for replacement.')

    comments = forms.CharField(widget=forms.Textarea,
                               required=False,
                               label='Source / Comments',
      help_text='Please credit the source of this image if scanned or '
                'otherwise provided by another site or person, along with '
                'any additional comments to the upload approver.')

class DownloadForm(forms.Form):
    """ Form for downloading data dumps. """

    purpose = forms.ChoiceField(required=False, widget=forms.RadioSelect,
      choices=(('private', 'Private use'),
               ('non-commercial', 'Public / Non-Commercial use'),
               ('commercial', 'Public / Commercial use')),
      label="[Optional] Purpose:")

    usage = forms.CharField(required=False, widget=forms.Textarea,
      label="[Optional] How or where do you plan to use the data?")

    # Set required=False so we can supply a better error message.
    accept_license = forms.BooleanField(required=False,
      label='I have read and accept the GCD data licensing terms and crediting '
            'guidelines')

    def clean(self):
        cd = self.cleaned_data
        cd['usage'] = cd['usage'].strip()

        if cd['accept_license'] is not True:
            raise forms.ValidationError, (
              'You must check the box indicating your acceptance of the licensing '
              'and crediting terms in order to download the data.')

        return cd
