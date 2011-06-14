# -*- coding: utf-8 -*-
import re

from django import forms
from django.core import urlresolvers
from django.db.models import Count, F
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.forms.widgets import TextInput

from apps.oi.models import *
from apps.gcd.models import *
from apps.gcd.templatetags.credits import format_page_count

CREATOR_CREDIT_HELP = 'The %s and similar credits for this sequence. If ' \
  'multiple persons or credits, please list them all separated with ' \
  'semicolons. If you do not know who did this, but the credit applies to ' \
  'this sequence type, enter a question mark.'
NO_CREATOR_CREDIT_HELP = 'Check this box if %s does not apply to this ' \
                'sequence, %s, and leave the %s field blank. ' \
                'If the credit is relevant but unknown ignore this checkbox '\
                'and enter a question mark in the %s field.'
GENERIC_ERROR_MESSAGE = 'Please correct the field errors.  Scroll down to see '\
                        'the specific error message(s) next to each field.'

DOC_URL = 'http://docs.comics.org/wiki/'
ISSUE_HELP_LINKS = {
    'number': 'Issue_Numbers',
    'volume': 'Volume',
    'no_volume': 'Volume',
    'display_volume_with_number': 'Display_Volume_with_Issue_Number',
    'publication_date': 'Published_Date',
    'indicia_frequency': 'Indicia_frequency',
    'no_indicia_frequency': 'Indicia_frequency',
    'key_date': 'Keydate',
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
    'notes': 'Notes_%28issue%29',
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
              u' <a href="%s%s">[?]</a>' % (DOC_URL, help_links[field]))

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

def _get_comments_form_field():
    return forms.CharField(widget=forms.Textarea, required=False,
      help_text='Comments between the Indexer and Editor about the change. '
                'These comments are part of the public change history, but '
                'are not part of the regular display.')

class PageCountInput(TextInput):
    def _format_value(self, value):
        return format_page_count(value)

    def render(self, name, value, attrs=None):
        value = self._format_value(value)
        return super(TextInput, self).render(name, value, attrs)

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

    if model_name == 'brand':
        return get_brand_revision_form(**kwargs)

    if model_name == 'series':
        if revision is None:
            return get_series_revision_form(**kwargs)
        if 'publisher' not in kwargs:
            kwargs['publisher'] = revision.publisher
        return get_series_revision_form(source=revision.source, **kwargs)

    if model_name == 'issue':
        if revision is not None and 'publisher' not in kwargs:
            kwargs['publisher'] = revision.series.publisher
        return get_issue_revision_form(revision=revision, **kwargs)

    if model_name == 'story':
        return get_story_revision_form(revision, **kwargs)

    if model_name == 'cover':
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
    if source is not None:
        class RuntimePublisherRevisionForm(PublisherRevisionForm):
            # Don't allow country to be un-set:
            if source.country.code == 'xx':
                country_queryset = Country.objects.all()
            else:
                country_queryset = Country.objects.exclude(code='xx')
            country = forms.ModelChoiceField(queryset=country_queryset,
                                             empty_label=None)
        return RuntimePublisherRevisionForm
    return PublisherRevisionForm

def _get_publisher_fields(middle=None):
    first = ['name', 'year_began', 'year_began_uncertain',
                     'year_ended', 'year_ended_uncertain']
    last = ['url', 'notes']
    if middle is not None:
        first.extend(middle)
    first.extend(last)
    return first

class PublisherRevisionForm(forms.ModelForm):
    class Meta:
        model = PublisherRevision
        fields = _get_publisher_fields(middle=('country',))

    country = forms.ModelChoiceField(queryset=Country.objects.exclude(code='xx'))
    comments = forms.CharField(widget=forms.Textarea,
                               required=False,
      help_text='Comments between the Indexer and Editor about the change. '
                'These comments are part of the public change history, but '
                'are not part of the regular display.')

    def clean(self):
        cd = self.cleaned_data
        cd['name'] = cd['name'].strip()
        cd['notes'] = cd['notes'].strip()
        cd['comments'] = cd['comments'].strip()
        return cd

def get_indicia_publisher_revision_form(source=None, user=None):
    if source is not None:
        class RuntimeIndiciaPublisherRevisionForm(IndiciaPublisherRevisionForm):
            # Don't allow country to be un-set:
            country = forms.ModelChoiceField(empty_label=None,
              queryset=Country.objects.exclude(code='xx'))
        return RuntimeIndiciaPublisherRevisionForm
    return IndiciaPublisherRevisionForm

class IndiciaPublisherRevisionForm(PublisherRevisionForm):
    class Meta:
        model = IndiciaPublisherRevision
        fields = _get_publisher_fields(middle=('is_surrogate', 'country'))

    name = forms.CharField(max_length=255,
      help_text='The name exactly as it appears in the indicia, including '
                'punctuation, abbreviations, suffixes like ", Inc.", etc.  '
                'Do not move articles to the end of the name.')

    is_surrogate = forms.BooleanField(required=False, label='Surrogate',
      help_text='Check if this was an independent company serving as a surrogate '
                'for the master publisher, rather than a company belonging to the '
                'master publisher.')

    def clean(self):
        cd = self.cleaned_data
        cd['name'] = cd['name'].strip()
        cd['notes'] = cd['notes'].strip()
        cd['comments'] = cd['comments'].strip()
        return cd

def get_brand_revision_form(source=None, user=None):
    return BrandRevisionForm

class BrandRevisionForm(forms.ModelForm):
    class Meta:
        model = BrandRevision
        fields = ['name', 'year_began', 'year_began_uncertain',
                  'year_ended', 'year_ended_uncertain', 'url', 'notes']

    name = forms.CharField(max_length=255,
      help_text='The name of the brand as it appears on the logo.  If the logo '
                'does not use words, then the name of the brand as it is '
                'commonly used.  Consult an editor if in doubt.')

    year_began = forms.IntegerField(required=False,
      help_text='The first year the brand was used.')
    year_began_uncertain = forms.BooleanField(required=False,
      help_text='Check if you are not certain of the first year the brand '
                'was used.')

    year_ended = forms.IntegerField(required=False,
      help_text='The last year the brand was used.  Leave blank if currently '
                'in use.')
    year_ended_uncertain = forms.BooleanField(required=False,
      help_text='Check if you are not certain of the last year the brand '
                'was used, or if you are not certain whether it is still in use.')

    url = forms.URLField(required=False,
      help_text='The official web site of the brand.  Leave blank if the '
                'publisher does not have a specific web site for the brand.')

    comments = forms.CharField(widget=forms.Textarea,
                               required=False,
      help_text='Comments between the Indexer and Editor about the change. '
                'These comments are part of the public change history, but '
                'are not part of the regular display.')

    def clean(self):
        cd = self.cleaned_data
        cd['name'] = cd['name'].strip()
        cd['notes'] = cd['notes'].strip()
        cd['comments'] = cd['comments'].strip()
        return cd

def get_series_revision_form(publisher=None, source=None, user=None):
    if source is None:
        can_request = None
        series_fields = _get_series_fields(source)

        if user is not None and user.indexer.can_reserve_another_ongoing():
            can_request = True
            series_fields = ['reservation_requested'] + series_fields

        class RuntimeAddSeriesRevisionForm(SeriesRevisionForm):
            class Meta:
                model = SeriesRevision
                fields = series_fields

            if can_request:
                reservation_requested = forms.BooleanField(required=False,
                  label = 'Request reservation',
                  help_text='Check this box to have the ongoing reservation for '
                            'this series assigned to you when it is approved, '
                            'unless you have gone over your ongoing reservation '
                            'limit at that time.')

        return RuntimeAddSeriesRevisionForm

    else:
        class RuntimeSeriesRevisionForm(SeriesRevisionForm):
            class Meta:
                model = SeriesRevision
                fields = _get_series_fields(source)

            # Don't allow country and language to be un-set:
            if source.country.code == 'xx':
                country_queryset = Country.objects.all()
            else:
                country_queryset = Country.objects.exclude(code='xx')
            country = forms.ModelChoiceField(queryset=country_queryset,
                                             empty_label=None)
            language = forms.ModelChoiceField(queryset=Language.objects.all(),
                                              empty_label=None)

            if source.imprint is not None:
                imprint = forms.ModelChoiceField(required=False,
                  queryset=Publisher.objects.filter(is_master=False,
                                                    deleted=False,
                                                    parent=publisher))
        return RuntimeSeriesRevisionForm

def _get_series_fields(source=None):
    fields = [
      'name',
      'format',
      'year_began',
      'year_ended',
      'is_current',
      'country',
      'language',
      'publication_notes',
      'tracking_notes',
      'notes',
    ]
    if source is None or source.imprint is None:
        return fields
    fields.append('imprint')
    return fields

class SeriesRevisionForm(forms.ModelForm):

    class Meta:
        model = SeriesRevision
        fields = (
            'name',
            'imprint',
            'format',
            'year_began',
            'year_ended',
            'is_current',
            'publication_notes',
            'tracking_notes',
            'country',
            'language',
            'notes',
        )

    name = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
      help_text=('Series name as it appears in the indicia (or cover only '
                 'if there is no indicia), with any leading article moved '
                 'to the end after a comma.'))

    year_began = forms.IntegerField(
      widget=forms.TextInput(attrs={'class': 'year'}),
      help_text='Year first issue published.')

    year_ended = forms.IntegerField(
      widget=forms.TextInput(attrs={'class': 'year'}),
      required=False,
      help_text='Leave blank if the series is still producing new issues.')

    is_current = forms.BooleanField(required=False,
      help_text='Check if new issues are still being produced for this series.')

    country = forms.ModelChoiceField(queryset=Country.objects.exclude(code='xx'))

    format = forms.CharField(
      widget=forms.TextInput(attrs={'class': 'wide'}),
      required=False,
      help_text='This is a compound field that holds size, binding, '
                'paper stock and other information, separated by '
                'semi-colons.  Consult the wiki for specifics.  This '
                'field is being replaced by several individual fields '
                'in the near future.')

    comments = forms.CharField(widget=forms.Textarea,
                               required=False,
      help_text='Comments between the Indexer and Editor about the change. '
                'These comments are part of the public change history, but '
                'are not part of the regular display.')

    def clean(self):
        cd = self.cleaned_data
        cd['name'] = cd['name'].strip()
        cd['format'] = cd['format'].strip()
        cd['publication_notes'] = cd['publication_notes'].strip()
        cd['tracking_notes'] = cd['tracking_notes'].strip()
        cd['notes'] = cd['notes'].strip()
        cd['comments'] = cd['comments'].strip()
        return cd

def _get_issue_fields():
    return [
        'number',
        'volume',
        'display_volume_with_number',
        'no_volume',
        'indicia_publisher',
        'indicia_pub_not_printed',
        'brand',
        'no_brand',
        'publication_date',
        'key_date',
        'indicia_frequency',
        'no_indicia_frequency',
        'price',
        'page_count',
        'page_count_uncertain',
        'editing',
        'no_editing',
        'isbn',
        'no_isbn',
        'barcode',
        'no_barcode',
        'notes',
    ]

def get_issue_revision_form(publisher, series=None, revision=None,
                            variant_of=None, user=None):
    if series is None and revision is not None:
        series = revision.series

    class RuntimeIssueRevisionForm(IssueRevisionForm):
        def __init__(self, *args, **kwargs):
            super(RuntimeIssueRevisionForm, self).__init__(*args, **kwargs)
            self.fields['brand'].queryset = \
              series.publisher.active_brands_no_pending()
            self.fields['indicia_publisher'].queryset = \
              series.publisher.active_indicia_publishers_no_pending()
            self.fields['no_isbn'].initial = _init_no_isbn(series, None)
            self.fields['no_barcode'].initial = _init_no_barcode(series, None)

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

            if cd['editing'] != "" and cd['no_editing']:
                raise forms.ValidationError('You cannot specify an editing '
                  'credit and check "no editing" at the same time')

            if cd['no_brand'] and cd['brand'] is not None:
                raise forms.ValidationError(
                  ['Brand field and No Brand checkbox cannot both be filled in.'])

            if cd['no_indicia_frequency'] and cd['indicia_frequency']:
                raise forms.ValidationError(
                  'You cannot list an indicia frequency and check '
                  '"no indicia frequency" at the same time.')

            if cd['no_isbn'] and cd['isbn']:
                raise forms.ValidationError(
                  'You cannot list an isbn and check "no isbn" at the same time.')

            return cd

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, ISSUE_HELP_LINKS)
            return super(IssueRevisionForm, self).as_table()

    if variant_of:
        class RuntimeAddVariantIssueRevisionForm(RuntimeIssueRevisionForm):
            class Meta:
                model = IssueRevision
                fields = _get_issue_fields()

        return RuntimeAddVariantIssueRevisionForm
        
    if revision is None or revision.source is None:
        add_fields = ['after']
        add_fields.extend(_get_issue_fields())

        can_request = False
        if series.get_ongoing_reservation() is None:
            can_request = True
            add_fields = ['reservation_requested'] + add_fields
        
        class RuntimeAddIssueRevisionForm(RuntimeIssueRevisionForm):
            class Meta:
                model = IssueRevision
                fields = add_fields

            if can_request:
                reservation_requested = forms.BooleanField(required=False,
                  label = 'Request reservation',
                  help_text='Check this box to have this issue reserved to you '
                            'automatically when it is approved, unless someone '
                            'has acquired the series\' ongoing reservation before '
                            'then.')

            after = forms.ModelChoiceField(required=False,
              queryset=Issue.objects.exclude(deleted=True) \
                .filter(series=series).order_by('sort_code'),
              empty_label="[add as first issue]",
              label = "Add this issue after")

        return RuntimeAddIssueRevisionForm

    return RuntimeIssueRevisionForm

class IssueRevisionForm(forms.ModelForm):
    class Meta:
        model = IssueRevision
        fields = _get_issue_fields()
        widgets = {
          'number': forms.TextInput(attrs={'class': 'wide'}),
          'volume': forms.TextInput(attrs={'class': 'wide'}),
          'key_date': forms.TextInput(attrs={'class': 'key_date'}),
          'indicia_frequency': forms.TextInput(attrs={'class': 'wide'}),
          'editing': forms.TextInput(attrs={'class': 'year'}),
          'isbn': forms.TextInput(attrs={'class': 'wide'}),
          'barcode': forms.TextInput(attrs={'class': 'wide'})
        }

    comments = _get_comments_form_field()


def get_bulk_issue_revision_form(series, method, user=None):
    if method == 'number':
        base = WholeNumberIssueRevisionForm
    elif method == 'volume':
        base = PerVolumeIssueRevisionForm
    elif method == 'year':
        base = PerYearIssueRevisionForm
    elif method == 'year_volume':
        base = PerYearVolumeIssueRevisionForm
    else:
        return render_error(request, 'Unknown method of adding issues.')

    class RuntimeBulkIssueRevisionForm(base):
        def __init__(self, *args, **kwargs):
            super(RuntimeBulkIssueRevisionForm, self).__init__(*args, **kwargs)
            self.fields['brand'].queryset = \
              series.publisher.active_brands_no_pending()
            self.fields['indicia_publisher'].queryset = \
              series.publisher.active_indicia_publishers_no_pending()
            self.fields['no_isbn'].initial = _init_no_isbn(series, None)
            self.fields['no_barcode'].initial = _init_no_barcode(series, None)
            
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

    number_of_issues = forms.IntegerField(min_value=1)

    comments = _get_comments_form_field()

    class Meta:
        model = IssueRevision
        fields = _get_issue_fields()
        exclude = ['number',]
        widgets = {
          'volume': forms.TextInput(attrs={'class': 'wide'}),
          'indicia_frequency': forms.TextInput(attrs={'class': 'wide'}),
          'editing': forms.TextInput(attrs={'class': 'year'}),
        }

    def _shared_key_order(self):
        return ['indicia_publisher', 'indicia_pub_not_printed', 'brand',
                'no_brand', 'indicia_frequency', 'no_indicia_frequency',
                'price', 'page_count', 'page_count_uncertain',
                'editing', 'no_editing', 'no_isbn', 'no_barcode', 'comments']

    def clean(self):
        cd = self.cleaned_data

        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)

        cd['indicia_frequency'] = cd['indicia_frequency'].strip()
        cd['price'] = cd['price'].strip()
        cd['editing'] = cd['editing'].strip()
        cd['comments'] = cd['comments'].strip()

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

        return cd

class WholeNumberIssueRevisionForm(BulkIssueRevisionForm):

    def __init__(self, *args, **kwargs):
        super(WholeNumberIssueRevisionForm, self).__init__(*args, **kwargs)
        ordering = ['after', 'number_of_issues', 'first_number',
                    'volume', 'display_volume_with_number', 'no_volume']
        ordering.extend(self._shared_key_order())
        self.fields.keyOrder = ordering

    def clean(self):
        cd = super(WholeNumberIssueRevisionForm, self).clean()

        cd['volume'] = cd['volume'].strip()
        if cd['volume'] != "" and cd['no_volume']:
            raise forms.ValidationError('You cannot specify a volume and check '
              '"no volume" at the same time')

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

        cd['volume'] = cd['volume'].strip()

        if cd['volume'] != "" and cd['no_volume']:
            raise forms.ValidationError('You cannot specify a volume and check '
              '"no volume" at the same time')

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

def get_story_revision_form(revision=None, user=None):
    extra = {}
    if revision is not None:
        # Don't allow blanking out the type field.  However, when its a new store
        # make indexers consciously choose a type by allowing an empty
        # initial value.  So only set None if there is an existing story revision.
        extra['empty_label'] = None

    special_types = ('(backcovers) *do not use* / *please fix*', '(unknown)', 
                     'biography (nonfictional)')
    queryset = StoryType.objects.all()
    if revision is None or (revision is not None and
                            revision.type.name not in special_types):
        queryset = queryset.exclude(name__in=special_types)

    class RuntimeStoryRevisionForm(StoryRevisionForm):
        type = forms.ModelChoiceField(queryset=queryset,
          help_text='Choose the most appropriate available type',
          **extra)

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, SEQUENCE_HELP_LINKS)
            return super(StoryRevisionForm, self).as_table()
    return RuntimeStoryRevisionForm

class StoryRevisionForm(forms.ModelForm):
    class Meta:
        model = StoryRevision
        fields = (
          'sequence_number',
          'title',
          'title_inferred',
          'type',
          'feature',
          'page_count',
          'page_count_uncertain',
          'script',
          'no_script',
          'pencils',
          'no_pencils',
          'inks',
          'no_inks',
          'colors',
          'no_colors',
          'letters',
          'no_letters',
          'editing',
          'no_editing',
          'genre',
          'characters',
          'job_number',
          'reprint_notes',
          'synopsis',
          'notes',
        )

    # The sequence number can only be changed through the reorder form, but
    # for new stories we add it through the initial value of a hidden field.
    sequence_number = forms.IntegerField(widget=forms.HiddenInput)

    title = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                            required=False,
      help_text='If the title is not listed, use the first line of dialog, '
                'place it in "quotation marks" and check the next box.  Do *not* '
                'place the title in brackets.  Title is required for sequences of '
                'type "story", "text story" and "text article", but may be left '
                'blank for sequences of other types.')
    title_inferred = forms.BooleanField(required=False,
      label='Unofficial title',
      help_text='Check if the title was taken from the first line of dialogue or '
                'was made up (titles from dialogue are preferred, and should be '
                'enclosed in "quotation marks")')

    page_count = forms.DecimalField(widget=PageCountInput, required=False,
                                    max_digits=10, decimal_places=3)
    page_count_uncertain = forms.BooleanField(required=False,
      help_text="Check if you do not know or aren't sure about the page count.")

    script = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                             required=False, 
                             help_text=CREATOR_CREDIT_HELP % 'scripter')
    pencils = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                              required=False,
                             help_text=CREATOR_CREDIT_HELP % 'penciler')
    inks = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                           required=False,
                           help_text=CREATOR_CREDIT_HELP % 'inker')
    colors = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                             required=False,
                             help_text=CREATOR_CREDIT_HELP % 'colorist')
    letters = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                              required=False,
                             help_text=CREATOR_CREDIT_HELP % 'letterer')
    editing = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                             required=False,
                             help_text=CREATOR_CREDIT_HELP % 'editor')

    no_script = forms.BooleanField(required=False,
      help_text=NO_CREATOR_CREDIT_HELP % ('script or plot', 
        'e.g. for a cover or single-page illustration', 'script', 'script'))
    no_pencils = forms.BooleanField(required=False,
      help_text=NO_CREATOR_CREDIT_HELP % ('penciler', 'e.g. for '
                'an unillustrated text article', 'pencils', 'pencils'))
    no_inks = forms.BooleanField(required=False,
      help_text=NO_CREATOR_CREDIT_HELP % ('inker', 'e.g. for a '
                'story colored straight from pencils', 'inks', 'inks'))
    no_colors = forms.BooleanField(required=False,
      help_text=NO_CREATOR_CREDIT_HELP % ('colorist', 'e.g. for '
                'a black-and-white comic', 'colors', 'colors'))
    no_letters = forms.BooleanField(required=False,
      help_text='Check this box if lettering does not apply to this sequence, '
                ' and leave the letters box blank.  '
                'However, if the only letters are produced as normal '
                'printed text rather than comic-style lettering, put the word '
                '"typeset" in the letters field and do not check this box. '
                'If the credit is relevant but unknown ignore this checkbox and '
                'enter a question mark in the letters field.')
    no_editing = forms.BooleanField(required=False,
      help_text='Check this box if there is no separate editor for this sequence. '
                'This is common when there is an editor for the whole issue.')
    synopsis = forms.CharField(widget=forms.Textarea(attrs={'style': 'height: 9em'}),
                               required=False,
      help_text='A brief (600 character maximum) description of the contents.  '
                'No text under copyright may be used without clear permission '
                'and credit.  Solicitation or other promotional text may NOT '
                'be used.')
    comments = forms.CharField(widget=forms.Textarea,
                               required=False,
      help_text='Comments between the Indexer and Editor about the change. '
                'These comments are part of the public change history, but '
                'are not part of the regular display.')

    def clean(self):
        cd = self.cleaned_data

        cd['title'] = cd['title'].strip()
        cd['feature'] = cd['feature'].strip()
        cd['script'] = cd['script'].strip()
        cd['pencils'] = cd['pencils'].strip()
        cd['inks'] = cd['inks'].strip()
        cd['colors'] = cd['colors'].strip()
        cd['letters'] = cd['letters'].strip()
        cd['editing'] = cd['editing'].strip()
        cd['genre'] = cd['genre'].strip()
        cd['characters'] = cd['characters'].strip()
        cd['job_number'] = cd['job_number'].strip()
        cd['reprint_notes'] = cd['reprint_notes'].strip()
        cd['synopsis'] = cd['synopsis'].strip()
        cd['notes'] = cd['notes'].strip()
        cd['comments'] = cd['comments'].strip()

        if not cd['no_script'] and cd['script'] == "":
            raise forms.ValidationError(
              ['Script field or No Script checkbox must be filled in.'])
        if cd['no_script'] and cd['script'] != "":
            raise forms.ValidationError(
              ['Script field and No Script checkbox cannot both be filled in.'])

        if not cd['no_pencils'] and cd['pencils'] == "":
            raise forms.ValidationError(
              ['Pencils field or No Pencils checkbox must be filled in.'])
        if cd['no_pencils'] and cd['pencils'] != "":
            raise forms.ValidationError(
              ['Pencils field and No Pencils checkbox cannot both be filled in.'])

        if not cd['no_inks'] and cd['inks'] == "":
            raise forms.ValidationError(
              ['Inks field or No Inks checkbox must be filled in.'])
        if cd['no_inks'] and cd['inks'] != "":
            raise forms.ValidationError(
              ['Inks field and No Inks checkbox cannot both be filled in.'])

        if not cd['no_colors'] and cd['colors'] == "":
            raise forms.ValidationError(
              ['Colors field or No Colors checkbox must be filled in.'])
        if cd['no_colors'] and cd['colors'] != "":
            raise forms.ValidationError(
              ['Colors field and No Colors checkbox cannot both be filled in.'])

        if not cd['no_letters'] and cd['letters'] == "":
            raise forms.ValidationError(
              ['Letters field or No Letters checkbox must be filled in.'])
        if cd['no_letters'] and cd['letters'] != "":
            raise forms.ValidationError(
              ['Letters field and No Letters checkbox cannot both be filled in.'])

        if not cd['no_editing'] and cd['editing'] == "":
            raise forms.ValidationError(
              ['Editing field or No Editing checkbox must be filled in.'])
        if cd['no_editing'] and cd['editing'] != "":
            raise forms.ValidationError(
              ['Editing field and No Editing checkbox cannot both be filled in.'])

        if (len(cd['synopsis']) > settings.LIMIT_SYNOPSIS_LENGTH and
            (self.instance is None or
             self.instance.synopsis.strip() != cd['synopsis'])):

            raise forms.ValidationError(
              ['The synopsis field may not be longer than 600 characters.'])

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
    source = forms.CharField(label='Source', required=False, 
      help_text='If you upload a scan from another website, please '
                'ask for permission and mention the source. If you upload '
                'on behalf of someone you can mention this here as well.')
    remember_source = forms.BooleanField(label='Remember the source', 
                                         required=False)
    marked = forms.BooleanField(label="Mark cover", required=False,
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
    comments = forms.CharField(widget=forms.Textarea,
                               required=False,
      help_text='Comments between the Indexer and Editor about the change. '
                'These comments are part of the public change history, but '
                'are not part of the regular display.')

    def clean(self):
        cd = self.cleaned_data
        cd['source'] = cd['source'].strip()
        cd['comments'] = cd['comments'].strip()
        if cd['is_wraparound'] and cd['is_gatefold']:
            raise forms.ValidationError(
              ['Wraparound cover and gatefold cover cannot be both selected. '
               'A cover that is both wraparound and gatefold should be '
               'submitted as a gatefold cover.'])
        return cd

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
