from django import forms
from apps.gcd.models import Country, Language, Indexer

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
             ['editor', 'Editor'],
             ['job_number', 'Job Number']]

DATE_FORMATS = ['%Y.%m.%d', '%Y-%m-%d',
                '%m/%d/%Y', '%m/%d/%y',
                '%b %d %Y', '%b %d, %Y',
                '%d %b %Y', '%d %b, %Y',
                '%B %d %Y', '%B %d, %Y',
                '%d %B %Y', '%d %B, %Y',
                '%Y']

class AdvancedSearch(forms.Form):
    target = forms.ChoiceField(choices=[['publisher', 'Publishers'],
                                        ['series', 'Series'],
                                        ['issue', 'Issues'],
                                        ['sequence', 'Stories']],
                               initial='series',
                               label='Search For')

    method_help = "All methods case-insensitive.  Regular expressions " + \
                  "use MYSQL's syntax."
    method = forms.ChoiceField(choices=[['iexact', 'Matches Exactly'],
                                        ['istartswith', 'Starts With'],
                                        ['icontains', 'Contains'],
                                       ], # ['iregex', 'Regular Expression']],
                               initial='icontains',
                               label='Search Method',
                               help_text = method_help)

    logic_help = "This option mostly applies to credit fields, and only " + \
                 "sort of works.  It will be replaced with something better."
    logic = forms.ChoiceField(choices=[[False, 'AND all fields'],
                                       [True, 'OR credit, AND other fields']],
                              initial=False,
                              label='Behavior',
                              help_text=logic_help)

    order1 = forms.ChoiceField(choices=ORDERINGS,
                               required=False,
                               initial='name',
                               label='First By')
    order2 = forms.ChoiceField(choices=ORDERINGS,
                               required=False,
                               label='Second By')
    order3 = forms.ChoiceField(choices=ORDERINGS,
                               required=False,
                               label='Third By')

#    start_date = forms.DateField(label='Start Date', required=False,
#                                 input_formats=DATE_FORMATS)
#    end_date = forms.DateField(label='End Date', required=False,
#                                 input_formats=DATE_FORMATS)

    pub_name = forms.CharField(label='Publisher', required=False)
    imprints = forms.BooleanField(label='Imprints', required=False)
#    pub_notes = forms.CharField(label='Notes', required=False)

    series = forms.CharField(label='Name', required=False)
#    format = forms.CharField(label='Format', required=False)
#    series_notes = forms.CharField(label='Series Notes', required=False)
#    tracking_notes = forms.CharField(label='Tracking Notes', required=False)
#    publication_notes = forms.CharField(label='Publication Notes',
#                                        required=False)

#    issues = forms.CharField(label='Issues', required=False)
#    price = forms.CharField(required=False)
#    issue_pages = forms.CharField(required=False)
#    issue_notes = forms.CharField(label='Issue Notes', required=False)
#    issue_reprints = forms.CharField(label='Issue Reprints', required=False)
    issue_editor = forms.CharField(required=False)
#    issue_date = forms.CharField(label='Cover Date', required=False)


    feature = forms.CharField(required=False)
#    type = forms.CharField(required=False)
    title = forms.CharField(required=False)
#    pages = forms.CharField(required=False)

    script = forms.CharField(required=False)
    pencils = forms.CharField(required=False)
    inks = forms.CharField(required=False)
    colors = forms.CharField(required=False)
    letters = forms.CharField(required=False)
    story_editor = forms.CharField(required=False)
    job_number = forms.CharField(label='Job Number', required=False)

    genre = forms.CharField(required=False)
    characters = forms.CharField(required=False)
    synopsis = forms.CharField(required=False)
    reprints = forms.CharField(required=False)

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

#    indexer = forms.ModelMultipleChoiceField(required=False,
#      queryset=Indexer.objects.all(),
#      widget=forms.SelectMultiple(attrs={'size' : '6'}))

