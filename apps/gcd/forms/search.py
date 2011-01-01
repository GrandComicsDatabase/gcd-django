# -*- coding: utf-8 -*-
from re import match
from decimal import Decimal, InvalidOperation
from django import forms
from apps.gcd.models import Country, Language, Indexer, StoryType

ORDERINGS = [['', '--'],
             ['date', 'Date'],
             ['series', 'Series Name'],
             ['publisher', 'Publisher'],
             ['country', 'Country'],
             ['language', 'Language'],
             ['script', 'Writer'],
             ['pencils', 'Penciler'],
             ['inks', 'Inker'],
             ['colors', 'Colorist'],
             ['letters', 'Letterer'],
             ['editing', 'Editing'],
             ['job_number', 'Job Number']]

DATE_FORMATS = ['%Y.%m.%d', '%Y-%m-%d',
                '%m/%d/%Y', '%m/%d/%y',
                '%m / %d / %Y', '%m / %d / %y',
                '%b %d %Y', '%b %d, %Y',
                '%d %b %Y', '%d %b, %Y',
                '%B %d %Y', '%B %d, %Y',
                '%d %B %Y', '%d %B, %Y',
                '%Y']

PAGE_RANGE_REGEXP = r'(?P<begin>(?:\d|\.)+)\s*-\s*(?P<end>(?:\d|\.)+)$'

class AdvancedSearch(forms.Form):
    target = forms.ChoiceField(choices=[['publisher', 'Publishers'],
                                        ['series', 'Series'],
                                        ['issue', 'Issues'],
                                        ['sequence', 'Stories'],
                                        ['cover', 'Covers']],
                               initial='sequence',
                               label='Search For')

    method_help = "All methods case-insensitive."
    method = forms.ChoiceField(choices=[['iexact', 'Matches Exactly'],
                                        ['istartswith', 'Starts With'],
                                        ['icontains', 'Contains'] ],
                               initial='icontains',
                               label='Search Method',
                               help_text = method_help)

    logic_help = "This option applies primarily to the story credit fields." \
                 "It will eventually be replaced by more powerful options."
    logic = forms.ChoiceField(choices=[[False, 'AND all fields'],
                                       [True, 'OR credits, AND other fields']],
                              initial=False,
                              label='Behavior',
                              help_text=logic_help)

    order1 = forms.ChoiceField(choices=ORDERINGS,
                               required=False,
                               initial='series',
                               label='First By')
    order2 = forms.ChoiceField(choices=ORDERINGS,
                               required=False,
                               initial='date',
                               label='Second By')
    order3 = forms.ChoiceField(choices=ORDERINGS,
                               required=False,
                               label='Third By')

    start_date = forms.DateField(label='Start Date', required=False,
                                 input_formats=DATE_FORMATS)
    end_date = forms.DateField(label='End Date', required=False,
                                 input_formats=DATE_FORMATS)

    pub_name = forms.CharField(label='Publisher', required=False)
    pub_notes = forms.CharField(label='Notes', required=False)

    series = forms.CharField(label='Name', required=False)
    format = forms.CharField(label='Format', required=False)
    series_notes = forms.CharField(label='Series Notes', required=False)
    tracking_notes = forms.CharField(label='Tracking Notes', required=False)
    publication_notes = forms.CharField(label='Publication Notes',
                                        required=False)
    not_reserved = forms.BooleanField(label="Not Reserved",
                                      required=False)
    is_current = forms.BooleanField(label="Current",
                                      required=False)

    issues = forms.CharField(label='Issues', required=False)
    # Volume is a char field to allow ranges and lists.
    volume = forms.CharField(label='Volume', required=False)
    brand = forms.CharField(required=False)
    indicia_publisher = forms.CharField(label='Indicia Publisher', required=False)
    price = forms.CharField(required=False)
    issue_pages = forms.CharField(required=False)
    issue_notes = forms.CharField(label='Issue Notes', required=False)
    issue_editing = forms.CharField(required=False)
    issue_date = forms.CharField(label='Cover Date', required=False)

    cover_needed = forms.BooleanField(label="Cover is Needed", 
                                       required=False)
    is_indexed = forms.NullBooleanField(label="Is Indexed", required=False,
      widget=forms.Select(choices=((None, ""),
                                   (True, "yes"),
                                   (False, "no"))))
    indexer = forms.ModelMultipleChoiceField(required=False,
      queryset=Indexer.objects.filter(imps__gt=0).\
      order_by('user__first_name', 'user__last_name').select_related('user'),
      widget=forms.SelectMultiple(attrs={'size' : '6'}))

    feature = forms.CharField(required=False)
    type = forms.ModelMultipleChoiceField(queryset=StoryType.objects.all(),
      widget=forms.SelectMultiple(attrs={'size' : '6'}),
      required=False)

    title = forms.CharField(required=False)
    pages = forms.CharField(required=False)

    script = forms.CharField(required=False)
    pencils = forms.CharField(required=False)
    inks = forms.CharField(required=False)
    colors = forms.CharField(required=False)
    letters = forms.CharField(required=False)
    story_editing = forms.CharField(required=False)
    job_number = forms.CharField(label='Job Number', required=False)

    genre = forms.CharField(required=False)
    characters = forms.CharField(required=False)
    synopsis = forms.CharField(required=False)
    reprint_notes = forms.CharField(required=False)

    notes = forms.CharField(label='Notes', required=False)

    country = forms.MultipleChoiceField(required=False,
      choices=([c.code, c.name.title()]
               for c in Country.objects.order_by('name')),
      widget=forms.SelectMultiple(attrs={'size' : '4'}))
    alt_country = forms.CharField(label='', required=False, max_length=3)

    language = forms.MultipleChoiceField(required=False,
      choices=([l.code, l.name] for l in Language.objects.order_by('name')),
      widget=forms.SelectMultiple(attrs={'size' : '4'}))
    alt_language = forms.CharField(label='', required=False, max_length=3)

    def clean_pages(self):
        pages_data = self.cleaned_data['pages']
        if pages_data:
            range_match = match(PAGE_RANGE_REGEXP, pages_data)
            if not range_match:
                try:
                    Decimal(pages_data)
                except InvalidOperation:
                    raise forms.ValidationError(
                          "Page count must be a decimal number or a pair of "
                          "decimal numbers separated by a hyphen.")
        return pages_data

    def clean_issue_pages(self):
        pages_data = self.cleaned_data['issue_pages']
        if pages_data:
            range_match = match(PAGE_RANGE_REGEXP, pages_data)
            if not range_match:
                try:
                    Decimal(pages_data)
                except InvalidOperation:
                    raise forms.ValidationError(
                          "Page count must be a decimal number or a pair of "
                          "decimal numbers separated by a hyphen.")
        return pages_data

    def clean(self):
        cleaned_data = self.cleaned_data
        if self.is_valid():
            if cleaned_data['cover_needed']:
                # use of in since after distinction stuff is cleared add series
                if cleaned_data['target'] not in ['issue','series']: 
                    raise forms.ValidationError(
                      "Searching for covers which are missing or need to be"
                      " replaced is valid only for issue or series searches.")
            if cleaned_data['target'] == 'cover' and cleaned_data['type']:
                if len(cleaned_data['type']) > 1 or StoryType.objects\
                  .get(name='cover') not in cleaned_data['type']:
                    raise forms.ValidationError("When searching for covers"
                          " only type cover can be selected.")
        return cleaned_data
