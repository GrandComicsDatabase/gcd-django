from django import forms
from apps.stddata.models import Country, Language
from apps.gcd.models import Publisher

PUBLISHERS = lambda: [[p.id, p.name]
               for p in Publisher.objects
                                 .filter(deleted=False)
                                 .order_by('name')]
COUNTRIES = lambda: [[c.id, c.name.title()]
                     for c in Country.objects.order_by('name')]

SEVERAL_COVER_PUBLISHER_IDS = [1984, 1950, 196, 1082, 512, 1846, 4475, 745, 4807, 78, 1027, 6084, 2761, 3932, 5867, 7151, 1868, 4004, 525, 3371, 4589, 543, 4551, 2105, 2114, 4476, 604, 613, 52, 3947, 61, 4720, 2550, 3336, 511, 549, 113, 3752, 1557, 764, 7459, 682, 2063, 445, 3591, 2547, 709, 336, 659, 1977, 76, 4999, 1197, 6229, 677, 946, 1901, 279, 3532, 1052, 3742, 3193, 2216, 570, 869, 769, 4508, 349, 4219, 7093, 778, 3032, 1513, 145, 7460, 3197, 4058, 3009, 4738, 538, 3165, 2758, 6124, 2066, 296, 4035, 670, 5043, 3361, 5346, 54, 8045, 8255, 4722, 3022, 8474, 454, 1810, 1071, 4437, 31]

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
