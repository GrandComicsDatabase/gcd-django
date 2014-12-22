from django.forms import ModelForm, CharField
from apps.mycomics.models import *
from apps.stddata.models import Date

class GCDDateField(CharField):
    def __init__(self, *args, **kwargs):
        super(GCDDateField, self).__init__(*args, **kwargs)
        self.d = None

    def prepare_value(self, value):
        if not value:
            return ''
        self.d = Date.objects.all().get(pk=value)
        return unicode(self.d)

    def clean(self, value):
        if not value:
            return None
        dparts = value.split('-')
        if not self.d:
            self.d = Date()
        self.d.set(year=dparts[0], month=dparts[1], day=dparts[2])
        self.d.save()
        return self.d


class CollectionForm(ModelForm):
    class Meta:
        model = Collection
        exclude = ('collector')


class CollectionItemForm(ModelForm):
    class Meta:
        model = CollectionItem
        exclude = ('collections', 'issue')

    acquisition_date = GCDDateField(max_length=10, required=False)
    sell_date = GCDDateField(max_length=10, required=False)

    def __init__(self, user, *args, **kwargs):
        super(CollectionItemForm, self).__init__(*args, **kwargs)
        self.fields['location'].queryset = Location.objects.filter(user=user)
        self.fields[
            'purchase_location'].queryset = PurchaseLocation.objects.filter(
            user=user)
        self.fields['grade'].queryset = ConditionGrade.objects.filter(
            scale=user.grade_system)
