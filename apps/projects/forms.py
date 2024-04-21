from django import forms
from apps.stddata.models import Country, Language
from apps.gcd.models import Publisher

PUBLISHERS = lambda: [[p.id, p.name]
               for p in Publisher.objects
                                 .filter(deleted=False)
                                 .order_by('name')]
COUNTRIES = lambda: [[c.id, c.name.title()]
                     for c in Country.objects.order_by('name')]

SEVERAL_COVER_PUBLISHER_IDS = [1984, 1082, 4475, 78, 2761, 3932, 7151, 4004, 525, 3371, 543, 4551, 2105, 604, 52, 4720, 2550, 764, 2063, 709, 659, 76, 1197, 279, 1052, 570, 869, 4508, 349, 4219, 7093, 778, 3032, 1513, 3197, 3009, 4738, 2758, 6124, 2066, 4035, 670, 5043, 3361, 54, 8255, 3022, 4437]

SEVERAL_COVER_PUBLISHERS = lambda: [[p.id, p.name]
               for p in Publisher.objects
                                 .filter(deleted=False,
                                         id__in=SEVERAL_COVER_PUBLISHER_IDS)
                                 .order_by('name')]

IN_USE_COUNTRIES = [['', '--']]

class IssuesWithCoversForm(forms.Form):
    """
    Form for filtering the listing of issues with several covers.
    """
    publisher = forms.ChoiceField(required=False,
                                  choices=SEVERAL_COVER_PUBLISHERS,
                                  initial=709)

class ReprintInspectionForm(forms.Form):
    """
    Form for filtering the listing of issues with identical issue and cover notes.
    """
    def __init__(self, *args, **kwargs):
        super(ReprintInspectionForm, self).__init__(*args, **kwargs)
        publisher_choices = [['', '--']]
        publisher_choices.extend(PUBLISHERS())
        self.fields['publisher'] = forms.ChoiceField(required=False,
                                                     choices=publisher_choices)
        IN_USE_COUNTRIES.extend(COUNTRIES())
        self.fields['country'] = forms.ChoiceField(required=False,
                                                   choices=IN_USE_COUNTRIES)
        languages = [['', '--']]
        languages.extend([l.id, l.name]
                         for l in Language.objects.order_by('name'))
        self.fields['language'] = forms.ChoiceField(required=False,
            choices=languages)

    publisher = forms.ChoiceField(required=False)
    country = forms.ChoiceField(required=False, initial='')
    language = forms.ChoiceField(required=False, initial='')
