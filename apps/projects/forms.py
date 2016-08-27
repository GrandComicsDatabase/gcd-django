from django import forms
from apps.stddata.models import Country, Language
from apps.gcd.models import Publisher

PUBLISHERS = [[p.id, p.name]
               for p in Publisher.objects
                                 .filter(is_master=True, deleted=False)
                                 .order_by('name')]

IN_USE_COUNTRIES = [['', '--']]
IN_USE_COUNTRIES.extend([c.id, c.name.title()]
                         for c in Country.objects.order_by('name'))

class IssuesWithCoversForm(forms.Form):
    """
    Form for filtering the listing of issues with several covers.
    """
    publisher = forms.ChoiceField(required=False,
                                  choices=PUBLISHERS,
                                  initial=54)

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
                                choices=IN_USE_COUNTRIES,
                                initial='')
    language = forms.ChoiceField(required=False,
                                choices=languages,
                                initial='')
