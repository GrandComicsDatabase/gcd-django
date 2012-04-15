from django import forms
from apps.gcd.models import Publisher, Country, Language

IMPRINTS_IN_USE_ORDERINGS = [
    ['', '--'],
    ['parent__name', 'Parent Name'],
    ['name', 'Imprint Name'],
    ['series_count', 'Series Count'],
    ['parent__country__name', 'Parent Country'],
]

PUBLISHERS = [[p.id, p.name]
                  for p in Publisher.objects
                                    .filter(is_master=True,
                                            deleted=False)
                                    .order_by('name')]
IMPRINTS_IN_USE_COUNTRIES = [['', '--']]
IMPRINTS_IN_USE_COUNTRIES.extend([c.id, c.name.title()]
                                 for c in Country.objects.order_by('name'))

IMPRINTS_IN_USE_PARENTS = [['', '--']]
IMPRINTS_IN_USE_PARENTS.extend([p.id, p.name]
                               for p in Publisher.objects
                                                 .filter(is_master=True,
                                                         imprint_count__gt=0)
                                                 .order_by('name'))
class ImprintsInUseForm(forms.Form):
    """
    Form for filtering the listing of imprints in use.
    """
    parent = forms.ChoiceField(required=False,
                               choices=IMPRINTS_IN_USE_PARENTS,
                               initial='')
    parent_country = forms.ChoiceField(required=False,
                                       choices=IMPRINTS_IN_USE_COUNTRIES,
                                       initial='')
    imprint_country = forms.ChoiceField(required=False,
                                        choices=IMPRINTS_IN_USE_COUNTRIES,
                                        initial='')
    order1 = forms.ChoiceField(choices=IMPRINTS_IN_USE_ORDERINGS,
                               required=False,
                               initial='series',
                               label='First By')
    order2 = forms.ChoiceField(choices=IMPRINTS_IN_USE_ORDERINGS,
                               required=False,
                               initial='date',
                               label='Second By')
    order3 = forms.ChoiceField(choices=IMPRINTS_IN_USE_ORDERINGS,
                               required=False,
                               label='Third By')

class IssuesWithCoversForm(forms.Form):
    """
    Form for filtering the listing of issues with several covers.
    """
    publisher = forms.ChoiceField(required=False,
                                  choices=PUBLISHERS,
                                  initial=54)

class IssueCoverNotesForm(forms.Form):
    """
    Form for filtering the listing of issues with identical issue and cover notes.
    """
    choices = [['', '--']]
    choices.extend(PUBLISHERS)
    languages = [['', '--']]
    languages.extend([l.id, l.name] for l in Language.objects.order_by('name'))
    publisher = forms.ChoiceField(required=False,
                                  choices=choices)
    country = forms.ChoiceField(required=False,
                                choices=IMPRINTS_IN_USE_COUNTRIES,
                                initial='')
    language = forms.ChoiceField(required=False,
                                choices=languages,
                                initial='')

class ReprintInspectionForm(forms.Form):
    """
    Form for filtering the listing of issues with identical issue and cover notes.
    """
    choices = [['', '--']]
    choices.extend(PUBLISHERS)
    languages = [['', '--']]
    languages.extend([l.id, l.name] for l in Language.objects.order_by('name'))
    publisher = forms.ChoiceField(required=False,
                                  choices=choices)
    country = forms.ChoiceField(required=False,
                                choices=IMPRINTS_IN_USE_COUNTRIES,
                                initial='')
    language = forms.ChoiceField(required=False,
                                choices=languages,
                                initial='')
                                