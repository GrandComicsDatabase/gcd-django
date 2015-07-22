from django.forms import ModelForm
from apps.mycomics.models import *
from apps.oi.forms import _clean_keywords

class CollectorForm(ModelForm):
    class Meta:
        model = Collector
        exclude = ('user')

    def __init__(self, collector, *args, **kwargs):
        kwargs['instance']=collector
        super(CollectorForm, self).__init__(*args, **kwargs)
        collections = Collection.objects.filter(collector=collector)
        self.fields['default_have_collection'].queryset = collections
        self.fields['default_want_collection'].queryset = collections


class CollectionForm(ModelForm):
    class Meta:
        model = Collection
        exclude = ('collector')


class LocationForm(ModelForm):
    class Meta:
        model = Location
        exclude = ('user')


class PurchaseLocationForm(ModelForm):
    class Meta:
        model = PurchaseLocation
        exclude = ('user')


class CollectionItemForm(ModelForm):
    class Meta:
        model = CollectionItem
        exclude = ('collections', 'issue', 'acquisition_date', 'sell_date')

    def __init__(self, user, *args, **kwargs):
        super(CollectionItemForm, self).__init__(*args, **kwargs)
        instance = kwargs['instance']
        # This generates a query for each check. If problematic these can be
        # avoided by going to python for the checks on an evaluated collections
        collections = instance.collections.all()
        if not collections.filter(condition_used=True).exists():
            self.fields.pop('grade')
        else:
            self.fields['grade'].queryset = ConditionGrade.objects.filter(
                scale=user.grade_system)
        if not collections.filter(location_used=True).exists():
            self.fields.pop('location')
        else:
            self.fields['location'].queryset = \
                        Location.objects.filter(user=user)
        if not collections.filter(purchase_location_used=True).exists():
            self.fields.pop('purchase_location')
        else:
            self.fields['purchase_location'].queryset = \
                        PurchaseLocation.objects.filter(user=user)
        if not collections.filter(was_read_used=True).exists():
            self.fields.pop('was_read')
        if not collections.filter(for_sale_used=True).exists():
            self.fields.pop('for_sale')
        if not collections.filter(signed_used=True).exists():
            self.fields.pop('signed')
        if not collections.filter(price_paid_used=True).exists():
            self.fields.pop('price_paid')
            self.fields.pop('price_paid_currency')
        if not collections.filter(market_value_used=True).exists():
            self.fields.pop('market_value')
            self.fields.pop('market_value_currency')
        if not collections.filter(sell_price_used=True).exists():
            self.fields.pop('sell_price')
            self.fields.pop('sell_price_currency')

    def clean_keywords(self):
        return _clean_keywords(self.cleaned_data)
