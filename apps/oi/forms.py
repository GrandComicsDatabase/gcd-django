from django import forms
from django.db.models import Count
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

from apps.oi.models import *
from apps.gcd.models import *

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

class PublisherRevisionForm(forms.ModelForm):
    class Meta:
        model = PublisherRevision
        fields = (
            'name',
            'year_began',
            'year_ended',
            'country',
            'url',
            'notes',
        )
# TODO: For now, parent publisher may only be set during an add, and not changed
#       later.  Fix this eventually.  The is_master field gets taken care of the
#       same way for now (true for non-imprints, false for imprints).
#
#     parent = ForeignKeyField(queryset=Publisher.objects.filter(is_master=True),
#                              target_name='Master Publisher',
#                              required=False,
#                              help_text='For imprints, the numeric database ID '
#                                        'of the master publisher with which '
#                                        'the imprint is associated.  Master '
#                                        'publishers generally should not set '
#                                        'this field.')

    comments = forms.CharField(widget=forms.Textarea,
                               required=False,
      help_text='Comments between the Indexer and Editor about the change. '
                'These comments are part of the public change history, but '
                'are not part of the regular display.')

class SeriesRevisionForm(forms.ModelForm):
    class Meta:
        model = SeriesRevision
        fields = (
            'name',
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
# TODO: For now, publisher and imprint may only be set during an add,
#       and not changed later.  Fix this eventually.
#
#     publisher = ForeignKeyField(queryset=Publisher.objects.filter(is_master=True),
#                              target_name='Publisher',
#                              help_text='The numeric database ID '
#                                        'of the master publisher which '
#                                        'publishes the series.')
# 
#     imprint = ForeignKeyField(queryset=Publisher.objects.filter(is_master=False),
#                              target_name='Imprint',
#                              required=False,
#                              help_text='The numeric database ID of the '
#                                        'imprint, if any, of the series. '
#                                        'Currently, "imprints" may also indicate '
#                                        'indicia publishers and/or cover brands.')

    name = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
      help_text=('Series name as it appears in the indicia (or cover only '
                 'if there is no indicia), with any leading article moved '
                 'to the end after a comma.'))
    format = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
      required=False,
      help_text='Catch-all field for size, binding, paper, coloring, etc.')
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

class IssueRevisionForm(forms.ModelForm):
    class Meta:
        model = IssueRevision
        fields = (
            'number',
            'volume',
            'display_volume_with_number',
            'price',
            'publication_date',
            'key_date',
        )

    number = forms.CharField(widget=forms.TextInput(attrs={'class': 'wide'}),
      help_text='The issue number (or other label) as it appears in the indicia. '
                'If there is no indicia the cover number may be used. '
                'Series that number by year (mosty European series) should write '
                'the year after a slash: "4/2009" for issue #4 in publication year '
                '2009.  Place brackets around an issue number if it is not '
                'printed in the indicia.  Use "[nn]" if there is no number '
                'printed anywhere on the issue.')

    volume = forms.IntegerField(
      help_text='Volume number (only numeric volumes allowed at this time). '
                'For collections or other items that only have a volume number, '
                'put the same number in both this field and the issue number '
                'and do *not* check "Display volume with number". '
                'If there is no volume, leave this field blank.')

    display_volume_with_number = forms.BooleanField(required=False,
      help_text='Check to cause the site to display the volume as part of the '
                'issue number.  For example with a volume of "2" and an issue '
                'number of "1", checking this box will display "v2#1" instead '
                'of just "1" in the status grids and issues lists for the series.')

    price = forms.CharField(
      help_text='Price in ISO format ("0.50 USD" for 50 cents (U.S.), '
                '"2.99 CAD" for $2.99 Canadian.  Use a format like '
                '"2/6 [0-2-6 GBP]" for pre-decimal British pounds. '
                'Use "0.00 FREE" for free issues. '
                'Separate multple prices with a semicolon.  Use parentheses after '
                'the currency code for notes: "2.99 USD; 3.99 USD (newsstand)" '
                'Use country codes after the currency code if more than one price '
                'uses the same currency: "3.99 EUR DE; 3.50 EUR AT; 1.50 EUR FR"')

    publication_date = forms.CharField(
      help_text='The publicaton date as printed on the comic, except with the '
                'name of the month (if any) spelled out.  Any part of the date '
                'that is not printed on the comic but is known should be put '
                'in square brackets, such as "[January] 2009".  Do NOT use the '
                'shipping date in this field, only the publication date.')

    key_date = forms.CharField(widget=forms.TextInput(attrs={'class': 'key_date'}),
      help_text='Special date form used for sorting:  YYYY.MM.DD where the day '
                '(DD) shoud be 00 for monthly books, and use arbitrary numbers '
                'such as 10, 20, 30 to indicate an "early" "mid" or "late" month '
                'cover date.  For the month (MM) on quarterlies, use 04 for '
                'Spring, 07 for Summer, 10 for Fall and 01 or 12 for Winter.  For '
                'annuals use a month of 00 or 13 or whatever sorts it best.  When '
                'in doubt, use anything that produces the correct sorting.')

    comments = forms.CharField(widget=forms.Textarea,
                               required=False,
      help_text='Comments between the Indexer and Editor about the change. '
                'These comments are part of the public change history, but '
                'are not part of the regular display.')

