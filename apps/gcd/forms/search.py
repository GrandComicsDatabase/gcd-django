# -*- coding: utf-8 -*-
from re import match
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple

from apps.stddata.models import Country, Language
from apps.indexer.models import Indexer
from apps.gcd.models import StoryType, OLD_TYPES, SeriesPublicationType
from apps.gcd.models.support import GENRES

ORDERINGS = [['', '--'],
             ['date', 'Date'],
             ['series', 'Series Name'],
             ['publisher', 'Publisher'],
             ['brand', 'Publisher Brand'],
             ['indicia_publisher', 'Indicia Publisher'],
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
COUNT_RANGE_REGEXP = r'(?P<min>\d+)?\s*-\s*(?P<max>\d+)?$'


class AdvancedSearch(forms.Form):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(AdvancedSearch, self).__init__(*args, **kwargs)
        self.fields['country'] = forms.MultipleChoiceField(
          required=False,
          widget=FilteredSelectMultiple('Countries', False),
          choices=([c.code, c.name.title()]
                   for c in Country.objects.order_by('name')))
        self.fields['language'] = forms.MultipleChoiceField(
          required=False,
          choices=([L.code, L.name]
                   for L in Language.objects.order_by('name')),
          widget=FilteredSelectMultiple('Languages', False))
        if user and user.is_authenticated:
            self.fields['in_collection'] = forms.ModelMultipleChoiceField(
              label='',
              widget=FilteredSelectMultiple('Collections', False),
              queryset=user.collector.collections.all(),
              required=False)
            self.user = user
            self.fields['in_selected_collection'] = forms.BooleanField(
              label="Is in the selected collections", required=False,
              initial=True)

    target = forms.ChoiceField(choices=[['publisher', 'Publishers'],
                                        ['brand_group',
                                         'Publisher Brand Group'],
                                        ['brand_emblem',
                                         'Publisher Brand Emblem'],
                                        ['indicia_publisher',
                                         'Indicia / Colophon Publisher'],
                                        ['series', 'Series'],
                                        ['issue', 'Issues'],
                                        ['issue_cover', 'Covers for Issues'],
                                        ['sequence', 'Stories'],
                                        ['cover', 'Covers']],
                               initial='sequence',
                               label='Search For')

    method_help = "All methods case-insensitive."
    method = forms.ChoiceField(choices=[
                               ['iexact', 'Matches Exactly'],
                               ['istartswith', 'Starts With'],
                               ['icontains', 'Contains'],
                               ['exact', 'Matches Exactly (case sensitive)'],
                               ['startswith', 'Starts With (case sensitive)'],
                               ['contains', 'Contains (case sensitive)'],
                               ],
                               initial='icontains',
                               label='Search Method',
                               help_text=method_help)

    logic_help = "This option applies primarily to the story credit fields." \
                 "It will eventually be replaced by more powerful options."
    logic = forms.BooleanField(widget=forms.Select(choices=(
                                   (False, 'AND all fields'),
                                   (True, 'OR credits, AND other fields'),
                                   )),
                               initial=False,
                               required=False,
                               label='Behavior',
                               help_text=logic_help)

    keywords = forms.CharField(required=False)

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
    use_on_sale_date = forms.BooleanField(label="Use On-Sale Date",
                                          required=False)
    updated_since = forms.DateField(label='Updated Since', required=False,
                                    input_formats=DATE_FORMATS)

    pub_name = forms.CharField(label='Publisher', required=False)
    pub_notes = forms.CharField(label='Notes', required=False)

    brand_group = forms.CharField(required=False)
    brand_emblem = forms.CharField(required=False)
    brand_notes = forms.CharField(label='Notes', required=False)

    indicia_publisher = forms.CharField(label='Indicia / Colophon Publisher',
                                        required=False)
    ind_pub_notes = forms.CharField(label='Notes', required=False)
    is_surrogate = forms.NullBooleanField(
      label='Is Surrogate?', required=False,
      widget=forms.Select(choices=((None, ""),
                                   (True, "yes"),
                                   (False, "no"))))

    series = forms.CharField(label='Name', required=False)
    series_notes = forms.CharField(label='Series Notes', required=False)
    tracking_notes = forms.CharField(label='Tracking Notes', required=False)
    not_reserved = forms.BooleanField(label="Not Reserved",
                                      required=False)
    is_current = forms.BooleanField(label="Current",
                                    required=False)
    issue_count = forms.CharField(label='Issue Count',
                                  required=False)
    series_year_began = forms.IntegerField(required=False,
                                           label='Series Year Began')
    is_comics = forms.NullBooleanField(
      label="Comics Publication, i.e. 50+x% comics", required=False,
      widget=forms.Select(choices=((None, ""),
                                   (True, "yes"),
                                   (False, "no"))))

    color = forms.CharField(label='Color', required=False)
    dimensions = forms.CharField(label='Dimensions', required=False)
    paper_stock = forms.CharField(label='Paper Stock', required=False)
    binding = forms.CharField(label='Binding', required=False)
    publishing_format = forms.CharField(label='Publishing Format',
                                        required=False)
    publication_type = forms.ModelMultipleChoiceField(
                             label='Publication Type',
                             queryset=SeriesPublicationType.objects.all(),
                             required=False)

    issues = forms.CharField(label='Issues', required=False)
    volume = forms.CharField(label='Volume', required=False)
    issue_title = forms.CharField(label='Title', required=False)
    variant_name = forms.CharField(label='Variant Name', required=False)
    is_variant = forms.NullBooleanField(
      label='Is a Variant', required=False,
      widget=forms.Select(choices=((None, ""),
                                   (True, "yes"),
                                   (False, "no"))))
    price = forms.CharField(required=False)
    issue_pages = forms.CharField(label='Issue Pages', required=False)
    issue_pages_uncertain = forms.NullBooleanField(
      label='Page count uncertain', required=False,
      widget=forms.Select(choices=((None, ""),
                                   (True, "yes"),
                                   (False, "no"))))
    issue_notes = forms.CharField(label='Issue Notes', required=False)
    issue_editing = forms.CharField(label='Issue Editing', required=False)
    issue_date = forms.CharField(label='Cover Date', required=False)
    isbn = forms.CharField(label='ISBN', required=False)
    barcode = forms.CharField(required=False)
    rating = forms.CharField(label="Publisher's Age Guidelines",
                             required=False)
    indicia_frequency = forms.CharField(label='Indicia Frequency',
                                        required=False)
    issue_reprinted = forms.ChoiceField(
      label="Reprinted", required=False,
      choices=[(None, ""),
               ('has_reprints', "parts of the issue are reprints"),
               ('is_reprinted', "parts of the issue are reprinted"),
               ('issue_level_reprints', "issue level reprints from sequences"),
               ('issue_level_reprinted', "issue level reprinted in sequences")])

    cover_needed = forms.BooleanField(label="Cover is Needed",
                                      required=False)
    is_indexed = forms.NullBooleanField(
      label="Is Indexed", required=False,
      widget=forms.Select(choices=((None, ""),
                                   (True, "yes"),
                                   (False, "no"))))
    image_resources = forms.MultipleChoiceField(
      label='Image Resources',
      widget=FilteredSelectMultiple('Image Resources', False),
      choices=(('has_soo', 'Has Statement of Ownership Scan'),
               ('needs_soo', 'Needs Statement of Ownership Scan'),
               ('has_indicia', 'Has Indicia Scan'),
               ('needs_indicia', 'Needs Indicia Scan')),
      required=False)
    indexer = forms.ModelMultipleChoiceField(
      required=False, label='',
      queryset=Indexer.objects.filter(imps__gt=0).
      order_by('user__first_name', 'user__last_name').select_related('user'),
      widget=FilteredSelectMultiple('Indexers', False, attrs={'size': '6'}))

    feature = forms.CharField(required=False)
    type = forms.ModelMultipleChoiceField(
      queryset=StoryType.objects.exclude(name__in=[i for i in OLD_TYPES]),
      widget=FilteredSelectMultiple('Story Types', False,
                                    attrs={'size': '6'}),
      required=False)

    title = forms.CharField(required=False)
    pages = forms.CharField(required=False)
    pages_uncertain = forms.NullBooleanField(
      label='Page count uncertain',
      required=False,
      widget=forms.Select(choices=((None, ""),
                                   (True, "yes"),
                                   (False, "no"))))

    credit_is_linked = forms.NullBooleanField(
      label="Linked and Text Credits", required=False,
      widget=forms.Select(choices=((None, "both linked and text credits"),
                                   (True, "linked credits only"),
                                   (False, "text credits only"))))
    script = forms.CharField(required=False)
    pencils = forms.CharField(required=False)
    inks = forms.CharField(required=False)
    colors = forms.CharField(required=False)
    letters = forms.CharField(required=False)
    story_editing = forms.CharField(label='Story Editing', required=False)
    job_number = forms.CharField(label='Job Number', required=False)

    first_line = forms.CharField(required=False)
    genre = forms.MultipleChoiceField(
      required=False,
      widget=FilteredSelectMultiple('Genres', False),
      choices=([c, c] for c in GENRES['en']))
    characters = forms.CharField(required=False)
    synopsis = forms.CharField(required=False)
    reprint_notes = forms.CharField(label='Reprint Notes', required=False)
    story_reprinted = forms.ChoiceField(
      label="Reprinted", required=False,
      choices=[('', ""),
               ('from', "is a linked reprint"),
               ('in', "has linked reprints"),
               ('not', "is not a linked reprint")])

    notes = forms.CharField(label='Notes', required=False)

    alt_country = forms.CharField(label='', required=False, max_length=3)

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

    def clean_issue_count(self):
        issue_count_data = self.cleaned_data['issue_count'].strip()
        if issue_count_data:
            issue_count_match = (issue_count_data != '-' and
                                 match(COUNT_RANGE_REGEXP, issue_count_data))
            if not issue_count_match:
                try:
                    int(issue_count_data)
                except ValueError:
                    raise forms.ValidationError(
                          "Issue count must be an integer or an integer "
                          "range reparated by a hyphen (e.g. 100-200, "
                          "100-, -200).")
        return issue_count_data

    def clean_keywords(self):
        keywords = self.cleaned_data['keywords']
        if keywords is not None:
            not_allowed = False
            for c in ['<', '>', '{', '}', ':', '/', '\\', '|', '@', ',']:
                if c in keywords:
                    not_allowed = True
                    break
            if not_allowed:
                raise forms.ValidationError('The following characters are '
                  'not allowed in a keyword: < > { } : / \\ | @ ,')

        return keywords

    def clean_in_collection(self):
        collections = self.cleaned_data['in_collection']
        if collections.exclude(collector=self.user.collector).count():
            raise forms.ValidationError(
                  "One cannot search in the collections of other users.")
        return collections

    def clean(self):
        cleaned_data = self.cleaned_data
        if self.is_valid():
            if cleaned_data['cover_needed']:
                # use of in since after distinction stuff is cleared add series
                if cleaned_data['target'] not in ['issue', 'series']:
                    raise forms.ValidationError(
                      "Searching for covers which are missing or need to be"
                      " replaced is valid only for issue or series searches.")
            if cleaned_data['target'] == 'cover' and cleaned_data['type']:
                if len(cleaned_data['type']) > 1 or StoryType.objects\
                  .get(name='cover') not in cleaned_data['type']:
                    raise forms.ValidationError(
                      "When searching for covers only type cover can be "
                      "selected.")
            if cleaned_data['use_on_sale_date']:
                if cleaned_data['target'] not in ['issue', 'sequence',
                                                  'issue_cover']:
                    raise forms.ValidationError(
                      "The on-sale date can only be used in issue or story "
                      "searches.")
            if cleaned_data['start_date'] or cleaned_data['end_date']:
                if (cleaned_data['start_date'] and
                    len(self.data['start_date']) <= 4) or \
                  (cleaned_data['end_date'] and
                   len(self.data['end_date']) <= 4):
                    if cleaned_data['target'] in ['issue', 'issue_cover',
                                                  'sequence', 'cover']:
                        raise forms.ValidationError(
                          "For issue-level search targets please use full "
                          "dates.")
        return cleaned_data
