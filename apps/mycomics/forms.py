from django.forms import ModelForm
from apps.mycomics.models import *


class CollectionForm(ModelForm):
    class Meta:
        model = Collection
        exclude = ('collector')


class CollectionItemForm(ModelForm):
    class Meta:
        model = CollectionItem
        exclude = ('collections', 'issue', 'acquisition_date', 'sell_date')

    def __init__(self, user, *args, **kwargs):
        super(CollectionItemForm, self).__init__(*args, **kwargs)
        self.fields['location'].queryset = Location.objects.filter(user=user)
        self.fields[
            'purchase_location'].queryset = PurchaseLocation.objects.filter(
            user=user)
        self.fields['grade'].queryset = ConditionGrade.objects.filter(
            scale=user.grade_system)
