from django.forms import ModelForm
from apps.mycomics.models import *

class CollectionForm(ModelForm):
    class Meta:
        model = Collection
        exclude = ('collector')
