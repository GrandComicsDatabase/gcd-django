from django import forms

from apps.oi.models import *

class ForeignKeyField(forms.IntegerField):
    def __init__(self, queryset, target_name, **kwargs):
        forms.IntegerField.__init__(self, **kwargs)
        self.queryset = queryset
        self.target_name = target_name

    def clean(self, value):
        id = forms.IntegerField.clean(self, value)
        if id is None:
            return id
        try:
            return self.queryset.get(id=id)
        except ObjectDoesNotExist:
            raise ValueError, ("%d is not the ID of a valid %s" %
                               (id, self.target_name))
        except MultipleObjectsReturned:
            raise ValueError, ("%d matched multiple instances of %s" %
                               (id, self.target_name))

class PublisherRevisionForm(forms.ModelForm):
    class Meta:
        model = PublisherRevision
        fields = (
            'name',
            'year_began',
            'year_ended',
            'country',
            'is_master',
            'parent',
            'url',
            'notes',
        )
    parent = ForeignKeyField(queryset=Publisher.objects.filter(is_master=True),
                             target_name='Master Publisher',
                             required=False,
                             help_text='For imprints, the numeric database ID '
                                       'of the master publisher with which '
                                       'the imprint is associated.  Master '
                                       'publishers generally should not set '
                                       'this field.')

    comments = forms.CharField(widget=forms.Textarea,
      help_text='Comments between the Indexer and Editor about the change. '
                'These comments are part of the public change history, but '
                'are not part of the regular display.')
