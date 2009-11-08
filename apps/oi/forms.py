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
            'volume',
            'number',
            'price',
            'publication_date',
            'key_date',
            'sort_code',
        )

