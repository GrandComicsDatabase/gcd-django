import re

from django import forms
from django.db.models import Count, F
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

from apps.oi.models import *
from apps.gcd.models import *

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

def get_publisher_revision_form(source=None):
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
    first = ['name', 'year_began', 'year_ended']
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

def get_indicia_publisher_revision_form(source=None):
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
    is_surrogate = forms.BooleanField(required=False, label='Surrogate',
      help_text='Check if this was an independent company serving as a surrogate '
                'for the master publisher, rather than a company belonging to the '
                'master publisher.')

def get_brand_revision_form(source=None):
    return BrandRevisionForm

class BrandRevisionForm(forms.ModelForm):
    class Meta:
        model = BrandRevision
        fields = ['name', 'year_began', 'year_ended', 'url', 'notes']
    comments = forms.CharField(widget=forms.Textarea,
                               required=False,
      help_text='Comments between the Indexer and Editor about the change. '
                'These comments are part of the public change history, but '
                'are not part of the regular display.')

def get_series_revision_form(publisher=None, source=None, indexer=None):
    if source is None:
        can_request = None
        series_fields = _get_series_fields(source)

        if indexer is not None and indexer.indexer.can_reserve_another_ongoing():
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
    year_began = forms.IntegerField(widget=forms.TextInput(attrs={'class': 'year'}),
      help_text='Year first issue published.')
    year_ended = forms.IntegerField(widget=forms.TextInput(attrs={'class': 'year'}),
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

def _get_issue_fields():
    return [
        'number',
        'volume',
        'display_volume_with_number',
        'no_volume',
        'indicia_publisher',
        'brand',
        'publication_date',
        'key_date',
        'indicia_frequency',
        'price',
        'page_count',
        'page_count_uncertain',
        'editing',
        'no_editing',
        'notes',
    ]

def get_issue_revision_form(publisher, series=None, revision=None):
    class RuntimeIssueRevisionForm(IssueRevisionForm):
        indicia_publisher = forms.ModelChoiceField(required=False,
          queryset=IndiciaPublisher.objects.filter(parent=publisher),
          help_text='The exact corporation listed as the publisher in the indicia, '
                    'if any.  If there is none, the copyright holder (if any) may '
                    'be used, with a comment in the notes field')
        brand = forms.ModelChoiceField(required=False,
          queryset=Brand.objects.filter(parent=publisher),
          help_text="The publisher's logo or tagline on the cover of the comic, "
                    "if any. Some U.S. golden age publishers did not put any "
                    "identifiable brand marks on their comics.")

    if revision is None:
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
              queryset=Issue.objects.filter(series=series).order_by('sort_code'),
              empty_label="[add as first issue]",
              label = "Add this issue after")

        return RuntimeAddIssueRevisionForm

    return RuntimeIssueRevisionForm

class IssueRevisionForm(forms.ModelForm):
    class Meta:
        model = IssueRevision
        fields = _get_issue_fields()

    number = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
      help_text='The issue number (or other label) as it appears in the indicia. '
                'If there is no indicia the cover number may be used. '
                'Series that number by year (mosty European series) should write '
                'the year after a slash: "4/2009" for issue #4 in publication year '
                '2009.  Place brackets around an issue number if there is an '
                'indicia but the number does not appear in it.  Use "[nn]" or the '
                'next logical number in brackets like "[2]" if '
                'there is no number printed anywhere on the issue.')

    volume = forms.IntegerField(required=False,
      help_text='Volume number (only numeric volumes allowed at this time). '
                'For collections or other items that only have a volume number, '
                'put the same number in both this field and the issue number '
                'and do *not* check "Display volume with number". ')

    no_volume = forms.BooleanField(required=False,
      help_text='If there is no volume, check this box and leave the volume field '
                'blank. This lets us distinguish between confirmed no-volume '
                'issues and issues indexed before we started tracking volume.')

    display_volume_with_number = forms.BooleanField(required=False,
      help_text='Check to cause the site to display the volume as part of the '
                'issue number.  For example with a volume of "2" and an issue '
                'number of "1", checking this box will display "v2#1" instead '
                'of just "1" in the status grids and issues lists for the series.')

    publication_date = forms.CharField(required=False,
      help_text='The publicaton date as printed on the comic, except with the '
                'name of the month (if any) spelled out.  Any part of the date '
                'that is not printed on the comic but is known should be put '
                'in square brackets, such as "[January] 2009".  Do NOT use the '
                'shipping date in this field, only the publication date.')

    key_date = forms.CharField(required=False,
      widget=forms.TextInput(attrs={'class': 'key_date'}),
      help_text='Special date form used for sorting:  YYYY.MM.DD where the day '
                '(DD) shoud be 00 for monthly books, and use arbitrary numbers '
                'such as 10, 20, 30 to indicate an "early" "mid" or "late" month '
                'cover date.  For the month (MM) on quarterlies, use 04 for '
                'Spring, 07 for Summer, 10 for Fall and 01 or 12 for Winter (in '
                'the northern hemisphere, shift accordingly in the southern).  For '
                'annuals use a month of 00 or 13 or whatever sorts it best.  When '
                'in doubt, use anything that produces the correct sorting.')

    indicia_frequency = forms.CharField(required=False,
      help_text='If relevant, the frequency of publication specified in the '
                'indicia, which may not match the actual publication schedule. '
                'This is most often found on U.S. ongoing series.')

    price = forms.CharField(required=False,
      help_text='Price in ISO format ("0.50 USD" for 50 cents (U.S.), '
                '"2.99 CAD" for $2.99 Canadian.  Use a format like '
                '"2/6 [0-2-6 GBP]" for pre-decimal British pounds. '
                'Use "0.00 FREE" for free issues. '
                'Separate multple prices with a semicolon.  Use parentheses after '
                'the currency code for notes: "2.99 USD; 3.99 USD (newsstand)" '
                'Use country codes after the currency code if more than one price '
                'uses the same currency: "3.99 EUR DE; 3.50 EUR AT; 1.50 EUR FR"')

    page_count_uncertain = forms.BooleanField(required=False,
      help_text="Check if you do not know or aren't sure about the page count.")

    editing = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
      required=False,
      help_text='The editor and any similar credits for the whole issue.  If no '
                'overall editor is known put a question mark in the field.')
    no_editing = forms.BooleanField(required=False,
      help_text='Check if there is no editor or similar credit (such as '
                'publisher) for the issue as a whole.')

    comments = forms.CharField(widget=forms.Textarea,
                               required=False,
      help_text='Comments between the Indexer and Editor about the change. '
                'These comments are part of the public change history, but '
                'are not part of the regular display.')

def get_bulk_issue_revision_form(series, method):
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
        after = forms.ModelChoiceField(required=False,
          queryset=Issue.objects.filter(series=series).order_by('sort_code'),
          empty_label="[add as initial issues]",
          label = "Add these issue after")

        brand = forms.ModelChoiceField(required=False,
          queryset=Brand.objects.filter(parent=series.publisher))

        indicia_publisher = forms.ModelChoiceField(required=False,
          queryset=IndiciaPublisher.objects.filter(parent=series.publisher))

    return RuntimeBulkIssueRevisionForm

class BulkIssueRevisionForm(forms.Form):
    first_number = forms.IntegerField(required=False,
      help_text='If blank, starts with the number after the issue specified '
                'in the "Add issues after" field, or "1" if '
                'inserting issues at the beginning')

    number_of_issues = forms.IntegerField(min_value=1)

    indicia_frequency = forms.CharField(required=False)

    price = forms.CharField(required=False)

    page_count = forms.DecimalField(required=False,
                                    max_digits=10, decimal_places=3)
    page_count_uncertain = forms.BooleanField(required=False)

    editing = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                              required=False)
    no_editing = forms.BooleanField(required=False)

    comments = forms.CharField(widget=forms.Textarea,
                               required=False,
      help_text='Comments between the Indexer and Editor about the change. '
                'These comments are part of the public change history, but '
                'are not part of the regular display.')

    def _shared_key_order(self):
        return ['brand', 'indicia_publisher', 'indicia_frequency',
                'price', 'page_count', 'page_count_uncertain',
                'editing', 'no_editing', 'comments']

class WholeNumberIssueRevisionForm(BulkIssueRevisionForm):

    volume = forms.IntegerField(required=False)

    no_volume = forms.BooleanField(required=False)

    display_volume_with_number = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super(WholeNumberIssueRevisionForm, self).__init__(*args, **kwargs)
        ordering = ['after', 'number_of_issues', 'first_number',
                    'volume', 'no_volume', 'display_volume_with_number']
        ordering.extend(self._shared_key_order())
        self.fields.keyOrder = ordering

    def clean(self):
        cd = self.cleaned_data

        if cd['volume'] is not None and cd['no_volume']:
            raise forms.ValidationError('You cannot specify a volume and check '
              '"no volume" at the same time')

        if cd['editing'] is not None and cd['no_editing']:
            raise forms.ValidationError('You cannot specify an editing credit and '
              'check "no editing" at the same time')

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
                'beginning')

    issues_per_volume = forms.IntegerField(min_value=1, initial=12,
      help_text='Number of issues in each volume')

    def __init__(self, *args, **kwargs):
        super(PerVolumeIssueRevisionForm, self).__init__(*args, **kwargs)
        ordering = ['after', 'number_of_issues', 'first_number',
                    'first_volume', 'issues_per_volume']
        ordering.extend(self._shared_key_order())
        self.fields.keyOrder = ordering

    def clean(self):
        cd = self.cleaned_data
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

    volume = forms.IntegerField(required=False)

    no_volume = forms.BooleanField(required=False)

    display_volume_with_number = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super(PerYearIssueRevisionForm, self).__init__(*args, **kwargs)
        ordering = ['after', 'number_of_issues',
                    'first_number', 'first_year', 'issues_per_year',
                    'volume', 'no_volume', 'display_volume_with_number']
        ordering.extend(self._shared_key_order())
        self.fields.keyOrder = ordering

    def clean(self):
        cd = self.cleaned_data
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
                'beginning')
    issues_per_cycle = forms.IntegerField(min_value=1, initial=12,
      help_text='Number of issues in each year/volume')

    display_volume_with_number = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super(PerYearIssueRevisionForm, self).__init__(*args, **kwargs)
        ordering = ['after', 'number_of_issues',
                    'first_number', 'first_year', 'first_volume',
                    'issues_per_cycle', 'display_volume_with_number']
        ordering.extend(self._shared_key_order())
        self.fields.keyOrder = ordering

    def clean(self):
        cd = self.cleaned_data
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

def get_story_revision_form(revision=None):
    if revision is None:
        class RuntimeStoryRevisionForm(StoryRevisionForm):
            # Make indexers consciously choose a type by allowing an empty
            # initial value.
            type = forms.ModelChoiceField(queryset=StoryType.objects.all(),
              help_text='Choose the most appropriate available type')
        return RuntimeStoryRevisionForm
    return StoryRevisionForm

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

    title = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                            required=False,
      help_text='If the title is not listed, use the first line of dialog, '
                'place it in "quotation marks" and check the next box.  Do *not* '
                'place the title in brackets.')
    title_inferred = forms.BooleanField(required=False,
      label='Unofficial title',
      help_text='Check if the title was taken from the first line of dialog or '
                'was made up (titles from dialog are preferred, and should be '
                'enclosed in "double quotes"')
    page_count_uncertain = forms.BooleanField(required=False,
      help_text="Check if you do not know or aren't sure about the page count.")

    script = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                             required=False)
    pencils = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                              required=False)
    inks = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                           required=False)
    colors = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                             required=False)
    letters = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                              required=False)
    editing = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
                             required=False)

    no_script = forms.BooleanField(required=False,
      help_text='Check if there is no script or plot to credit, i.e. for a '
                'cover or single-page illustration.  Leave the script field blank.')
    no_pencils = forms.BooleanField(required=False,
      help_text='Check if there is no penciler to credit, i.e. for an '
                'unillustrated text article.  Leave the pencils field blank.')
    no_inks = forms.BooleanField(required=False,
      help_text='Check if there is no inker to credit, i.e. for an '
                'unillustrated text article.  Leave the inks field blank.')
    no_colors = forms.BooleanField(required=False,
      help_text='Check if there is no colorist to credit, i.e. for a '
                'black-and-white comic.  Leave the colors field blank.')
    no_letters = forms.BooleanField(required=False,
      help_text='Check if there is no lettering to credit. Leave the letters box '
                'blank.  However, if the only letters are produced as normal '
                'printed text rather than comic-style lettering, put the word '
                '"typeset" in the letters field and do not check this box.')
    no_editing = forms.BooleanField(required=False,
      help_text='Check if there is no separate editor for this sequence. '
                'This is common when there is an editor for the whole issue.')

    type = forms.ModelChoiceField(queryset=StoryType.objects.all(),
      empty_label=None,
      help_text='Choose the most appropriate available type')

    comments = forms.CharField(widget=forms.Textarea,
                               required=False,
      help_text='Comments between the Indexer and Editor about the change. '
                'These comments are part of the public change history, but '
                'are not part of the regular display.')

