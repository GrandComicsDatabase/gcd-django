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
        return get_issue_revision_form(**kwargs)

    if model_name == 'story':
        return StoryRevisionForm

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

def get_series_revision_form(publisher=None, source=None):
    if source is None:
        class RuntimeAddSeriesRevisionForm(SeriesRevisionForm):
            class Meta:
                model = SeriesRevision
                fields = _get_series_fields(source)

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
            if source.format != '':
                format = forms.CharField(
                  widget=forms.TextInput(attrs={'class': 'wide'}),
                  required=False,
                  help_text='Check with an editor before modifying this field.')

        return RuntimeSeriesRevisionForm

def _get_series_fields(source=None):
    fields = [
      'name',
      'year_began',
      'year_ended',
      'is_current',
      'country',
      'language',
      'publication_notes',
      'tracking_notes',
      'notes',
    ]
    if source is None or (source.format == '' and source.imprint is None):
        return fields
    if source.format != '':
        fields.append('format')
    if source.imprint is not None:
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

    comments = forms.CharField(widget=forms.Textarea,
                               required=False,
      help_text='Comments between the Indexer and Editor about the change. '
                'These comments are part of the public change history, but '
                'are not part of the regular display.')

def get_issue_revision_form(publisher):
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

    return RuntimeIssueRevisionForm

class IssueRevisionForm(forms.ModelForm):
    class Meta:
        model = IssueRevision
        fields = (
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
            'size',
            'binding',
            'paper_stock',
            'printing_process',
            'editing',
            'notes',
        )

    number = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
      help_text='The issue number (or other label) as it appears in the indicia. '
                'If there is no indicia the cover number may be used. '
                'Series that number by year (mosty European series) should write '
                'the year after a slash: "4/2009" for issue #4 in publication year '
                '2009.  Place brackets around an issue number if it is not '
                'printed in the indicia.  Use "[nn]" if there is no number '
                'printed anywhere on the issue.')

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
                'Spring, 07 for Summer, 10 for Fall and 01 or 12 for Winter.  For '
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

    size = forms.CharField(required=False,
      help_text='Either the name of a standard size (i.e. U.S. Golden Age) or '
                'width x height in inches or centimeters as appropriate.')

    binding = forms.CharField(required=False,
      help_text='A description of the binding.  A pamphlet stapled through the '
                'spine with the staple ends inside the center fold is considered '
                '"saddle-stitched".')

    paper_stock = forms.CharField(required=False,
      help_text='The type of paper (i.e. "newsprint", "glossy" or the name of '
                'a particular stock if known) used for the comic.  If the cover '
                'is of unusual stock that may be noted here as well.')

    printing_process = forms.CharField(required=False,
      help_text='Color vs black-and-white printing.  Note that a book with only '
                'shades of one color still uses a color printing process.')

    editing = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
      help_text='The editor and any similar credits for the whole issue.  If no '
                'overall editor is known put a question mark in the field.')

    comments = forms.CharField(widget=forms.Textarea,
                               required=False,
      help_text='Comments between the Indexer and Editor about the change. '
                'These comments are part of the public change history, but '
                'are not part of the regular display.')

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
                'place it in double quotes and check the next box.  Do *not* '
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

    type = forms.ModelChoiceField(queryset=StoryType.objects.all(),
      empty_label=None,
      help_text='Choose the most appropriate available type')

    comments = forms.CharField(widget=forms.Textarea,
                               required=False,
      help_text='Comments between the Indexer and Editor about the change. '
                'These comments are part of the public change history, but '
                'are not part of the regular display.')

