from django import forms
from apps.stddata.models import Country, Language
from apps.gcd.models import Publisher

PUBLISHERS = [[p.id, p.name]
               for p in Publisher.objects
                                 .filter(is_master=True, deleted=False)
                                 .order_by('name')]

SEVERAL_COVER_PUBLISHER_IDS = [829, 1984, 1950, 196, 1082, 512, 1846, 890, 1163, 286, 223, 4475, 2020, 2549, 119, 745, 4807, 78, 1027, 6084, 6907, 2761, 5132, 3932, 5867, 2476, 6524, 7151, 3093, 672, 1868, 4004, 525, 3371, 8162, 4589, 1974, 543, 4551, 2105, 2114, 4476, 3113, 138, 717, 604, 936, 84, 2044, 613, 1847, 947, 4580, 728, 52, 8886, 4677, 3947, 493, 380, 61, 4720, 5735, 2550, 104, 809, 339, 3336, 511, 549, 113, 3752, 1557, 764, 307, 2565, 4177, 5176, 610, 7459, 895, 6989, 682, 3729, 3372, 3058, 4493, 2063, 445, 3591, 6894, 4473, 7956, 5732, 856, 2547, 67, 2463, 709, 336, 659, 1977, 4604, 76, 379, 3123, 7454, 7018, 4999, 1197, 6229, 677, 946, 1901, 833, 2562, 279, 1954, 5987, 485, 3532, 1052, 3742, 1963, 2542, 3193, 2492, 382, 6538, 4377, 2216, 71, 570, 869, 6889, 3916, 819, 3161, 1818, 769, 4508, 349, 3077, 3640, 7022, 4219, 828, 7093, 778, 715, 3032, 1513, 900, 2512, 145, 32, 7460, 3097, 2001, 3197, 8997, 4058, 3009, 4738, 8943, 920, 538, 3165, 2758, 6124, 2066, 3287, 509, 4223, 296, 4035, 5701, 825, 4887, 670, 5043, 4573, 515, 364, 6189, 8443, 3361, 5346, 10084, 906, 88, 1792, 54, 3370, 8045, 2900, 1146, 802, 4835, 8255, 4722, 3022, 8474, 169, 454, 1810, 1071, 4437, 5730, 2696, 4681, 2981, 4593, 1819, 31, 823]

SEVERAL_COVER_PUBLISHERS = [[p.id, p.name]
               for p in Publisher.objects
                                 .filter(is_master=True, deleted=False,
                                         id__in=SEVERAL_COVER_PUBLISHER_IDS)
                                 .order_by('name')]

IN_USE_COUNTRIES = [['', '--']]
IN_USE_COUNTRIES.extend([c.id, c.name.title()]
                         for c in Country.objects.order_by('name'))

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
